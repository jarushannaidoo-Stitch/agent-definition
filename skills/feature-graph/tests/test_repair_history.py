import json

from support import GraphV2Case
import graph_state


class RepairHistoryTests(GraphV2Case):
    def revised_run(self, previous, name):
        path = self.root / (name + '-previous.json')
        path.write_text(json.dumps(previous))
        spec = self.root / (name + '-spec.md')
        spec.write_text('AC-1: approved revised observable behavior\n')
        approval = self.root / (name + '-approval.md')
        approval.write_text('Fixture approval for revised spec\n')
        contract = {**self.contract, 'spec': str(spec), 'approval': str(approval),
                    'budget_previous_run': str(path)}
        return graph_state.initialize(contract), path

    def test_repeated_cause_requires_diagnosis_across_two_spec_revisions(self):
        self.finish('prepare')
        graph_state.repair(self.state, 'prepare', 'Missing tool', cause='missing-executable')
        original_start = self.state['budget']['started']
        for name in ('first', 'second'):
            self.state, _ = self.revised_run(self.state, name)
            self.assertEqual(self.state['budget']['started'], original_start)
            self.assertTrue(all(n['status'] == 'pending' for n in self.state['nodes'].values()))
        self.finish('prepare')
        with self.assertRaisesRegex(ValueError, 'Diagnosis.*repeated cause'):
            graph_state.repair(self.state, 'prepare', 'Same missing tool', cause='missing-executable')
        graph_state.repair(self.state, 'prepare', 'Diagnosed repeated tool issue',
                           cause='missing-executable', diagnosis=self.report)
        self.assertEqual(self.state['nodes']['prepare']['status'], 'pending')

    def test_new_cause_can_be_repaired_after_a_spec_revision(self):
        self.finish('prepare')
        graph_state.repair(self.state, 'prepare', 'Missing tool', cause='missing-executable')
        self.state, _ = self.revised_run(self.state, 'revised')
        self.finish('prepare')
        graph_state.repair(self.state, 'prepare', 'Different failure', cause='registry-timeout')
        self.assertEqual(self.state['repairs'], 1)

    def test_changed_predecessor_cannot_hide_recurrence(self):
        self.finish('prepare')
        graph_state.repair(self.state, 'prepare', 'Missing tool', cause='missing-executable')
        self.state, path = self.revised_run(self.state, 'revised')
        self.finish('prepare')
        prior = json.loads(path.read_text())
        prior['history'] = []
        path.write_text(json.dumps(prior))
        with self.assertRaisesRegex(ValueError, 'Pinned evidence'):
            graph_state.repair(self.state, 'prepare', 'Same missing tool', cause='missing-executable')
