import json
import time
from datetime import datetime, timezone

from support import GraphV2Case


class BudgetRecoveryTests(GraphV2Case):
    def prepared_run(self):
        contract = self.v5_contract()
        contract.update(budget_seconds=2, review_checkpoint_seconds=1)
        contract_path = self.root / 'contract.json'
        contract_path.write_text(json.dumps(contract))
        self.run_count = getattr(self, 'run_count', 0) + 1
        path = self.root / f'run-{self.run_count}.json'
        self.assertEqual(self.cli('init', path, '--contract', contract_path).returncode, 0)
        self.assertEqual(self.cli('start', path, 'prepare', '--worker', 'cos').returncode, 0)
        self.state = json.loads(path.read_text())
        receipt = self.root / 'prepare.json'
        receipt.write_text(json.dumps(self.receipt('prepare')))
        result = self.cli('complete', path, 'prepare', '--receipt', receipt)
        self.assertEqual(result.returncode, 0, result.stderr)
        return path

    def expire(self, path):
        state = json.loads(path.read_text())
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(state['budget']['started'])).total_seconds()
        time.sleep(max(0, state['budget']['seconds'] - elapsed) + 0.05)

    def test_approved_extension_can_recover_expired_budget_with_stale_or_missing_report(self):
        for damage in ('overwritten', 'missing'):
            with self.subTest(damage=damage):
                path = self.prepared_run()
                if damage == 'missing':
                    self.report.unlink()
                else:
                    self.report.write_text('overwritten report')
                self.expire(path)
                result = self.cli('budget', path, '--seconds', '60', '--approval', self.approval)
                self.assertEqual(result.returncode, 0, result.stderr)
                rejected = self.cli('start', path, 'tests', '--worker', 'writer')
                self.assertEqual(rejected.returncode, 2, 'Extension must not waive stale delivery evidence')
                status = self.cli('status', path)
                self.assertEqual(json.loads(status.stdout)['ready'], [])
                repaired = self.cli('repair', path, 'prepare', '--cause', 'damaged-report', '--reason', 'Recreate setup proof')
                self.assertEqual(repaired.returncode, 0, repaired.stderr)
                self.assertEqual(self.cli('start', path, 'prepare', '--worker', 'cos-repair').returncode, 0)
                self.report.write_text('Fixture evidence\n')
                path.unlink()

    def test_external_wait_can_be_recorded_while_delivery_evidence_is_stale(self):
        path = self.prepared_run()
        self.report.write_text('overwritten report')
        result = self.cli('wait', path, 'user', '--evidence', self.approval)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli('start', path, 'tests', '--worker', 'writer').returncode, 2)
        self.assertEqual(self.cli('wait', path, 'end').returncode, 0)

    def test_budget_recovery_still_rejects_changed_freeze(self):
        path = self.prepared_run()
        before = path.read_bytes()
        self.spec.write_text('unapproved changed spec')
        result = self.cli('budget', path, '--seconds', '60', '--approval', self.approval)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(path.read_bytes(), before)
