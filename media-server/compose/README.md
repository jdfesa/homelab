# Media Server Compose Modules

Real service manifests owned by this VM. Runtime copies live in Debian under `/srv/media-server/compose/`; configuration/cache live on the NVMe, not in this repository.

- [Jellyfin](jellyfin/README.md): LAN movie/TV playback, with read-only HDD library access.

- [qBittorrent](qbittorrent/README.md): cliente de descargas; desplegado/healthy; rutas/categorías verificadas, primer ingreso confirmado; primera descarga sin verificar.

- [Prowlarr](prowlarr/README.md): gestor de indexadores; desplegado/healthy; autenticaciónForms/Enabled guardada/verificada; primera fuente pendiente.

Manager modules will be added only when deployed. See the [Roadmap](../ROADMAP.md) for the remaining automation pipeline.
