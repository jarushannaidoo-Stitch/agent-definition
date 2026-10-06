import copy
import json

from support import GraphV2Case, SKILL
import graph_state


class ParallelTests(GraphV2Case):
    workflow = SKILL / 'references/v3/workflow.json'

    def start_reviews(self):
        for node in ('verification', 'regression', 'arc', 'styla'):
            graph_state.start(self.state, node, node)

    def finish_reviews(self):
        for node in ('verification', 'regression', 'arc', 'styla'):
            graph_state.complete(self.state, node, self.receipt(node))

    def test_test_writer_and_implementer_overlap_until_both_seals_join(self):
        self.finish('prepare')
        graph_state.start(self.state, 'tests', 'writer')
        self.finish('plan')
        graph_state.start(self.state, 'implement', 'implementer')
        (self.repo / 'new-test.txt').write_text('test artifact\n')
        (self.repo / 'source.txt').write_text('implementation artifact\n')
        graph_state.complete(self.state, 'tests', self.receipt('tests'))
        self.finish('seal_tests')
        with self.assertRaisesRegex(ValueError, 'prerequisites'):
            graph_state.start(self.state, 'capture', 'cos')
        graph_state.complete(self.state, 'implement', self.receipt('implement'))
        self.finish('seal_implementation')
        self.finish('capture')
        self.assertEqual(self.state['version'], 3)

    def test_implementation_can_finish_first_but_capture_waits_for_tests(self):
        self.finish('prepare')
        self.finish('plan')
        graph_state.start(self.state, 'implement', 'implementer')
        graph_state.start(self.state, 'tests', 'writer')
        graph_state.complete(self.state, 'implement', self.receipt('implement'))
        self.finish('seal_implementation')
        with self.assertRaisesRegex(ValueError, 'prerequisites'):
            graph_state.start(self.state, 'capture', 'cos')
        graph_state.complete(self.state, 'tests', self.receipt('tests'))
        self.finish('seal_tests')
        self.finish('capture')

    def test_implementation_still_requires_approved_plan(self):
        self.finish('prepare')
        graph_state.start(self.state, 'tests', 'writer')
        with self.assertRaisesRegex(ValueError, 'plan'):
            graph_state.start(self.state, 'implement', 'implementer')

    def test_reviews_overlap_checks_and_cannot_bypass_failed_checks(self):
        graph_state.select_endpoint(self.state, 'local', self.approval)
        self.through('capture')
        graph_state.start(self.state, 'checks', 'executor')
        self.start_reviews()
        self.finish_reviews()
        with self.assertRaisesRegex(ValueError, 'checks'):
            graph_state.start(self.state, 'reconcile', 'cos')
        graph_state.complete(self.state, 'checks', self.receipt('checks', 'fail'))
        with self.assertRaisesRegex(ValueError, 'checks'):
            graph_state.start(self.state, 'reconcile', 'cos')
        reviews = {n: copy.deepcopy(self.state['nodes'][n]) for n in
                   ('verification', 'regression', 'arc', 'styla')}
        graph_state.repair(self.state, 'checks', 'Environment retry', cause='tool-unavailable')
        for node, original in reviews.items():
            self.assertEqual(self.state['nodes'][node], original)
        self.finish('checks')
        self.finish('reconcile')
        self.finish('handoff')
        self.finish('closeout')
        self.assertTrue(graph_state.status(self.state)['complete'])

    def test_successful_checks_cannot_bypass_any_required_review(self):
        self.through('capture')
        self.start_reviews()
        self.finish('checks')
        for node in ('verification', 'regression', 'arc', 'styla'):
            with self.assertRaisesRegex(ValueError, 'prerequisites'):
                graph_state.start(self.state, 'reconcile', 'cos')
            graph_state.complete(self.state, node, self.receipt(node))
        self.finish('reconcile')

    def test_changed_candidate_reopens_all_reviews_and_rejects_old_receipts(self):
        self.through('capture')
        graph_state.start(self.state, 'checks', 'executor')
        self.start_reviews()
        old = self.receipt('verification')
        (self.repo / 'source.txt').write_text('unexpected mutation\n')
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            graph_state.complete(self.state, 'verification', old)
        with self.assertRaisesRegex(ValueError, 'stopped workers'):
            graph_state.repair(self.state, 'implement', 'Repair source', cause='wrong-result')
        for node in ('checks', 'verification', 'regression', 'arc', 'styla'):
            graph_state.complete(self.state, node, self.receipt(node, 'blocked'))
        result = graph_state.repair(self.state, 'implement', 'Repair source', cause='wrong-result')
        for node in ('capture', 'checks', 'verification', 'regression', 'arc', 'styla'):
            self.assertIn(node, result['invalidated'])
        for node in ('implement', 'seal_implementation', 'capture'):
            self.finish(node)
        graph_state.start(self.state, 'verification', 'new-verifier')
        with self.assertRaisesRegex(ValueError, 'Stale or wrong attempt'):
            graph_state.complete(self.state, 'verification', old)

    def test_both_author_repair_reopens_both_parallel_branches(self):
        self.through('capture')
        result = graph_state.repair(self.state, 'tests', 'Both need correction', cause='wrong-contract-use')
        for node in ('tests', 'seal_tests', 'plan', 'implement', 'seal_implementation'):
            self.assertIn(node, result['invalidated'])
        graph_state.start(self.state, 'tests', 'writer')
        self.finish('plan')
        graph_state.start(self.state, 'implement', 'implementer')

    def test_tests_only_repair_preserves_implementation_without_permitting_source_changes(self):
        self.through('capture')
        result = graph_state.repair(self.state, 'tests', 'Fix assertion', cause='assertion',
                                    preservation=self.report)
        self.assertNotIn('implement', result['invalidated'])
        self.finish('tests')
        self.finish('seal_tests')
        (self.repo / 'source.txt').write_text('forbidden source change\n')
        graph_state.start(self.state, 'capture', 'cos')
        with self.assertRaisesRegex(ValueError, 'changed implementation'):
            graph_state.complete(self.state, 'capture', self.receipt('capture'))

    def test_spec_revision_carries_budget_and_repair_cause_into_parallel_run(self):
        self.finish('prepare')
        graph_state.repair(self.state, 'prepare', 'Missing tool', cause='missing-tool')
        previous = self.root / 'previous.json'
        previous.write_text(json.dumps(self.state))
        self.state = graph_state.initialize({**self.contract, 'budget_previous_run': str(previous)})
        self.finish('prepare')
        with self.assertRaisesRegex(ValueError, 'repeated cause'):
            graph_state.repair(self.state, 'prepare', 'Still missing', cause='missing-tool')

