# Media Server Documentation

Operational documentation for this VM only. Start at the module [README](../README.md) and follow the [Roadmap](../ROADMAP.md); do not repeat a completed destructive step.

| Guide | Scope |
| --- | --- |
| [Session handoff](session-handoff.md) | Last verified state, exact next steps and safety boundaries for the next session |
| [Service access directory](service-access.md) | Tabla central de servicios, puertos publicados y URLs de referencia; URLs clicables reales en `.local/`; texto reutilizable con placeholders |
| [Setup](setup-guide.md) | Proxmox wizard, Debian installation and reviewed screenshots |
| [Post-install](post-install-guide.md) | Applied base packages, fixed IP, SSH status and network recovery |
| [Storage](storage-guide.md) | Authorized GPT/ext4 preparation, `/data`, permissions, mount guards and verification |
| [Jellyfin](jellyfin.md) | Guía propia: versión, despliegue, rutas, asistente completo con capturas aprobadas y verificaciones |
| [qBittorrent](qbittorrent.md) | Guía propia: cliente de descargas, imagen fijada, rutas/categorías, acceso inicial, verificación y operación |
| [Prowlarr](prowlarr.md) | Guía propia: imagen/Compose, persistencia NVMe, alta inicial de autenticación y futuras fuentes/integraciones |
| [Radarr](radarr.md) | Guía propia ordenada: prerrequisitos, imagen/Compose, despliegue, cuenta/raíz y Knaben verificados; cliente qBit Test + Save confirmado por UI con capturas; perfiles/renombrado, película de prueba y aceptación pendientes |
| [Stack plan](stack-plan.md) | Four automation layers, shared paths and future Compose integration |
| [Decision log](decision-log.md) | Module-specific choices, rationale and evidence boundaries |

Prose guides use Spanish with English headings. Host-wide conventions are referenced from the repository's shared docs, not copied here. Runtime data and private evidence belong in this module's ignored `.local/` directory, not in public documentation.

## Service Documentation Convention

Cada servicio configurado tiene **una guía canónica propia en `docs/<servicio>.md`**, no una guía operativa duplicada en su carpeta Compose. Debe registrar:

1. Responsabilidad, alcance y estado real (preparado, desplegado, configurado, verificado).
2. Versión, origen y digest de imagen, requisitos y límites.
3. Rutas persistentes NVMe/HDD, permisos, puertos y dependencias.
4. Receta reproducible de despliegue con entradas privadas separadas.
5. Configuración paso a paso con nombres reales de campos, valores elegidos y capturas finales aprobadas.
6. Verificaciones realizadas y pendientes, operación, actualización/rollback y backup/restore.
7. Fuentes primarias y decisiones relevantes, sin secretos por defecto. Única excepción autorizada: [ejemplo de acceso qBit del laboratorio](qbittorrent.md#laboratory-login-example); no publicar otras contraseñas ni API keys.
8. Entrada actualizada en el [catálogo de accesos](service-access.md) y su copia local con las URLs reales, al agregar un servicio o cambiar su puerto.

`compose/<servicio>/` conserva manifiesto, plantilla de entorno, lock de imagen y README corto que enlaza esta guía. Las capturas permanecen en `images/`; scripts y tests en sus carpetas propias. Una guía no demuestra por sí sola que un despliegue o prueba ya se haya completado. Al cerrar cada paso, actualizar el diagrama/tabla del README, esta guía canónica, handoff, roadmap/TODO y vm-config, distinguiendo evidencia UI, API y aceptación real.
