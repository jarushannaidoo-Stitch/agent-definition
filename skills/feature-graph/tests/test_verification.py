import copy
import json

from support import GraphV2Case
import graph_state


class VerificationTests(GraphV2Case):
    def test_new_run_has_all_four_reviews_and_both_capture_prerequisites(self):
        self.assertEqual(self.state['version'], 2)
        self.assertNotIn('acceptance', self.state['nodes'])
        self.assertEqual(self.state['graph']['capture']['needs'], ['seal_tests', 'seal_implementation'])
        self.through('checks')
        self.assertEqual(set(graph_state.status(self.state)['ready']),
                         {'verification', 'regression', 'arc', 'styla'})
        for node in ('verification', 'regression', 'arc', 'styla'):
            graph_state.start(self.state, node, node)
        for node in ('verification', 'regression', 'arc'):
            graph_state.complete(self.state, node, self.receipt(node))
        with self.assertRaisesRegex(ValueError, 'prerequisites'):
            graph_state.start(self.state, 'reconcile', 'cos')
        graph_state.complete(self.state, 'styla', self.receipt('styla'))
        self.finish('reconcile')

    def test_cannot_make_specialist_optional_or_omit_freeze_decisions(self):
        for name in ('arc', 'styla'):
            contract = copy.deepcopy(self.contract)
            contract[name]['required'] = False
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'mandatory'):
                graph_state.initialize(contract)
        graph_state.start(self.state, 'prepare', 'cos')
        for flag in ('decisions_resolved', 'budget_approved', 'verification_plan_approved'):
            receipt = self.receipt('prepare')
            receipt['details'][flag] = False
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, flag):
                graph_state.complete(self.state, 'prepare', receipt)

    def test_missing_plan_criterion_path_or_deferred_proof_blocks_verification(self):
        self.through('checks')
        graph_state.start(self.state, 'verification', 'auditor')
        for key, value in [('criteria_verified', []), ('paths_traced', []),
                           ('deferred_proof_completed', False), ('checks', [])]:
            receipt = self.receipt('verification')
            receipt['details'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                graph_state.complete(self.state, 'verification', receipt)
        graph_state.complete(self.state, 'verification', self.receipt('verification'))

    def test_incomplete_review_cannot_pass_or_release_reconcile(self):
        self.through('checks')
        graph_state.start(self.state, 'regression', 'reviewer')
        receipt = self.receipt('regression')
        receipt['details']['coverage_remaining'] = ['untested fallback caller']
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            graph_state.complete(self.state, 'regression', receipt)
        receipt['outcome'] = 'blocked'
        graph_state.complete(self.state, 'regression', receipt)
        self.assertEqual(self.state['nodes']['regression']['receipt']['details']['coverage_remaining'],
                         ['untested fallback caller'])
        with self.assertRaises(ValueError):
            graph_state.start(self.state, 'reconcile', 'cos')

    def test_failed_verification_returns_a_repair_target(self):
        self.through('checks')
        graph_state.start(self.state, 'verification', 'auditor')
        receipt = self.receipt('verification', 'fail')
        receipt['details'].pop('repair')
        with self.assertRaisesRegex(ValueError, 'repair owner'):
            graph_state.complete(self.state, 'verification', receipt)
        receipt['details']['repair'] = {'target': 'implement', 'criterion': 'AC-1',
                                       'reason': 'Entry accepts stale scope'}
        graph_state.complete(self.state, 'verification', receipt)
        self.assertEqual(self.state['nodes']['implement']['status'], 'pass')

    def test_bug_proof_must_be_behavioral_and_on_exact_baseline(self):
        path = self.root / 'verification-plan.json'
        plan = json.loads(path.read_text())
        plan.update(kind='bug', defer_new_boundary=False)
        path.write_text(json.dumps(plan))
        self.state = graph_state.initialize(self.contract)
        self.finish('prepare')
        graph_state.start(self.state, 'tests', 'writer')
        valid = self.receipt('tests')
        valid['details']['early_proof'] = {
            'baseline': self.baseline, 'result': 'Expected refund suppression but refund was sent',
            'behavior_failure': True, 'command': 'test refund', 'exit_code': 1, 'log': str(self.report)}
        for key, value in [('baseline', '0' * 40), ('behavior_failure', False), ('exit_code', 0)]:
            receipt = copy.deepcopy(valid)
            receipt['details']['early_proof'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                graph_state.complete(self.state, 'tests', receipt)
        graph_state.complete(self.state, 'tests', valid)

    def test_feature_deferral_still_requires_executed_baseline_checks(self):
        self.finish('prepare')
        graph_state.start(self.state, 'tests', 'writer')
        receipt = self.receipt('tests')
        receipt['details']['early_proof']['checks'][0]['exit_code'] = 1
        with self.assertRaisesRegex(ValueError, 'exit zero'):
            graph_state.complete(self.state, 'tests', receipt)

    def test_plan_is_pinned_and_cannot_be_rewritten_during_run(self):
        (self.root / 'verification-plan.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Pinned evidence'):
            graph_state.start(self.state, 'prepare', 'cos')

    def test_local_version_two_endpoint_completes_without_publication(self):
        graph_state.select_endpoint(self.state, 'local', self.approval)
        self.through('reconcile')
        self.finish('handoff')
        self.finish('closeout')
        self.assertTrue(graph_state.status(self.state)['complete'])
        self.assertEqual(self.state['nodes']['publish']['status'], 'pending')
