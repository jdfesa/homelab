# Future Services

**Status:** Planned and research candidates, not deployed · **Updated:** 2026-10-22.

Pendientes transversales de servicios futuros y opciones a investigar. No forman parte del inventario instalado; investigar una opción no implica aprobar su instalación. Los pendientes de servicios existentes permanecen en su módulo.

## Research Candidates

- [ ] **Karakeep — research only:** evaluar si organizar enlaces, artículos y notas con búsqueda por contenido y archivado aporta valor frente a las herramientas actuales.
  - Revisar funcionamiento sin IA ni APIs de pago, consumo de recursos y mantenimiento antes de decidir su adopción. Sin instalación ni asignación de huésped aprobadas.

- [ ] **HomeBox — research only:** evaluar si un inventario doméstico con ubicaciones, fotos, documentos y garantías aporta valor para organizar pertenencias y repuestos.
  - Revisar esfuerzo de carga y mantenimiento del inventario, recursos y opciones de exportación y backup antes de decidir su adopción. Sin instalación ni asignación de huésped aprobadas.

## File Synchronization

- [ ] **Syncthing:** sincronizar carpetas y documentos seleccionados entre dispositivos.
  - Definir la topología: equipos participantes, necesidad y ubicación de un nodo en el homelab, disponibilidad y conectividad. VM/LXC, recursos y módulo responsable quedan pendientes; no asumir su incorporación a `media-server` o `homepage`.
  - Definir carpetas, permisos y sentido de sincronización; acordar tratamiento de conflictos, borrados y versionado. La sincronización no sustituye un backup independiente.
  - Antes de incorporar documentos importantes, validar el flujo con archivos de prueba, incluidos cambios, borrados y reconexión de un equipo.
