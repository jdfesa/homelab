"""Sonarr first-deployment contract: pure/local checks, no network or Docker."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

MODULE = Path(__file__).resolve().parents[1]
SCRIPT = MODULE / 'scripts/deploy-sonarr.py'
SPEC = importlib.util.spec_from_file_location('deploy_sonarr', SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class SonarrContract(unittest.TestCase):
    def setUp(self):
        self.service = {
            'image': DEPLOY.IMAGE,
            'environment': {'PUID': '1000', 'PGID': '2000', 'UMASK': '002', 'TZ': 'America/Argentina/Buenos_Aires'},
            'ports': [{'target': 8989, 'published': '8989', 'protocol': 'tcp', 'host_ip': '10.0.0.10'}],
            'volumes': [
                {'type': 'bind', 'target': '/config', 'source': str(DEPLOY.APPDATA), 'bind': {'create_host_path': False}},
                {'type': 'bind', 'target': '/data', 'source': '/data', 'bind': {'create_host_path': False}}],
            'security_opt': ['no-new-privileges:true']}
        self.config = {'name': 'media-sonarr', 'services': {'sonarr': self.service}}

    def test_accepts_reviewed_image_and_one_common_data_bind(self):
        self.assertEqual(DEPLOY.validate_configuration(self.config, {'10.0.0.10'})[1], '10.0.0.10')

    def test_refuses_mutable_or_other_digest(self):
        for image in ('lscr.io/linuxserver/sonarr:latest', 'lscr.io/linuxserver/sonarr@sha256:' + 'a' * 64):
            self.service['image'] = image
            with self.subTest(image=image), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_elevated_init_network_and_devices(self):
        for change in ({'privileged': True}, {'network_mode': 'host'}, {'devices': ['/dev/fake']},
                       {'pid': 'host'}, {'ipc': 'host'}, {'user': '0:0'}, {'command': ['shell']},
                       {'entrypoint': ['shell']}, {'cap_add': ['SYS_ADMIN']}):
            cfg = copy.deepcopy(self.config); cfg['services']['sonarr'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})

    def test_refuses_split_extra_readonly_and_autocreated_data_mounts(self):
        for change in ({'source': '/data/media'}, {'target': '/tv'}, {'read_only': True},
                       {'bind': {'create_host_path': True}}, {'source': '/'}):
            cfg = copy.deepcopy(self.config); cfg['services']['sonarr']['volumes'][1].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})
        self.service['volumes'].append({'type': 'bind', 'source': '/data/downloads', 'target': '/downloads'})
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_hdd_config_wrong_identity_and_auth_overrides(self):
        self.service['volumes'][0]['source'] = '/data/config'
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})
        self.service['volumes'][0]['source'] = str(DEPLOY.APPDATA)
        for key, value in (('PGID', '1000'), ('UMASK', '027'), ('SONARR__AUTH__METHOD', 'None')):
            cfg = copy.deepcopy(self.config); cfg['services']['sonarr']['environment'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})

    def test_refuses_other_projects_and_missing_security(self):
        self.config['name'] = 'another-project'
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})
        self.config['name'] = 'media-sonarr'; self.service['security_opt'] = []
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
        self.assertEqual(root.findtext('Port'), '8989')
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
        self.assertTrue((MODULE / 'docs/sonarr.md').is_file())
        self.assertIn('../../docs/sonarr.md', (MODULE / 'compose/sonarr/README.md').read_text())
        self.assertFalse((MODULE / 'compose/sonarr/service-guide.md').exists())
        self.assertIn('SONARR_BIND_ADDRESS=\n', (MODULE / 'compose/sonarr/.env.example').read_text())
        lock = json.loads((MODULE / 'compose/sonarr/image-lock.json').read_text())
        self.assertEqual(lock['release'], DEPLOY.VERSION)
        self.assertEqual(lock['image'], DEPLOY.IMAGE)
        self.assertEqual(lock['image_version_label'], DEPLOY.IMAGE_VERSION)

    def test_policy_has_one_equal_hd_group_without_upgrades(self):
        policy = json.loads((MODULE / 'docs/sonarr-profile-policy.json').read_text())
        profile = policy['profile']
        self.assertEqual(policy['verified_sonarr_version'], DEPLOY.VERSION)
        self.assertEqual(policy['format'], 'declarative-policy-not-direct-api-payload')
        self.assertEqual(profile['name'], 'HD - 720p/1080p')
        self.assertFalse(profile['upgrade_allowed'])
        self.assertFalse(profile['allow_unlisted_qualities'])
        self.assertEqual(len(profile['quality_groups']), 1)
        self.assertEqual(set(profile['quality_groups'][0]['qualities']), {
            'HDTV-720p', 'WEBDL-720p', 'WEBRip-720p', 'Bluray-720p',
            'HDTV-1080p', 'WEBDL-1080p', 'WEBRip-1080p', 'Bluray-1080p',
            'Bluray-1080p Remux'})
        self.assertFalse(policy['quality_size_limits_changed'])

    def test_policy_preserves_audio_preferences_and_matching_extra_files(self):
        policy = json.loads((MODULE / 'docs/sonarr-profile-policy.json').read_text())
        self.assertEqual(policy['profile']['minimum_custom_format_score'], 1)
        self.assertEqual(policy['profile']['custom_format_scores'], {
            'Prefer original audio': 100, 'English fallback': 10})
        languages = {}
        for item in policy['custom_formats']:
            self.assertFalse(item['includeCustomFormatWhenRenaming'])
            self.assertEqual(len(item['specifications']), 1)
            spec = item['specifications'][0]
            self.assertEqual(spec['implementation'], 'LanguageSpecification')
            self.assertFalse(spec['negate'])
            self.assertFalse(spec['required'])
            self.assertFalse(spec['fields']['exceptLanguage'])
            languages[item['name']] = spec['fields']['value']
        self.assertEqual(languages, {'Prefer original audio': -2, 'English fallback': 1})
        self.assertTrue(policy['naming']['renameEpisodes'])
        self.assertEqual(policy['naming']['seasonFolderFormat'], 'Season {season:00}')
        self.assertIn('S{season:00}E{episode:00}', policy['naming']['standardEpisodeFormat'])
        for name in policy['screenshots']:
            self.assertTrue((MODULE / 'images' / name).is_file())

    def test_reference_distinguishes_connections_from_real_series_import(self):
        state = json.loads((MODULE / 'vm-config.json').read_text())
        app = state['applications']['sonarr']
        self.assertTrue(app['deployed_verified'])
        self.assertTrue(app['single_common_data_bind_verified'])
        self.assertEqual(app['version'], DEPLOY.VERSION)
        self.assertEqual(app['authentication_method'], 'Forms')
        self.assertEqual(app['authentication_required'], 'Enabled')
        self.assertEqual(app['admin_username'], 'sonarr-admin')
        self.assertEqual(app['configured_root_folder'], '/data/media/tv')
        self.assertTrue(app['prowlarr_sync_verified'])
        self.assertTrue(app['download_client']['connection_test_verified'])
        self.assertEqual(app['download_client']['category'], 'tv')
        self.assertFalse(app['download_client']['remove_completed'])
        self.assertFalse(app['download_client']['remove_failed'])
        self.assertTrue(app['filesystem_hardlink_probe_verified'])
        self.assertTrue(app['application_hardlink_import_verified'])
        self.assertTrue(app['existing_series_adopted'])
        self.assertTrue(app['completed_download_handling_enabled'])
        self.assertTrue(state['validation']['series_existing_download_import_verified'])
        self.assertTrue(state['validation']['automatic_library_discovery_verified'])
        self.assertEqual(state['validation']['automatic_library_discovery_scope'], 'new-episodes-in-initialized-tv-library')
        self.assertTrue(state['applications']['jellyfin']['automatic_tv_episode_discovery_verified'])
        self.assertFalse(state['validation']['series_pipeline_verified'])



if __name__ == '__main__':
    unittest.main()
