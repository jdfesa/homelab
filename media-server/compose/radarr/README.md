# Radarr Compose Module

**Status:** Deployed and healthy; version, LAN, identity/mounts and filesystem hardlinks verified. Forms/Enabled account and `/data/media/movies` root saved and verified; Prowlarr/Knaben sync is verified; qBittorrent client Test + Save are confirmed by UI. Profiles/naming are next; real movie download/import/playback still pending. See the canonical guide for the actual checkpoint.

- [Service guide](../../docs/radarr.md) — canonical prerequisites, first deployment, user setup, planned integrations, acceptance and recovery.
- [Manifest](compose.yaml), [environment template](.env.example), [image lock](image-lock.json).
- [First-deployment script](../../scripts/deploy-radarr.py) — explicit apply, guarded existing storage and no existing state.

Runtime `/srv/media-server/compose/radarr/`; `/config` on NVMe and **one `/data:/data` RW bind** on HDD. No downloads/media/database files or secrets in this module. No other services are deployed by this manifest.
