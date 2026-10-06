import copy
import json

from support import GraphV2Case, SKILL
import graph_state


class ReviewReuseTests(GraphV2Case):
    workflow = SKILL / 'references/v4/workflow.json'

    def candidate_pair(self, node='arc', outcome='pass'):
        self.through('capture')
        graph_state.start(self.state, node, 'original-reviewer')
        receipt = self.receipt(node, outcome)
        receipt['details']['coverage_completed'] = ['stable boundary', 'repair boundary']
        if outcome != 'pass':
            receipt['details']['coverage_remaining'] = ['unfinished path']
        graph_state.complete(self.state, node, receipt)
        self.prior = copy.deepcopy(self.state['nodes'][node])
        self.before = copy.deepcopy(self.state['candidate'])
        graph_state.repair(self.state, 'implement', 'Correct owner behavior', cause='owner-result')
        (self.repo / 'source.txt').write_text('corrected owner\n')
        for stage in ('implement', 'seal_implementation', 'capture'):
            self.finish(stage)

    def assessment(self, node='arc', mode='retain'):
        data = {
            'node': node, 'mode': mode, 'approved_by': 'cos',
            'prior_attempt': self.prior['attempt'], 'prior_snapshot': self.before['sha256'],
            'snapshot': self.state['candidate']['sha256'],
            'spec_sha256': self.state['spec']['sha256'],
            'changed_paths': ['source.txt'],
            'reason': 'The corrected output does not alter the retained boundary.',
            'impact': {'uncertain': False, 'criteria': [], 'coverage': [],
                       'callers': 'Caller signatures and admission remain unchanged.',
                       'contracts': 'No public shape changed.',
                       'configuration': 'No configuration changed.',
                       'dependencies': 'Retained coverage depends on removed.txt only.',
                       'invariants': 'The retained invariant has no changed input.'},
            'unchanged_inputs': ['removed.txt'],
            'retained_coverage': ['stable boundary', 'repair boundary'], 'review_coverage': [],
            'retained_criteria': [], 'review_criteria': [],
            'retained_checks': [], 'rerun_checks': [],
        }
        if mode == 'focused':
            data['retained_coverage'] = ['stable boundary']
            data['review_coverage'] = ['repair boundary']
            data['impact']['coverage'] = ['repair boundary']
        if node == 'verification':
            data['retained_criteria'] = ['AC-1']
            data['retained_checks'] = ['tests']
        return data

    def save_assessment(self, data):
        path = self.root / 'assessment.json'
        path.write_text(json.dumps(data))
        return path

    def configure(self, data):
        return graph_state.configure_review(self.state, data['node'], self.save_assessment(data))

    def test_retained_review_has_new_identity_and_preserves_original(self):
        self.candidate_pair()
        self.configure(self.assessment())
        entry = self.state['nodes']['arc']
        self.assertEqual(entry['status'], 'pass')
        self.assertNotEqual(entry['attempt'], self.prior['attempt'])
        self.assertEqual(entry['receipt']['snapshot'], self.state['candidate']['sha256'])
        self.assertEqual(entry['receipt']['details']['retained_from'], self.prior['attempt'])
        self.assertEqual(entry['receipt']['details']['coverage_completed'], [])
        self.assertEqual(self.state['history'][-1]['nodes']['arc'], self.prior)
        self.assertEqual(self.state['nodes']['checks']['status'], 'pending')
        with self.assertRaisesRegex(ValueError, 'prerequisites'):
            graph_state.start(self.state, 'reconcile', 'cos')

    def test_incorrect_delta_inputs_identity_and_uncertainty_are_rejected(self):
        self.candidate_pair()
        for key, value in [('changed_paths', []), ('unchanged_inputs', ['source.txt']),
                           ('unchanged_inputs', ['absent.txt']), ('prior_attempt', 'wrong'),
                           ('snapshot', self.before['sha256'])]:
            with self.subTest(key=key, value=value):
                data = self.assessment()
                data[key] = value
                with self.assertRaises(ValueError):
                    self.configure(data)
        data = self.assessment()
        data['impact']['uncertain'] = True
        with self.assertRaisesRegex(ValueError, 'uncertain'):
            self.configure(data)

    def test_failed_review_cannot_be_carried_but_can_finish_its_missing_coverage(self):
        self.candidate_pair(outcome='blocked')
        with self.assertRaisesRegex(ValueError, 'passing review'):
            self.configure(self.assessment())
        data = self.assessment(mode='focused')
        with self.assertRaisesRegex(ValueError, 'unfinished'):
            self.configure(data)
        data['review_coverage'] += ['unfinished path', 'AC-1']
        self.configure(data)
        graph_state.start(self.state, 'arc', 'repair-reviewer')
        receipt = self.receipt('arc')
        receipt['details'].update(coverage_completed=data['review_coverage'],
                                  retained_from=self.prior['attempt'],
                                  previous_findings_resolved=True)
        graph_state.complete(self.state, 'arc', receipt)
        self.assertIn('stable boundary', self.state['nodes']['arc']['validated_coverage']['coverage_completed'])

    def test_focused_verification_executes_affected_checks_and_covers_criteria(self):
        self.candidate_pair('verification')
        data = self.assessment('verification', 'focused')
        data.update(retained_criteria=[], review_criteria=['AC-1'],
                    retained_checks=[], rerun_checks=['tests'])
        data['impact']['criteria'] = ['AC-1']
        self.configure(data)
        graph_state.start(self.state, 'verification', 'repair-reviewer')
        receipt = self.receipt('verification')
        receipt['details'].update(coverage_completed=['repair boundary'],
                                  retained_from=self.prior['attempt'], previous_findings_resolved=True)
        missing = copy.deepcopy(receipt)
        missing['details']['checks'] = []
        with self.assertRaisesRegex(ValueError, 'checks|Checks'):
            graph_state.complete(self.state, 'verification', missing)
        graph_state.complete(self.state, 'verification', receipt)
        self.assertEqual(set(self.state['nodes']['verification']['validated_coverage']['coverage_completed']),
                         {'stable boundary', 'repair boundary'})

    def test_retained_check_requires_successful_original_execution(self):
        self.candidate_pair('verification', 'blocked')
        data = self.assessment('verification', 'focused')
        data['review_coverage'] += ['unfinished path', 'AC-1']
        prior = self.state['history'][-1]['nodes']['verification']
        prior['receipt']['details']['checks'][0]['exit_code'] = 1
        with self.assertRaisesRegex(ValueError, 'exit zero'):
            self.configure(data)

    def test_modified_original_evidence_blocks_reuse(self):
        self.candidate_pair()
        self.report.write_text('changed old report\n')
        with self.assertRaisesRegex(ValueError, 'Pinned evidence'):
            self.configure(self.assessment())

    def test_retention_evidence_is_checked_on_later_dispatch(self):
        self.candidate_pair()
        self.configure(self.assessment())
        (self.root / 'assessment.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Pinned evidence'):
            graph_state.start(self.state, 'checks', 'executor')

    def test_deleted_and_untracked_files_are_part_of_exact_delta(self):
        self.candidate_pair()
        graph_state.repair(self.state, 'implement', 'Additional repair', cause='cleanup')
        (self.repo / 'removed.txt').unlink()
        (self.repo / 'new.txt').write_text('new dependency')
        for stage in ('implement', 'seal_implementation', 'capture'):
            self.finish(stage)
        with self.assertRaisesRegex(ValueError, 'delta'):
            self.configure(self.assessment())

    def test_cli_retention_and_old_version_rejection(self):
        self.candidate_pair()
        state_path = self.root / 'run.json'
        state_path.write_text(json.dumps(self.state))
        result = self.cli('review-plan', state_path, 'arc', '--assessment',
                          self.save_assessment(self.assessment()))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(state_path.read_text())['nodes']['arc']['status'], 'pass')
        self.state['version'] = 3
        with self.assertRaisesRegex(ValueError, 'version 4'):
            self.configure(self.assessment())

    def test_interrupted_focused_review_retains_its_valid_prior_coverage(self):
        self.candidate_pair()
        data = self.assessment(mode='focused')
        self.configure(data)
        graph_state.start(self.state, 'arc', 'interrupted-reviewer')
        receipt = self.receipt('arc', 'blocked')
        receipt['details'].update(coverage_completed=[], coverage_remaining=['repair boundary'],
                                  retained_from=self.prior['attempt'],
                                  repair={'target': 'review', 'criterion': 'repair boundary',
                                          'reason': 'Interrupted before inspection'})
        graph_state.complete(self.state, 'arc', receipt)
        interrupted = copy.deepcopy(self.state['nodes']['arc'])
        graph_state.repair(self.state, 'arc', 'Complete interrupted review', cause='interruption')
        data.update(prior_attempt=interrupted['attempt'],
                    prior_snapshot=self.state['candidate']['sha256'], changed_paths=[])
        retry_path = self.root / 'focused-retry.json'
        retry_path.write_text(json.dumps(data))
        graph_state.configure_review(self.state, 'arc', retry_path)
        graph_state.start(self.state, 'arc', 'resumed-reviewer')
        resumed = self.receipt('arc')
        resumed['details'].update(coverage_completed=['repair boundary'],
                                  retained_from=interrupted['attempt'], previous_findings_resolved=True)
        graph_state.complete(self.state, 'arc', resumed)
        self.assertEqual(set(self.state['nodes']['arc']['validated_coverage']['coverage_completed']),
                         {'stable boundary', 'repair boundary'})

    def test_completed_retention_can_carry_through_a_second_source_repair(self):
        self.candidate_pair()
        self.configure(self.assessment())
        previous = copy.deepcopy(self.state['nodes']['arc'])
        before = copy.deepcopy(self.state['candidate'])
        graph_state.repair(self.state, 'implement', 'Second behavior repair', cause='new-input')
        (self.repo / 'source.txt').write_text('second repair\n')
        for stage in ('implement', 'seal_implementation', 'capture'):
            self.finish(stage)
        data = self.assessment()
        data.update(prior_attempt=previous['attempt'], prior_snapshot=before['sha256'])
        path = self.root / 'second-assessment.json'
        path.write_text(json.dumps(data))
        graph_state.configure_review(self.state, 'arc', path)
        self.assertEqual(self.state['nodes']['arc']['status'], 'pass')
        (self.root / 'assessment.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Pinned evidence'):
            graph_state.start(self.state, 'checks', 'executor')

    def test_older_pass_cannot_bypass_a_later_failed_review(self):
        self.candidate_pair()
        self.configure(self.assessment())
        graph_state.repair(self.state, 'arc', 'Reassess new evidence', cause='new-evidence')
        graph_state.start(self.state, 'arc', 'reviewer')
        graph_state.complete(self.state, 'arc', self.receipt('arc', 'fail'))
        graph_state.repair(self.state, 'arc', 'Resolve review failure', cause='finding')
        data = self.assessment()
        path = self.root / 'older-assessment.json'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'most recent'):
            graph_state.configure_review(self.state, 'arc', path)

    def test_initial_review_cannot_skip_full_coverage(self):
        self.through('capture')
        graph_state.start(self.state, 'verification', 'reviewer')
        receipt = self.receipt('verification')
        receipt['details']['criteria_verified'] = []
        with self.assertRaisesRegex(ValueError, 'every frozen criterion'):
            graph_state.complete(self.state, 'verification', receipt)
