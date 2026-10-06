"""Version 4 review reuse, with immutable prior evidence and explicit coverage."""

import copy
import json
from pathlib import Path

from evidence import file_record, require, verify_record
from verification import items, nonempty


REVIEWS = {'verification', 'regression', 'arc', 'styla'}


def prior_review(state, node, attempt):
    for history in reversed(state['history']):
        entry = history['nodes'].get(node, {})
        if entry.get('receipt') and history['candidate']:
            require(entry.get('attempt') == attempt, 'Use the most recent archived review attempt')
            require(entry['receipt']['snapshot'] == history['candidate']['sha256'],
                    'Prior review does not identify its captured candidate')
            require(entry['receipt']['spec_sha256'] == state['spec']['sha256'], 'Prior spec changed')
            for record in entry['evidence']:
                verify_record(record)
            return entry, history['candidate']
    raise ValueError('No archived review matches prior_attempt')


def effective(entry):
    return entry.get('validated_coverage', entry['receipt']['details'])


def partition(retained, reviewed, required, label):
    require(not set(retained) & set(reviewed), f'{label} cannot be retained and rerun')
    require(set(retained) | set(reviewed) == set(required), f'Incomplete {label}')


def check_results(prior, names, passing_checks):
    results = effective(prior).get('checks', [])
    selected = [result for result in results if result['name'] in names]
    records = passing_checks(selected, names) if names else []
    require(all(record in prior['evidence'] for record in records),
            'Retained check logs were not pinned by the original review')
    return selected


def build(state, node, path, passing_checks):
    record = file_record(path)
    data = json.loads(Path(record['path']).read_text())
    require(data.get('node') == node, 'Assessment names another review')
    require(data.get('approved_by') == 'cos', 'CoS must approve review reuse')
    require(data.get('mode') in {'retain', 'focused'}, 'Choose retain or focused review')
    require(data.get('snapshot') == state['candidate']['sha256'], 'Assessment has wrong candidate')
    require(data.get('spec_sha256') == state['spec']['sha256'], 'Assessment has wrong frozen spec')
    nonempty(data.get('reason'), 'reuse reason')
    prior, old = prior_review(state, node, data.get('prior_attempt'))
    require(data.get('prior_snapshot') == old['sha256'], 'Assessment has wrong prior candidate')
    before = {row[0]: row[1:] for row in old['files']}
    after = {row[0]: row[1:] for row in state['candidate']['files']}
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    items(data.get('changed_paths'), 'exact changed paths', empty=True)
    require(set(data['changed_paths']) == changed, 'Assessment must list the complete source delta')
    impact = data.get('impact', {})
    require(impact.get('uncertain') is False, 'Impact is uncertain; rerun the full review')
    for field in ('callers', 'contracts', 'configuration', 'dependencies', 'invariants'):
        nonempty(impact.get(field), f'{field} impact analysis')
    for field in ('coverage', 'criteria'):
        items(impact.get(field), f'affected {field}', empty=True)
    for field in ('retained_coverage', 'review_coverage', 'retained_criteria', 'review_criteria',
                  'retained_checks', 'rerun_checks'):
        items(data.get(field), field, empty=True)
    require(data['retained_coverage'], 'No completed coverage to retain; run a full review')
    items(data.get('unchanged_inputs'), 'unchanged retained coverage inputs')
    for name in data['unchanged_inputs']:
        require(name in before and before[name][0] in {'file', 'executable'} and before[name] == after.get(name),
                f'Retained input changed or is absent: {name}')
    if data['mode'] == 'retain':
        require(prior['status'] == 'pass', 'Only a passing review can be carried forward')
    previous = effective(prior)
    done, todo = set(previous['coverage_completed']), set(previous['coverage_remaining'])
    retained, reviewed = set(data['retained_coverage']), set(data['review_coverage'])
    require(retained <= done and not retained & reviewed, 'Only completed coverage can be retained')
    require((done - retained) | todo <= reviewed, 'Complete unfinished and affected coverage')
    require(set(impact['coverage']) <= reviewed, 'Affected coverage must be reviewed')
    if data['mode'] == 'retain':
        require(not reviewed and not todo and retained == done,
                'Whole review retention must cover the complete prior review')
        require(not impact['coverage'] and not impact['criteria'], 'Affected reviews must rerun')
    else:
        require(reviewed, 'Focused review needs affected or unfinished coverage')
        if prior['status'] != 'pass':
            criterion = prior['receipt']['details'].get('repair', {}).get('criterion')
            require(criterion in reviewed, 'Focused review must resolve the previous finding')
    selected = []
    if node == 'verification':
        plan = state['verification_plan']['data']
        partition(data['retained_criteria'], data['review_criteria'], plan['criteria'], 'criteria')
        require(set(data['retained_criteria']) <= set(previous.get('criteria_verified', [])),
                'Retained criteria were not previously verified')
        require(set(impact['criteria']) <= set(data['review_criteria']), 'Affected criteria must rerun')
        partition(data['retained_checks'], data['rerun_checks'], plan['checks'], 'independent checks')
        selected = check_results(prior, data['retained_checks'], passing_checks)
        if data['mode'] == 'retain':
            require(not data['review_criteria'] and not data['rerun_checks'],
                    'Whole review retention cannot leave verification work')
            require(previous.get('first_principles_audit') is True
                    and previous.get('test_validity_reviewed') is True,
                    'Prior verification audit is incomplete')
            require(not plan['defer_new_boundary'] or previous.get('deferred_proof_completed') is True,
                    'Deferred runtime proof is incomplete')
    else:
        require(not any(data[field] for field in ('retained_criteria', 'review_criteria',
                                                  'retained_checks', 'rerun_checks')),
                'Only verification plans partition criteria and executable checks')
    return {'record': record, 'data': data, 'prior': copy.deepcopy(prior), 'checks': selected}


