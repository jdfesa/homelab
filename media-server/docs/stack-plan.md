# Stack Architecture

## Responsibilities

| Capa | Servicio | Responsabilidad |
| --- | --- | --- |
| Fuentes | Prowlarr | Centraliza y sincroniza indexadores |
| Películas | Radarr | Busca, aplica perfiles y organiza importaciones |
| Series | Sonarr | Adopción existente por hardlink comprobada; adquisición nueva por validar |
| Transferencia | qBittorrent | Descarga y comunica estado al gestor |
| Biblioteca | Jellyfin | Lee, cataloga y reproduce |
| Subtítulos | Bazarr | Inventaría EN/ES, busca faltantes y avisa a Jellyfin |
| Ingreso de contenido existente | Samba nativo | Expone sólo Movies/TV con autenticación para copiar desde la LAN |

El [Mermaid principal](../README.md#workflow) muestra el recorrido desde añadir un título hasta reproducirlo; el [procedimiento cotidiano](workflow.md) contiene los pasos de uso.

## Verified Connections

| Conexión | Configuración comprobada |
| --- | --- |
| Prowlarr → Sonarr | App Full Sync; Knaben y The Pirate Bay sincronizados |
| Sonarr → qBittorrent | Cliente Test/Save, categoría tv; manejo de completos ON, sin removals |
| Prowlarr → Radarr | App Full Sync; Knaben y The Pirate Bay sincronizados |
| Radarr → Prowlarr | Consultas de las fuentes gestionadas, TCP9696, API key privada |
| Radarr → qBittorrent | TCP8080, credencial vigente, categoría movies |
| Radarr → HDD | Importación/renombrado mediante hardlink real |
| Sonarr → HDD | Adopción de descargas existentes mediante hardlink real; origen conservado |
| Jellyfin → HDD | `/data/media` como `/media`, RO; raíces inicializadas y monitor probado con episodio posterior |
| Bazarr → Sonarr | API y SignalR; inventario con pistas inglesas integradas y español faltante |
| Bazarr → Radarr | API y SignalR; metadatos de películas con archivo, sin Path Mappings |
| Bazarr → HDD | Reconocimiento de integrados y SRT descargados; sólo biblioteca RW |
| Bazarr → OpenSubtitles.com | Cuenta privada, hash ON; faltantes al incorporar archivos y cada 6 h |
| Bazarr → Jellyfin | API key dedicada; Movies/Shows, Immediate; descarga ES de episodio visible sin escaneo manual |
| Tablet → Jellyfin | Reproducción LAN y selección de subtítulos incluidos, TCP8096 |
| Samba → HDD | Movies/TV sobre las bibliotecas; probe de copia autenticada y lectura desde Jellyfin comprobados; acceso Finder confirmado |

Las APIs llevan órdenes/resultados, no el video. qBittorrent recibe datos de los peers. Los proyectos Compose separados no comparten `localhost`; utilizar los endpoints verificados de la VM y no asumir DNS entre proyectos.

## Storage Contract

```text
/srv/media-server/appdata/       # NVMe: configuración y bases de datos
  jellyfin/
  qbittorrent/
  prowlarr/
  radarr/
  bazarr/
  sonarr/

/data/                          # Un filesystem ext4 en el HDD
  downloads/
    incomplete/
    movies/
    tv/
  media/
    movies/
    tv/
```

| Servicio | Montajes necesarios |
| --- | --- |
| Jellyfin | Config/cache NVMe y `/data/media:/media:ro` |
| qBittorrent | Config NVMe y `/data/downloads:/data/downloads` RW |
| Prowlarr | Sólo config NVMe; sin acceso al contenido |
| Radarr / Sonarr | Config NVMe y **un único `/data:/data` RW** cada uno |
| Bazarr | Config NVMe y sólo `/data/media:/data/media` RW; sin downloads |

UID1000/GID2000 y directorios compartidos 2770. La guarda del motor Docker exige UUID/ext4/RW correctos antes de arrancar. No aplicar `chmod 777` ni cambios recursivos sobre datos/DSM.

Samba comparte únicamente las dos carpetas de biblioteca y aplica `force group = media` a sus sesiones, sin ampliar grupos Unix del usuario. `smbd` tiene su propia dependencia de `data.mount` y la misma guarda de almacenamiento. [Acceso SMB](samba.md).

Un hardlink mantiene dos nombres del mismo dispositivo/inode, no dos copias del video. Debe comprobarse en una importación real, no sólo en un probe. Sigue ocupando espacio mientras exista un enlace; no es un backup. [Validación](validation.md#hardlink-import).

## Deployment and Recovery

Un módulo Compose por servicio, por organización; no implica un ahorro de CPU/RAM. Cada módulo conserva manifiesto, plantilla sin secretos, imagen fijada y README que enlaza su guía canónica. No crear manifests vacíos ni repetir un instalador de primer despliegue sobre estado existente.

La configuración y el HDD requieren políticas de backup distintas. Los backups internos del mismo NVMe no son copia independiente; restauración aún no probada. No publicar paneles en WAN ni añadir acceso Docker, VPN o actualizadores automáticos como efecto secundario.

## Known Limits

Adquisición nueva de series desde Sonarr, registro de colección SMB y restauración independiente siguen pendientes. La descarga ES y aviso a Jellyfin están probados con episodios; falta la prueba equivalente de película. OpenSubtitles.com puede limitar cuota o no disponer de una edición; la búsqueda automática reintenta sin garantizar un plazo. No añadir servicios auxiliares sin necesidad comprobada; [pendientes técnicos](../TODO.md).
