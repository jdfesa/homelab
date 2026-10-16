"""Pure/local reset recipe tests; never access Docker, credentials or a server."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1]
SCRIPT = MODULE / 'scripts/reset-qbittorrent-webui.py'
SPEC = importlib.util.spec_from_file_location('qbit_reset', SCRIPT)
RESET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESET)


class QBittorrentResetTests(unittest.TestCase):
    def test_credentials_respect_application_minimum_without_echoing_values(self):
        RESET.validate_credentials('admin', 'example-pass')
        for username, password in [('ab', 'example-pass'), ('bad:name', 'example-pass'),
                                   ('admin', 'short'), ('admin', 'some\nvalue')]:
            with self.subTest(username=username), self.assertRaises(ValueError):
                RESET.validate_credentials(username, password)

    def test_qsettings_pbkdf2_format_matches_reviewed_version(self):
        salt = bytes(range(16))
        encoded = RESET.encoded_password('unit-test-password', salt)
        self.assertTrue(encoded.startswith('@ByteArray(') and encoded.endswith(')'))
        encoded_salt, encoded_digest = encoded[len('@ByteArray('):-1].split(':')
        self.assertEqual(base64.b64decode(encoded_salt), salt)
        self.assertEqual(base64.b64decode(encoded_digest), hashlib.pbkdf2_hmac('sha512', b'unit-test-password', salt, 100000, 64))
        self.assertNotIn('unit-test-password', encoded)

    def test_invalid_salt_refused(self):
        with self.assertRaises(ValueError):
            RESET.encoded_password('unit-test-password', b'short')

    def test_only_two_webui_authentication_settings_change(self):
        original = '[Preferences]\nWebUI\\Username=old-user\nWebUI\\Password_PBKDF2=old-hash\nWebUI\\CSRFProtection=true\nWebUI\\Port=8080\n\n[Other]\nuntouched=value\n'
        result = RESET.replace_auth(original, 'admin', 'unit-test-password')
        before, after = RESET.settings(original), RESET.settings(result)
        self.assertEqual(after[('Preferences', 'WebUI\\Username')], 'admin')
        changed = {key for key in before if before[key] != after[key]}
        self.assertEqual(changed, {('Preferences', key) for key in RESET.AUTH_KEYS})
        self.assertEqual(result.count('WebUI\\Password_PBKDF2='), 1)
        self.assertNotIn('unit-test-password', result)

    def test_missing_preferences_refused(self):
        with self.assertRaises(ValueError):
            RESET.replace_auth('[Other]\nkey=value\n', 'admin', 'unit-test-password')

    def test_accepts_current_and_legacy_login_but_not_failure(self):
        self.assertTrue(RESET.login_ok(204, b''))
        self.assertTrue(RESET.login_ok(200, b'Ok.'))
        for code, body in [(200, b''), (200, b'Fails.'), (401, b'Unauthorized'), (204, b'unexpected')]:
            self.assertFalse(RESET.login_ok(code, body))

    def test_no_apply_refuses_before_environment_or_password_prompt(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No changes without explicit --apply', result.stderr)

    def test_image_lock_matches_reset_scope(self):
        lock = json.loads((MODULE / 'compose/qbittorrent/image-lock.json').read_text())
        self.assertEqual(lock['image'], RESET.IMAGE)


if __name__ == '__main__':
    unittest.main()