def records(plan):
    return [plan['record'], *plan['prior']['evidence']]


def receipt(node, outcome, details, state, passing_checks):
    plan = state['nodes'][node]['review_plan']
    data = plan['data']
    require(details.get('retained_from') == data['prior_attempt'], 'Receipt must identify retained review')
    if outcome != 'pass':
        completed = set(details.get('coverage_completed', []))
        remaining = set(details.get('coverage_remaining', []))
        assigned = set(data['review_coverage'])
        require(completed <= assigned and assigned - completed <= remaining,
                'Interrupted review must preserve unfinished assigned coverage')
        return records(plan)
    require(details.get('blocking_findings') == [], 'Review has unresolved blockers')
    require(details.get('coverage_remaining') == [], 'Focused review is incomplete')
    require(set(details.get('coverage_completed', [])) == set(data['review_coverage']),
            'Receipt must complete every assigned repair coverage item')
    if data['mode'] == 'retain':
        return records(plan)
    require(details.get('previous_findings_resolved') is True, 'Resolve previous findings explicitly')
    if node != 'verification':
        return records(plan)
    require(set(details.get('criteria_verified', [])) == set(data['review_criteria']),
            'Focused verification must complete affected criteria')
    items(details.get('paths_traced'), 'actual repair paths traced')
    require(details.get('first_principles_audit') is True and details.get('test_validity_reviewed') is True,
            'Focused verification requires a first-principles and test-validity audit')
    if state['verification_plan']['data']['defer_new_boundary']:
        require(details.get('deferred_proof_completed') is True, 'Deferred runtime proof is still required')
    results = details.get('checks', [])
    execution = passing_checks(results, data['rerun_checks']) if results or data['rerun_checks'] else []
    return [*records(plan), *execution]


def coverage(plan, receipt_details):
    data = plan['data']
    result = copy.deepcopy(receipt_details if data['mode'] == 'focused' else effective(plan['prior']))
    result['coverage_completed'] = data['retained_coverage'] + receipt_details['coverage_completed']
    result['coverage_remaining'] = receipt_details['coverage_remaining']
    if data['node'] == 'verification':
        result['criteria_verified'] = data['retained_criteria'] + [criterion for criterion in receipt_details.get('criteria_verified', [])
                                                             if criterion not in data['retained_criteria']]
        result['checks'] = plan['checks'] + [check for check in receipt_details.get('checks', [])
                                           if check['name'] not in data['retained_checks']]
    return result
