# Media Server Compose Modules

Manifiestos desplegados por servicio. Runtime en Debian bajo `/srv/media-server/compose/`; appdata en NVMe, fuera del repositorio. Cada módulo enlaza su procedimiento canónico y fija una imagen inmutable.

- [Jellyfin](jellyfin/README.md): catálogo y reproducción; biblioteca RO.
- [qBittorrent](qbittorrent/README.md): transferencias; sólo descargas RW.
- [Prowlarr](prowlarr/README.md): fuentes e integración con Radarr; sin biblioteca.
- [Sonarr](sonarr/README.md): perfil HD, conexiones y adopción real por hardlink probados; adquisición nueva pendiente.
- [Radarr](radarr/README.md): gestión de películas y hardlinks; bind común `/data`.
- [Bazarr](bazarr/README.md): EN/ES con Radarr/Sonarr, OpenSubtitles.com y aviso a Jellyfin; sólo biblioteca RW.

Los límites funcionales se encuentran en el [roadmap](../ROADMAP.md); healthy no equivale a una prueba de todo el flujo.
