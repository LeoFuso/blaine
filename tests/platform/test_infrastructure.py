"""Security boundaries for the operator-controlled cloud activation path."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('grafana_cloud', ROOT / 'infra/grafana-cloud.py')
cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud)


class CloudContractTests(unittest.TestCase):
    def values(self):
        return dict(zip(cloud.FIELDS, ['https://otlp-gateway-test.grafana.net/otlp', '12345', 'synthetic_token_for_unit_tests_only']))

    def test_placeholders_and_environment_injection_fail_closed(self):
        for unsafe in ['', 'REPLACE_ME_NOT_ACTIVE', 'changeme', 'a\nEVIL=yes', 'x$(id)', 'x`id`', 'x\\y', 'x\x00y']:
            with self.subTest(value=unsafe):
                v = self.values()
                v[cloud.FIELDS[2]] = unsafe
                with self.assertRaises(ValueError):
                    cloud.validate(v)

    def test_endpoint_cannot_send_credentials_to_another_host(self):
        for endpoint in ['http://otlp-gateway-test.grafana.net/otlp', 'https://grafana.net.evil.invalid/otlp',
                         'https://otlp-gateway-test.grafana.net@evil.invalid/otlp', 'https://localhost/otlp',
                         'https://otlp-gateway-test.grafana.net/otlp?token=oops',
                         'https://otlp-gateway-test.grafana.net/otlp#fragment']:
            v = self.values()
            v[cloud.FIELDS[0]] = endpoint
            with self.assertRaises(ValueError):
                cloud.validate(v)

    def test_complete_selected_fields_required(self):
        self.assertEqual(cloud.validate(self.values()), self.values())
        v = self.values()
        v['BW_SESSION'] = 'must-not-be-materialized'
        with self.assertRaises(ValueError):
            cloud.validate(v)

    def test_atomic_materialization_restricts_permissions_and_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'cloud.env'
            cloud.atomic(path, 'synthetic\n', 0o600)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.read_text(), 'synthetic\n')
            link = Path(d) / 'link'
            link.symlink_to(path)
            with self.assertRaises(RuntimeError):
                cloud.atomic(link, 'overwritten', 0o600)
            self.assertEqual(path.read_text(), 'synthetic\n')


if __name__ == '__main__':
    unittest.main()
