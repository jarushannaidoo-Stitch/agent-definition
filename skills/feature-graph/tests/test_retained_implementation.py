import copy

from support import GraphV2Case
import graph_state


class RetentionTests(GraphV2Case):
    def test_tests_only_repair_preserves_source_but_waits_for_current_test_seal(self):
        self.through('reconcile')
        original = copy.deepcopy(self.state['nodes'])
        result = graph_state.repair(self.state, 'tests', 'Wrong assertion', cause='test-assertion',
                                    preservation=self.report)
        for name in ('plan', 'implement', 'seal_implementation'):
            self.assertEqual(self.state['nodes'][name], original[name])
            self.assertNotIn(name, result['invalidated'])
        self.assertIsNone(self.state['candidate'])
        self.assertEqual(graph_state.status(self.state)['ready'], ['tests'])
        for stage in ('tests', 'seal_tests'):
            with self.assertRaisesRegex(ValueError, 'seal_tests'):
                graph_state.start(self.state, 'capture', 'cos')
            self.finish(stage)
        (self.repo / 'new-test.txt').write_text('fixed assertion\n')
        self.finish('capture')
        self.finish('checks')
        self.assertEqual(set(graph_state.status(self.state)['ready']),
                         {'verification', 'regression', 'arc', 'styla'})

    def test_retained_implementation_rejects_changed_deleted_or_new_non_test_file(self):
        self.through('capture')
        graph_state.repair(self.state, 'tests', 'Assertion repair', cause='assertion',
                           preservation=self.report)
        self.finish('tests')
        self.finish('seal_tests')
        graph_state.start(self.state, 'capture', 'cos')
        original = (self.repo / 'source.txt').read_bytes()
        for operation in ('modify', 'delete', 'new'):
            if operation == 'modify':
                (self.repo / 'source.txt').write_text('changed source')
            elif operation == 'delete':
                (self.repo / 'source.txt').unlink()
            else:
                (self.repo / 'new-source.txt').write_text('new source')
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'changed implementation'):
                graph_state.complete(self.state, 'capture', self.receipt('capture'))
            (self.repo / 'source.txt').write_bytes(original)
            (self.repo / 'new-source.txt').unlink(missing_ok=True)
        graph_state.complete(self.state, 'capture', self.receipt('capture'))

    def test_both_author_repair_still_invalidates_plan_and_source_seal(self):
        self.through('capture')
        result = graph_state.repair(self.state, 'tests', 'Both artifacts wrong', cause='shared-contract')
        for name in ('plan', 'implement', 'seal_implementation'):
            self.assertIn(name, result['invalidated'])

    def test_retention_requires_unchanged_candidate_and_stopped_reviewers(self):
        self.through('checks')
        graph_state.start(self.state, 'verification', 'auditor')
        with self.assertRaisesRegex(ValueError, 'stopped workers'):
            graph_state.repair(self.state, 'tests', 'fix', cause='assertion', preservation=self.report)
        graph_state.complete(self.state, 'verification', self.receipt('verification', 'blocked'))
        (self.repo / 'source.txt').write_text('already changed')
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            graph_state.repair(self.state, 'tests', 'fix', cause='assertion', preservation=self.report)

    def test_no_fixed_repair_cap_but_repeated_cause_requires_diagnosis(self):
        for cause in ('environment-a', 'environment-b', 'environment-c'):
            self.finish('prepare')
            graph_state.repair(self.state, 'prepare', 'Reproduce a distinct failure', cause=cause)
        self.finish('prepare')
        with self.assertRaisesRegex(ValueError, 'repeated cause'):
            graph_state.repair(self.state, 'prepare', 'Same failure returned', cause='environment-a')
        graph_state.repair(self.state, 'prepare', 'Diagnosis confirms corrected setup',
                           cause='environment-a', diagnosis=self.report)
        self.assertEqual(self.state['repairs'], 4)

    def test_test_writer_retry_keeps_valid_retention_before_recapture(self):
        self.through('capture')
        graph_state.repair(self.state, 'tests', 'Assertion repair', cause='assertion',
                           preservation=self.report)
        graph_state.start(self.state, 'tests', 'writer')
        (self.repo / 'new-test.txt').write_text('incomplete test')
        graph_state.complete(self.state, 'tests', self.receipt('tests', 'blocked'))
        graph_state.repair(self.state, 'tests', 'Finish interrupted test work', cause='interrupted',
                           preservation=self.report)
        self.assertEqual(self.state['nodes']['seal_implementation']['status'], 'pass')
        self.finish('tests')
        self.finish('seal_tests')
        self.finish('capture')
