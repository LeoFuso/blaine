"""Metrics credentials stay scoped to Hosted Metrics and existing BWS bootstrap."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('metrics_materializer', Path(__file__).resolve().parents[2] / 'infra/grafana-cloud.py')
cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud)

class MetricsSecretTests(unittest.TestCase):
    def values(self):
        return {'GRAFANA_CLOUD_METRICS_API_KEY': 'synthetic_metrics_test_credential_only'}

    def test_unsafe_credentials_rejected(self):
        for bad in ['x\nINJECT=yes', '$(id)', 'REPLACE_ME', 'short']:
            with self.subTest(value=bad), self.assertRaises(ValueError):
                cloud.validate_metrics({'GRAFANA_CLOUD_METRICS_API_KEY': bad})

    def test_nonsecret_configuration_does_not_belong_in_bws_material(self):
        for name in ['GRAFANA_CLOUD_METRICS_URL', 'GRAFANA_CLOUD_METRICS_INSTANCE_ID']:
            values = self.values()
            values[name] = 'nonsecret-configuration'
            with self.assertRaises(ValueError):
                cloud.validate_metrics(values)

    def test_extra_fields_rejected(self):
        values = self.values()
        values['BWS_ACCESS_TOKEN'] = 'synthetic-bootstrap'
        with self.assertRaises(ValueError):
            cloud.validate_metrics(values)

    def test_missing_and_duplicate_keys_fail_without_privileged_write(self):
        rows = [{'key': k, 'value': v} for k, v in self.values().items()]
        for invalid in (rows[:-1], rows + [rows[-1]]):
            with patch.object(cloud.subprocess, 'run', side_effect=[
                SimpleNamespace(returncode=0, stdout='synthetic-bootstrap'),
                SimpleNamespace(returncode=0, stdout=json.dumps(invalid)),
            ]) as run:
                with self.assertRaises(RuntimeError):
                    cloud.metrics_from_bws()
                self.assertEqual(run.call_count, 2)

    def test_materialization_passes_only_selected_values_over_stdin(self):
        with patch.object(cloud, 'metrics_from_bws', return_value=self.values()), \
             patch.object(cloud.sys, 'argv', ['grafana-cloud.py', 'materialize-metrics']), \
             patch.object(cloud.subprocess, 'run') as run:
            cloud.main()
        args, kwargs = run.call_args
        self.assertEqual(args[0][-1], 'write-metrics-env')
        self.assertEqual(json.loads(kwargs['input']), self.values())
        self.assertNotIn(self.values()[cloud.METRICS_FIELDS[0]], args[0])

    def test_composition_preserves_local_receivers_and_limits_input(self):
        root = Path(__file__).resolve().parents[2]
        base = (root / 'infra/alloy/config.alloy').read_text()
        composed = cloud.compose_metrics(base, (root / 'infra/alloy/metrics.alloy.inactive').read_text())
        self.assertEqual(composed.count('sample_limit = 5000'), 2)
        self.assertEqual(composed.count('body_size_limit = "2MiB"'), 2)
        self.assertEqual(composed.count('otelcol.receiver.prometheus.local.receiver,'), 2)
        self.assertIn('otelcol.exporter.file.local.input', composed)
        self.assertNotIn('remotecfg {', composed)
        with self.assertRaises(RuntimeError):
            cloud.compose_metrics(composed, '')
