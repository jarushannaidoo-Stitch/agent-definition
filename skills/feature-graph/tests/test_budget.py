from datetime import timedelta
import json
from unittest.mock import patch

from support import GraphV2Case
import budget
import graph_state


class BudgetTests(GraphV2Case):
    def at(self, seconds):
        return (budget.instant(self.state['budget']['started']) + timedelta(seconds=seconds)).isoformat()

    def test_expiry_blocks_dispatch_and_repair_but_can_record_results(self):
        graph_state.start(self.state, 'prepare', 'cos')
        with patch.object(graph_state, 'now', return_value=self.at(3601)):
            graph_state.complete(self.state, 'prepare', self.receipt('prepare'))
            for action in (lambda: graph_state.start(self.state, 'tests', 'writer'),
                           lambda: graph_state.repair(self.state, 'prepare', 'retry', cause='setup')):
                with self.assertRaisesRegex(ValueError, 'budget exhausted'):
                    action()
            status = graph_state.status(self.state)
            self.assertEqual(status['ready'], [])
            self.assertGreater(status['timing']['active_seconds'], 3600)

    def test_extension_keeps_elapsed_work_and_pins_approval(self):
        budget.extend(self.state, 7200, self.approval, self.at(3700))
        self.assertEqual(budget.report(self.state, self.at(3800))['active_seconds'], 3800)
        self.assertEqual(budget.report(self.state, self.at(3800))['remaining_seconds'], 3400)
        self.approval.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Pinned evidence'):
            graph_state.verify(self.state)

    def test_external_waits_are_separate_and_internal_work_remains_counted(self):
        budget.wait(self.state, 'user', self.report, self.at(100))
        with self.assertRaisesRegex(ValueError, 'external wait'):
            budget.available(self.state, self.at(500))
        budget.wait(self.state, 'end', None, self.at(500))
        result = budget.report(self.state, self.at(800))
        self.assertEqual(result['total_seconds'], 800)
        self.assertEqual(result['wait_seconds'], {'user': 400, 'external_ci': 0})
        self.assertEqual(result['active_seconds'], 400)

    def test_cannot_hide_author_work_as_external_wait(self):
        graph_state.start(self.state, 'prepare', 'cos')
        with self.assertRaisesRegex(ValueError, 'Stop internal workers'):
            budget.wait(self.state, 'user', self.report, self.at(20))
        with self.assertRaisesRegex(ValueError, 'publication'):
            other = self.initialize()
            budget.wait(other, 'external_ci', self.report, self.at(20))

    def test_budget_survives_repairs_and_resume(self):
        self.finish('prepare')
        started = self.state['budget']['started']
        with patch.object(graph_state, 'now', return_value=self.at(100)):
            graph_state.repair(self.state, 'prepare', 'Retry setup', cause='setup')
        self.assertEqual(self.state['budget']['started'], started)
        self.assertEqual(budget.report(self.state, self.at(200))['active_seconds'], 200)

    def test_cli_extension_and_wait_accounting(self):
        path, _ = self.init_cli()
        for args in [('wait', path, 'user', '--evidence', self.report),
                     ('wait', path, 'end'),
                     ('budget', path, '--seconds', '7200', '--approval', self.approval)]:
            result = self.cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_reopening_completed_local_run_excludes_dormant_interval(self):
        graph_state.select_endpoint(self.state, 'local', self.approval)
        self.through('reconcile')
        with patch.object(graph_state, 'now', return_value=self.at(300)):
            self.finish('handoff')
            self.finish('closeout')
        with patch.object(graph_state, 'now', return_value=self.at(86400)):
            graph_state.select_endpoint(self.state, 'draft', self.approval)
            result = graph_state.status(self.state)
            self.assertEqual(result['ready'], ['publish'])
            self.assertEqual(result['timing']['active_seconds'], 300)
            self.assertEqual(result['timing']['inactive_seconds'], 86100)
        self.assertEqual(budget.report(self.state, self.at(86500))['active_seconds'], 400)

    def test_new_approved_spec_run_keeps_previous_work_and_wait_exclusions(self):
        budget.wait(self.state, 'user', self.report, self.at(100))
        budget.wait(self.state, 'end', None, self.at(7300))
        previous = self.root / 'previous-run.json'
        previous.write_text(json.dumps(self.state))
        contract = {**self.contract, 'budget_previous_run': str(previous)}
        with patch.object(graph_state, 'now', return_value=self.at(7800)):
            new = graph_state.initialize(contract)
            self.assertEqual(budget.report(new, self.at(7800))['active_seconds'], 600)
            self.assertEqual(budget.report(new, self.at(7800))['wait_seconds']['user'], 7200)
        previous.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Pinned evidence'):
            graph_state.verify(new)

    def test_completed_run_cannot_double_exclude_a_dormant_interval_as_a_wait(self):
        graph_state.select_endpoint(self.state, 'local', self.approval)
        self.through('reconcile')
        self.finish('handoff')
        self.finish('closeout')
        with self.assertRaisesRegex(ValueError, 'already exclude dormant time'):
            budget.wait(self.state, 'user', self.report, self.at(100))
