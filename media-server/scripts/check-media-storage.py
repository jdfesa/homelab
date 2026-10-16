#!/usr/bin/env python3
"""Fail closed unless /data is the expected writable ext4 filesystem."""
import json
from pathlib import Path
import subprocess
import sys

STATE = Path("/var/lib/media-server/provisioning/storage.json")


def validate_mount(state, mount):
    if mount.get("target") != "/data" or mount.get("fstype") != "ext4":
        raise ValueError("/data is not an ext4 mountpoint")
    if mount.get("uuid") != state["filesystem_uuid"]:
        raise ValueError("/data has an unexpected filesystem UUID")
    if "rw" not in mount.get("options", "").split(","):
        raise ValueError("/data is not writable")


def main():
    try:
        state = json.loads(STATE.read_text())
        result = subprocess.run(
            ["findmnt", "--json", "--mountpoint", "/data", "-o", "TARGET,FSTYPE,UUID,OPTIONS"],
            capture_output=True, text=True, check=True,
        )
        mounts = json.loads(result.stdout).get("filesystems", [])
        if len(mounts) != 1:
            raise ValueError("Expected exactly one /data mount")
        validate_mount(state, mounts[0])
        print("media-storage: expected writable ext4 is mounted on /data")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"media-storage: REFUSED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
