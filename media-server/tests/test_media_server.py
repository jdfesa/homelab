"""Validación local de referencias; no ejecuta aprovisionamiento ni usa SSH."""
import json
from pathlib import Path
import re
import subprocess
import unittest


MODULE = Path(__file__).resolve().parents[1]
PRIVATE_PARTS = {".local", "__pycache__", "appdata", "data", "downloads", "cache", "secrets", "backups", "exports"}


def is_public(path):
    return not any(part in PRIVATE_PARTS for part in path.relative_to(MODULE).parts)


class MediaServerReferenceTests(unittest.TestCase):
    def test_configuration_and_package_lock_agree(self):
        config = json.loads((MODULE / "vm-config.json").read_text())
        lock = json.loads((MODULE / "base-packages.lock.json").read_text())
        mapping = {
            "docker_engine": "docker-ce",
            "docker_compose": "docker-compose-plugin",
            "containerd": "containerd.io",
            "docker_buildx": "docker-buildx-plugin",
        }
        for field, package in mapping.items():
            with self.subTest(package=package):
                self.assertIn(config["base"][field], lock["packages"][package])
        self.assertFalse(config["media_disk"]["attach_during_os_installation"])
        self.assertTrue(config["media_disk"]["formatting_performed"])
        self.assertEqual(config["installer"]["root_password_policy"], "locked-password")
        self.assertEqual(config["installer"]["selected_tasks"], ["ssh-server", "standard"])

    def test_media_hdd_reference_preserves_mount_and_hardlink_contract(self):
        state = json.loads((MODULE / "vm-config.json").read_text())
        disk = state["media_disk"]
        self.assertTrue(disk["attached_verified"])
        self.assertEqual(disk["bus_device"], "scsi1")
        self.assertEqual(disk["attachment_method"], "whole-physical-disk-by-id")
        self.assertTrue(disk["stable_device_path_verified"])
        self.assertIsNone(disk["stable_device_path"])
        self.assertFalse(disk["read_only"])
        self.assertFalse(disk["backup_included"])
        self.assertEqual(disk["partition_table"], "gpt")
        self.assertEqual(disk["filesystem"], "ext4")
        self.assertEqual(disk["mountpoint"], "/data")
        self.assertEqual(disk["directory_gid"], 2000)
        self.assertEqual(disk["directory_mode"], "2770")
        self.assertTrue(disk["mounted_verified"])
        self.assertTrue(disk["fstab_by_uuid"])
        self.assertIsNone(disk["filesystem_uuid"])
        self.assertTrue(disk["mount_reboot_persistence_verified"])
        self.assertTrue(disk["filesystem_hardlink_probe_verified"])
        self.assertTrue(disk["application_hardlink_import_verified"])
        self.assertTrue(state["validation"]["application_hardlink_import_verified"])
        self.assertTrue(state["applications"]["radarr"]["single_common_data_bind_verified"])
        self.assertTrue(disk["docker_mount_guard_verified"])
        self.assertTrue(disk["missing_mount_private_namespace_probe_verified"])
        self.assertFalse(disk["physical_disconnect_test_verified"])
        self.assertTrue((MODULE / disk["guide"]).is_file())

    def test_ssh_reference_keeps_nonroot_installation_boundary(self):
        base = json.loads((MODULE / "vm-config.json").read_text())["base"]
        self.assertEqual(base["ssh_key_authorization"], "installed-publickey-verified")
        self.assertTrue(base["ssh_publickey_connection_verified"])
        self.assertFalse(base["ssh_global_authentication_policy_changed"])
        self.assertNotIn("password", base)
        self.assertTrue((MODULE / base["ssh_key_installer"]).is_file())

    def test_local_document_links_exist(self):
        for document in MODULE.rglob("*.md"):
            if not is_public(document):
                continue
            for link in re.findall(r"\]\(([^)]+)\)", document.read_text()):
                if "://" in link or link.startswith("#"):
                    continue
                with self.subTest(document=document.name, link=link):
                    self.assertTrue((document.parent / link.split("#", 1)[0]).exists())

    def test_public_text_has_no_private_network_or_key_material(self):
        for path in MODULE.rglob("*"):
            if not is_public(path) or "tests" in path.relative_to(MODULE).parts:
                continue
            if path.suffix not in {".md", ".json", ".sh", ".py"}:
                continue
            text = path.read_text()
            with self.subTest(path=str(path.relative_to(MODULE))):
                self.assertNotRegex(text, r"192\.168\.8\.\d+")
                self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", text)
                self.assertNotIn("BEGIN RSA PRIVATE KEY", text)

    def test_network_template_requires_local_values(self):
        values = {}
        for line in (MODULE / ".env.example").read_text().splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value
        for key in ("NETWORK_ADDRESS", "NETWORK_GATEWAY", "NETWORK_DNS"):
            self.assertEqual(values[key], "")
        self.assertEqual(values["NETWORK_DHCP_EXCLUDED"], "no")

    def test_shell_scripts_parse(self):
        for script in (MODULE / "scripts").glob("*.sh"):
            with self.subTest(script=script.name):
                result = subprocess.run(
                    ["bash", "-n", str(script)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_network_script_refuses_implicit_apply(self):
        # La primera guarda se ejecuta antes de consultar o modificar la red.
        result = subprocess.run(
            ["bash", str(MODULE / "scripts/configure-static-ip.sh")],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--apply", result.stderr)


    def test_runbook_is_a_compact_single_entry_point(self):
        runbook = (MODULE / "RUNBOOK.md").read_text()
        self.assertLessEqual(len(runbook.split()), 750)
        self.assertLessEqual(len(runbook.splitlines()), 80)
        self.assertIn("(RUNBOOK.md)", (MODULE / "README.md").read_text())
        self.assertIn("(../RUNBOOK.md)", (MODULE / "docs/README.md").read_text())



if __name__ == "__main__":
    unittest.main()
