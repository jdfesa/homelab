# Homepage Configuration

Reviewed native-service inputs. Site addresses belong in the private runtime files, not these templates.

- `homepage.service` — systemd unit for the dedicated non-login service user.
- `homepage.env.example` — explicit LAN bind, allowed hosts and trusted-LAN access policy; replace placeholders outside Git.
- `settings.yaml` — portal presentation and card layout.
- `services.yaml.example` — service links only; no API keys or monitoring integrations. Infrastructure includes Proxmox, ProxMenux Monitor and DSM; all nine portal cards are confirmed. Local icon paths are deployed, HTTP hashes verified and browser appearance confirmed.
- `widgets.yaml` — English date/time display (`en-US`, full date, 12-hour AM/PM); applied and confirmed in the portal. No service credentials.
- `source-lock.json` — exact upstream source and toolchain artifacts; not a backup of configuration or appdata.

Use the [service setup guide](../docs/service-setup.md) for execution context, verification and limits.
