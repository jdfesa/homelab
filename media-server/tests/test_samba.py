"""Portable SMB configuration contracts; no network, credentials or runtime writes."""
import configparser
import json
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1]
CONFIG = MODULE / 'config/samba/smb.conf.example'


class SambaContract(unittest.TestCase):
    def setUp(self):
        # Samba module keys contain ':', e.g. fruit:resource; only '=' is a delimiter.
        self.config = configparser.ConfigParser(interpolation=None, delimiters=('=',))
        self.config.read(CONFIG)

    def test_only_english_named_library_shares(self):
        self.assertEqual(self.config.sections(), ['global', 'Movies', 'TV'])
        self.assertEqual(self.config['Movies']['path'], '/data/media/movies')
        self.assertEqual(self.config['TV']['path'], '/data/media/tv')
        self.assertNotIn('/data/downloads', CONFIG.read_text())

    def test_authenticated_smb3_only(self):
        g = self.config['global']
        for key, value in {'security': 'user', 'map to guest': 'Never',
                           'server min protocol': 'SMB3_00', 'server signing': 'mandatory',
                           'smb encrypt': 'required', 'restrict anonymous': '2',
                           'invalid users': 'root', 'unix password sync': 'no'}.items():
            self.assertEqual(g[key], value)
        for name in ['Movies', 'TV']:
            self.assertEqual(self.config[name]['valid users'], '<SMB_USER>')
            self.assertEqual(self.config[name]['guest ok'], 'no')

    def test_explicit_lan_placeholders_no_site_values(self):
        g = self.config['global']
        self.assertEqual(g['interfaces'], '127.0.0.1/8 <LAN_ADDRESS_CIDR>')
        self.assertEqual(g['bind interfaces only'], 'yes')
        self.assertEqual(g['hosts allow'], '127.0.0.1 <LAN_NETWORK_CIDR>')
        self.assertEqual(g['hosts deny'], 'ALL')
        self.assertNotIn('0.0.0.0', CONFIG.read_text())
        self.assertNotRegex(CONFIG.read_text(), r'192\.168\.\d+\.\d+')

    def test_no_legacy_discovery_printers_or_usershares(self):
        g = self.config['global']
        for key, value in {'smb ports': '445', 'disable netbios': 'yes',
                           'load printers': 'no', 'disable spoolss': 'yes',
                           'usershare max shares': '0', 'usershare allow guests': 'no',
                           'server multi channel support': 'no'}.items():
            self.assertEqual(g[key], value)

    def test_group_scope_and_new_file_permissions(self):
        for name in ['Movies', 'TV']:
            s = self.config[name]
            self.assertEqual(s['force group'], 'media')
            self.assertNotIn('force user', s)
            for key in ['create mask', 'force create mode']:
                self.assertEqual(s[key], '0660')
            for key in ['directory mask', 'force directory mode']:
                self.assertEqual(s[key], '2770')
            self.assertEqual(s['read only'], 'no')

    def test_symlink_escape_disabled(self):
        for name in ['Movies', 'TV']:
            self.assertEqual(self.config[name]['wide links'], 'no')
            self.assertEqual(self.config[name]['follow symlinks'], 'no')

    def test_apple_compatibility_does_not_store_resource_forks_in_small_xattrs(self):
        for name in ['Movies', 'TV']:
            s = self.config[name]
            self.assertEqual(s['vfs objects'], 'fruit streams_xattr')
            self.assertEqual(s['fruit:metadata'], 'stream')
            self.assertEqual(s['fruit:resource'], 'file')
            self.assertEqual(s['fruit:time machine'], 'no')

    def test_guarded_mount_is_service_prerequisite(self):
        text = (MODULE / 'config/samba/media-storage.conf').read_text()
        for required in ['Requires=data.mount', 'BindsTo=data.mount',
                         'After=data.mount network-online.target',
                         'ExecStartPre=/usr/local/sbin/check-media-storage']:
            self.assertIn(required, text)

    def test_reference_tracks_server_finder_and_copied_media_playback_separately(self):
        smb = json.loads((MODULE / 'vm-config.json').read_text())['file_sharing']['samba']
        self.assertEqual(smb['shares'], {'Movies': '/data/media/movies', 'TV': '/data/media/tv'})
        self.assertTrue(smb['authenticated_roundtrip_verified'])
        self.assertTrue(smb['finder_connection_verified'])
        self.assertTrue(smb['finder_transfer_verified'])
        self.assertTrue(smb['jellyfin_copied_media_playback_verified'])
        self.assertEqual(smb['tcp_port'], 445)
        self.assertFalse(smb['unix_user_group_membership_changed'])
        self.assertTrue((MODULE / smb['guide']).is_file())

    def test_password_setup_precedes_enable_and_documents_distinct_prompts(self):
        guide = (MODULE / 'docs/samba.md').read_text()
        password = guide.index("sudo smbpasswd '<SMB_USER>'")
        enable = guide.index("sudo smbpasswd -e '<SMB_USER>'")
        self.assertLess(password, enable)
        for text in ['sólo habilita', 'New SMB password', 'Retype new SMB password',
                     '[sudo] password', 'Contraseña del usuario **Debian**']:
            self.assertIn(text, guide)

    def test_documentation_identifies_native_service_and_python_role(self):
        guide = (MODULE / 'docs/samba.md').read_text()
        for text in ['## Execution Model and Python', 'Python no sirve los archivos',
                     'qm guest exec', 'No son necesarios para reproducir',
                     '../scripts/check-media-storage.py', '<REVIEWED_SMB_CONF>',
                     '<MODULE_DIR>/config/samba/media-storage.conf']:
            self.assertIn(text, guide)


if __name__ == '__main__':
    unittest.main()
