# Media Server Scripts

Reusable scripts for the media VM and its storage. **Do not run every script in sequence or as root on the administration Mac.** Read the execution target and safety boundary first. Site-specific addresses, physical serials, UUIDs and logs belong in the ignored `media-server/.local/` directory, not here.

## Script Index

| Script | Run on | Purpose | Safety boundary |
| --- | --- | --- | --- |
| [bootstrap-debian.sh](bootstrap-debian.sh) | Debian VM, root | Install official Docker/Compose and base utilities; record package versions | Rejects Proxmox; does not configure disks or networking |
| [configure-static-ip.sh](configure-static-ip.sh) | Debian VM, root | Configure the existing dhcpcd stack with address checks and timed rollback | Requires explicit `--apply`; use console/Guest Agent and verify externally before cancelling rollback |
| [install-ssh-public-key.py](install-ssh-public-key.py) | Debian VM, root | Install one approved Ed25519 public key for a non-root user, with backup and duplicate detection | Requires `--apply`, expected hostname and UID; preserves old key bytes/restrictions, refuses symlinks/unsafe owners; no sshd, password, sudo or group changes |
| [deploy-jellyfin.py](deploy-jellyfin.py) | Debian VM, root | First deployment of the reviewed Jellyfin Compose module with NVMe appdata and read-only HDD library | Requires `--apply`, official version/digest, non-root user and assigned private IPv4; refuses existing stack, wrong mount contract or missing `/data`; no access/password/disk changes |
| [deploy-qbittorrent.py](deploy-qbittorrent.py) | Debian VM, root | First deployment of pinned downloader; config on NVMe, downloads only on HDD, empty client | Requires `--apply`, existing guarded mount and assigned LAN IPv4; refuses existing state, disables both router mappings before startup, preserves authentication; private temporary login file, never print full logs |
| [reset-qbittorrent-webui.py](reset-qbittorrent-webui.py) | Debian VM, root | Explicit recovery of qBit WebUI credentials in this empty lab; private backup and fresh-login verification | Requires `--apply`, password via getpass/stdin, reviewed image/project/mounts and empty torrent state; changes only two WebUI credential keys, stops/starts only the same qBit container, preserves other services; guarded rollback, no reinstall/auth bypass/network changes |
| [deploy-prowlarr.py](deploy-prowlarr.py) | Debian VM, root | First deployment of pinned indexer manager with NVMe config only | Requires `--apply`, guarded mount, assigned LAN IPv4 and absent state; no HDD bind, accounts, sources, downloads or integrations; native auth setup remains user action |
| [deploy-radarr.py](deploy-radarr.py) | Debian VM, root | First deployment of the pinned movie manager; NVMe config and one common HDD `/data` bind | Requires `--apply`, exact reviewed image, guarded existing storage, absent stack/appdata and LAN7878; no accounts/movies/integrations; cleaned-up filesystem probe as1000:2000 is not a movie-import test |
| [set-media-disk-writable.py](set-media-disk-writable.py) | Proxmox, root | Revalidate an already attached read-only HDD, cleanly shut down only the media VM, enable writes on `scsi1`, start and verify it | Requires `--apply`, exact physical identity and distinct protected VM; no formatting or forced shutdown |
| [prepare-media-storage.py](prepare-media-storage.py) | Debian VM, root | **Erase the confirmed NTFS HDD**, create GPT/ext4, UUID mount at `/data`, media directories/group, hardlink probe and Docker mount guard | Requires `--apply`, exact guest serial/size/hostname; refuses mounted/in-use/read-only disks, unexpected filesystems and repeat provisioning |
| [check-media-storage.py](check-media-storage.py) | Debian VM | Read-only check of the expected ext4 UUID and writable `/data` mount | Exits nonzero if absent/wrong/read-only; installed as `/usr/local/sbin/check-media-storage` for Docker `ExecStartPre` |
| [verify-media-storage.py](verify-media-storage.py) | Debian VM, root | Verify fstab, permissions, journal, Docker dependencies, services and free space; optional missing-mount probe | `--probe-missing-mount` unmounts only in a private child mount namespace; the real `/data` remains mounted |

## Review and Use

- Minimal Debian may lack `fuser`: install the Debian `psmisc` package first (`apt-get update` then `apt-get install -y psmisc`). Storage tools also require `fdisk`, `e2fsprogs` and `util-linux`; they were already present in the reviewed guest. Missing prerequisites stop provisioning before any erase.
- Use `python3 <script> --help` for required parameters. Scripts do not discover which HDD the human meant to erase.
- Review [Storage Guide](../docs/storage-guide.md) for commands, choices, recorded evidence and recovery limitations; [Post-install Guide](../docs/post-install-guide.md) covers base/network setup.
- Copy the reviewed storage scripts into a root-owned directory on the guest; pass the guard file path via `--guard-source`.
- A whole-disk path is selected from the **unique guest serial and exact capacity**, not from an assumed `/dev/sdb`. The host script verifies the physical `by-id` mapping separately.
- Formatting is **not idempotent** and has no automatic data rollback. A saved partition table is not a backup of files. Once provisioned, use the read-only guard and filesystem inspection, never rerun the formatter to repair a mount.
- The media group defaults to GID `2000`; collisions are rejected. Directories are root-owned, group `media`, mode `2770`. No `chmod 777`, root SSH, passwordless sudo or Docker-group access is added.
- The Docker guard applies to this dedicated media VM only, not Proxmox or DSM. Missing/wrong storage blocks Docker startup; removing an active mount also stops Docker through `BindsTo`.
- Formatting is logical preparation, **not a secure overwrite of every old byte**. It retains ext4 journaling and a 1% reserved margin; the `largefile` profile trades inode density for multimedia storage (about one inode per MiB). Monitor free bytes and inodes before expanding scope.

## Local Validation

From the `media-server/` directory, run `python3 -m unittest discover -s tests -v`; see the [tests README](../tests/README.md). Local tests use pure functions and explicit-refusal paths only; they do not require RTK, format a disk or contact Proxmox. Actual guest mounts, service guards and application imports require separate recorded verification.
