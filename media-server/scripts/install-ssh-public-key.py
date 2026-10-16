#!/usr/bin/env python3
"""Install one approved Ed25519 public key in the Debian guest, preserving keys."""
import argparse
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import shlex
import socket
import stat
import tempfile


def parse_public_key(text):
    lines = text.strip().splitlines()
    if len(lines) != 1 or any(ord(char) < 32 or ord(char) == 127 for char in lines[0]):
        raise ValueError("Expected one plain public-key line")
    fields = lines[0].split(maxsplit=2)
    if len(fields) < 2 or fields[0] != "ssh-ed25519":
        raise ValueError("Expected a plain ssh-ed25519 public key, without options")
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("Invalid public-key encoding") from error
    prefix = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"
    if len(blob) != len(prefix) + 32 or not blob.startswith(prefix):
        raise ValueError("Invalid Ed25519 key structure")
    canonical = base64.b64encode(blob).decode("ascii")
    comment = " " + fields[2] if len(fields) == 3 else ""
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return canonical, comment, fingerprint


def append_public_key(existing, public_key):
    """Preserve every old byte and never broaden an already-present key."""
    blob, comment, fingerprint = parse_public_key(public_key)
    for line in existing.decode("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        tokens = shlex.split(line, comments=False)
        if any(tokens[index:index + 2] == ["ssh-ed25519", blob]
               for index in range(len(tokens) - 1)):
            return existing, False, fingerprint
    separator = b"\n" if existing and not existing.endswith(b"\n") else b""
    entry = f"no-agent-forwarding,no-X11-forwarding ssh-ed25519 {blob}{comment}\n"
    return existing + separator + entry.encode("utf-8"), True, fingerprint


def validate_owner(info, uid, directory):
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected_type(info.st_mode) or info.st_uid != uid or info.st_mode & 0o022:
        raise ValueError("Refusing unexpected ownership, type, or writable group/other permissions")
    if not directory and info.st_nlink != 1:
        raise ValueError("Refusing hardlinked authorized_keys")


def install(user, public_key):
    home = Path(user.pw_dir)
    if home != Path("/home") / user.pw_name or home.resolve() != home:
        raise ValueError("Expected a non-symlink /home/<user> home directory")
    with_home = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        validate_owner(os.fstat(with_home), user.pw_uid, True)
        try:
            os.mkdir(".ssh", mode=0o700, dir_fd=with_home)
            os.chown(".ssh", user.pw_uid, user.pw_gid, dir_fd=with_home, follow_symlinks=False)
        except FileExistsError:
            pass
        directory = os.open(".ssh", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=with_home)
    finally:
        os.close(with_home)
    temporary = None
    try:
        validate_owner(os.fstat(directory), user.pw_uid, True)
        old_info = None
        try:
            descriptor = os.open("authorized_keys", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            existing = b""
        else:
            with os.fdopen(descriptor, "rb") as source:
                old_info = os.fstat(source.fileno())
                validate_owner(old_info, user.pw_uid, False)
                existing = source.read(1024 * 1024 + 1)
                if len(existing) > 1024 * 1024:
                    raise ValueError("Unexpectedly large authorized_keys")
        updated, changed, fingerprint = append_public_key(existing, public_key)
        result = {"user": user.pw_name, "uid": user.pw_uid, "fingerprint": fingerprint,
                  "changed": changed, "existing_bytes_preserved": updated.startswith(existing)}
        if not changed:
            return result
        backup_root = Path("/var/backups/media-server")
        backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if backup_root.resolve() != backup_root:
            raise ValueError("Refusing symlink backup directory")
        validate_owner(backup_root.stat(), 0, True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = Path(tempfile.mkdtemp(prefix=f"ssh-key-{stamp}-", dir=backup_root))
        (backup / "authorized_keys.before").write_bytes(existing)
        os.chmod(backup / "authorized_keys.before", 0o600)
        (backup / "before.json").write_text(json.dumps({
            "existed": old_info is not None, "uid": old_info.st_uid if old_info else None,
            "gid": old_info.st_gid if old_info else None,
            "mode": oct(stat.S_IMODE(old_info.st_mode)) if old_info else None,
            "sha256": hashlib.sha256(existing).hexdigest(),
        }, indent=2) + "\n")
        temporary = ".authorized_keys-" + os.urandom(12).hex()
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(updated)
            destination.flush()
            os.fchown(destination.fileno(), user.pw_uid, user.pw_gid)
            os.fchmod(destination.fileno(), 0o600)
            os.fsync(destination.fileno())
        # Refuse concurrent replacement/edit; operate through the opened directory.
        if old_info is None:
            try:
                os.stat("authorized_keys", dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError("authorized_keys appeared during installation")
        else:
            current = os.stat("authorized_keys", dir_fd=directory, follow_symlinks=False)
            if (current.st_ino, current.st_mtime_ns, current.st_size) != (
                    old_info.st_ino, old_info.st_mtime_ns, old_info.st_size):
                raise ValueError("authorized_keys changed during installation")
        os.replace(temporary, "authorized_keys", src_dir_fd=directory, dst_dir_fd=directory)
        temporary = None
        os.fsync(directory)
        result["backup"] = str(backup)
        (backup / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        if temporary is not None:
            os.unlink(temporary, dir_fd=directory)
        os.close(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--user", required=True)
    parser.add_argument("--expected-uid", required=True, type=int)
    parser.add_argument("--expected-hostname", default="media-server")
    parser.add_argument("--public-key-file", required=True)
    args = parser.parse_args()
    if not args.apply:
        parser.error("No changes without explicit --apply")
    if os.geteuid() != 0 or Path("/etc/pve").exists():
        raise RuntimeError("Run as root inside the Debian VM, never on Proxmox")
    release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    if release.get("ID", "").strip('"') != "debian" or socket.gethostname() != args.expected_hostname:
        raise RuntimeError("Unexpected OS or hostname")
    user = pwd.getpwnam(args.user)
    if args.expected_uid <= 0 or user.pw_uid != args.expected_uid or user.pw_gid == 0:
        raise RuntimeError("Refusing root or unexpected user identity")
    public_key = Path(args.public_key_file).read_text()
    parse_public_key(public_key)  # Validate before creating any directory.
    print(json.dumps(install(user, public_key), indent=2))


if __name__ == "__main__":
    main()
