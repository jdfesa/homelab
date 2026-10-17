"""Bazarr first-deployment contract: pure/local checks, no network or Docker."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1]
SCRIPT = MODULE / 'scripts/deploy-bazarr.py'
SPEC = importlib.util.spec_from_file_location('deploy_bazarr', SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class BazarrContract(unittest.TestCase):
    def setUp(self):
        self.service = {
            'image': DEPLOY.IMAGE,
            'environment': {'PUID': '1000', 'PGID': '2000', 'UMASK': '002', 'TZ': 'America/Argentina/Buenos_Aires'},
            'ports': [{'target': 6767, 'published': '6767', 'protocol': 'tcp', 'host_ip': '10.0.0.10'}],
            'volumes': [
                {'type': 'bind', 'target': '/config', 'source': str(DEPLOY.APPDATA), 'bind': {'create_host_path': False}},
                {'type': 'bind', 'target': '/data/media', 'source': '/data/media', 'bind': {'create_host_path': False}}],
            'security_opt': ['no-new-privileges:true']}
        self.config = {'name': 'media-bazarr', 'services': {'bazarr': self.service}}

    def test_accepts_reviewed_image_and_library_only_bind(self):
        self.assertEqual(DEPLOY.validate_configuration(self.config, {'10.0.0.10'})[1], '10.0.0.10')

    def test_refuses_mutable_or_other_digest(self):
        for image in ('lscr.io/linuxserver/bazarr:latest', 'lscr.io/linuxserver/bazarr@sha256:' + 'a' * 64):
            self.service['image'] = image
            with self.subTest(image=image), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_elevated_init_network_and_devices(self):
        for change in ({'privileged': True}, {'network_mode': 'host'}, {'devices': ['/dev/fake']},
                       {'pid': 'host'}, {'ipc': 'host'}, {'user': '0:0'}, {'command': ['shell']},
                       {'entrypoint': ['shell']}, {'cap_add': ['SYS_ADMIN']}):
            cfg = copy.deepcopy(self.config); cfg['services']['bazarr'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})

    def test_refuses_extra_readonly_and_autocreated_data_mounts(self):
        for change in ({'source': '/data'}, {'target': '/movies'}, {'read_only': True},
                       {'bind': {'create_host_path': True}}, {'source': '/'}):
            cfg = copy.deepcopy(self.config); cfg['services']['bazarr']['volumes'][1].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})
        self.service['volumes'].append({'type': 'bind', 'source': '/data/downloads', 'target': '/downloads'})
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_hdd_config_wrong_identity_and_auth_overrides(self):
        self.service['volumes'][0]['source'] = '/data/config'
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})
        self.service['volumes'][0]['source'] = str(DEPLOY.APPDATA)
        for key, value in (('PGID', '1000'), ('UMASK', '027'), ('BAZARR__AUTH__METHOD', 'None')):
            cfg = copy.deepcopy(self.config); cfg['services']['bazarr']['environment'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(cfg, {'10.0.0.10'})

    def test_refuses_other_projects_and_missing_security(self):
        self.config['name'] = 'another-project'
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})
        self.config['name'] = 'media-bazarr'; self.service['security_opt'] = []
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_refuses_wildcard_public_linklocal_loopback_or_unassigned_ip(self):
        for address in ('0.0.0.0', '8.8.8.8', '127.0.0.1', '169.254.10.1', '10.0.0.11', '::1'):
            self.service['ports'][0]['host_ip'] = address
            with self.subTest(address=address), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(self.config, {'10.0.0.10'})
        self.service['ports'][0]['host_ip'] = '10.0.0.10'
        self.service['ports'][0]['published'] = '8787'
        with self.assertRaises(ValueError): DEPLOY.validate_configuration(self.config, {'10.0.0.10'})

    def test_seed_protects_auth_and_disables_all_search_sources(self):
        seed = DEPLOY.initial_configuration('bazarr-admin', 'test-only-credential-not-a-secret')
        self.assertEqual(seed['auth']['type'], 'form')
        self.assertEqual(seed['auth']['username'], 'bazarr-admin')
        self.assertNotEqual(seed['auth']['password'], 'test-only-credential-not-a-secret')
        self.assertEqual(len(seed['auth']['password']), 32)
        self.assertEqual(len(seed['auth']['apikey']), 32)
        general = seed['general']
        self.assertEqual(general['enabled_providers'], [])
        for key in ('use_sonarr', 'use_radarr', 'auto_update', 'single_language', 'upgrade_subs', 'use_postprocessing'):
            self.assertFalse(general[key])
        self.assertTrue(general['use_embedded_subs'])
        self.assertFalse(seed['subsync']['use_subsync'])
        self.assertFalse(seed['analytics']['enabled'])
        self.assertEqual(general['concurrent_jobs'], 1)
        other = DEPLOY.initial_configuration('bazarr-admin', 'test-only-credential-not-a-secret')
        self.assertNotEqual(seed['auth']['apikey'], other['auth']['apikey'])

    def test_rejects_short_password_or_unsafe_username(self):
        for user, password in [('a', 'short'), ('../admin', 'x'*30), ('', 'x'*30)]:
            with self.subTest(user=user), self.assertRaises(ValueError):
                DEPLOY.initial_configuration(user, password)

    def test_refuses_without_apply_before_any_real_work(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--compose-file', 'missing', '--env-file', 'missing', '--username', 'bazarr-admin'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No changes without explicit --apply', result.stderr)

    def test_canonical_docs_and_lock_match_the_recipe(self):
        self.assertTrue((MODULE / 'docs/bazarr.md').is_file())
        self.assertIn('../../docs/bazarr.md', (MODULE / 'compose/bazarr/README.md').read_text())
        self.assertFalse((MODULE / 'compose/bazarr/service-guide.md').exists())
        self.assertIn('BAZARR_BIND_ADDRESS=\n', (MODULE / 'compose/bazarr/.env.example').read_text())
        lock = json.loads((MODULE / 'compose/bazarr/image-lock.json').read_text())
        self.assertEqual(lock['release'], DEPLOY.VERSION)
        self.assertEqual(lock['image'], DEPLOY.IMAGE)
        self.assertEqual(lock['image_version_label'], DEPLOY.IMAGE_VERSION)


class BazarrPolicy(unittest.TestCase):
    def test_both_languages_full_without_audio_exclusion_or_cutoff(self):
        policy = json.loads((MODULE / 'docs/bazarr-profile-policy.json').read_text())
        profile = policy['profile']
        self.assertEqual(profile['name'], 'English + Spanish')
        self.assertIsNone(profile['cutoff'])
        self.assertEqual([x['language'] for x in profile['items']], ['en', 'es'])
        for item in profile['items']:
            self.assertEqual(item['audio_exclude'], 'False')
            self.assertEqual(item['audio_only_include'], 'False')
            self.assertEqual(item['forced'], 'False')
            self.assertEqual(item['hi'], 'False')
            self.assertNotIn('audioExclude', item)
        self.assertTrue(policy['embedded_count_as_downloaded'])
        self.assertFalse(policy['single_language'])
        self.assertFalse(policy['upgrade_subs'])
        self.assertFalse(policy['automatic_sync'])
        self.assertEqual(policy['providers_enabled'], ['opensubtitlescom'])
        self.assertEqual(policy['provider_options'], {
            'use_hash': True, 'include_ai_translated': False, 'include_machine_translated': False})
        self.assertEqual(policy['automatic_search'], {
            'missing_series_every_hours': 6, 'missing_movies_every_hours': 6,
            'new_imports_via_signalr': True, 'concurrent_jobs': 1})
        self.assertEqual(policy['jellyfin']['refresh_method'], 'immediate')
        self.assertTrue(policy['jellyfin']['enabled'])
        self.assertTrue(policy['jellyfin']['update_movie_library'])
        self.assertTrue(policy['jellyfin']['update_series_library'])
        self.assertEqual(policy['jellyfin']['movie_library_names'], ['Movies'])
        self.assertEqual(policy['jellyfin']['series_library_names'], ['Shows'])
        self.assertNotIn('apikey', policy['jellyfin'])
        self.assertEqual(policy['external_subtitle_folder'], 'current')

    def test_reference_distinguishes_installed_from_end_to_end(self):
        app = json.loads((MODULE / 'vm-config.json').read_text())['applications']['bazarr']
        self.assertTrue(app['deployed_verified'])
        self.assertTrue(app['radarr_connection_verified'])
        self.assertTrue(app['embedded_subtitles_index_verified'])
        self.assertTrue(app['external_subtitles_index_verified'])
        self.assertEqual(app['external_subtitles_index_scope'], 'manual-and-downloaded-sidecars-on-managed-series')
        self.assertTrue(app['manual_sidecars_index_verified'])
        self.assertTrue(app['jellyfin_manual_sidecar_discovery_verified'])
        self.assertTrue(app['subtitle_download_verified'])
        self.assertTrue(app['providers_configured'])
        self.assertTrue(app['automatic_search_enabled'])
        self.assertEqual(app['missing_subtitle_search_hours'], 6)
        self.assertTrue(app['jellyfin_connection_verified'])
        self.assertTrue(app['jellyfin_episode_refresh_verified'])
        self.assertFalse(app['jellyfin_movie_refresh_verified'])
        self.assertEqual(app['jellyfin_refresh_method'], 'immediate')
        self.assertTrue(app['sonarr_enabled'])
        self.assertTrue(app['sonarr_connection_verified'])
        self.assertTrue(app['sonarr_signalr_verified'])
        self.assertTrue(app['series_embedded_subtitles_index_verified'])
        self.assertEqual(app['admin_username'], 'bazarr-admin')
        self.assertEqual(app['path_mappings'], [])

    def test_manual_sidecars_have_a_distinct_recipe_and_inventory_boundary(self):
        guide = (MODULE / 'docs/bazarr.md').read_text()
        self.assertIn('### Manual Sidecars', guide)
        self.assertIn('Series - S01E01 - Title WEBRip-1080p.es.srt', guide)
        self.assertIn('Daily, 4:00', guide)
        self.assertIn('Scan Disk', guide)
        self.assertIn('.variant-b.es.srt', guide)
        self.assertIn('sin sobrescribir', guide)

    def test_real_captures_exist_and_are_referenced(self):
        policy = json.loads((MODULE / 'docs/bazarr-profile-policy.json').read_text())
        guide = (MODULE / 'docs/bazarr.md').read_text()
        for name in policy['screenshots']:
            self.assertIn('../images/' + name, guide)
            self.assertTrue((MODULE / 'images' / name).read_bytes().startswith(b'\xff\xd8\xff'))


if __name__ == '__main__':
    unittest.main()
