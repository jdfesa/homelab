#!/usr/bin/env python3
"""Destructive, explicit-once GPT/ext4 provisioning INSIDE the Debian guest."""
import argparse
import datetime
import grp
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import sys
import time

STATE = Path("/var/lib/media-server/provisioning/storage.json")
MOUNT = Path("/data")
DROPIN = Path("/etc/systemd/system/docker.service.d/media-storage.conf")
GUARD = Path("/usr/local/sbin/check-media-storage")
DIRECTORIES = ("downloads", "downloads/movies", "downloads/tv", "media", "media/movies", "media/tv")


def run(*args, input=None, allowed=(0,), timeout=180):
    result = subprocess.run(args, input=input, capture_output=True, text=True, timeout=timeout)
    if result.returncode not in allowed:
        raise RuntimeError(f"{args[0]} exited {result.returncode}: {result.stderr.strip()}")
    return result


def flatten(items):
    for item in items:
        yield item
        yield from flatten(item.get("children", []))


def select_disk(inventory, serial, size):
    matches = [d for d in inventory if d.get("type") == "disk" and d.get("serial") == serial]
    if len(matches) != 1 or matches[0].get("size") != size:
        raise ValueError("Expected exactly one whole disk with the confirmed serial and size")
    disk = matches[0]
    nodes = list(flatten([disk]))
    if any(d.get("type") not in ("disk", "part") or any(d.get("mountpoints") or []) for d in nodes):
        raise ValueError("Target or descendants are in use (mount/swap/mapper)")
    if any(d.get("ro") for d in nodes):
        raise ValueError("Target is still read-only")
    if not any(d.get("fstype") == "ntfs" for d in nodes):
        raise ValueError("Expected original NTFS; refusing a repeat format or unexpected disk")
    return disk


def disk_tree():
    return json.loads(run("lsblk", "--json", "--bytes", "-o", "NAME,PATH,TYPE,SIZE,SERIAL,FSTYPE,UUID,MOUNTPOINTS,RO").stdout)["blockdevices"]


