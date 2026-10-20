# Future Services

**Status:** Planned, not deployed · **Updated:** 2026-10-20.

Pendientes transversales de servicios futuros. No forman parte del inventario instalado; los pendientes de servicios existentes permanecen en su módulo.

## File Synchronization

- [ ] **Syncthing:** sincronizar carpetas y documentos seleccionados entre dispositivos.
  - Definir la topología: equipos participantes, necesidad y ubicación de un nodo en el homelab, disponibilidad y conectividad. VM/LXC, recursos y módulo responsable quedan pendientes; no asumir su incorporación a `media-server` o `homepage`.
  - Definir carpetas, permisos y sentido de sincronización; acordar tratamiento de conflictos, borrados y versionado. La sincronización no sustituye un backup independiente.
  - Antes de incorporar documentos importantes, validar el flujo con archivos de prueba, incluidos cambios, borrados y reconexión de un equipo.
