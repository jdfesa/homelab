"""Pure SSH key guards; never connect to servers or modify real accounts."""
import base64
import importlib.util
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
import unittest

MODULE = Path(__file__).resolve().parents[1]
SCRIPT = MODULE / "scripts/install-ssh-public-key.py"
SPEC = importlib.util.spec_from_file_location("install_ssh_public_key", SCRIPT)
KEYS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KEYS)
BLOB = base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + bytes(range(32))).decode()
PUBLIC = "ssh-ed25519 " + BLOB + " test-only"


class SshPublicKeyGuards(unittest.TestCase):
    def test_accepts_only_one_plain_structurally_valid_public_key(self):
        self.assertEqual(KEYS.parse_public_key(PUBLIC + "\n")[0], BLOB)
        for key in ("", PUBLIC + "\n" + PUBLIC, "restrict " + PUBLIC,
                    "ssh-ed25519 !!!!", "ssh-ed25519 YWJj", "ssh-rsa " + BLOB,
                    PUBLIC + "\x00bad"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                KEYS.parse_public_key(key)

    def test_preserves_old_bytes_with_or_without_final_newline(self):
        for existing in (b"", b"# keep this comment\n", b"# no final newline"):
            with self.subTest(existing=existing):
                updated, changed, fingerprint = KEYS.append_public_key(existing, PUBLIC)
                self.assertTrue(changed)
                self.assertTrue(updated.startswith(existing))
                self.assertIn(b"no-agent-forwarding,no-X11-forwarding ssh-ed25519 ", updated)
                self.assertTrue(fingerprint.startswith("SHA256:"))
                self.assertEqual(KEYS.append_public_key(updated, PUBLIC), (updated, False, fingerprint))

    def test_existing_restricted_key_is_not_duplicated_or_broadened(self):
        existing = ('command="printf hello world",no-pty ' + PUBLIC + "\n").encode()
        updated, changed, _ = KEYS.append_public_key(existing, PUBLIC)
        self.assertFalse(changed)
        self.assertEqual(updated, existing)
        self.assertTrue(KEYS.append_public_key(("# " + PUBLIC + "\n").encode(), PUBLIC)[1])

    def test_refuses_bad_owner_mode_type_and_hardlinks(self):
        safe = {"st_uid": 1000, "st_mode": stat.S_IFREG | 0o600, "st_nlink": 1}
        KEYS.validate_owner(SimpleNamespace(**safe), 1000, False)
        for change in ({"st_uid": 0}, {"st_mode": stat.S_IFREG | 0o666},
                       {"st_mode": stat.S_IFLNK | 0o700}, {"st_nlink": 2}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                KEYS.validate_owner(SimpleNamespace(**dict(safe, **change)), 1000, False)

    def test_refuses_without_apply_before_accessing_files_or_accounts(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--user", "not-a-real-user",
                                 "--expected-uid", "1000", "--public-key-file", "not-present"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No changes without explicit --apply", result.stderr)


if __name__ == "__main__":
    unittest.main()
