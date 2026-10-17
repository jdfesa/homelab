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

    def test_saved_hd_policy_has_one_equal_group_including_remux(self):
        policy = json.loads((MODULE / 'docs/radarr-profile-policy.json').read_text())
        profile = policy['profile']
        expected = {'HDTV-720p', 'WEBDL-720p', 'WEBRip-720p', 'Bluray-720p',
                    'HDTV-1080p', 'WEBDL-1080p', 'WEBRip-1080p', 'Bluray-1080p', 'Remux-1080p'}
        self.assertEqual(len(profile['quality_groups']), 1)
        group = profile['quality_groups'][0]
        self.assertEqual(group['name'], '720p + 1080p (equal)')
        self.assertEqual(set(group['qualities']), expected)
        self.assertEqual(len(group['qualities']), len(expected))
        self.assertFalse(profile['allow_unlisted_qualities'])
        self.assertFalse(profile['upgrade_allowed'])
        self.assertFalse(policy['quality_size_limits_changed'])
        state = json.loads((MODULE / 'vm-config.json').read_text())
        radarr = state['applications']['radarr']
        self.assertEqual(radarr['selected_quality_profile'], profile['name'])
        self.assertEqual(radarr['allowed_resolutions'], [720, 1080])
        self.assertEqual(radarr['resolution_priority'], 'equal')
        self.assertTrue(radarr['remux_1080p_allowed'])

    def test_language_policy_prefers_original_and_rejects_other_only(self):
        policy = json.loads((MODULE / 'docs/radarr-profile-policy.json').read_text())
        profile = policy['profile']
        self.assertEqual(profile['language'], 'Any')
        scores = profile['custom_format_scores']
        self.assertEqual(scores, {'Prefer original audio': 100, 'English fallback': 10})
        self.assertEqual(profile['minimum_custom_format_score'], 1)
        definitions = {cf['name']: cf for cf in policy['custom_formats']}
        self.assertEqual(set(definitions), set(scores))
        for name, language in [('Prefer original audio', -2), ('English fallback', 1)]:
            cf = definitions[name]
            self.assertFalse(cf['includeCustomFormatWhenRenaming'])
            self.assertEqual(len(cf['specifications']), 1)
            spec = cf['specifications'][0]
            self.assertEqual(spec['implementation'], 'LanguageSpecification')
            self.assertFalse(spec['negate'])
            self.assertFalse(spec['required'])
            self.assertEqual(spec['fields'], {'value': language, 'exceptLanguage': False})
        # Policy arithmetic only; release-language parsing and actual audio remain E2E tests.
        for original, english, expected_score, accepted in [
                (False, False, 0, False), (False, True, 10, True),
                (True, False, 100, True), (True, True, 110, True)]:
            score = int(original) * scores['Prefer original audio'] + int(english) * scores['English fallback']
            with self.subTest(original=original, english=english):
                self.assertEqual(score, expected_score)
                self.assertEqual(score >= profile['minimum_custom_format_score'], accepted)

    def test_naming_and_real_capture_references_match_policy(self):
        policy = json.loads((MODULE / 'docs/radarr-profile-policy.json').read_text())
        naming = policy['naming']
        self.assertTrue(naming['renameMovies'])
        self.assertTrue(naming['replaceIllegalCharacters'])
        self.assertEqual(naming['colonReplacementFormat'], 'smart')
        self.assertEqual(naming['standardMovieFormat'], '{Movie Title} ({Release Year}) {Quality Full}')
        self.assertEqual(naming['movieFolderFormat'], '{Movie Title} ({Release Year})')
        guide = (MODULE / 'docs/radarr.md').read_text()
        self.assertEqual(len(policy['screenshots']), 6)
        for name in policy['screenshots']:
            with self.subTest(screenshot=name):
                self.assertIn('../images/' + name, guide)
                self.assertTrue((MODULE / 'images' / name).read_bytes().startswith(b'\xff\xd8\xff'))
        radarr = json.loads((MODULE / 'vm-config.json').read_text())['applications']['radarr']
        self.assertTrue(radarr['copy_using_hardlinks'])
        self.assertTrue(radarr['rename_movies_enabled'])
        self.assertEqual(radarr['movie_policy_reference'], 'docs/radarr-profile-policy.json')


if __name__ == '__main__':
    unittest.main()
