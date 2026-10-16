# Media Server Decision Log

**Status:** Accepted decisions and verified boundaries · **Updated:** 2026-10-16.

## Accepted Decisions

| Date | Decision | Reason / consequence |
| --- | --- | --- |
| 2026-10-15 | Módulo autocontenido `media-server/` con README y roadmap | Configuración, guías, scripts, pruebas y decisiones de esta VM tienen un único dueño; raíz homelab sólo índice y elementos compartidos |
| 2026-10-15 | Películas y series primero; libros y música después | Conservar automatización completa en cuatro capas sin incorporar todas las alternativas del video |
| 2026-10-15 | VM Debian con Compose modular y HDD propio; DSM independiente | Separar SO/configuración sobre NVMe de contenido; no montar ni modificar el HDD DSM desde otro huésped |
| 2026-10-15 | Preparar red fija y Docker/Compose oficiales | Base verificada; dirección completa, claves y detalles del sitio sólo en evidencia privada |
| 2026-10-15 | Asignación inicial del HDD por `by-id`, temporalmente RO | Proteger NTFS mientras se pedía confirmación exacta de borrado; hotplug verificado sin apagar VMs |
| 2026-10-15 | Tras autorización, GPT/ext4 y `/data` por UUID | Journaling, perfil largefile, 1% reservado, grupo media GID2000 y directorios2770; prueba de reinicio correcta aunque cambió el nombre sdX |
| 2026-10-15 | Downloads y biblioteca separados con hardlinks | Evitar segunda copia del video; probe de filesystem sin root correcto, importaciones reales Radarr/Sonarr aún pendientes |
| 2026-10-15 | Docker requiere el montaje y UUID correctos | Impedir escrituras al SO si falta el HDD; comprobación negativa en namespace privado, sin desconectar físicamente el disco |
| 2026-10-15 | Scripts públicos parametrizados con README interno | No publicar series, UUID reales, direcciones o credenciales; guardar versiones y pasos realmente ejecutados |
| 2026-10-15 | Tests, guías y evidencia privada dentro del módulo | Pruebas portables desde este directorio; `.local/` ignorado; el índice global sólo enlaza, no duplica recetas |
| 2026-10-16 | Pública SSH dedicada sólo para el usuario Debian | Instalación autorizada, backup y prueba directa `publickey`; sin cambios a sshd/sudo/grupos, sin pública root; contraseña temporal aún debe cambiarse privadamente |
| 2026-10-16 | Tablet y computadoras como clientes Jellyfin iniciales | Validar reproducción LAN en ambos; no asumir códecs compatibles ni reproducción directa antes de probar contenido |
| 2026-10-16 | Un Compose por servicio, confirmado por el usuario | Modularidad organizativa; no duplicar VM/motorDocker ni atribuir ahorro de recursos al número de archivos |
| 2026-10-16 | Jellyfin configurado con capturas finales como referencia | Shows `/media/tv`, Movies `/media/movies`, metadatosEnglish/Argentina y cuentaejemplo `jellyfin-admin`; password fuera de guía |
| 2026-10-16 | Permiso remotoJellyfin marcado por elección del usuario | No implica publicaciónWAN; no configurar router/VPN/proxy por esta elección |
| 2026-10-16 | Cliente de descargas antes de prueba manual de reproducción | Usuario prefiere continuar qBittorrent; playback se valida con primer contenido autorizado |
| 2026-10-16 | Una guía canónica por servicio en docs | Pedido explícito de reproducibilidad/orden; Compose sólo manifiestos, plantilla, lock y README de enlace |
| 2026-10-16 | qBittorrent5.2.4 desplegado con acceso mínimo | ConfigNVMe, sólo downloadsHDD, PUID1000/PGID2000/UMASK002, WebUI LAN, sin peerportpublicado ni UPnP; categorías movies/tv, cero torrents; login de usuario pendiente |
| 2026-10-16 | Contraseña permanente qBit cambiada por el usuario; prueba manual no iniciada | Documentar ciclo temporal→permanente y uso futuro en gestores sin registrar valor; continuar automatización modular con Prowlarr |
| 2026-10-16 | Prowlarr2.6.5.5623 desplegado como módulo propio | ConfigNVMe única, sin HDD, puerto9696privado; primero altaForms/Enabled del usuario, después fuentes/apps. Sin descargas ni integraciones automáticas aún |
| 2026-10-16 | Ejemplo público de acceso qBittorrent por solicitud expresa del propietario | Única excepción a la regla de secretos privados: [valor canónico en su guía](qbittorrent.md#laboratory-login-example), sin duplicarlo en Compose/scripts/JSON; llamarlo ejemplo no lo oculta ni autoriza publicar otras claves |
| 2026-10-16 | Radarr → qBittorrent probado y guardado con capturas originales | Categoría movies, API Key vacía, ambos Remove OFF y sin mapping; Test verde y tarjeta Enabled tras Save. La IP LAN del formulario original es evidencia del sitio, no una plantilla reutilizable. Perfiles/renombrado y E2E pendientes |
| 2026-10-16 | Diagrama Mermaid y tabla de avance en README | Mostrar conexiones comprobadas frente a recorridos futuros; actualizar junto a guía, capturas, handoff, roadmap/TODO y vm-config al cerrar cada paso; no equiparar configuración con descarga/importación/playback |

## Execution and Safety Record

Se preparó la base y el HDD tras autorizaciones explícitas. El primer intento del preparador abortó antes de borrar por falta de `fuser`; se instaló únicamente `psmisc` y se documentó la dependencia. Se hicieron dos reinicios controlados de esta VM, ninguno de DSM. Configuración y proceso DSM permanecieron intactos. No se cambiaron contraseñas ni sudoers.

La pública SSH dedicada fue instalada el 2026-10-16; conexión directa con clave y huella estricta verificada. Pruebas negativas confirman que no se concedió sudo sin contraseña ni acceso al socket Docker. Configuración efectiva sshd y grupos coinciden antes/después; DSM conserva configuración y proceso. No se reiniciaron VMs en esta instalación. Contraseña temporal pendiente de rotación privada; autenticación global por contraseña no se deshabilitó. Jellyfin12.2.0 ya está desplegado/healthy, con asistente y bibliotecas completados y HTTP200 LAN. La receta completa de adquisición/reproducción sigue sin verificar. Ver [Post-install Guide](post-install-guide.md), [Storage Guide](storage-guide.md) y [Roadmap](../ROADMAP.md).

El ordenamiento del repositorio del 2026-10-15 fue local; no confundirlo con la instalación SSH del día siguiente. Los informes privados conservan las rutas históricas de su ejecución; consultar las rutas actuales del módulo para operar, no copiar destinos sdX de logs antiguos.

## Remaining Decisions

Fuentes autorizadas, perfiles de calidad/idioma, política de seeding/limpieza, versiones de imágenes, identidades de contenedores y backup/restore: ver el Roadmap. Una propuesta no se declara completada sólo por documentarla o instalar un contenedor.
