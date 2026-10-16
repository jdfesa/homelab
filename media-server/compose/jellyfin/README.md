# Jellyfin Compose Module

**Status:** Deployed and healthy; setup wizard and Shows/Movies libraries complete. Real playback pending. Updated2026-10-16.

- [Service guide](../../docs/jellyfin.md) — **canonical reference** for deployment, all approved setup screenshots, exact options, verification and operation.
- [Manifest](compose.yaml), [private environment template](.env.example), [image lock](image-lock.json).
- [First-deployment script](../../scripts/deploy-jellyfin.py) — already executed; do not rerun on the current VM.

Official image12.2 pinned by digest, running12.2.0. Runtime `/srv/media-server/compose/jellyfin/`; config/cache NVMe; HDD library read-only; UID1000:GID2000, TCP8096 private LAN. Remote connections allowed by user choice, **without WAN/router configuration**. No secrets or runtime data belong here.
