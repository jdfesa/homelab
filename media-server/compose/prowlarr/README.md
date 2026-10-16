# Prowlarr Compose Module

**Status:** Deployed and healthy; Forms/Enabled authentication saved and verified; Knaben saved/enabled; manager integrations pending.

- [Service guide](../../docs/prowlarr.md) — canonical setup, authentication, integration plan, verification and operation.
- [Manifest](compose.yaml), [private environment template](.env.example), [image lock](image-lock.json).
- [First-deployment script](../../scripts/deploy-prowlarr.py) — explicit apply, existing-storage guard, refuses existing state.

Runtime `/srv/media-server/compose/prowlarr/`; appdata only on NVMe. No access to HDD downloads/library. No secrets or databases here.
