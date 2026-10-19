# Homepage Icons

**Status:** Nine local PNGs deployed; all served hashes and browser appearance verified, with Homepage active.

**Updated:** 2026-10-19.

## Source and Integrity

The owner downloaded these assets from [Homarr Labs — Dashboard Icons](https://github.com/homarr-labs/dashboard-icons). PNG bytes and received filenames are preserved unchanged. The upstream commit and individual upstream blob identities were **not independently verified**; do not interpret local hashes as a signed upstream release.

[icons-lock.json](icons-lock.json) records the nine card-to-file mappings, dimensions, sizes, SHA-256 hashes and license hash. Reconstruction uses the exact versioned local copies, not a mutable CDN URL or a disposable download script. The PNGs total 317286 bytes, approximately 310 KiB.

| Service | Local file |
| --- | --- |
| Proxmox | `proxmox.png` |
| ProxMenux Monitor | `proxmenu.png` |
| DSM | `synology-dsm.png` |
| Jellyfin | `jellyfin.png` |
| qBittorrent | `qbittorrent.png` |
| Prowlarr | `prowlarr.png` |
| Radarr | `radarr.png` |
| Sonarr | `sonarr.png` |
| Bazarr | `bazarr.png` |

## License and Attribution

The owner-supplied [LICENSE.txt](LICENSE.txt) contains the upstream Apache-2.0 license and attribution to Bjorn Lammers, Meier Lukas, Thomas Camlong and Homarr Labs. This third-party license is separate from the root repository license. Product names and marks belong to their owners; the icons identify the services and do not imply endorsement.

## Deployment Boundary

The assets are installed in the native release's `public/icons/` directory, referenced by `/icons/<filename>.png`. All nine HTTP responses matched the manifest hashes after the service restart. Their browser appearance was confirmed in the real [current snapshot](../README.md#current-snapshot). Preserve root ownership, directory mode `0755` and file mode `0644`; the Homepage process must not write these files. New public files require a service restart before verification. There is no CDN fallback configured.

Keep these files, the manifest and license together when rebuilding. They preserve assets, not private URLs, settings or backups of the server. See the [canonical service guide](../docs/service-setup.md#local-icons) for runtime status and limits.
