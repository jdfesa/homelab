# Design Decisions

Decisiones que explican la configuración reproducible; no es un historial de conversaciones ni de descargas.

| Decisión | Motivo y consecuencia |
| --- | --- |
| Una VM Debian, Compose por servicio | Separar responsabilidades sin duplicar sistemas; guías canónicas en docs y manifiestos/locks en compose |
| Configuración/bases en NVMe, contenido en HDD | Mantener appdata fuera de la biblioteca y separar recuperación de configuración/contenido |
| HDD por identidad estable y montaje UUID | No depender de nombres sdX; ext4/RW y guarda antes del arranque Docker |
| Grupo media GID2000, directorios2770 | Acceso compartido sin chmod777 ni cambio recursivo de permisos |
| Un bind común `/data` en el gestor | Permitir hardlinks entre descargas y biblioteca sin copiar el video |
| Jellyfin con biblioteca RO | Lectura/reproducción sin escrituras de NFO, artwork o subtítulos en medios |
| qBittorrent sólo con downloads | Limitar el acceso del cliente; el gestor organiza la biblioteca |
| Prowlarr sin HDD | Gestionar fuentes no requiere acceso a videos |
| Bazarr sólo con biblioteca RW y perfil EN/ES | Reutilizar pistas existentes, incluso inglés con audio inglés; OpenSubtitles.com busca faltantes por eventos/cada6h y avisa a Jellyfin. Upgrades y autosync OFF; respetar cuotas |
| Cuentas nuevas `<service>-admin` | Identificación consistente por servicio; contraseñas únicas elegidas por el propietario, fuera del repo |
| Samba nativo, recursos Movies/TV autenticados | Copiar contenido existente desde Finder sin pasar por gestores; sólo biblioteca, SMB3 cifrado y LAN, sin ampliar grupos Unix ni el montaje RO de Jellyfin |
| Imágenes por digest y actualización manual | Reconstrucción predecible; migraciones de base requieren backup/rollback compatibles |
| WebUI sólo LAN, sin UPnP ni peerport publicado | Evitar publicación automática; no implica anonimato ni garantiza conectividad con todos los peers |
| 720p/1080p en un grupo equivalente, REMUX permitido | Sin preferir una resolución, sin superiores ni mejoras automáticas; límites de tamaño predeterminados no modificados |
| Audio original 100 / inglés 10, mínimo 1 | Preferencia por metadatos del release; comprobar las pistas reales y no confundirlo con descarga de subtítulos |
| Guías públicas frente a notas temporales | Publicar pasos/configuración probados y herramientas reutilizables; actividad, ensayos e inventarios en tmp/local ignorados |

El [ejemplo de acceso qBit](qbittorrent.md#laboratory-login-example) se conserva en su sección canónica, sin duplicar valores. Cada instalación debe elegir sus propias credenciales y mantenerlas fuera del repositorio.

Las capacidades no validadas se enumeran sólo como [límites/pendientes](../TODO.md), no como procedimientos funcionales.
