#!/usr/bin/env python3
"""Verify configured storage; optional missing-mount test uses a private namespace."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=60).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-missing-mount", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0 or Path("/etc/pve").exists():
        raise RuntimeError("Run as root in the Debian media VM, not Proxmox")
    state = json.loads(Path("/var/lib/media-server/provisioning/storage.json").read_text())
    if not state.get("complete"):
        raise RuntimeError("Provisioning has not completed")
    run("/usr/local/sbin/check-media-storage")
    mounted = json.loads(run("findmnt", "--json", "--mountpoint", "/data", "-o", "TARGET,SOURCE,FSTYPE,UUID,OPTIONS"))["filesystems"][0]
    run("findmnt", "--verify", "--tab-file", "/etc/fstab")
    if Path("/etc/fstab").read_text().count(state["fstab_entry"]) != 1:
        raise RuntimeError("Managed fstab entry missing or duplicated")
    directories = {}
    for relative in ("", "downloads", "downloads/movies", "downloads/tv", "media", "media/movies", "media/tv"):
        path = Path("/data") / relative
        info = path.stat()
        if info.st_uid != 0 or info.st_gid != state["media_gid"] or stat.S_IMODE(info.st_mode) != 0o2770:
            raise RuntimeError(f"Unexpected directory ownership/mode: {path}")
        directories[str(path)] = {"uid": info.st_uid, "gid": info.st_gid, "mode": oct(stat.S_IMODE(info.st_mode))}
    properties = run("systemctl", "show", "docker", "-p", "RequiresMountsFor", "-p", "BindsTo", "-p", "ExecStartPre")
    if "data.mount" not in properties or "check-media-storage" not in properties or "/data" not in properties:
        raise RuntimeError("Docker mount dependencies/guard are missing")
    metadata = run("tune2fs", "-l", mounted["source"])
    features = next(line for line in metadata.splitlines() if line.startswith("Filesystem features:"))
    if "has_journal" not in features:
        raise RuntimeError("ext4 journal missing")
    namespace_probe = False
    if args.probe_missing_mount:
        # Only the child mount namespace is altered; the parent's /data stays mounted.
        script = '''set -eu
umount /data
set +e
/usr/local/sbin/check-media-storage
result=$?
set -e
test "$result" -eq 1
test -z "$(ls -A /data)"
printf '%s\\n' 'missing-mount guard refused; underlying OS directory empty'
'''
        run("unshare", "--mount", "--propagation", "private", "--", "/bin/sh", "-c", script)
        run("/usr/local/sbin/check-media-storage")
        namespace_probe = True
    run("systemctl", "is-active", "data.mount", "docker", "containerd", "ssh", "qemu-guest-agent")
    failed = run("systemctl", "--failed", "--no-legend", "--plain").strip()
    if failed:
        raise RuntimeError("Failed units require review: " + failed)
    usage = os.statvfs("/data")
    print(json.dumps({"verified": True, "mount": mounted, "directories": directories,
                      "docker_mount_properties": properties, "ext4_features": features,
                      "missing_mount_private_namespace_verified": namespace_probe,
                      "hardlink_probe_at_provisioning": state["hardlink_probe"],
                      "size_bytes": usage.f_blocks * usage.f_frsize,
                      "available_bytes": usage.f_bavail * usage.f_frsize,
                      "inode_count": usage.f_files, "free_inodes": usage.f_favail,
                      "persistent_containers": run("docker", "ps", "-aq").split(), "failed_units": 0}, indent=2))


if __name__ == "__main__":
    main()
