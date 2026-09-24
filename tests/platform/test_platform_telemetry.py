"""Protect unrelated live Alloy ownership while reconciling infrastructure metrics."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('reconcile', ROOT / 'infra/telemetry/reconcile-alloy.py')
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.base = 'prometheus.remote_write "grafana_metrics" {}\notelcol.receiver.prometheus "local" {}\n// independently owned application configuration\n'
        self.fragment = (ROOT / 'infra/alloy/platform-telemetry.alloy').read_text()

    def test_unrelated_configuration_survives_updates_and_convergence(self):
        first = reconcile.compose(self.base, self.fragment)
        self.assertTrue(first.startswith(self.base))
        concurrent = first + '\n// later independent edit\n'
        self.assertEqual(reconcile.compose(concurrent, self.fragment), concurrent)
        updated = reconcile.compose(concurrent, self.fragment + '\n// platform update')
        self.assertTrue(updated.startswith(self.base))
        self.assertTrue(updated.endswith('\n// later independent edit\n'))
        self.assertEqual(updated.count(reconcile.BEGIN), 1)

    def test_malformed_ownership_or_duplicate_sources_stop(self):
        for invalid in [self.base + reconcile.BEGIN, self.base + reconcile.END,
                        self.base + 'prometheus.scrape "vllm" {}',
                        self.base + 'prometheus.scrape "gpu" {}',
                        self.base + 'remotecfg {}', '']:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                reconcile.compose(invalid, self.fragment)


if __name__ == '__main__':
    unittest.main()
