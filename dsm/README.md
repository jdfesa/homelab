# DSM

**Status:** Existing VM; current configuration and public screenshots documented; manual installation procedure incomplete · **Updated:** October 22, 2026.

This module is the entry point for the existing DSM NAS workload. It covers its VM and installation reference, not unrelated services. It records what is known and what still needs documenting, without claiming that file sharing, packages or backups were verified internally.

## Documentation

- [Installation guide](docs/installation-guide.md) — current DSM version, owner-identified RR loader, VM settings and real screenshots with identifiers redacted. The owner installed DSM on the lab's current physical hardware; the original installation steps have not yet been reconstructed or repeated.

## Observed Scope

| Item | Configuration and evidence |
| --- | --- |
| Guest | Proxmox VM100, DSM; running at the host inventory checkpoint |
| CPU | 2 vCPU, CPU host; confirmed in the owner-supplied Hardware screenshot |
| Memory | 3072 MiB (3 GiB); owner-confirmed on October 19 and shown in the October 22 screenshot |
| Boot disk | 3.5 GiB virtual disk on local-lvm |
| Data disk | Dedicated physical 2 TB HDD via stable by-id mapping; identifiers remain private |
| Startup | onboot=1 observed |
| Network | VirtIO on vmbr0; its firewall flag alone does not prove filtering |

The owner reports normal DSM operation with 3 GiB. This is not a measured memory-pressure test or an independently repeated host query. Historical inventory snapshots retain their original values. These are observations, not a live status monitor. The shared [guest inventory](../docs/installed-services.md#dsm) and [hardware inventory](../docs/hardware-inventory.md) own host resource details. DSM version and loader identity now have the evidence described in the installation guide; shares, SMB/Time Machine, users and packages are not inferred from the VM name.

## Next Documentation Steps

- Complete the manual installation procedure: VM creation/import method and loader/DSM installation steps.
- Inventory services/packages and intended use without exporting personal files or credentials.
- Document storage ownership, access and backup destination/retention privately where necessary.
- Verify an independent backup and a sample restore before storage changes.
- Add service guides/scripts only when they describe work actually reviewed and performed.

## Safety Boundary

Do not mount, format, repair or reuse this HDD from Proxmox or the media VM. The media-server HDD is a different disk. This documentation task does not authorize changing DSM, its users, loader, disks, power state or network.

There are no installer scripts, runtime exports or credentials in this module. Shared ignore rules already protect future `.local/`, secrets, backups and exports; add a module-specific `.gitignore` only if DSM-specific file types need it. Keep any future site notes in ignored `dsm/.local/`.
