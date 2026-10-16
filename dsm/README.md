# DSM

**Status:** Existing VM; host-level inventory only, not a reproducible DSM installation recipe · **Updated:** October 16, 2026.

This module is the entry point for the existing DSM workload. It records what is known and what still needs documenting, without claiming that NAS services or backups were verified internally.

## Observed Scope

| Item | Last observed configuration |
| --- | --- |
| Guest | Proxmox VM100, DSM; running at the host inventory checkpoint |
| Resources | 2 vCPU, CPU host, 4096 MiB RAM |
| Boot disk | 3.5 GiB virtual disk on local-lvm |
| Data disk | Dedicated physical 2 TB HDD via stable by-id mapping; identifiers remain private |
| Startup | onboot=1 observed |
| Network | VirtIO on vmbr0; its firewall flag alone does not prove filtering |

These are observations, not a live status monitor. The shared [guest inventory](../docs/installed-services.md#dsm) and [hardware inventory](../docs/hardware-inventory.md) own host resource details. No DSM version, loader, shares, SMB/Time Machine, users or packages are inferred from the VM name.

## Next Documentation Steps

- Inventory the internal DSM version, services/packages and intended use without exporting personal files or credentials.
- Document storage ownership, access and backup destination/retention privately where necessary.
- Verify an independent backup and a sample restore before storage changes.
- Add service guides/scripts only when they describe work actually reviewed and performed.

## Safety Boundary

Do not mount, format, repair or reuse this HDD from Proxmox or the media VM. The media-server HDD is a different disk. This documentation task does not authorize changing DSM, its users, loader, disks, power state or network.

There are no installer scripts, runtime exports or credentials in this module. Shared ignore rules already protect future `.local/`, secrets, backups and exports; add a module-specific `.gitignore` only if DSM-specific file types need it. Keep any future site notes in ignored `dsm/.local/`.
