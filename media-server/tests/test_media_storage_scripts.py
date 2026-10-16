"""Pure guard tests; no storage writes, root operations, or SSH."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1]
SCRIPTS = MODULE / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MediaStorageGuards(unittest.TestCase):
    def setUp(self):
        self.prepare = load("prepare-media-storage")
        self.guard = load("check-media-storage")
        self.disk = {"name": "test", "path": "/dev/not-real", "type": "disk", "size": 2000,
                     "serial": "confirmed-test-disk", "ro": False, "mountpoints": [],
                     "children": [{"type": "part", "fstype": "ntfs", "ro": False, "mountpoints": []}]}

    def test_only_unique_confirmed_whole_disk_is_selected(self):
        self.assertEqual(self.prepare.select_disk([self.disk], "confirmed-test-disk", 2000), self.disk)
        for inventory, serial, size in (([self.disk], "wrong", 2000), ([self.disk], "confirmed-test-disk", 1),
                                         ([self.disk, self.disk], "confirmed-test-disk", 2000)):
            with self.assertRaises(ValueError):
                self.prepare.select_disk(inventory, serial, size)

    def test_refuses_mounted_swap_mapper_readonly_and_repeat_format(self):
        for update in ({"mountpoints": ["/"]}, {"mountpoints": ["[SWAP]"]},
                       {"ro": True}, {"type": "lvm"}, {"fstype": "ext4"}):
            disk = copy.deepcopy(self.disk)
            disk["children"][0].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.prepare.select_disk([disk], "confirmed-test-disk", 2000)

    def test_mount_guard_requires_correct_uuid_type_target_and_rw(self):
        state = {"filesystem_uuid": "test-uuid"}
        mount = {"target": "/data", "fstype": "ext4", "uuid": "test-uuid", "options": "rw,nodev,noatime"}
        self.guard.validate_mount(state, mount)
        for change in ({"target": "/"}, {"fstype": "ntfs"}, {"uuid": "wrong"}, {"options": "ro,nodev"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.guard.validate_mount(state, dict(mount, **change))

    def test_formatter_refuses_without_apply_before_environment_checks(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / "prepare-media-storage.py"),
                                 "--confirm-erase", "test", "--expected-bytes", "2000", "--guard-source", "not-present"],
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No changes without explicit --apply", result.stderr)

    def test_all_python_scripts_parse_without_execution(self):
        for path in SCRIPTS.glob("*.py"):
            with self.subTest(script=path.name):
                compile(path.read_text(), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
