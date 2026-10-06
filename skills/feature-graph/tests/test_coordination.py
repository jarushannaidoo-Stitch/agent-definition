import copy
import json

from support import GraphV2Case, SKILL
import coordination
import graph_state


class CoordinationTests(GraphV2Case):
    workflow = SKILL / 'workflow.json'

    def initialize(self):
        self.contract = self.v5_contract()
        self.contract['endpoint'] = 'local'
        return graph_state.initialize(self.contract)

    def delivery(self):
        return {**coordination.identity(self.state), 'message_id': 'native-transcript:42', 'evidence': str(self.report)}

    def test_actual_main_delivery_required_before_handoff_and_closeout(self):
        self.through('reconcile')
        graph_state.start(self.state, 'handoff', 'cos-1')
        receipt = self.receipt('handoff')
        with self.assertRaisesRegex(ValueError, 'Main must deliver'):
            graph_state.complete(self.state, 'handoff', receipt)
        with self.assertRaisesRegex(ValueError, 'Only recorded main'):
            coordination.authorize(self.state, 'cos-1', main=True)
        coordination.authorize(self.state, 'main-1', main=True)
        coordination.delivered(self.state, self.delivery(), graph_state.now())
        graph_state.complete(self.state, 'handoff', receipt)
        self.finish('closeout')
        self.assertTrue(graph_state.status(self.state)['complete'])

    def test_delivery_is_idempotent_and_survives_reload(self):
        self.through('reconcile')
        data = self.delivery()
        coordination.delivered(self.state, data, graph_state.now())
        self.state = json.loads(json.dumps(self.state))
        coordination.delivered(self.state, data, graph_state.now())
        self.assertEqual(len(self.state['coordination']['deliveries']), 1)
        coordination.require_delivery(self.state)

    def test_endpoint_change_requires_new_delivery(self):
        self.through('reconcile')
        data = self.delivery()
        coordination.delivered(self.state, data, graph_state.now())
        graph_state.select_endpoint(self.state, 'draft', self.approval)
        with self.assertRaisesRegex(ValueError, 'Stale delivery'):
            coordination.delivered(self.state, data, graph_state.now())
        with self.assertRaisesRegex(ValueError, 'Main must deliver'):
            coordination.require_delivery(self.state)

    def test_native_handle_cannot_be_replaced_or_bound_to_old_attempt(self):
        entry = graph_state.start(self.state, 'prepare', 'stable-dispatch')
        coordination.bind(self.state, 'prepare', entry['attempt'], 'agent', 'native-1')
        coordination.bind(self.state, 'prepare', entry['attempt'], 'agent', 'native-1')
        with self.assertRaisesRegex(ValueError, 'Reconcile the original'):
            coordination.bind(self.state, 'prepare', entry['attempt'], 'agent', 'native-2')
        with self.assertRaisesRegex(ValueError, 'Stale native assignment'):
            coordination.bind(self.state, 'prepare', 'old-attempt', 'agent', 'native-1')

    def test_replacement_fences_old_coordinator_and_requires_stopped_evidence(self):
        proof = self.root / 'stopped.json'
        data = {'previous_cos': 'cos-1', 'cos_stopped': True, 'workers_stopped': True,
                'commands_stopped': True, 'descendants_absent': False, 'git_reconciled': True,
                'observations': 'Disposable fixture has no launched native work'}
        proof.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'descendants_absent'):
            coordination.replace(self.state, 'cos-2', proof)
        data['descendants_absent'] = True
        proof.write_text(json.dumps(data))
        coordination.replace(self.state, 'cos-2', proof)
        with self.assertRaisesRegex(ValueError, 'Only recorded cos'):
            coordination.authorize(self.state, 'cos-1')
        coordination.authorize(self.state, 'cos-2')
        self.assertEqual(self.state['generation'], 1)

    def test_cli_rejects_wrong_coordinator(self):
        path, _ = self.init_cli()
        result = self.cli('start', path, 'prepare', '--worker', 'stable', '--actor', 'stranger')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Only recorded cos', result.stderr)

    def test_role_record_drift_blocks_dispatch(self):
        self.root.joinpath('roles.json').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Pinned evidence changed'):
            graph_state.start(self.state, 'prepare', 'stable')

    def test_main_can_record_stopped_run_without_dispatch_authority(self):
        path, _ = self.init_cli()
        self.assertEqual(self.cli('start', path, 'prepare', '--worker', 'old-worker').returncode, 0)
        proof = self.root / 'stop-proof.json'
        proof.write_text(json.dumps({'previous_cos': 'cos-1', 'cos_stopped': True,
            'workers_stopped': True, 'commands_stopped': True, 'descendants_absent': True,
            'git_reconciled': True, 'observations': 'Fixture reservation never launched a process'}))
        blocked = self.cli('coordinator', path, '--cos', 'cos-2', '--proof', proof, '--actor', 'main-1')
        self.assertNotEqual(blocked.returncode, 0)
        result = self.cli('stop-run', path, '--proof', proof, '--actor', 'main-1')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli('coordinator', path, '--cos', 'cos-2', '--proof', proof, '--actor', 'main-1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.read_text())['nodes']['prepare']['status'], 'blocked')
        denied = self.cli('repair', path, 'prepare', '--reason', 'Resume stopped reservation',
                          '--cause', 'native-stop', '--actor', 'main-1')
        self.assertNotEqual(denied.returncode, 0)
        repaired = self.cli('repair', path, 'prepare', '--reason', 'Resume stopped reservation',
                            '--cause', 'native-stop', '--actor', 'cos-2')
        self.assertEqual(repaired.returncode, 0, repaired.stderr)

    def test_superseded_never_launched_wait_does_not_block_replacement(self):
        self.state['coordination']['commands']['superseded-check'] = {'status': 'superseded'}
        proof = self.root / 'stopped.json'
        proof.write_text(json.dumps({'previous_cos': 'cos-1', 'cos_stopped': True,
            'workers_stopped': True, 'commands_stopped': True, 'descendants_absent': True,
            'git_reconciled': True, 'observations': 'Prior pending check never launched'}))
        coordination.replace(self.state, 'cos-2', proof)
        coordination.authorize(self.state, 'cos-2')
