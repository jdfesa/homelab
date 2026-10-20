"""Pure downloader contract checks; no Docker, SSH, HTTP or disk provisioning."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import struct
import sys
import unittest
from unittest.mock import patch

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

    def test_seed_stops_after_one_hour_without_native_removal(self):
        seed = DEPLOY.initial_configuration('10.0.0.10')
        for setting in (r'Session\GlobalMaxRatio=-1',
                        r'Session\GlobalMaxSeedingMinutes=60',
                        r'Session\GlobalMaxInactiveSeedingMinutes=-1',
                        r'Session\ShareLimitAction=Stop'):
            self.assertIn(setting, seed)
        self.assertNotIn('ShareLimitAction=Remove', seed)

    def verify_with_preferences(self, changes=None):
        """Exercise the actual login/preferences gate without HTTP or real secrets."""
        prefs = {
            'upnp': False, 'web_ui_upnp': False, 'bypass_local_auth': False,
            'bypass_auth_subnet_whitelist_enabled': False,
            'web_ui_csrf_protection_enabled': True,
            'web_ui_host_header_validation_enabled': True,
            'web_ui_clickjacking_protection_enabled': True,
            'temp_path_enabled': True, 'save_path': '/data/downloads/',
            'temp_path': '/data/downloads/incomplete/',
            'max_ratio_enabled': False, 'max_ratio': -1,
            'max_seeding_time_enabled': True, 'max_seeding_time': 60,
            'max_inactive_seeding_time_enabled': False, 'max_inactive_seeding_time': -1,
            'max_ratio_act': 0,
        }
        prefs.update(changes or {})

        class Response:
            def __init__(self, data, status=200):
                self.status, self.data = status, data

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                return self.data

        class Opener:
            authenticated = False

            def open(self, request, timeout):
                path = request.full_url.split('/api/v2/', 1)[1]
                if path == 'app/preferences':
                    if not self.authenticated:
                        error = DEPLOY.urllib.error.HTTPError(request.full_url, 403, 'Forbidden', {}, io.BytesIO())
                        error.close()
                        raise error
                    return Response(json.dumps(prefs).encode())
                if path == 'auth/login':
                    self.authenticated = True
                    return Response(b'', 204)
                if path == 'app/version':
                    return Response(b'v5.2.4')
                if path == 'torrents/info':
                    return Response(b'[]')
                if path == 'torrents/categories':
                    return Response(json.dumps({
                        name: {'savePath': '/data/downloads/' + name}
                        for name in ('movies', 'tv')}).encode())
                if path in ('torrents/createCategory', 'auth/logout'):
                    return Response(b'')
                raise AssertionError('Unexpected fixture request')

        with patch.object(DEPLOY.urllib.request, 'build_opener', return_value=Opener()):
            return DEPLOY.verify_api('10.0.0.10', 'synthetic-test-only')

    def test_api_verifies_native_stop_independent_of_library(self):
        result = self.verify_with_preferences()
        verified = result['settings_verified']
        self.assertEqual(verified['max_seeding_time'], 60)
        self.assertTrue(verified['max_seeding_time_enabled'])
        self.assertEqual(verified['max_ratio_act'], 0)

    def test_api_rejects_missing_hour_earlier_triggers_or_native_removal(self):
        for change in (
                {'max_seeding_time_enabled': False}, {'max_seeding_time': 0},
                {'max_seeding_time': -1}, {'max_ratio_enabled': True}, {'max_ratio': 1},
                {'max_inactive_seeding_time_enabled': True}, {'max_inactive_seeding_time': 30},
                {'max_ratio_act': 1}, {'max_ratio_act': 2}, {'max_ratio_act': 3}):
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, 'seeding policy'):
                self.verify_with_preferences(change)

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

    def test_verified_capabilities_do_not_claim_complete_automation(self):
        state = json.loads((MODULE / 'vm-config.json').read_text())
        app = state['applications']['jellyfin']
        self.assertTrue(app['remote_access_enabled'])
        self.assertFalse(app['wan_publication_configured'])
        self.assertEqual(app['libraries_confirmed_in_ui'], {'Shows': '/media/tv', 'Movies': '/media/movies'})
        verified = state['validation']
        for capability in ('movie_search_download_import_verified', 'application_hardlink_import_verified',
                           'lan_tablet_playback_verified', 'embedded_subtitle_selection_verified'):
            self.assertTrue(verified[capability])
        for capability in ('series_pipeline_verified', 'backup_restore_verified'):
            self.assertFalse(verified[capability])
        self.assertTrue((MODULE / verified['guide']).is_file())

    def test_public_reference_is_configuration_not_download_inventory(self):
        state = json.loads((MODULE / 'vm-config.json').read_text())
        self.assertEqual(state['schema_version'], 2)
        forbidden = {'infohash', 'title', 'seeders', 'downloaded_bytes', 'queue_total_records',
                     'request_examples', 'series_acquisition', 'sintel_test', 'first_movie_test'}
        def check_keys(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values():
                    check_keys(child)
            elif isinstance(value, list):
                for child in value:
                    check_keys(child)
        check_keys(state)
        self.assertIn('tmp/', (MODULE.parent / '.gitignore').read_text().splitlines())
        graph = (MODULE / 'README.md').read_text().split('```mermaid\n', 1)[1].split('```', 1)[0]
        for line in graph.splitlines():
            self.assertNotRegex(line, r'\["[0-9]+\. ')
        for term in ('Radarr', 'Prowlarr', 'qBittorrent', 'hardlink', 'Series: Sonarr', 'Nueva adquisición por validar', 'monitor de episodios probado'):
            self.assertIn(term, graph)
        for term in ('Torrent manual: categoría y ruta', 'manual --> download',
                     'Registro de colección SMB pendiente', 'existing -.->',
                     'Sólo faltantes: eventos y cada 6 h'):
            self.assertIn(term, graph)


class ManualTorrentWorkflow(unittest.TestCase):
    def test_manual_torrent_guide_distinguishes_downloads_from_library(self):
        guide = (MODULE / 'docs/workflow.md').read_text()
        self.assertIn('## Add a Torrent Manually', guide)
        self.assertIn('| Series | `tv` | `/data/downloads/tv` | Sonarr: `/data/media/tv` |', guide)
        self.assertIn('| Películas | `movies` | `/data/downloads/movies` | Radarr: `/data/media/movies` |', guide)
        self.assertIn('Category no registra el título', guide)
        self.assertIn('auto_tmm: false', guide)
        self.assertIn('sonarr.md#adopt-existing-downloads', guide)
        self.assertIn('##' + '# Worked Example: Manual Season', guide)
        self.assertIn('../images/jellyfin-manual-season-imported.jpg', guide)
        self.assertTrue((MODULE / 'images/jellyfin-manual-season-imported.jpg').read_bytes().startswith(b'\xff\xd8\xff'))

    def test_manual_add_screenshot_is_full_form_not_final_configuration(self):
        guide = (MODULE / 'docs/workflow.md').read_text()
        image_name = 'qbittorrent-manual-add-form.png'
        self.assertIn('../images/' + image_name, guide)
        self.assertIn(image_name, (MODULE / 'images/README.md').read_text())
        image = (MODULE / 'images' / image_name).read_bytes()
        self.assertTrue(image.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(image[12:16], b'IHDR')
        self.assertEqual(struct.unpack('>II', image[16:24]), (1303, 992))
        for distinction in ('antes de Download', 'Category vacía',
                            'no la configuración final comprobada',
                            'cambiar sólo la ruta de descarga no completa ese paso',
                            'El paso extra fue registrar la serie y dejar que Sonarr la importara'):
            self.assertIn(distinction, guide)


if __name__ == '__main__':
    unittest.main()
