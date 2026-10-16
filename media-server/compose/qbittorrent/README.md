# qBittorrent Compose Module

Reviewed deployment files for the Debian media VM. **Deployed and healthy; LAN/API verified. User login and permanent-password change confirmed; no manual download started. Automation integration pending.**

- [Service guide](../../docs/qbittorrent.md) — canonical deployment, configuration and verification instructions.
- [Manifest](compose.yaml), [private environment template](.env.example), [image lock](image-lock.json).
- [First-deployment script](../../scripts/deploy-qbittorrent.py) — guarded, explicit apply; not an upgrade script.

Runtime: `/srv/media-server/compose/qbittorrent/`. Appdata on NVMe; downloads only on the HDD. No secrets or runtime data here.
