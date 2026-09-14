import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('blaine_dev', Path(__file__).resolve().parents[1] / 'scripts/dev.py')
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)


class ProcessOwnership(unittest.TestCase):
    def test_stale_record_never_signals_unrelated_process(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(dev, 'LOCAL', Path(directory)):
            with subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']) as unrelated:
                try:
                    (dev.LOCAL / 'runtime.pid.json').write_text(json.dumps({
                        'pid': unrelated.pid, 'start': ['wrong-boot', 'wrong-namespace', '0']}))
                    dev.stop('runtime')
                    self.assertIsNone(unrelated.poll())
                finally:
                    unrelated.terminate()
                    unrelated.wait()

    def test_matching_record_stops_only_owned_process(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(dev, 'LOCAL', Path(directory)):
            with subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']) as child:
                try:
                    (dev.LOCAL / 'runtime.pid.json').write_text(json.dumps({
                        'pid': child.pid, 'start': dev.identity(child.pid)}))
                    dev.stop('runtime')
                    self.assertIsNotNone(child.poll())
                    self.assertFalse((dev.LOCAL / 'runtime.pid.json').exists())
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.wait()
