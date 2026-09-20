"""Offline policy tests only: never run volume main() from a test."""
import importlib.util
from pathlib import Path
import sys
import unittest

from test_backup import backup, ROOT

sys.modules["backup"] = backup
spec = importlib.util.spec_from_file_location("prepare_volume", ROOT / "infra/backup/prepare-volume.py")
volume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(volume)


class VolumePlanTests(unittest.TestCase):
    def test_fstab_preserves_existing_bytes_and_reapplies_unchanged(self):
        original = "# existing configuration\nUUID=root-uuid / ext4 defaults 0 1\n"
        desired = volume.fstab_text(original)
        self.assertTrue(desired.startswith(original))
        self.assertIn(volume.ENTRY, desired)
        self.assertEqual(volume.fstab_text(desired), desired)

    def test_conflicting_uuid_mountpoint_or_duplicate_entry_stops(self):
        for original in [
            f"UUID={volume.UUID} /other ext4 defaults 0 0\n",
            f"UUID=other {volume.MOUNT} ext4 defaults 0 0\n",
            volume.ENTRY + "\n" + volume.ENTRY + "\n",
        ]:
            with self.subTest(original=original), self.assertRaises(backup.Refused):
                volume.fstab_text(original)


if __name__ == "__main__":
    unittest.main()