def atomic_write(path, text, mode):
    temporary = path.with_name(path.name + ".media-server-tmp")
    if temporary.exists():
        raise RuntimeError(f"Stale temporary file: {temporary}")
    with temporary.open("x") as handle:
        handle.write(text)
        handle.flush()
        os.fchmod(handle.fileno(), mode)
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-erase", required=True, help="Exact guest serial to erase")
    parser.add_argument("--expected-bytes", type=int, required=True)
    parser.add_argument("--expected-hostname", default="media-server")
    parser.add_argument("--media-gid", type=int, default=2000)
    parser.add_argument("--probe-uid", type=int, default=1000)
    parser.add_argument("--guard-source", required=True, help="Reviewed check-media-storage.py in the guest")
    args = parser.parse_args()
    if not args.apply:
        parser.error("No changes without explicit --apply and --confirm-erase")
    os.umask(0o077)
    if os.geteuid() != 0 or Path("/etc/pve").exists() or socket.gethostname() != args.expected_hostname:
        raise RuntimeError("Run only as root inside the expected Debian VM, never Proxmox")
    if 'ID=debian' not in Path("/etc/os-release").read_text().splitlines():
        raise RuntimeError("Expected Debian")
    if STATE.exists():
        raise RuntimeError("Storage state already exists: never rerun formatting; inspect instead")
    for command in ("lsblk", "sfdisk", "mkfs.ext4", "udevadm", "findmnt", "blkid", "mount", "fuser", "systemctl", "docker", "groupadd"):
        if not shutil.which(command):
            raise RuntimeError(f"Missing prerequisite: {command}")
    guard_source = Path(args.guard_source)
    if not guard_source.is_file() or GUARD.exists() or DROPIN.exists():
        raise RuntimeError("Missing reviewed guard source or existing guard/drop-in; review first")
    compile(guard_source.read_text(), str(guard_source), "exec")
    if args.media_gid <= 999 or args.probe_uid <= 999:
        raise RuntimeError("Use unprivileged media group and probe UID")
    pwd.getpwuid(args.probe_uid)
    try:
        group = grp.getgrnam("media")
        if group.gr_gid != args.media_gid:
            raise RuntimeError("Existing media group has a different GID")
    except KeyError:
        try:
            grp.getgrgid(args.media_gid)
        except KeyError:
            pass
        else:
            raise RuntimeError("Requested media GID belongs to another group")
    if run("docker", "ps", "-q").stdout.strip():
        raise RuntimeError("Running containers: schedule maintenance, do not provision automatically")
    fstab = Path("/etc/fstab")
    original_fstab = fstab.read_text()
    for line in original_fstab.splitlines():
        fields = line.split()
        if fields and not line.lstrip().startswith("#") and len(fields) > 1 and fields[1] == "/data":
            raise RuntimeError("/data already in fstab")
    if MOUNT.is_symlink() or (MOUNT.exists() and (not MOUNT.is_dir() or any(MOUNT.iterdir()))):
        raise RuntimeError("/data must be absent or an empty real directory")
    disk = select_disk(disk_tree(), args.confirm_erase, args.expected_bytes)
    device = disk["path"]
    nodes = list(flatten([disk]))
    for node in nodes:
        if list(Path("/sys/class/block", node["name"], "holders").iterdir()):
            raise RuntimeError("Target has holders")
    if run("fuser", *(d["path"] for d in nodes), allowed=(0, 1)).returncode != 1:
        raise RuntimeError("Target has open users")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path("/var/backups/media-server", "storage-" + stamp)
    backup.mkdir(parents=True, mode=0o700)
    (backup / "fstab.before").write_text(original_fstab)
    (backup / "partition-table.before").write_text(run("sfdisk", "--dump", device).stdout)
    (backup / "lsblk.before.json").write_text(json.dumps(disk, indent=2))
    shutil.copyfile(__file__, backup / "prepare-media-storage.py")
    shutil.copyfile(guard_source, backup / "check-media-storage.py")
    report = {"started_at_utc": stamp, "device_at_execution": device, "guest_serial": args.confirm_erase,
              "expected_bytes": args.expected_bytes, "backup_directory": str(backup), "complete": False,
              "formatting_started": False, "formatting_performed": False}
    report_file = backup / "result.json"

    def record():
        report_file.write_text(json.dumps(report, indent=2) + "\n")

    record()
    try:
        # Revalidate just before the destructive boundary. Never format the host disk.
        if select_disk(disk_tree(), args.confirm_erase, args.expected_bytes)["path"] != device:
            raise RuntimeError("Disk identity changed")
        report["formatting_started"] = True
        record()
        result = run("sfdisk", "--lock=yes", "--wipe=always", "--wipe-partitions=always", device,
                     input='label: gpt\nunit: sectors\n\nstart=2048, type=L, name="media-data"\n')
        report["sfdisk_output"] = result.stdout + result.stderr
        run("udevadm", "settle")
        fresh = next(d for d in disk_tree() if d.get("serial") == args.confirm_erase)
        partitions = fresh.get("children", [])
        if len(partitions) != 1 or partitions[0]["type"] != "part" or partitions[0]["size"] < args.expected_bytes * 0.99:
            raise RuntimeError("Unexpected partition layout after GPT creation")
        partition = partitions[0]["path"]
        layout = json.loads(run("sfdisk", "--json", device).stdout)["partitiontable"]
        if layout["label"] != "gpt" or layout["partitions"][0]["start"] != 2048:
            raise RuntimeError("Unexpected GPT/alignment")
        # Largefile = ~1 inode/MiB; retain ext4 journal and a 1% reserved margin.
        result = run("mkfs.ext4", "-L", "media-data", "-m", "1", "-T", "largefile", "-E",
                     "nodiscard,lazy_itable_init=1,lazy_journal_init=0", partition, timeout=600)
        report["mkfs_output"] = result.stdout + result.stderr
        report["formatting_performed"] = True
        record()
        uuid = run("blkid", "-s", "UUID", "-o", "value", partition).stdout.strip()
        if not uuid or run("blkid", "-s", "TYPE", "-o", "value", partition).stdout.strip() != "ext4":
            raise RuntimeError("Cannot verify new ext4 UUID")
        MOUNT.mkdir(mode=0o000, exist_ok=True)
        os.chmod(MOUNT, 0o000)  # Protect the underlying OS directory while unmounted.
        options = "defaults,noatime,nodev,nosuid,noexec,nofail,x-systemd.device-timeout=10s"
        entry = f"UUID={uuid} /data ext4 {options} 0 2\n"
        atomic_write(fstab, original_fstab.rstrip() + "\n\n# media-server: dedicated multimedia HDD\n" + entry, 0o644)
        report.update({"filesystem_uuid": uuid, "partition": partition, "fstab_entry": entry.strip(),
                       "partition_table": layout, "mount_options": options, "media_gid": args.media_gid})
        record()
        run("systemctl", "daemon-reload")
        run("findmnt", "--verify", "--tab-file", str(fstab))
        run("mount", "/data")
        mounted = json.loads(run("findmnt", "--json", "--mountpoint", "/data", "-o", "TARGET,FSTYPE,UUID,OPTIONS").stdout)["filesystems"][0]
        if mounted["fstype"] != "ext4" or mounted["uuid"] != uuid or "rw" not in mounted["options"].split(","):
            raise RuntimeError("Wrong mounted filesystem")
        try:
            grp.getgrnam("media")
        except KeyError:
            run("groupadd", "--gid", str(args.media_gid), "media")
        for path in (MOUNT,) + tuple(MOUNT / relative for relative in DIRECTORIES):
            path.mkdir(exist_ok=True)
            os.chown(path, 0, args.media_gid)
            os.chmod(path, 0o2770)
        # Test actual group access with no root or supplementary-group privileges.
        probe = '''import json, os, uuid
from pathlib import Path
name = ".hardlink-check-" + uuid.uuid4().hex
source = Path("/data/downloads/movies") / name
target = Path("/data/media/movies") / name
os.umask(0o007)
try:
    source.write_bytes(b"media-server-hardlink-check\\n")
    os.link(source, target)
    a, b = source.stat(), target.stat()
    assert (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino) and a.st_nlink == 2
    source.unlink()
    assert target.read_bytes() == b"media-server-hardlink-check\\n"
    print(json.dumps({"same_device_inode": True, "links_before_unlink": 2, "other_name_survives": True}))
finally:
    source.unlink(missing_ok=True)
    target.unlink(missing_ok=True)
'''
        def unprivileged():
            os.setgroups([])
            os.setgid(args.media_gid)
            os.setuid(args.probe_uid)
        checked = subprocess.run([sys.executable, "-c", probe], text=True, capture_output=True, preexec_fn=unprivileged, check=True)
        report["hardlink_probe"] = json.loads(checked.stdout)
        report["probe_uid"] = args.probe_uid
        STATE.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(STATE, json.dumps(report, indent=2) + "\n", 0o600)
        shutil.copyfile(guard_source, GUARD)
        os.chmod(GUARD, 0o755)
        DROPIN.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(DROPIN, "[Unit]\nRequiresMountsFor=/data\nBindsTo=data.mount\nAfter=data.mount\n\n[Service]\nExecStartPre=/usr/local/sbin/check-media-storage\n", 0o644)
        run(str(GUARD))
        run("systemctl", "daemon-reload")
        run("systemctl", "restart", "docker")
        run("systemctl", "is-active", "docker", "data.mount")
        report.update({"complete": True, "docker_mount_guard_installed": True,
                       "finished_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        atomic_write(STATE, json.dumps(report, indent=2) + "\n", 0o600)
        record()
        print(json.dumps(report, indent=2))
    except Exception as error:
        report["error"] = str(error)
        record()
        # No automatic rollback of a format: the old files cannot be restored by this script.
        raise


if __name__ == "__main__":
    main()
