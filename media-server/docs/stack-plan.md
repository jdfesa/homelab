# Stack Plan

**Status:** Jellyfin/qBittorrent configured; Prowlarr/Knaben ready; Radarr healthy with verified account/root and Knaben sync; qBittorrent client Test + Save confirmed by UI; profiles/naming next · **Updated:** 2026-10-16.

El [Roadmap](../ROADMAP.md) define fases, estado real y criterios de aceptación. La separación entre descargas y biblioteca está creada y el probe de hardlinks del filesystem pasó; importaciones reales por aplicaciones aún pendientes. Jellyfin está configurado; el usuario eligió continuar con el cliente de descargas antes de una prueba manual de reproducción.

## Four Automation Layers

| Layer | Service | Responsibility |
| --- | --- | --- |
| 1 — Indexers | Prowlarr | Centralizar las fuentes configuradas y su integración con los gestores |
| 2 — Content management | Radarr | Monitorizar películas, aplicar preferencias y organizar las importaciones |
| 2 — Content management | Sonarr | Monitorizar series/episodios, aplicar preferencias y organizar las importaciones |
| 3 — Downloads | qBittorrent | Descargar y comunicar el estado a los gestores |
| 4 — Library and playback | Jellyfin | Catalogar y reproducir desde computadoras, tablet y otros clientes compatibles |

Estas capas son responsabilidades, no cuatro VMs ni una exigencia de instalar todas las alternativas del video. No sumar Jackett, Transmission o Plex sin una necesidad concreta. Se añadirá un gestor de subtítulos para español e inglés seleccionables, todavía sin herramienta elegida. Libros y música se evaluarán después.

## Normal User Workflow

1. Agregar una película en **Radarr** o una serie en **Sonarr**, con sus preferencias/perfiles.
2. Los gestores consultan fuentes/indexadores centralizados en **Prowlarr** y envían una versión compatible a **qBittorrent** cuando está disponible.
3. qBittorrent descarga al HDD; Radarr/Sonarr importan/organizan en `media`, con hardlinks a verificar.
4. **Jellyfin** incorpora la biblioteca y la reproduce; audio/subtítulos siguen las preferencias acordadas.

No pedir al usuario que busque torrents y mueva archivos manualmente como flujo normal. La pantalla manual qBittorrent revisada era sólo una prueba opcional y no bloquea continuar con Prowlarr e integraciones. qBittorrent no es el gestor de fuentes del diseño acordado. Usuario confirmó después que no inició esa descarga manual; continuar con Prowlarr.

## Integration Map — Planned Connections

