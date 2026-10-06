import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import patch

from support import GraphCase, SKILL
import graph_state
import run_check


class CommandWaitTests(GraphCase):
    def setUp(self):
        super().setUp()
        self.path, _ = self.init_cli()
        result = self.cli('start', self.path, 'prepare', '--worker', 'prepare-worker')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.lock_path = self.root / 'heavy.lock'
        self.owner_path = self.root / 'heavy.lock.owner.json'
        self.args = argparse.Namespace(state=self.path, actor='cos-1', node='prepare',
                                       command_id='check-1', name='baseline', cwd=None,
                                       argv=[sys.executable, '-c', 'print("observed output")'])

    def saved(self):
        return json.loads(self.path.read_text())['coordination']['commands']['check-1']

    def release(self):
        value = json.loads(self.owner_path.read_text())
        proof = self.root / 'cleanup.json'
        proof.write_text(json.dumps({**value, 'runner_stopped': True, 'native_session_closed': True,
                                     'descendants_absent': True, 'observations': 'Synchronous fixture child reaped; process group absent'}))
        self.args.proof = proof
        return run_check.release(self.args)

    def test_wait_is_persisted_and_rechecked_after_release(self):
        with self.lock_path.open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = run_check.execute(self.args)
            self.assertEqual(result['status'], 'waiting')
            self.assertEqual(self.saved()['status'], 'waiting')
            self.assertFalse(run_check.probe(self.path)['available'])
        self.assertTrue(run_check.probe(self.path)['available'])
        result = run_check.execute(self.args)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(Path(result['log']).read_text(), 'observed output\n')
        self.assertFalse(run_check.probe(self.path)['available'])
        self.release()
        self.assertTrue(run_check.probe(self.path)['available'])
        self.assertEqual(run_check.execute(self.args), result)
        state = json.loads(self.path.read_text())
        self.assertEqual(state['budget']['waits'], [])

    def test_release_during_registration_is_not_a_lost_wakeup(self):
        lock = self.lock_path.open('a+')
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        original = run_check.register
        def register_then_release(args):
            value = original(args)
            fcntl.flock(lock, fcntl.LOCK_UN)
            return value
        with patch.object(run_check, 'register', register_then_release):
            result = run_check.execute(self.args)
        self.assertEqual(result['status'], 'finished')
        self.release()

    def test_ambiguous_owner_prevents_new_launch(self):
        self.owner_path.write_text(json.dumps({'status': 'running', 'run': 'old', 'pid': 123}))
        result = run_check.execute(self.args)
        self.assertEqual(result["status"], "waiting")
        self.assertEqual(result["reason"], "owner_cleanup_pending")
        self.assertFalse((self.root / 'checks/check-1.log').exists())

    def test_same_id_cannot_run_different_inputs(self):
        run_check.execute(self.args)
        self.release()
        self.args.argv = [sys.executable, '-c', 'raise SystemExit(2)']
        with self.assertRaisesRegex(ValueError, 'different inputs'):
            run_check.execute(self.args)

    def test_completion_waits_for_cleanup(self):
        run_check.execute(self.args)
        state = json.loads(self.path.read_text())
        self.state = state
        with self.assertRaisesRegex(ValueError, 'cleanup'):
            graph_state.complete(state, 'prepare', self.receipt('prepare'))
        self.release()

    def test_failed_command_preserves_log_and_exit_code(self):
        self.args.argv = [sys.executable, '-c', 'print("actual failure"); raise SystemExit(7)']
        result = run_check.execute(self.args)
        self.assertEqual(result['exit_code'], 7)
        self.assertEqual(Path(result['log']).read_text(), 'actual failure\n')
        self.release()

    def test_cancelled_native_command_keeps_cleanup_responsibility(self):
        argv = [sys.executable, '-B', str(SKILL / 'scripts/run_check.py'), 'run', str(self.path),
                '--actor', 'cos-1', '--node', 'prepare', '--id', 'check-1', '--name', 'long', '--',
                sys.executable, '-c', 'import time; time.sleep(60)']
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: child.kill() if child.poll() is None else None)
        deadline = time.monotonic() + 5
        pid = None
        while time.monotonic() < deadline:
            data = json.loads(self.path.read_text())['coordination']['commands'].get('check-1', {})
            pid = data.get('pid')
            if pid:
                break
            time.sleep(.01)
        self.assertIsNotNone(pid)
        child.send_signal(signal.SIGTERM)
        stdout, stderr = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 1, stderr)
        self.assertTrue(json.loads(stdout)['cancelled'])
        self.assertTrue(run_check.group_absent(pid))
        self.assertFalse(run_check.probe(self.path)['available'])
        self.release()
        self.assertTrue(run_check.probe(self.path)['available'])

    def test_pending_cleanup_is_waiting_and_visible_in_status(self):
        run_check.execute(self.args)
        other = argparse.Namespace(**vars(self.args))
        other.command_id = 'second-check'
        result = run_check.execute(other)
        self.assertEqual(result['status'], 'waiting')
        status = json.loads(self.cli('status', self.path).stdout)
        self.assertIn('check-1', status['coordination']['pending_commands'])
        self.assertIn('second-check', status['coordination']['pending_commands'])
        self.release()
        self.assertEqual(run_check.execute(other)['exit_code'], 0)
        self.args = other
        self.release()

    def test_main_can_release_stopped_coordinator_slot_without_execution_authority(self):
        run_check.execute(self.args)
        value = json.loads(self.owner_path.read_text())
        proof = self.root / 'main-cleanup.json'
        data = {**value, 'runner_stopped': True, 'native_session_closed': True,
                'descendants_absent': True, 'observations': 'Synchronous fixture has no remaining process group',
                'previous_cos': 'cos-1', 'cos_stopped': True}
        proof.write_text(json.dumps(data))
        self.args.actor = 'main-1'
        self.args.proof = proof
        run_check.release(self.args)
        self.assertTrue(run_check.probe(self.path)['available'])
        self.args.command_id = 'main-may-not-execute'
        with self.assertRaisesRegex(ValueError, 'Only recorded cos'):
            run_check.execute(self.args)

    def test_interruption_before_running_state_still_has_recoverable_slot_owner(self):
        with patch.object(run_check, 'update', side_effect=RuntimeError('simulated interruption')):
            with self.assertRaisesRegex(RuntimeError, 'simulated interruption'):
                run_check.execute(self.args)
        self.assertEqual(self.saved()['status'], 'waiting')
        self.assertEqual(json.loads(self.owner_path.read_text())['command_id'], 'check-1')
        self.assertFalse(run_check.probe(self.path)['available'])
        self.assertFalse((self.root / 'checks/check-1.log').exists())
        self.release()
        self.assertTrue(run_check.probe(self.path)['available'])
        self.assertEqual(run_check.execute(self.args)['exit_code'], 0)
        self.release()

    def test_detached_descendant_keeps_capacity_until_native_cleanup(self):
        marker = self.root / 'descendant.pid'
        self.args.argv = [sys.executable, '-c',
            'import subprocess,sys,pathlib; p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"], start_new_session=True); pathlib.Path(sys.argv[1]).write_text(str(p.pid))', str(marker)]
        result = run_check.execute(self.args)
        pid = int(marker.read_text())
        try:
            os.kill(pid, 0)
            self.assertEqual(result['status'], 'finished')
            self.assertFalse(run_check.probe(self.path)['available'])
            value = json.loads(self.owner_path.read_text())
            proof = self.root / 'incomplete-cleanup.json'
            proof.write_text(json.dumps({**value, 'runner_stopped': True, 'native_session_closed': True,
                                         'descendants_absent': False, 'observations': f'Owned detached child {pid} still exists'}))
            self.args.proof = proof
            with self.assertRaisesRegex(ValueError, 'descendants_absent'):
                run_check.release(self.args)
        finally:
            os.kill(pid, signal.SIGKILL)
        deadline = time.monotonic() + 3
        while not run_check.group_absent(pid) and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(run_check.group_absent(pid))
        self.release()
        self.assertTrue(run_check.probe(self.path)['available'])
