"""Local Jellyfin deployment contract; no Docker, network or runtime writes."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1]
SCRIPT = MODULE / "scripts/deploy-jellyfin.py"
SPEC = importlib.util.spec_from_file_location("deploy_jellyfin", SCRIPT)
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class JellyfinContract(unittest.TestCase):
    def setUp(self):
        self.config = {"services": {"jellyfin": {
            "image": "jellyfin/jellyfin:12.2@sha256:" + "a" * 64,
            "user": "1000:2000",
            "ports": [{"target": 8096, "published": "8096", "protocol": "tcp", "host_ip": "10.0.0.10"}],
            "volumes": [{"type": "bind", "target": "/config", "source": str(DEPLOY.APPDATA / "config")},
                        {"type": "bind", "target": "/cache", "source": str(DEPLOY.APPDATA / "cache")},
                        {"type": "bind", "target": "/media", "source": "/data/media", "read_only": True}],
        }}}

    def test_accepts_official_digest_nonroot_readonly_media_and_assigned_lan(self):
        service, address = DEPLOY.validate_configuration(self.config, {"10.0.0.10"})
        self.assertEqual(address, "10.0.0.10")
        self.assertEqual(service["user"], "1000:2000")

    def test_refuses_mutable_images_root_and_extra_services(self):
        for change in ({"image": "jellyfin/jellyfin:latest"}, {"user": "0:0"},
                       {"privileged": True}, {"devices": ["/dev/dri"]}):
            config = copy.deepcopy(self.config)
            config["services"]["jellyfin"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(config, {"10.0.0.10"})
        self.config["services"]["other"] = {}
        with self.assertRaises(ValueError):
            DEPLOY.validate_configuration(self.config, {"10.0.0.10"})

    def test_refuses_all_interface_public_or_unassigned_bindings(self):
        for address in ("0.0.0.0", "8.8.8.8", "127.0.0.1", "10.0.0.11"):
            config = copy.deepcopy(self.config)
            config["services"]["jellyfin"]["ports"][0]["host_ip"] = address
            with self.subTest(address=address), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(config, {"10.0.0.10"})

    def test_refuses_media_writes_extra_mounts_and_wrong_appdata(self):
        for index, change in ((2, {"read_only": False}), (0, {"source": "/data/appdata"}),
                              (2, {"source": "/"})):
            config = copy.deepcopy(self.config)
            config["services"]["jellyfin"]["volumes"][index].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                DEPLOY.validate_configuration(config, {"10.0.0.10"})

    def test_refuses_without_apply_before_environment_or_docker_access(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--compose-file", "not-present", "--env-file", "not-present"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No changes without explicit --apply", result.stderr)


if __name__ == "__main__":
    unittest.main()
