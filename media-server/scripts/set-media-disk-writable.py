#!/usr/bin/env python3
"""Enable writes to an already attached HDD; runs ONLY on Proxmox, never formats."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import time


def run(*args, allowed=(0,), timeout=120):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode not in allowed:
        raise RuntimeError(f"{args[0]} exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def config(node, vmid):
    return json.loads(run("pvesh", "get", f"/nodes/{node}/qemu/{vmid}/config", "--output-format", "json"))


def process(vmid):
    pid = Path(f"/run/qemu-server/{vmid}.pid").read_text().strip()
    start = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    return {"pid": pid, "start_ticks": start, "status": run("qm", "status", str(vmid)).strip()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--node", required=True)
    parser.add_argument("--vmid", type=int, required=True)
    parser.add_argument("--protected-vmid", type=int, required=True)
    parser.add_argument("--disk-by-id", required=True)
    parser.add_argument("--expected-host-serial", required=True)
    parser.add_argument("--expected-model", required=True)
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--guest-serial", default="media-hdd-2tb")
    args = parser.parse_args()
    if not args.apply:
        parser.error("No changes without explicit --apply")
    os.umask(0o077)
    if os.geteuid() != 0 or not Path("/etc/pve/qemu-server").is_dir() or args.vmid == args.protected_vmid:
        raise RuntimeError("Expected root on Proxmox and distinct target/protected VMs")
    by_id = Path(args.disk_by_id)
    if by_id.parent != Path("/dev/disk/by-id") or not by_id.is_symlink() or "-part" in by_id.name:
        raise RuntimeError("Use an existing whole-disk by-id symlink")
    device = by_id.resolve(strict=True)
    before = config(args.node, args.vmid)
    protected_path = Path(f"/etc/pve/qemu-server/{args.protected_vmid}.conf")
    protected_bytes = protected_path.read_bytes()
    protected_process = process(args.protected_vmid)
    if before.get("name") != "media-server" or before.get("scsihw") != "virtio-scsi-single" or "lock" in before:
        raise RuntimeError("Unexpected target VM/controller or lock")
    if run("qm", "status", str(args.vmid)).strip() != "status: running" or protected_process["status"] != "status: running":
        raise RuntimeError("Both VMs must already be running")
    fields = before.get("scsi1", "").split(",")
    if not fields or Path(fields[0]).resolve() != device or "ro=1" not in fields or "serial=" + args.guest_serial not in fields:
        raise RuntimeError("scsi1 is not the expected read-only disk/serial")
    if any(not line.startswith("cur ") for line in run("qm", "pending", str(args.vmid)).splitlines() if line):
        raise RuntimeError("Unrelated pending changes")
    disk = json.loads(run("lsblk", "--json", "--bytes", "-o", "NAME,PATH,TYPE,SIZE,MODEL,SERIAL,MOUNTPOINTS", str(by_id)))["blockdevices"][0]
    if (disk["type"], disk["model"].strip(), disk["serial"], disk["size"]) != ("disk", args.expected_model, args.expected_host_serial, args.expected_bytes):
        raise RuntimeError("Physical disk identity mismatch")
    for item in [disk] + disk.get("children", []):
        if item["type"] not in ("disk", "part") or any(item.get("mountpoints") or []) or list(Path("/sys/class/block", item["name"], "holders").iterdir()):
            raise RuntimeError("Physical disk is mounted or has holders")
    for scope in ("qemu-server", "lxc"):
        for path in Path("/etc/pve/nodes").glob(f"*/{scope}/*.conf"):
            for line in path.read_text().splitlines():
                if ":" not in line or line.startswith("#"):
                    continue
                key, value = line.split(":", 1)
                volume = value.strip().split(",", 1)[0].removeprefix("file=")
                if volume.startswith("/dev/") and Path(volume).resolve() == device:
                    if scope != "qemu-server" or path.stem != str(args.vmid) or key != "scsi1":
                        raise RuntimeError("Physical disk referenced by another device/guest")
    smart = json.loads(run("smartctl", "--all", "--json", str(by_id)))
    attributes = {str(a["id"]): a["raw"]["value"] for a in smart["ata_smart_attributes"]["table"]}
    if not smart["smart_status"]["passed"] or smart["serial_number"] != args.expected_host_serial or any(attributes.get(k) != 0 for k in ("5", "197", "198", "199")):
        raise RuntimeError("SMART needs review")
    guest_query = "import json,subprocess; print(subprocess.check_output(['lsblk','--json','--bytes','-o','NAME,TYPE,SIZE,SERIAL,FSTYPE,MOUNTPOINTS,RO'],text=True))"

    def guest_disk():
        result = json.loads(run("qm", "guest", "exec", str(args.vmid), "--timeout", "5", "--", "/usr/bin/python3", "-c", guest_query, timeout=15))
        if result.get("exitcode") != 0 or not result.get("exited"):
            raise RuntimeError("Guest Agent not ready")
        disks = json.loads(result["out-data"])["blockdevices"]
        matches = [d for d in disks if d.get("serial") == args.guest_serial]
        if len(matches) != 1 or matches[0]["size"] != args.expected_bytes:
            raise RuntimeError("Guest disk identity mismatch")
        return matches[0]

    initial_guest = guest_disk()
    if not initial_guest["ro"] or any(any(d.get("mountpoints") or []) for d in [initial_guest] + initial_guest.get("children", [])):
        raise RuntimeError("Expected unmounted read-only guest disk")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path("/root/media-server-provisioning", "enable-write-" + stamp)
    backup.mkdir(parents=True, mode=0o700)
    (backup / "102.conf.before").write_bytes(Path(f"/etc/pve/qemu-server/{args.vmid}.conf").read_bytes())
    (backup / "protected.conf.before").write_bytes(protected_bytes)
    report = {"backup_directory": str(backup), "config_before": before, "protected_process_before": protected_process,
              "host_disk": disk, "guest_disk_before": initial_guest, "complete": False, "formatting_performed": False}
    result_path = backup / "result.json"

    def record():
        result_path.write_text(json.dumps(report, indent=2) + "\n")
    record()
    try:
        run("qm", "shutdown", str(args.vmid), "--timeout", "90", "--forceStop", "0", timeout=105)
        if run("qm", "status", str(args.vmid)).strip() != "status: stopped":
            raise RuntimeError("Controlled shutdown did not complete; never force stop automatically")
        current = config(args.node, args.vmid)
        if {k:v for k,v in current.items() if k != "digest"} != {k:v for k,v in before.items() if k != "digest"}:
            raise RuntimeError("Config changed during shutdown")
        probe = subprocess.run(["fuser", str(by_id)] + [d["path"] for d in disk.get("children", [])], capture_output=True)
        if probe.returncode != 1:
            raise RuntimeError("Disk still has open users after target shutdown")
        updated = ",".join("ro=0" if field == "ro=1" else field for field in fields)
        run("qm", "set", str(args.vmid), "--digest", current["digest"], "--scsi1", updated)
        report["write_enabled"] = True
        record()
        run("qm", "start", str(args.vmid))
        for _ in range(40):
            try:
                after_guest = guest_disk()
                break
            except (RuntimeError, KeyError, json.JSONDecodeError):
                time.sleep(3)
        else:
            raise RuntimeError("Guest Agent did not return; review VM before continuing")
        if after_guest["ro"]:
            raise RuntimeError("Guest still sees read-only disk")
        after = config(args.node, args.vmid)
        for key, value in before.items():
            if key not in ("digest", "scsi1") and after.get(key) != value:
                raise RuntimeError(f"Unexpected config change: {key}")
        if protected_path.read_bytes() != protected_bytes or process(args.protected_vmid) != protected_process:
            raise RuntimeError("Protected VM changed")
        report.update({"complete": True, "controlled_restart": True, "config_after": after,
                       "guest_disk_after": after_guest, "protected_config_and_process_unchanged": True})
        record()
        print(json.dumps(report, indent=2))
    except Exception as error:
        report["error"] = str(error)
        record()
        print(json.dumps(report, indent=2))
        raise


if __name__ == "__main__":
    main()
