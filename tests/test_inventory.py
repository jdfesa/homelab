"""Tests de reducción de datos; no se conecta a ningún servidor."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import subprocess

source = Path(__file__).resolve().parents[1] / "scripts/inventory_host.py"
spec = importlib.util.spec_from_file_location("inventory_host", source)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class InventoryPrivacyTests(unittest.TestCase):
    def test_guest_disk_and_mac_redacted(self):
        raw = """name: test-vm
memory: 4096
sata1: /dev/disk/by-id/ata-MODEL-PRIVATE_SERIAL,size=2T
net0: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0,firewall=1
ide2: local:iso/private-installer.iso,media=cdrom
args: -secret password=SECRET
description: private notes
"""
        result = inventory.guest_config(raw)
        serialized = json.dumps(result)
        for secret in ["PRIVATE_SERIAL", "AA:BB:CC:DD:EE:FF", "SECRET", "private notes", "private-installer"]:
            self.assertNotIn(secret, serialized)
        self.assertTrue(result["disks"]["sata1"]["physical_device"])
        self.assertEqual(result["network"]["net0"], {"model": "virtio", "bridge": "vmbr0", "firewall": "1"})

    def test_dimm_serial_redacted(self):
        result = inventory.dimms("Memory Device\n\tSize: 8 GB\n\tSerial Number: SECRET\n\tPart Number: DIMM-MODEL\n")
        self.assertEqual(result, [{"Size": "8 GB", "Part Number": "DIMM-MODEL"}])

    def test_lvm_log_and_uuid_redacted(self):
        raw = {"report": [{"lv": [{"vg_name": "pve", "lv_name": "data", "lv_size": "100",
                                   "lv_uuid": "PRIVATE_UUID"}]}],
               "log": [{"log_object_id": "PRIVATE_UUID", "log_message": "SECRET"}]}
        self.assertEqual(inventory.lvm_summary(raw), [{"vg_name": "pve", "lv_name": "data", "lv_size": "100"}])
        self.assertNotIn("PRIVATE_UUID", json.dumps(inventory.lvm_summary(raw)))

    def test_smart_allowlist_even_with_nonzero_health_exit(self):
        raw = {"serial_number": "SECRET", "model_name": "Disk", "smart_status": {"passed": False},
               "messages": [{"string": "serial SECRET"}],
               "ata_smart_attributes": {"table": [{"id": 5, "name": "Reallocated_Sector_Ct", "raw": {"value": 3}}]},
               "nvme_smart_health_information_log": {"media_errors": 2, "vendor_private": "SECRET"}}
        completed = subprocess.CompletedProcess([], 8, stdout=json.dumps(raw), stderr="SECRET")
        with patch.object(inventory, "run", return_value=completed):
            result = inventory.smart_summary("/dev/sda", [])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertFalse(result["health_passed"])
        self.assertEqual(result["exit_status"], 8)
        self.assertEqual(result["nvme"], {"media_errors": 2})

    def test_command_failure_does_not_export_stderr(self):
        completed = subprocess.CompletedProcess([], 1, stdout="", stderr="password=SECRET")
        errors = []
        with patch.object(inventory.subprocess, "run", return_value=completed):
            self.assertIsNone(inventory.text(["tool"], errors))
        self.assertEqual(errors, [{"tool": "tool", "returncode": 1}])


if __name__ == "__main__":
    unittest.main()
