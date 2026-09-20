"""Offline controls for the one-shot live binding. Never invokes Codex."""
import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('live_binding_tests',ROOT/'experiments/kernel-increment-11/live/binding.py')
binding=importlib.util.module_from_spec(spec);spec.loader.exec_module(binding)

class LiveBoundaryTests(unittest.TestCase):
    def test_normalization_is_only_closed_json_serialization(self):
        self.assertEqual(binding.normalize('{"organization":"FLOWER", "marker":"MASKED_01"}'),'{"marker":"MASKED_01","organization":"FLOWER"}')
        for raw in ('{"organization":"FLOWER"}','{"organization":"FLOWER","marker":"MASKED_01","extra":1}',
                    '{"organization":"FLOWER","marker":"a","marker":"b"}','not json'):
            with self.assertRaises((ValueError,TypeError)):binding.normalize(raw)

    def test_claim_is_exclusive_persistent_and_never_reset(self):
        with tempfile.TemporaryDirectory() as d:
            receipt=Path(d)/'attempt.json';r=SimpleNamespace(worker_dispatch_id='dispatch:fixture/2',context_digest='a'*64)
            binding.claim_dispatch(receipt,r)
            with self.assertRaises(FileExistsError):binding.claim_dispatch(receipt,r)
            self.assertEqual(json.loads(receipt.read_text())['worker_dispatch_id'],r.worker_dispatch_id)

    def test_blaine_owns_process_group_termination(self):
        p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],start_new_session=True)
        try:binding.stop_process(p);self.assertIsNotNone(p.poll())
        finally:
            if p.poll() is None:p.kill();p.wait()

    def test_command_pins_worker_model_and_empty_workspace(self):
        command=binding.command()
        self.assertIn('--ephemeral',command);self.assertIn('gpt-6-astra',command)
        self.assertIn('/probe',command);self.assertIn('--die-with-parent',command)
        self.assertIn('read-only',command);self.assertNotIn(str(ROOT),command)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',command)
