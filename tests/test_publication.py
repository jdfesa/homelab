"""Local publication guards use disposable fixtures; no user repo writes or network."""
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publication", ROOT / "scripts/check-publication.py")
PUBLICATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUBLICATION)


class PublicationTests(unittest.TestCase):
    def test_real_git_rules_protect_nested_modules_and_preserve_templates(self):
        ignored = [".local/site.env", "future-vm/.local/note.json", "future-vm/private/note.json",
                   "future-vm/backups/backup.zip", "future-vm/exports/config.json", "future-vm/secrets/key.txt",
                   "future-vm/service.env", "future-vm/state.db", "future-vm/state.sqlite3-wal", "future-vm/.env.production", "future-vm/terraform.tfstate",
                   "future-vm/id_ed25519", "future-vm/client.ovpn", "nested/.DS_Store",
                   "media-server/appdata/test.db", "media-server/state.db-wal", "media-server/movie.torrent",
                   "media-server/state.fastresume"]
        ignored.extend(["tmp/media-server/credentials/opensubtitles.json",
                        "media-server/.local/sonarr-config.xml",
                        "media-server/config.xml", "media-server/config.yaml",
                        "media-server/smb.conf", "media-server/passdb.tdb",
                        "media-server/secrets.ldb", "media-server/passdb.tdb-wal"])
        visible = ["README.md", "dsm/README.md", "media-server/.env.example",
                   "future-vm/service.env.example", "media-server/compose/radarr/.env.example",
                   "media-server/compose/radarr/compose.yaml", "media-server/compose/radarr/image-lock.json",
                   "resources/ebook-proxmox.pdf", "media-server/docs/qbittorrent.md"]
        visible.append("media-server/config/samba/smb.conf.example")
        with PUBLICATION.portable_view(ROOT) as view:
            self.assertEqual(PUBLICATION.ignored_paths(ROOT, view, ignored + visible), set(ignored))

    def test_per_service_access_files_are_ignored_before_creation(self):
        services = ('jellyfin', 'qbittorrent', 'prowlarr', 'radarr', 'bazarr', 'sonarr')
        ignored = []
        templates = []
        for service in services:
            ignored.extend([
                f'media-server/.local/access/{service}.env',
                f'media-server/.local/access/{service}.env.example',
                f'media-server/compose/{service}/.env',
                f'media-server/compose/{service}/credentials.env',
            ])
            templates.append(f'media-server/compose/{service}/.env.example')
        with PUBLICATION.portable_view(ROOT) as view:
            self.assertEqual(PUBLICATION.ignored_paths(ROOT, view, ignored + templates), set(ignored))

    def test_literal_config_detection_withholds_secret_and_accepts_placeholders(self):
        value = "synthetic-not-a-real-credential"
        findings = PUBLICATION.scan_text("client.json", json.dumps({"password": value}, indent=2))
        self.assertEqual(findings[0]["kind"], "literal-config-credential")
        self.assertNotIn(value, json.dumps(findings))
        self.assertFalse(PUBLICATION.scan_text("example.json", '{"password": "<YOUR_PASSWORD>"}'))

    def test_lab_exception_requires_flag_exact_file_and_section(self):
        source = "## Laboratory Login Example\n\n| Password | `synthetic-demo-only` |\n"
        self.assertTrue(PUBLICATION.scan_text(PUBLICATION.LAB_GUIDE, source))
        self.assertFalse(PUBLICATION.scan_text(PUBLICATION.LAB_GUIDE, source, True))
        self.assertTrue(PUBLICATION.scan_text("other.md", source, True))
        self.assertTrue(PUBLICATION.scan_text(PUBLICATION.LAB_GUIDE, source.replace("Laboratory", "Other"), True))
        self.assertTrue(PUBLICATION.scan_text(PUBLICATION.LAB_GUIDE, source + "| API Key | `synthetic-api-secret` |\n", True))

    def test_common_tokens_and_private_key_headers_are_detected_without_echo(self):
        samples = ["ghp_" + "A" * 32, "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
                   "AKIA" + "A" * 16, "xoxb-" + "A" * 30]
        for sample in samples:
            with self.subTest(prefix=sample[:4]):
                results = PUBLICATION.scan_text("note.md", sample)
                self.assertTrue(results)
                self.assertNotIn(sample, json.dumps(results))

    def test_current_preflight_requires_deliberate_public_exception(self):
        result = PUBLICATION.audit(ROOT, True)
        self.assertFalse(result["findings"], result["findings"])
        self.assertTrue(result["public_lab_password_acknowledged"])
        self.assertFalse(PUBLICATION.audit(ROOT)["public_lab_password_acknowledged"])

    def test_dry_run_does_not_initialize_project_or_depend_on_global_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Synthetic fixture\n")
            excludes = root / "local-excludes"
            excludes.write_text("README.md\n")
            with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(excludes)}):
                result = PUBLICATION.audit(root)
            self.assertFalse((root / ".git").exists())
            self.assertEqual(result["candidates"], 2)

    def test_staged_secret_is_detected_even_if_working_file_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            PUBLICATION.git(["init", "--quiet", "--template=", str(root)], root)
            config = root / "client.json"
            config.write_text('{"password": "synthetic-staged-credential"}')
            PUBLICATION.git(["add", "client.json"], root)
            config.write_text('{"password": "<YOUR_PASSWORD>"}')
            result = PUBLICATION.audit(root)
            self.assertIn("index:literal-config-credential", [f["kind"] for f in result["findings"]])

    def test_tracked_ignored_file_cannot_be_hidden_by_new_ignore_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            PUBLICATION.git(["init", "--quiet", "--template=", str(root)], root)
            (root / ".gitignore").write_text(".local/\n")
            (root / ".local").mkdir()
            (root / ".local/note.txt").write_text("synthetic fixture")
            PUBLICATION.git(["add", "-f", ".local/note.txt"], root)
            findings = PUBLICATION.audit(root)["findings"]
            self.assertIn("already-tracked-despite-ignore", [f["kind"] for f in findings])

    def test_binary_and_symlink_need_manual_review_not_secret_free_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image.png").write_bytes(b"\x89PNG\0fixture")
            (root / "pointer").symlink_to("missing-private-target")
            result = PUBLICATION.audit(root)
            self.assertEqual(result["binary_files"], ["image.png"])
            self.assertEqual(result["findings"][0]["kind"], "symlink-needs-review")

    def test_root_map_has_one_host_two_workloads_and_no_experimental_guest(self):
        readme = (ROOT / "README.md").read_text()
        diagram = readme.split("```mermaid\n", 1)[1].split("```", 1)[0]
        for label in ["Proxmox VE - one physical host", "VM 100 - DSM", "VM 102 - media-server",
                      "Docker Compose", "Jellyfin", "qBittorrent", "Prowlarr", "Radarr", "Sonarr", "Bazarr",
                      "Native services", "Samba and scheduled maintenance"]:
            self.assertIn(label, diagram)
        self.assertNotIn('Sonarr - planned, not deployed', diagram)
        for excluded in ["WinXP", "Windows XP", "VM 101", "hardlink", "Full Sync", "/data/", "torrent-cleanup.py"]:
            self.assertNotIn(excluded, diagram)
        self.assertNotRegex(diagram, r':\d{2,5}')
        self.assertLessEqual(len(re.findall(r'^\s*[A-Za-z]\w*\[', diagram, re.MULTILINE)), 8)
        self.assertLessEqual(diagram.count(' --> '), 6)
        self.assertIn('media-server/README.md#workflow', readme)
        self.assertTrue((ROOT / "dsm/README.md").is_file())


if __name__ == "__main__":
    unittest.main()
