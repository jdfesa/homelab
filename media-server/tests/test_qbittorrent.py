"""Pure downloader contract checks; no Docker, SSH, HTTP or disk provisioning."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1]
SCRIPT = MODULE / 'scripts/deploy-qbittorrent.py'
SPEC = importlib.util.spec_from_file_location('deploy_qbittorrent', SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class QbittorrentContract(unittest.TestCase):
    def setUp(self):
        self.service = {
            'image': 'lscr.io/linuxserver/qbittorrent@sha256:' + 'a' * 64,
            'environment': {'PUID': '1000', 'PGID': '2000', 'UMASK': '002',
                            'TZ': 'America/Argentina/Buenos_Aires', 'WEBUI_PORT': '8080', 'TORRENTING_PORT': '6881'},
            'ports': [{'target': 8080, 'published': '8080', 'protocol': 'tcp', 'host_ip': '10.0.0.10'}],
            'volumes': [{'type': 'bind', 'target': '/config', 'source': str(DEPLOY.APPDATA), 'bind': {'create_host_path': False}},
                        {'type': 'bind', 'target': '/data/downloads', 'source': '/data/downloads', 'bind': {'create_host_path': False}}],
            'security_opt': ['no-new-privileges:true']}
        self.config = {'name': 'media-qbittorrent', 'services': {'qbittorrent': self.service}}

    def test_accepts_pinned_image_limited_mounts_and_lan(self):
        self.assertEqual(DEPLOY.validate_configuration(self.config, {'10.0.0.10'})[1], '10.0.0.10')

    def test_rejects_mutable_image_privileged_init_override_and_extra_service(self):
        for change in ({'image': 'lscr.io/linuxserver/qbittorrent:latest'}, {'privileged': True},
                       {'network_mode': 'host'}, {'devices': ['/dev/sdb']}, {'user': '0:0'}, {'entrypoint': ['/bin/sh']}):
            cfg = copy.deepcopy(self.config); cfg['services']['qbittorrent'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})
        self.config['services']['other'] = {}
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_rejects_media_mount_automatic_bind_creation_and_wrong_identity(self):
        for edit in ('media', 'autocreate', 'gid'):
            cfg = copy.deepcopy(self.config); service = cfg['services']['qbittorrent']
            if edit == 'media': service['volumes'][1]['source'] = '/data'
            if edit == 'autocreate': service['volumes'][1]['bind']['create_host_path'] = True
            if edit == 'gid': service['environment']['PGID'] = '1000'
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})

    def test_rejects_unassigned_public_wildcard_and_peer_publication(self):
        for address in ('0.0.0.0', '8.8.8.8', '127.0.0.1', '10.0.0.11'):
            cfg = copy.deepcopy(self.config); cfg['services']['qbittorrent']['ports'][0]['host_ip'] = address
            with self.subTest(address=address), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})
        self.service['ports'].append({'target': 6881, 'published': '6881'})
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_seed_disables_both_router_mappings_and_keeps_auth(self):
        seed = DEPLOY.initial_configuration('10.0.0.10')
        for setting in ('PortForwardingEnabled=false', r'WebUI\UseUPnP=false', r'WebUI\LocalHostAuth=true',
                        r'WebUI\AuthSubnetWhitelistEnabled=false', r'WebUI\CSRFProtection=true',
                        r'WebUI\HostHeaderValidation=true', r'Session\DefaultSavePath=/data/downloads/',
                        r'Session\TempPath=/data/downloads/incomplete/'):
            self.assertIn(setting, seed)
        self.assertNotIn('Password', seed)
        self.assertNotIn('/data/media', seed)

    def test_refuses_implicit_apply(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--compose-file', 'missing', '--env-file', 'missing'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No changes without explicit --apply', result.stderr)

    def test_accepts_204_login_but_not_empty_200_or_failure(self):
        self.assertTrue(DEPLOY.login_response_accepted(204, ''))
        self.assertTrue(DEPLOY.login_response_accepted(200, 'Ok.'))
        for status, body in ((200, ''), (200, 'Fails.'), (403, ''), (204, 'Fails.')):
            self.assertFalse(DEPLOY.login_response_accepted(status, body))

    def test_deployed_services_have_canonical_docs_not_duplicate_guides(self):
        for service in ('jellyfin', 'qbittorrent', 'prowlarr', 'radarr'):
            self.assertTrue((MODULE / 'docs' / (service + '.md')).is_file())
            self.assertFalse((MODULE / 'compose' / service / 'service-guide.md').exists())
            self.assertIn('../../docs/' + service + '.md', (MODULE / 'compose' / service / 'README.md').read_text())

    def test_completed_jellyfin_setup_does_not_claim_playback(self):
        app = json.loads((MODULE / 'vm-config.json').read_text())['applications']['jellyfin']
        self.assertTrue(app['startup_wizard_completed_verified'])
        self.assertTrue(app['remote_access_enabled_confirmed_by_user'])
        self.assertFalse(app['wan_publication_configured'])
        self.assertFalse(app['playback_verified'])


if __name__ == '__main__':
    unittest.main()
