"""Published Homepage configuration contracts; no server or private-state access."""
import json
import hashlib
from pathlib import Path
import re
import struct
import subprocess
import unittest
import zlib

MODULE = Path(__file__).resolve().parents[1]
CONFIG = MODULE / "config"


class HomepageContracts(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((CONFIG / "source-lock.json").read_text())
        self.unit = (CONFIG / "homepage.service").read_text()
        self.environment = dict(
            line.split("=", 1)
            for line in (CONFIG / "homepage.env.example").read_text().splitlines()
            if line and not line.startswith("#")
        )

    def test_source_and_toolchain_are_pinned_with_integrity(self):
        self.assertRegex(self.lock["homepage"]["version"], r"^\d+\.\d+\.\d+$")
        self.assertRegex(self.lock["homepage"]["commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(self.lock["homepage"]["pnpm_lock_sha256"], r"^[0-9a-f]{64}$")
        for name in ("node", "pnpm"):
            self.assertRegex(self.lock[name]["version"], r"^\d+\.\d+\.\d+$")
            self.assertRegex(self.lock[name]["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(self.lock[name]["url"].startswith("https://"))
            self.assertNotIn("latest", self.lock[name]["url"])
        self.assertTrue(self.lock["pnpm"]["integrity"].startswith("sha512-"))

    def test_dependencies_do_not_re_resolve_or_run_install_scripts(self):
        command = self.lock["build"]["dependency_install"]
        self.assertIn("--frozen-lockfile", command)
        self.assertIn("--ignore-scripts", command)
        self.assertEqual(self.lock["build"]["production_build"], "pnpm run build")
        self.assertEqual(self.lock["build"]["output"], ".next/standalone")

    def test_runtime_matches_the_pinned_node(self):
        version = self.lock["node"]["version"]
        self.assertIn(f"/node-v{version}-linux-x64/bin/node ", self.unit)
        self.assertIn("/opt/homepage/current/server.js", self.unit)
        self.assertNotIn("pnpm", self.unit)
        self.assertNotIn("next dev", self.unit)

    def test_service_is_nonroot_and_cannot_modify_system_configuration(self):
        for value in ("User=homepage", "Group=homepage", "NoNewPrivileges=yes",
                      "ProtectSystem=strict", "ProtectHome=yes", "PrivateTmp=yes",
                      "CapabilityBoundingSet=\n", "AmbientCapabilities=\n"):
            self.assertIn(value, self.unit)
        self.assertNotIn("User=root", self.unit)
        writes = re.findall(r"^ReadWritePaths=(.*)$", self.unit, re.MULTILINE)
        self.assertEqual(writes, ["/var/cache/homepage/runtime"])
        self.assertNotIn("MemoryDenyWriteExecute=yes", self.unit)

    def test_memory_caps_leave_room_for_the_base_system(self):
        service_limit = int(re.search(r"^MemoryMax=(\d+)M$", self.unit, re.MULTILINE).group(1))
        self.assertLess(service_limit, self.lock["build"]["runtime_lxc_memory_mib"])
        self.assertGreater(self.lock["build"]["temporary_lxc_memory_mib"],
                           self.lock["build"]["runtime_lxc_memory_mib"])

    def test_site_address_is_a_placeholder_and_host_allowlist_is_not_wildcard(self):
        self.assertEqual(self.environment["HOSTNAME"], "<homepage-ip>")
        hosts = self.environment["HOMEPAGE_ALLOWED_HOSTS"]
        self.assertIn("<homepage-ip>:3000", hosts)
        self.assertNotIn("*", hosts)
        self.assertNotRegex(hosts, r"\b\d{1,3}(?:\.\d{1,3}){3}\b")

    def test_initial_access_policy_is_explicit_without_published_passwords(self):
        self.assertEqual(self.environment["HOMEPAGE_AUTH_ENABLED"], "false")
        self.assertEqual(self.environment["PORT"], "3000")
        for key in self.environment:
            self.assertNotRegex(key, r"PASSWORD|TOKEN|SECRET|API_KEY")

    def test_config_and_logs_do_not_need_a_writable_release_tree(self):
        self.assertEqual(self.environment["HOMEPAGE_CONFIG_DIR"], "/etc/homepage")
        self.assertEqual(self.environment["LOG_TARGETS"], "stdout")
        self.assertEqual(self.environment["NEXT_TELEMETRY_DISABLED"], "1")
        self.assertIn("EnvironmentFile=/etc/homepage/homepage.env", self.unit)
        self.assertIn("CacheDirectory=homepage/runtime", self.unit)

    def test_datetime_is_english_without_changing_global_language(self):
        widget = (CONFIG / "widgets.yaml").read_text()
        for value in ("locale: en-US", "dateStyle: full", "timeStyle: short", "hourCycle: h12"):
            self.assertIn(value, widget)
        self.assertNotIn("timeZone:", widget)
        self.assertIn("language: es", (CONFIG / "settings.yaml").read_text())

    def test_manual_clock_recipe_matches_versioned_widget(self):
        guide = (MODULE / "docs/service-setup.md").read_text()
        match = re.search(r"cat > /etc/homepage/widgets\.yaml\.new <<'EOF'\n(.*?)\nEOF", guide, re.DOTALL)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1) + "\n", (CONFIG / "widgets.yaml").read_text())
        self.assertIn("cp -a --backup=numbered /etc/homepage/widgets.yaml", guide)
        self.assertIn("chown root:homepage /etc/homepage/widgets.yaml.new", guide)
        self.assertIn("chmod 0640 /etc/homepage/widgets.yaml.new", guide)

    def test_infrastructure_links_are_not_grouped_with_media(self):
        services = (CONFIG / "services.yaml.example").read_text()
        infrastructure, media = services.split("- Media:\n")
        for service in ("Proxmox", "ProxMenux Monitor", "DSM"):
            self.assertIn(f"- {service}:", infrastructure)
            self.assertNotIn(f"- {service}:", media)

    def test_nine_local_icons_match_recorded_bytes_and_png_checksums(self):
        root = MODULE / "icons"
        lock = json.loads((root / "icons-lock.json").read_text())
        self.assertEqual(len(lock["files"]), 9)
        self.assertEqual({p.name for p in root.glob("*.png")}, {item["file"] for item in lock["files"]})
        for item in lock["files"]:
            with self.subTest(file=item["file"]):
                data = (root / item["file"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
                self.assertEqual(len(data), item["bytes"])
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", data[16:24]), (item["width"], item["height"]))
                offset = 8
                last = None
                while offset < len(data):
                    size = struct.unpack(">I", data[offset:offset+4])[0]
                    kind = data[offset+4:offset+8]
                    payload = data[offset+8:offset+8+size]
                    crc = struct.unpack(">I", data[offset+8+size:offset+12+size])[0]
                    self.assertEqual(zlib.crc32(kind+payload) & 0xffffffff, crc)
                    offset += 12 + size
                    last = kind
                self.assertEqual((offset, last), (len(data), b"IEND"))

    def test_icon_mapping_and_license_are_local_with_honest_provenance(self):
        root = MODULE / "icons"
        lock = json.loads((root / "icons-lock.json").read_text())
        services = (CONFIG / "services.yaml.example").read_text()
        icons = re.findall(r"^\s*icon: (.+)$", services, re.MULTILINE)
        self.assertEqual(set(icons), {"/icons/"+item["file"] for item in lock["files"]})
        self.assertEqual(len(icons), 9)
        for item in lock["files"]:
            self.assertIn(f'- {item["service"]}:\n        icon: /icons/{item["file"]}', services)
        self.assertEqual(lock["repository"], "https://github.com/homarr-labs/dashboard-icons")
        if lock["upstream_identity_verified"]:
            self.assertRegex(lock["upstream_commit"], r"^[0-9a-f]{40}$")
        else:
            self.assertIsNone(lock["upstream_commit"])
        license = (root / lock["license"]["file"]).read_bytes()
        self.assertEqual(hashlib.sha256(license).hexdigest(), lock["license"]["sha256"])
        self.assertIn(b"Apache License", license)
        self.assertIn(b"Homarr Labs", license)
        self.assertEqual(lock["license"]["identifier"], "Apache-2.0")

    def test_first_deployment_copies_versioned_icons_not_temporary_payloads(self):
        guide = (MODULE / "docs/service-setup.md").read_text()
        self.assertIn("`homepage/icons/` PNGs, `icons-lock.json` and `LICENSE.txt`", guide)
        self.assertIn("/var/lib/homepage/staging/icons/*.png", guide)
        self.assertIn("/var/lib/homepage/staging/icons/icons-lock.json", guide)
        self.assertIn("/var/lib/homepage/staging/icons/LICENSE.txt", guide)
        self.assertIn('install -m 0644 -o root -g root "$file"', guide)
        self.assertNotIn("tmp/homepage/install-icons.sh", guide)

    def test_readme_presents_evolving_snapshot_without_a_redundant_diagram(self):
        readme = (MODULE / "README.md").read_text()
        capture = MODULE / "images/homepage-dashboard.png"
        self.assertEqual(capture.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIn("images/homepage-dashboard.png", readme)
        self.assertIn("## Current Snapshot", readme)
        self.assertIn("Real, unedited capture", readme)
        self.assertIn("point-in-time view", readme)
        self.assertIn("will be reviewed and updated", readme)
        self.assertNotIn("```mermaid", readme)

    def test_service_template_contains_only_expected_links_and_placeholders(self):
        services = (CONFIG / "services.yaml.example").read_text()
        for service in ("Proxmox", "ProxMenux Monitor", "DSM", "Jellyfin", "qBittorrent", "Prowlarr", "Radarr", "Sonarr", "Bazarr"):
            self.assertIn(f"- {service}:", services)
        hrefs = re.findall(r"href: (.+)", services)
        self.assertEqual(len(hrefs), 9)
        self.assertTrue(all(re.fullmatch(r"<[a-z-]+-url>", value) for value in hrefs))
        self.assertNotIn("widget:", services)
        self.assertNotRegex(services, r"(?i)api[_-]?key|token:|password:")

    def test_canonical_guides_are_separate_and_linked(self):
        creation = MODULE / "docs/installation-guide.md"
        service = MODULE / "docs/service-setup.md"
        self.assertTrue(creation.is_file())
        self.assertTrue(service.is_file())
        index = (MODULE / "docs/README.md").read_text()
        self.assertIn("installation-guide.md", index)
        self.assertIn("service-setup.md", index)

    def test_recipe_matches_source_and_toolchain_pins(self):
        guide = (MODULE / "docs/service-setup.md").read_text()
        self.assertIn(self.lock["homepage"]["commit"], guide)
        for name in ("node", "pnpm"):
            self.assertIn(self.lock[name]["url"], guide)
        self.assertIn(self.lock["build"]["dependency_install"].removeprefix("pnpm "), guide)
        self.assertIn("trap restore EXIT", guide)
        self.assertIn("pct set 103 --memory 1024", guide)

    def test_recipe_shell_blocks_parse_without_execution(self):
        guide = (MODULE / "docs/service-setup.md").read_text()
        blocks = re.findall(r"```(?:sh|bash)\n(.*?)```", guide, re.DOTALL)
        self.assertGreater(len(blocks), 4)
        for number, block in enumerate(blocks, 1):
            with self.subTest(block=number):
                result = subprocess.run(["bash", "-n"], input=block, text=True,
                                        capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("tmp/homepage/", block)

    def test_new_public_text_does_not_include_site_rfc1918_addresses(self):
        for folder in ("config", "docs"):
            for path in (MODULE / folder).iterdir():
                if path.is_file():
                    with self.subTest(path=path.name):
                        self.assertNotRegex(path.read_text(),
                                            r"\b(?:192\.168\.|10\.\d+\.|172\.(?:1[6-9]|2\d|3[01])\.)\d+\.\d+\b")


if __name__ == "__main__":
    unittest.main()
