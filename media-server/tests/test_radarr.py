"""Radarr first-deployment contract: pure/local checks, no network or Docker."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

MODULE = Path(__file__).resolve().parents[1]
SCRIPT = MODULE / 'scripts/deploy-radarr.py'
SPEC = importlib.util.spec_from_file_location('deploy_radarr', SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class RadarrContract(unittest.TestCase):
    def setUp(self):
        self.service = {
            'image': DEPLOY.IMAGE,
            'environment': {'PUID': '1000', 'PGID': '2000', 'UMASK': '002', 'TZ': 'America/Argentina/Buenos_Aires'},
            'ports': [{'target': 7878, 'published': '7878', 'protocol': 'tcp', 'host_ip': '10.0.0.10'}],
            'volumes': [
                {'type': 'bind', 'target': '/config', 'source': str(DEPLOY.APPDATA), 'bind': {'create_host_path': False}},
                {'type': 'bind', 'target': '/data', 'source': '/data', 'bind': {'create_host_path': False}}],
            'security_opt': ['no-new-privileges:true']}
        self.config = {'name': 'media-radarr', 'services': {'radarr': self.service}}

    def test_accepts_reviewed_image_and_one_common_data_bind(self):
        self.assertEqual(DEPLOY.validate_configuration(self.config, {'10.0.0.10'})[1], '10.0.0.10')

    def test_refuses_mutable_or_other_digest(self):
        for image in ('lscr.io/linuxserver/radarr:latest', 'lscr.io/linuxserver/radarr@sha256:' + 'a' * 64):
            self.service['image'] = image
            with self.subTest(image=image), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_elevated_init_network_and_devices(self):
        for change in ({'privileged': True}, {'network_mode': 'host'}, {'devices': ['/dev/fake']},
                       {'pid': 'host'}, {'ipc': 'host'}, {'user': '0:0'}, {'command': ['shell']},
                       {'entrypoint': ['shell']}, {'cap_add': ['SYS_ADMIN']}):
            cfg = copy.deepcopy(self.config); cfg['services']['radarr'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})

    def test_refuses_split_extra_readonly_and_autocreated_data_mounts(self):
        for change in ({'source': '/data/media'}, {'target': '/movies'}, {'read_only': True},
                       {'bind': {'create_host_path': True}}, {'source': '/'}):
            cfg = copy.deepcopy(self.config); cfg['services']['radarr']['volumes'][1].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})
        self.service['volumes'].append({'type': 'bind', 'source': '/data/downloads', 'target': '/downloads'})
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_hdd_config_wrong_identity_and_auth_overrides(self):
        self.service['volumes'][0]['source'] = '/data/config'
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})
        self.service['volumes'][0]['source'] = str(DEPLOY.APPDATA)
        for key, value in (('PGID', '1000'), ('UMASK', '027'), ('RADARR__AUTH__METHOD', 'None')):
            cfg = copy.deepcopy(self.config); cfg['services']['radarr']['environment'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})

    def test_refuses_other_projects_and_missing_security(self):
        self.config['name'] = 'another-project'
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})
        self.config['name'] = 'media-radarr'; self.service['security_opt'] = []
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_wildcard_public_linklocal_loopback_or_unassigned_ip(self):
        for address in ('0.0.0.0', '8.8.8.8', '127.0.0.1', '169.254.10.1', '10.0.0.11', '::1'):
            self.service['ports'][0]['host_ip'] = address
            with self.subTest(address=address), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(self.config, {'10.0.0.10'})
        self.service['ports'][0]['host_ip'] = '10.0.0.10'
        self.service['ports'][0]['published'] = '8787'
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_seed_keeps_native_authentication_without_embedded_secrets(self):
        root = ET.fromstring(DEPLOY.initial_configuration())
        self.assertEqual(root.findtext('Port'), '7878')
        self.assertEqual(root.findtext('AuthenticationRequired'), 'Enabled')
        self.assertEqual(root.findtext('UpdateMechanism'), 'Docker')
        self.assertEqual(root.findtext('UpdateAutomatically'), 'False')
        for name in ('AuthenticationMethod', 'Username', 'Password', 'ApiKey'):
            self.assertIsNone(root.find(name))

    def test_refuses_without_apply_before_any_real_work(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--compose-file', 'missing', '--env-file', 'missing'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No changes without explicit --apply', result.stderr)

    def test_canonical_docs_and_lock_match_the_recipe(self):
        self.assertTrue((MODULE / 'docs/radarr.md').is_file())
        self.assertIn('../../docs/radarr.md', (MODULE / 'compose/radarr/README.md').read_text())
        self.assertFalse((MODULE / 'compose/radarr/service-guide.md').exists())
        self.assertIn('RADARR_BIND_ADDRESS=\n', (MODULE / 'compose/radarr/.env.example').read_text())
        lock = json.loads((MODULE / 'compose/radarr/image-lock.json').read_text())
        self.assertEqual(lock['release'], DEPLOY.VERSION)
        self.assertEqual(lock['image'], DEPLOY.IMAGE)
        self.assertEqual(lock['image_version_label'], DEPLOY.IMAGE_VERSION)


if __name__ == '__main__':
    unittest.main()
