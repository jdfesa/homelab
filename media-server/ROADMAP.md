# Media Server Roadmap

**Status:** Jellyfin/qBittorrent configured; Prowlarr/Knaben ready; Radarr deployed/healthy, account and movie root folder verified; Prowlarr/Knaben sync verified; qBittorrent Test + Save confirmed by UI; profiles/naming next. Real import/playback pending · **Updated:** 2026-10-16.

## Resume Point

Leer [Session Handoff](docs/session-handoff.md): **base, almacenamiento, SSH y primer despliegue Jellyfin terminados; no reformatear ni reinstalar**. Jellyfin12.2.0 está healthy y HTTP200 desde LAN. Asistente y bibliotecas `/media/tv` y `/media/movies` completos: Media Server, English/Argentina y permiso remoto marcado por decisión del usuario (sin publicaciónWAN). Eligió continuar primero con qBittorrent, ya desplegado/healthy con rutas/categorías verificadas y primer ingreso de usuario confirmado, primera descarga aún no verificada; reproducción desde tablet/computadoras aún pendiente. No condicionar el avance a cambios de acceso/credenciales no solicitados. Automatización completa después.

## Goal

Construir un servidor multimedia propio, modular y reproducible para películas y series: seleccionar o monitorizar un título, buscarlo en fuentes autorizadas, descargarlo, organizarlo e incorporarlo a Jellyfin sin mover archivos manualmente. Reproducir desde otra computadora o tablet en la LAN.

Las cuatro capas son Prowlarr (indexadores), Radarr/Sonarr (gestión de contenido), qBittorrent (descargas) y Jellyfin (biblioteca/reproducción). Validar primero Jellyfin no reemplaza el objetivo de automatización completa. Libros y música quedan para una etapa posterior.

## Content Language Preferences

Preferencia explícita del usuario, confirmada el 2026-10-16 y aplicable a futuras pantallas/perfiles:

- **Audio:** idioma original de la obra; si no está disponible, inglés. No reemplazar automáticamente audio original no inglés por un doblaje inglés.
- **Subtítulos:** español **e** inglés disponibles para elegir durante la reproducción. El usuario aclaró que no pide ambos idiomas simultáneos en pantalla.
- **Interfaz:** English. Idioma de interfaz, metadatos, audio y subtítulos son decisiones distintas.
- Implementar esta prioridad al seleccionar versiones y configurar reproducción y el futuro gestor de subtítulos. La pantalla de metadatos de biblioteca no garantiza disponibilidad de pistas ni aplica por sí sola la prioridad de audio.

## Current State

