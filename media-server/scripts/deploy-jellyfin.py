#!/usr/bin/env python3
"""First deployment only: reviewed Jellyfin Compose module inside Debian."""
import argparse
import grp
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess


APPDATA = Path("/srv/media-server/appdata/jellyfin")
STACK = Path("/srv/media-server/compose/jellyfin")


def run(*args, timeout=90):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout).stdout


def validate_configuration(config, addresses):
    if set(config["services"]) != {"jellyfin"}:
        raise ValueError("Only the Jellyfin service is in scope")
    service = config["services"]["jellyfin"]
    if not re.fullmatch(r"jellyfin/jellyfin:[0-9.]+@sha256:[a-f0-9]{64}", service["image"]):
        raise ValueError("Require official version and immutable digest")
    if service.get("user") != "1000:2000" or service.get("privileged") or service.get("devices"):
        raise ValueError("Expected non-root UID1000/media GID2000, without devices or privileged mode")
    expected = {"/config": (str(APPDATA / "config"), False),
                "/cache": (str(APPDATA / "cache"), False), "/media": ("/data/media", True)}
    volumes = service.get("volumes", [])
    if len(volumes) != 3 or {v["target"] for v in volumes} != set(expected):
        raise ValueError("Unexpected bind mounts")
    for volume in volumes:
        if volume.get("type") != "bind" or (volume["source"], volume.get("read_only", False)) != expected[volume["target"]]:
            raise ValueError("Require NVMe appdata and read-only HDD media")
    ports = service.get("ports", [])
    if len(ports) != 1:
        raise ValueError("Only one TCP web port is in scope")
    port = ports[0]
    address = ipaddress.ip_address(port["host_ip"])
    if (address.version != 4 or not address.is_private or address.is_loopback or address.is_unspecified
            or str(address) not in addresses or int(port["published"]) != 8096
            or port["target"] != 8096 or port.get("protocol", "tcp") != "tcp"):
        raise ValueError("Require TCP8096 on an assigned private LAN IPv4")
    return service, str(address)


def directory(path, uid=0, gid=0, mode=0o755):
    if path.resolve() != path:
        raise ValueError("Refusing symlink directory: " + str(path))
    if not path.exists():
        path.mkdir(mode=mode)
        os.chown(path, uid, gid)
        os.chmod(path, mode)
    info = path.stat()
    if not path.is_dir() or (info.st_uid, info.st_gid) != (uid, gid) or info.st_mode & 0o022:
        raise ValueError("Unexpected directory ownership/permissions: " + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--compose-file", required=True)
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()
    if not args.apply:
        parser.error("No changes without explicit --apply")
    if os.geteuid() != 0 or Path("/etc/pve").exists() or socket.gethostname() != "media-server":
        raise RuntimeError("Run as root only inside the media-server Debian VM")
    if 'ID=debian' not in Path("/etc/os-release").read_text().splitlines():
        raise RuntimeError("Expected Debian")
    run("/usr/local/sbin/check-media-storage")
    if grp.getgrnam("media").gr_gid != 2000:
        raise RuntimeError("Expected existing media GID2000")
    if STACK.exists():
        raise RuntimeError("First deployment only; refusing to overwrite an existing stack")
    source = Path(args.compose_file).resolve(strict=True)
    environment = Path(args.env_file).resolve(strict=True)
    config = json.loads(run("docker", "compose", "--env-file", str(environment), "-f", str(source), "config", "--format", "json"))
    addresses = {entry["local"] for interface in json.loads(run("ip", "-j", "-4", "address", "show"))
                 for entry in interface.get("addr_info", [])}
    service, address = validate_configuration(config, addresses)
    run("docker", "image", "inspect", service["image"])
    if run("docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=media-jellyfin").strip():
        raise RuntimeError("Existing Jellyfin Compose project requires review")
    for target in ("/data/media", "/data/media/movies", "/data/media/tv"):
        if not Path(target).is_dir() or Path(target).resolve() != Path(target):
            raise RuntimeError("Missing or symlink library directory: " + target)
    # Only create/chown these new application directories, never recurse through media.
    for path in (Path("/srv/media-server"), Path("/srv/media-server/appdata"), APPDATA,
                 Path("/srv/media-server/compose")):
        directory(path)
    if APPDATA.stat().st_dev == Path("/data").stat().st_dev:
        raise RuntimeError("Appdata must stay on the OS/NVMe filesystem")
    for name in ("config", "cache"):
        directory(APPDATA / name, 1000, 2000, 0o750)
    directory(STACK)
    shutil.copyfile(source, STACK / "compose.yaml")
    shutil.copyfile(environment, STACK / ".env")
    os.chmod(STACK / "compose.yaml", 0o644)
    os.chmod(STACK / ".env", 0o600)
    compose = ("docker", "compose", "--project-directory", str(STACK), "-f", str(STACK / "compose.yaml"))
    run(*compose, "config", "--quiet")
    run("/usr/local/sbin/check-media-storage")
    run(*compose, "up", "-d", "--wait", "--wait-timeout", "180", "--pull", "never", timeout=210)
    print(json.dumps({"deployed": True, "image": service["image"], "stack": str(STACK),
                      "url": f"http://{address}:8096", "compose_ps": json.loads(run(*compose, "ps", "--format", "json"))}, indent=2))


if __name__ == "__main__":
    main()
