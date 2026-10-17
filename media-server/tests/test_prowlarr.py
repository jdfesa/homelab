"""Prowlarr pure deployment contract; no Docker, accounts, network or provisioning."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

MODULE = Path(__file__).resolve().parents[1]
SCRIPT = MODULE / 'scripts/deploy-prowlarr.py'
SPEC = importlib.util.spec_from_file_location('deploy_prowlarr', SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class ProwlarrContract(unittest.TestCase):
    def setUp(self):
        self.service = {
            'image': 'lscr.io/linuxserver/prowlarr@sha256:' + 'a' * 64,
            'environment': {'PUID': '1000', 'PGID': '2000', 'UMASK': '027', 'TZ': 'America/Argentina/Buenos_Aires'},
            'ports': [{'target': 9696, 'published': '9696', 'protocol': 'tcp', 'host_ip': '10.0.0.10'}],
            'volumes': [{'type': 'bind', 'target': '/config', 'source': str(DEPLOY.APPDATA), 'bind': {'create_host_path': False}}],
            'security_opt': ['no-new-privileges:true']}
        self.config = {'name': 'media-prowlarr', 'services': {'prowlarr': self.service}}

    def test_accepts_pinned_image_minimal_config_and_lan(self):
        self.assertEqual(DEPLOY.validate_configuration(self.config, {'10.0.0.10'})[1], '10.0.0.10')

    def test_refuses_mutable_image_host_network_devices_and_auth_env_override(self):
        for change in ({'image': 'lscr.io/linuxserver/prowlarr:latest'}, {'privileged': True}, {'network_mode': 'host'},
                       {'devices': ['/dev/sdb']}, {'command': ['shell']}, {'user': '0:0'}):
            cfg = copy.deepcopy(self.config); cfg['services']['prowlarr'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})
        self.service['environment']['PROWLARR__AUTH__METHOD'] = 'None'
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_hdd_or_extra_mounts_and_automatic_creation(self):
        for change in ({'source': '/data/appdata'}, {'source': '/'}, {'bind': {'create_host_path': True}}):
            cfg = copy.deepcopy(self.config); cfg['services']['prowlarr']['volumes'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})
        self.service['volumes'].append({'type': 'bind', 'source': '/data', 'target': '/data'})
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_public_wildcard_unassigned_or_extra_ports(self):
        for address in ('0.0.0.0', '8.8.8.8', '127.0.0.1', '10.0.0.11'):
            cfg = copy.deepcopy(self.config); cfg['services']['prowlarr']['ports'][0]['host_ip'] = address
            with self.subTest(address=address), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})
        self.service['ports'].append({'target': 22})
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_initial_config_does_not_force_auth_bypass_or_embed_secrets(self):
        root = ET.fromstring(DEPLOY.initial_configuration())
        self.assertEqual(root.findtext('AuthenticationRequired'), 'Enabled')
        self.assertIsNone(root.find('AuthenticationMethod'))
        self.assertEqual(root.findtext('UpdateMechanism'), 'Docker')
        self.assertEqual(root.findtext('UpdateAutomatically'), 'False')
        for field in ('ApiKey', 'Password', 'Username'):
            self.assertIsNone(root.find(field))

    def test_refuses_without_explicit_apply(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--compose-file', 'missing', '--env-file', 'missing'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No changes without explicit --apply', result.stderr)

    def test_module_has_canonical_guide_and_blank_site_address(self):
        self.assertTrue((MODULE / 'docs/prowlarr.md').is_file())
        self.assertIn('../../docs/prowlarr.md', (MODULE / 'compose/prowlarr/README.md').read_text())
        self.assertFalse((MODULE / 'compose/prowlarr/service-guide.md').exists())
        self.assertIn('PROWLARR_BIND_ADDRESS=\n', (MODULE / 'compose/prowlarr/.env.example').read_text())
        lock = json.loads((MODULE / 'compose/prowlarr/image-lock.json').read_text())
        self.assertEqual(lock['release'], DEPLOY.VERSION)

    def test_reference_contains_saved_sources_and_native_authentication(self):
        app = json.loads((MODULE / 'vm-config.json').read_text())['applications']['prowlarr']
        self.assertEqual(app['authentication_method'], 'Forms')
        self.assertEqual(app['authentication_required'], 'Enabled')
        self.assertFalse(app['hdd_mounted'])
        self.assertEqual(app['radarr_sync_level'], 'FullSync')
        sources = {source['name']: source for source in app['indexers']}
        self.assertEqual(set(sources), {'Knaben', 'The Pirate Bay'})
        self.assertTrue(sources['Knaben']['prefer_magnet_url'])
        self.assertEqual(sources['The Pirate Bay']['api_url'], 'apibay.org')
        self.assertTrue(all(source['sync_profile'] == 'Standard' for source in sources.values()))


if __name__ == '__main__':
    unittest.main()