| From → To | Purpose / endpoint | Private authentication | Current state |
| --- | --- | --- | --- |
| Prowlarr → Radarr | Registrar/sincronizar indexadores en API del gestor, TCP7878 | API key de Radarr | Verificado:1AppRadarr/FullSync yKnaben registrado enRadarr; no adquisición real |
| Prowlarr → Sonarr | Registrar/sincronizar indexadores en API del gestor, TCP8989 | API key de Sonarr | Pendiente: Sonarr no desplegado |
| Radarr/Sonarr → Prowlarr | Consultas Torznab según fuentes configuradas, TCP9696 | API key de Prowlarr | Knaben ya registrado enRadarr, RSS/búsquedas habilitados; consulta de película real pendiente; Sonarr no desplegado |
| Radarr/Sonarr → qBittorrent | Enviar/monitorizar descargas, TCP8080; categorías movies/tv | Cuenta qBit y contraseña vigente; [ejemplo del laboratorio](qbittorrent.md#laboratory-login-example) por pedido del propietario | Radarr: Test y Save confirmados por UI, categoría movies. Sonarr y descargas reales pendientes |
| Radarr/Sonarr → HDD | Importar de downloads a media bajo un bind común `/data` | UID/GID y permisos filesystem, no API | ProbeFS pasó; importación real/hardlinks aún pendientes |
| Jellyfin → HDD | Leer biblioteca `/data/media` como `/media` RO y escanear | Permisos filesystem | Montaje/verificación lectura listos; contenido/playback pendientes |
| Cliente tablet/computadora → Jellyfin | Reproducir biblioteca, TCP8096 | Cuenta Jellyfin | Web/setup listos; reproducción pendiente |

Los puertos de gestores son los previstos, no prueba de servicios ya activos. Las URLs reutilizables usan placeholders y las API keys permanecen privadas. La única excepción de credencial pública es el ejemplo qBit solicitado por el propietario; el formulario original aprobado conserva su IP LAN como evidencia del sitio. Cada Compose tiene red propia: nunca usar `localhost` para otra app ni asumir resolución DNS entre proyectos. El transporte concreto entre apps se verifica al integrarlas; no darlo por resuelto con este mapa. Los subtítulos ES/EN tendrán su integración propia cuando se elija/configure el gestor.

## Storage Contract

Diseño dentro de Debian: `/data` ya está montado en ext4 y las ramas downloads/media creadas. Appdata Jellyfin/qBittorrent/Prowlarr ya está en NVMe; el resto se prepara al desplegar cada servicio:

```text
/srv/media-server/appdata/       # NVMe: configuración y bases de datos
  jellyfin/
  qbittorrent/
  prowlarr/
  radarr/
  sonarr/

/data/                          # HDD dedicado: un filesystem montado
  downloads/
    movies/
    tv/
  media/
    movies/
    tv/
```

- Radarr y Sonarr deben ver una raíz común `/data` para acceder a descargas y biblioteca en el mismo filesystem y permitir hardlinks.
- qBittorrent solo necesita las descargas, conservando rutas internas coherentes, por ejemplo `/data/downloads`.
- Jellyfin solo necesita la biblioteca, preferentemente en modo de solo lectura; su configuración/base de datos queda local en el NVMe.
- Prowlarr no necesita acceso a toda la biblioteca para gestionar indexadores.
- Elegir usuarios/grupos y permisos antes de crear contenido; no aplicar `chmod 777` ni `chown -R` sobre el host, DSM o todo `/media`.
- No mantener descargas en el NVMe y biblioteca en el HDD si se esperan hardlinks entre ambas.

Los dos primeros directorios del esquema son rutas de runtime **dentro de la VM**, no carpetas del repositorio de la Mac.

### No Unnecessary Media Copies

`downloads/{movies,tv}` contiene archivos con la estructura necesaria para qBittorrent; `media/{movies,tv}` es la biblioteca organizada para Jellyfin. Repetir nombres de categorías no implica duplicar datos. La propuesta es importar archivos terminados que siguen compartiéndose mediante **hardlinks**, dos nombres para el mismo archivo, no dos copias ni enlaces simbólicos.

El probe de filesystem ya pasó sin root, con GID2000. La integración aún requiere un bind mount común `/data` en Radarr/Sonarr, configuración y permisos correctos; no se dará por verificada sin comparar dispositivo/inode de una importación real de película y episodio. La [Storage Guide](storage-guide.md) registra GPT/ext4, fstab, guardas y scripts; el [Roadmap](../ROADMAP.md#storage-semantics) explica políticas pendientes. Un hardlink no es un backup.

## Compose Modules

El usuario confirmó un Compose por servicio por organización, no por ahorro de CPU/RAM. `media-server/compose/jellyfin/` ya está desplegado; qBittorrent5.2.4 también está desplegado/healthy con rutas y categorías verificadas, login y cambio de clave qBit confirmados; no descarga manual. Prowlarr también desplegado/healthy, con autenticaciónForms/Enabled y Knaben habilitado. Radarr6.4.4.10685 también desplegado/healthy, con cuenta/raíz y Prowlarr/Knaben verificados y cliente qBit Test + Save confirmado por UI; perfiles/renombrado y flujo real pendientes; único `/data` común verificado. Ver [guía Radarr](radarr.md). Cada módulo incluye `compose.yaml`, `.env.example` sin secretos, lock de imagen y README corto. **Cada servicio tiene una única guía propia en `docs/<servicio>.md`**, con pasos, valores, capturas y verificaciones, enlazada desde el README del módulo; no duplicarla en Compose. Los demás se añaden al configurarlos, no como manifests vacíos.

Cada módulo debe registrar: imagen y versión exacta o política explícita, puertos/acceso LAN, persistencia, variables requeridas, dependencias/redes compartidas, comprobación de salud, backup, restauración y actualización/rollback. La comunicación entre proyectos Compose debe declararse, no asumirse por el nombre de los contenedores.

No publicar paneles administrativos en Internet. Inicialmente se probará acceso desde la LAN. Guardar contraseñas, API keys, direcciones privadas y configuración específica del equipo fuera de Git. No instalar actualizadores automáticos ni rutas VPN sin decidirlos por separado.

## End-to-End Test

El objetivo final **no es solamente tener Jellyfin**: agregar un título autorizado o monitorizar una serie, localizar una descarga compatible con las preferencias, descargar, importar/organizar y reproducir desde otro dispositivo sin mover archivos manualmente.

La adquisición depende de disponibilidad, permisos de acceso a las fuentes y preferencias configuradas; no se garantiza encontrar cualquier título. Registrar categorías del cliente, raíces de biblioteca, perfiles, integración por API y prueba de un episodio futuro. Capturar configuraciones revisadas sin secretos para poder reconstruir también los ajustes hechos en las interfaces web.

## Backup Boundary

Separar backup de la VM/configuración de la protección del HDD multimedia. Definir qué contenido necesita copia independiente, destino, retención y restauración; no asumir que snapshots o el flag Backup del disco de sistema incluyen el HDD físico. Los secretos y las claves de recuperación requieren custodia privada fuera del repositorio.

## References

- [Servarr Docker Guide](https://github.com/Servarr/Wiki/blob/master/docker-guide.md) — rutas coherentes, permisos y hardlinks.
- [Jellyfin Storage](https://jellyfin.org/docs/general/administration/storage/) — bases de datos locales y almacenamiento disponible.
- [Repository Stack Guide](../../docs/stack-guide.md) — requisitos comunes para despliegues reales.