- **Verificado previamente:** VM Debian `media-server`, 2 vCPU / 4 GiB, disco virtual de 64 GiB sobre NVMe, Guest Agent, IPv4 fija terminada en `.104`, Docker/Compose oficiales y prueba `hello-world`.
- **Acceso SSH verificado:** pública dedicada instalada para UID1000 preservando claves, conexión directa `publickey` probada con host key estricta; sin conceder pública root, sudo sin contraseña ni acceso Docker. Política global sshd intacta; contraseña temporal pendiente de rotación privada.
- **HDD preparado y verificado:** borrado autorizado y ejecutado; `scsi1` por `by-id`, RW, GPT+ext4 y `/data` por UUID, directorios/permisos y probe de hardlinks sin root. Montaje, IP y servicios comprobados después de reiniciar sólo VM102. DSM sin cambios. Ver [Storage Guide](docs/storage-guide.md).
- **Guardas verificadas:** Docker requiere `/data` y UUID/ext4/RW correctos; prueba negativa en namespace privado sin desmontar volumen global. No se probó desconexión física.
- **Jellyfin desplegado:** imagen oficial12.2 fijada por digest, servidor12.2.0; Compose propio, config/cacheNVMe, bibliotecaRO, UID1000:GID2000 y sóloTCP8096 sobreIPv4privada. Healthy, permisos y HTTP200 desdeMac verificados; asistente/bibliotecas completos; prueba de reproducción pendiente. Ver [módulo Jellyfin](compose/jellyfin/README.md).
- **qBittorrent desplegado:** LinuxServer5.2.4 por digest, app UID1000:GID2000/UMASK002, configNVMe y sólo `/data/downloads` RW, WebUI8080 privada, sin peerportpublicado y ambos UPnP OFF. API/rutas/categorías verificadas, cero torrents, primer login confirmado, primera descarga pendiente de verificar. Ver [guía qBittorrent](docs/qbittorrent.md).
- **Prowlarr desplegado:** LinuxServer2.6.5.5623 por digest; sólo configNVMe y TCP9696IPv4privada, sin HDD. Healthy/APIversión verificados; Knaben guardado/habilitado;1AppRadarr/FullSync yKnaben(Prowlarr) enRadarr verificados porAPI/captura. ClienteqBit enRadarr guardado/habilitado por UI trasTest correcto; falta prueba real. **AutenticaciónForms/Enabled guardada y verificada**, web anónima va/login; intento1337x bloqueado por Cloudflare, sin guardar esa fuente; solución aplazada por el usuario, no descartada, con seguimiento en [TODO](TODO.md#prowlarr--recuperar-acceso-a-1337x). Knaben guardado y habilitado: Test exitoso reportado y capturaIndexers1/Enabled1. EZTV no guardado; usuario confirma bloqueo en todas las URLs ofrecidas. No repetir esas pruebas. Recomendación: continuar gestores con Knaben y evaluar FlareSolverr después. Ver [TODO EZTV](TODO.md#prowlarr--verificar-acceso-a-eztv). BootstrapNone es sólo estado histórico inicial. Ver [guía Prowlarr](docs/prowlarr.md).
- **Radarr desplegado:**6.4.4.10685-ls321 por digest; configNVMe y único `/data` RW, UID1000:GID2000/UMASK002, sólo7878LAN, healthy/API/identidad/montajes y probeFS comprobados. DSM y servicios existentes sin cambios. **Cuenta Forms/Enabled guardada y verificada**, username `radarr-admin` del formulario aprobado; raíz `/data/media/movies` guardada y accesible; Knaben sincronizado de Prowlarr conRSS/búsquedas activadas; cliente qBit Test + Save confirmados por UI; perfiles/renombrado e importación real pendientes. [Guía Radarr](docs/radarr.md).
- **Pendiente multimedia:** aplicaciones/integraciones, importación real, gestor de subtítulos y backup/restore. Clientes iniciales confirmados: tablet y computadoras; sistema/códecs aún por revisar. Música y libros después.

El usuario aceptó la separación descargas/biblioteca y autorizó explícitamente GPT+ext4 y `/data`; se completó esa preparación sin desplegar aplicaciones. No repetir formato sobre el contenido futuro. Los scripts usados están en [scripts/README.md](scripts/README.md), con destinos, requisitos y límites de seguridad. Ver [Post-install Guide](docs/post-install-guide.md) para la base, SSH verificado y rotación privada aún pendiente.

## Architecture and Boundaries

- **Ownership del módulo:** guías/decisiones en `docs/`, automatización en `scripts/`, pruebas en `tests/` y evidencia privada en `.local/`, cada sección documentada desde su README. El índice homelab sólo enlaza y conserva hechos transversales, no duplica pasos de esta VM.
- Una VM Debian con servicios Docker Compose modulares; no una VM por capa.
- HDD nuevo de 2 TB dedicado a multimedia y exclusivo de esta VM. DSM y su HDD permanecen intactos.
- Asignación por `/dev/disk/by-id`, `ro=0`, GPT y una partición ext4 montada por UUID en `/data`, todo verificado. Identificadores reales sólo en evidencia privada; nunca seleccionar por nombre `sdX`.
- SO, bases de datos y configuración en NVMe bajo `/srv/media-server/appdata/`; descargas y bibliotecas en el HDD.
- Un Compose por servicio, confirmado por el usuario para organización; `compose/jellyfin/` y `compose/qbittorrent/` ya desplegados. No duplicar bajo `docker/` ni crear archivos vacíos sin validar; uno/varios archivos no es una optimización de CPU/RAM.
- Acceso inicial sólo LAN. No publicar paneles en Internet ni sumar VPN, actualizadores automáticos o aceleración de video sin evaluación separada.
- Datos de runtime, secretos y detalles privados del equipo fuera del repositorio. Un solo HDD no aporta redundancia y el backup de la VM no incluye automáticamente un disco físico asignado.

## Storage Semantics

La estructura está **creada y montada** en ext4. Ambas ramas comparten un filesystem; no contienen todavía contenido multimedia:

```text
/data/                      # Una partición del HDD
├── downloads/              # Archivos gestionados por qBittorrent
│   ├── movies/
│   └── tv/
└── media/                  # Biblioteca organizada para Jellyfin
    ├── movies/
    └── tv/
```

### Paths Are Not Copies

Repetir los nombres `movies` y `tv` clasifica por tipo de contenido en dos contextos distintos; por sí solo no duplica archivos. `downloads` conserva nombres y estructura del torrent para descargar/compartir. `media` contiene nombres y carpetas organizados por Radarr/Sonarr para Jellyfin.

El objetivo es **hardlink al importar un archivo terminado que continúa compartiéndose**, no una segunda copia del video. Dos rutas apuntan al mismo archivo (mismo dispositivo e inode). Un video de 10 GB ocupa aproximadamente 10 GB de datos, no 20 GB, más un pequeño coste de metadatos. Esto no deduplica copias previas ni versiones distintas de una película.

Un hardlink no es un enlace simbólico ni un backup. Eliminar un nombre no elimina el otro; los datos siguen ocupando espacio mientras quede algún enlace (o un proceso los mantenga abiertos). Modificar el contenido del archivo en el sitio modifica lo visto por ambos nombres; no habilitar tareas que reescriban videos compartidos sin evaluarlas.

### Conditions and Failure Modes

- Descarga y biblioteca deben estar en el mismo filesystem montado, no en particiones distintas ni una en NVMe y otra en HDD.
- Radarr y Sonarr deben recibir un único bind mount común `/data:/data`; no montar descargas y biblioteca por separado dentro de esos contenedores. Estar en el mismo disco físico no basta.
- Configurar la importación mediante hardlinks en Radarr/Sonarr y permisos compatibles con el cliente de descarga; una casilla activada no prueba que funcione.
- qBittorrent sólo necesita `/data/downloads`; Jellyfin sólo `/data/media`, preferentemente de sólo lectura. Los nombres internos deben ser coherentes entre aplicaciones.
- Si falla el hardlink, una importación puede terminar en copia y consumir el doble. Detectar y corregir ese caso antes de dar la automatización por terminada.
- No usar `downloads` como raíz de biblioteca ni limpiar torrents activos con borrados indiscriminados. Acordar seeding y limpieza mediante el cliente/gestores, conservando la biblioteca.
- Archivos incompletos, extras, subtítulos, otra calidad o una actualización todavía no limpiada pueden ocupar espacio adicional legítimo. Los hardlinks no eliminan ese consumo.

### Acceptance Check

La prueba debe importar realmente una película y un episodio mediante Radarr/Sonarr, manteniendo su descarga disponible para compartir. Dentro de Debian, comparar los dos archivos de cada importación con GNU `stat` (sustituir las variables por sus rutas reales):

```sh
stat -c 'device=%d inode=%i links=%h bytes=%s %n' -- "$DOWNLOAD_FILE" "$LIBRARY_FILE"
```

Aceptar sólo si ambos nombres tienen **el mismo dispositivo y el mismo inode**, con al menos dos enlaces. No basta con que coincidan tamaño o hash: dos copias también pueden coincidir. El tamaño que muestra un explorador al sumar las dos rutas tampoco demuestra consumo doble.

Se comprobó soporte de hardlinks en Debian con UID1000/GID2000, sin root: mismo dispositivo/inode, dos enlaces y supervivencia del segundo nombre al borrar el primero. La prueba **mediante importaciones reales de Radarr/Sonarr sigue pendiente**; no confundirla con el probe del filesystem ni con tests locales.

### Efficiency Policy

- Evitar una lectura y escritura completas adicionales del video al importar mediante hardlinks; no prometer que toda la actividad de disco se reduce a la mitad.
- Descarga, reproducción, seeding, verificaciones y backups seguirán generando E/S. Mantener configuración y bases de datos en NVMe; ajustar concurrencia y tareas intensivas después de medir.
- No inferir una mejora concreta de vida útil del HDD a partir de los bytes evitados. Revisar salud, temperatura y carga, manteniendo backups independientes.
- No sacrificar integridad para optimizar: no desactivar journaling, verificaciones necesarias ni políticas seguras de escritura.

## Milestones

| Phase | Work | Exit criterion | State |
| --- | --- | --- | --- |
| 0 — Base | Debian, red fija, Guest Agent, Docker/Compose | Servicios base y `hello-world` verificados; red/servicios persistentes tras reinicio | Completed |
| 1 — Design and access | Diseño de rutas acordado; instalar pública aprobada | Diseño revisado y conexión SSH key-only probada; claves preservadas | Completed; no further access changes requested |
| 2 — Storage | Borrado autorizado; GPT/ext4, montaje UUID, GID2000/2770 y probe sin root | HDD en `/data`, DSM intacto y hardlinks de filesystem comprobados; importaciones de apps en fase5 | Completed |
| 3 — Mount safety | Dependencias Docker, chequeo UUID, prueba negativa namespace y reinicio | Red/montaje/servicios persistentes; guarda rechaza montaje ausente y directorio SO vacío | Completed; physical removal not tested |
| 4 — Playback | Jellyfin desplegado y configurado; contenido autorizado de prueba pendiente | Película y episodio reproducibles desde otro dispositivo LAN, perfil compatible con el hardware | Container/HTTP and wizard verified; playback pending |
| 5 — Automation | Desplegar qBittorrent, Prowlarr, Radarr y Sonarr; integrar APIs, categorías, raíces y perfiles | Búsqueda, descarga, importación por hardlink y actualización de Jellyfin sin mover archivos manualmente | qBittorrent configured; Prowlarr/Knaben configured; Radarr healthy, account/root and Knaben sync verified; qBittorrent client Test/Save confirmed by UI; profiles/naming and real import pending; Sonarr not deployed |
| 6 — Operations | Fijar versiones, backup/restore, actualización/rollback, espacio libre y limpieza | Restauración probada; guía permite reconstruir configuración e integraciones sin secretos en Git | Pending |
| 7 — Expansion | Evaluar libros y música | Nuevo alcance y herramientas acordados, sin comprometer lo anterior | Deferred |

No marcar una fase como completada sólo por instalar sus contenedores. Registrar evidencia privada de las pruebas y actualizar el estado público sin direcciones completas, credenciales ni seriales.

## Next Step After qBittorrent

Con **Knaben guardado y habilitado** en Prowlarr y **Radarr ya desplegado**, **cliente qBit ya guardado/habilitado tras Test correcto**. Revisar ahora perfiles/renombrado de Radarr; cuenta, raíz `/data/media/movies` y sincronización de Knaben desde Prowlarr ya verificadas antes de probar una película completa; Sonarr después. El usuario confirma que todas las URLs de EZTV están bloqueadas;1337x/EZTV y la evaluación de FlareSolverr quedan registrados en TODO, sin instalación auxiliar autorizada todavía. La descarga manual era sólo una prueba opcional; no condiciona avanzar. El uso final consiste en agregar títulos en Radarr/Sonarr y reproducirlos en Jellyfin, no buscar torrents manualmente desde el cliente. Usuario confirmó que no inició descarga manual y que cambió la contraseña qBit; continuar perfiles/renombrado de Radarr sin exigir esa prueba manual.

## Decisions Still Open

- Este formato ya fue autorizado y ejecutado; no repetirlo para resolver fallos de montaje.
- Fuentes/indexadores autorizados, disponibilidad y requisitos de acceso.
- Calidad, tamaño y versiones adicionales por definir; idiomas ya acordados arriba, falta implementarlos/verificarlos en fuentes, reproducción y gestor de subtítulos.
- Política de seeding, retirada de torrents, descargas fallidas y limpieza segura.
- Margen mínimo de espacio libre, alertas y límites de concurrencia.
- Clientes/dispositivos y formatos objetivo; preferir reproducción directa y medir antes de exigir transcodificación a esta VM.
- Destino, retención y pruebas de backup para configuración, secretos y contenido que se quiera preservar.

## Completion Definition

- [ ] Una película y una serie recorren las cuatro capas y se reproducen en otro dispositivo sin mover archivos manualmente.
- [ ] Un episodio futuro de la serie monitorizada se incorpora automáticamente cuando una fuente configurada ofrece una versión compatible.
- [ ] Las importaciones que siguen compartiéndose usan hardlinks comprobados, sin segunda copia del mismo video.
- [ ] La limpieza acordada no rompe biblioteca ni torrents activos; el espacio libre se controla.
- [x] El reinicio restaura red, montaje y servicios; la guarda rechaza montaje ausente en namespace privado y el directorio SO está vacío. Desconexión física no probada.
- [ ] Configuración, integraciones, versiones y restauración quedan documentadas y probadas.

No se garantiza encontrar cualquier título: depende de fuentes disponibles, acceso autorizado y perfiles configurados.

## Related Documents and Sources

- [Storage Guide](docs/storage-guide.md) — asignación aplicada, comprobaciones y límite previo al borrado.
- [Stack Plan](docs/stack-plan.md) — responsabilidades, montajes y módulos Compose.
- [Setup Guide](docs/setup-guide.md) — instalación Debian y opciones importantes de Proxmox.
- [Post-install Guide](docs/post-install-guide.md) — preparación ya aplicada y recuperación de red.
- [Servarr Docker Guide](https://github.com/Servarr/Wiki/blob/master/docker-guide.md) — coherencia de rutas y montajes para importaciones eficientes.
- [Linux link(2)](https://man7.org/linux/man-pages/man2/link.2.html) — semántica y límites de los hardlinks.
