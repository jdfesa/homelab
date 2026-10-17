# Media Server

Servidor multimedia sobre Debian con servicios multimedia Docker Compose independientes y acceso a archivos mediante Samba nativo. Configuración y bases de datos en NVMe; descargas y biblioteca en un HDD ext4 montado en `/data`.

**Comprobado:** búsqueda y descarga de películas, importación/renombrado mediante hardlink y reproducción desde una tablet con selección de subtítulos incluidos. También se comprobaron adopción de series por hardlink y detección automática de episodios en Jellyfin tras inicializar TV. La adquisición nueva de series desde Sonarr sigue por validar.

## Start Here

**[RUNBOOK — orden de instalación y recuperación](RUNBOOK.md)**. Es la entrada breve para reconstruir el servidor; las guías de cada servicio se consultan sólo cuando corresponden. El objetivo de pocos minutos aún requiere backup y restauración medidos.

## Workflow

| Acción | Interfaz |
| --- | --- |
| Buscar y añadir una película | **Radarr → Add New**, TCP7878 |
| Añadir series y temporadas | **Sonarr**, TCP8989; adopción existente probada |
| Copiar películas/series que ya existen en otro equipo | **Finder → SMB Movies/TV**, TCP445; [guía](docs/samba.md) |
| Revisar idiomas y subtítulos faltantes | **Bazarr**, TCP6767; EN/ES existentes y búsqueda automática de faltantes |
| Ver contenido de la biblioteca | **Jellyfin**, TCP8096 |

Prowlarr y qBittorrent trabajan detrás del gestor para adquirir contenido nuevo. Una colección existente entra por SMB sin pasar por ellos. El buscador de Jellyfin consulta la biblioteca existente.

```mermaid
flowchart TB
    request["Elegir un título"]
    radarr["Películas: Radarr"]
    sonarr["Series: Sonarr"]
    search["El gestor consulta fuentes mediante Prowlarr"]
    download["qBittorrent descarga de los peers"]
    organize["El gestor importa y renombra mediante hardlink"]
    library["Biblioteca organizada en el HDD"]
    existing["Copiar contenido existente: SMB Movies/TV"]
    register["Registrar colección existente en Radarr/Sonarr; sin redescarga"]
    manual["Torrent manual: categoría y ruta; título registrado en el gestor"]
    scan["Jellyfin incorpora el contenido"]
    watch["Reproducir en la tablet y elegir pistas"]
    bazarr["Bazarr: perfil EN/ES e inventario de pistas existentes"]
    providers["Faltantes: OpenSubtitles.com; sujeto a cuotas"]
    subtitles["Subtítulos externos junto al video"]
    request --> radarr
    request --> sonarr
    request --> manual
    radarr --> search
    sonarr -.->|"Nueva adquisición por validar"| search
    sonarr -->|"Adopción existente comprobada"| organize
    search --> download
    manual --> download
    download --> organize
    organize --> library
    existing --> library
    existing -.->|"Registro de colección SMB pendiente"| register
    register -.-> bazarr
    radarr -->|"Metadatos de películas gestionadas"| bazarr
    sonarr -->|"Metadatos de series gestionadas"| bazarr
    library -->|"Lectura de pistas existentes"| bazarr
    bazarr -->|"Sólo faltantes: eventos y cada 6 h"| providers
    providers --> subtitles
    subtitles --> scan
    bazarr -->|"Aviso API: refresco de episodio comprobado"| scan
    library -->|"Inicialización requerida; monitor de episodios probado"| scan
    scan --> watch
```

El recorrido de películas está probado. Sonarr ya adopta descargas existentes con hardlinks y Jellyfin detecta episodios nuevos; falta validar una adquisición nueva iniciada por Sonarr. Las líneas discontinuas representan capacidades pendientes; Bazarr busca EN/ES faltantes y avisa a Jellyfin; descarga externa y refresco automático de episodio comprobados, sujetos a disponibilidad/cuotas. El contenido copiado por SMB requiere registro adicional en el gestor para aparecer en Bazarr. Prowlarr devuelve resultados/enlaces; los videos llegan desde los peers. [Uso cotidiano](docs/workflow.md) · [Mapa técnico](docs/stack-plan.md).

## Storage and Boundaries

- `/srv/media-server/appdata/`: configuración y bases de datos en NVMe.
- `/data/downloads/{movies,tv}`: archivos gestionados por qBittorrent.
- `/data/media/{movies,tv}`: biblioteca organizada para Jellyfin.
- Radarr y Sonarr usan **un único bind `/data:/data`** para permitir hardlinks. Bazarr sólo recibe `/data/media` RW para archivos de subtítulos. Jellyfin recibe la biblioteca como `/media`, de sólo lectura.
- Un hardlink evita otra copia del mismo video; no es un backup. El disco físico no queda respaldado automáticamente con el disco virtual de la VM.
- Mantener DSM y su HDD fuera del alcance de este módulo. No publicar paneles en Internet ni cambiar router/VPN como efecto secundario.

## Reference

- [Índice de guías](docs/README.md) y [accesos](docs/service-access.md).
- [Scripts reutilizables](scripts/README.md), [contratos/pruebas locales](tests/README.md) y [módulos Compose](compose/README.md).
- [Configuración de referencia](vm-config.json): no es un export ejecutable de Proxmox ni un inventario de descargas.
- [Política de Radarr](docs/radarr-profile-policy.json): declarativa; resolver IDs por nombre en cada instalación.
- [Decisiones de diseño](docs/decision-log.md), [alcance y límites](ROADMAP.md) y [pendientes técnicos](TODO.md).

Los valores del sitio permanecen en `.local/`. Las notas de trabajo y pruebas transitorias van en `tmp/`, fuera de Git. La guía conserva procedimientos comprobados, no una bitácora por título descargado. El [ejemplo de acceso qBit](docs/qbittorrent.md#laboratory-login-example) ilustra los campos; no reutilizar sus valores en otras instalaciones.
