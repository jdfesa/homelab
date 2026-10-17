# Media Server — Scope and Milestones

## Goal

Añadir películas o series en su gestor y reproducirlas desde la tablet sin mover archivos manualmente. Mantener configuración en NVMe y contenido en el HDD, con importaciones eficientes y una receta reproducible.

| Área | Estado comprobado | Límite |
| --- | --- | --- |
| Base y almacenamiento | Debian, Docker/Compose, red fija, HDD ext4/UUID, GID2000 y guarda de montaje | Sin prueba de desconexión física |
| Películas | Radarr → Prowlarr → qBittorrent; descarga e importación/renombrado por hardlink | Disponibilidad depende de cada fuente y de peers |
| Reproducción | Jellyfin y tablet; selección de subtítulos incluidos | No certifica todos los códecs/dispositivos |
| Detección de biblioteca | Raíz TV inicializada y episodio posterior detectado sin escaneo manual | Retardo variable; no equivale a que un archivo en copia esté listo |
| Series | Sonarr y conexiones; adopción existente por hardlink, monitor Jellyfin, manejo de completos ON | Registrar colección SMB y validar adquisición nueva desde Sonarr |
| Subtítulos | Bazarr + Radarr/Sonarr, EN/ES existentes, OpenSubtitles.com y aviso automático de episodio a Jellyfin | Cuotas/disponibilidad; registrar colección SMB y probar aviso con una película |
| Recuperación | Guardas y [runbook de instalación/recuperación](RUNBOOK.md) | Backup independiente, restauración y tiempo de reconstrucción aún no probados |

## Design Constraints

- Una VM Debian; un módulo Compose por servicio. DSM y su HDD quedan fuera del alcance.
- Un único filesystem `/data` y bind común en gestores para hardlinks. [Contrato de almacenamiento](docs/stack-plan.md#storage-contract).
- Calidad 720p/1080p equivalente, sin superiores ni mejoras automáticas. Audio original con inglés como alternativa. No se modificaron los límites de tamaño predeterminados.
- Credenciales y datos del sitio fuera de ejemplos nuevos; no publicar interfaces en WAN.
- Libros y música quedan fuera de esta etapa.

## Completion Criteria

- Una película y un episodio recorren búsqueda, descarga, importación y reproducción sin mover archivos manualmente.
- Las incorporaciones aparecen en Jellyfin sin escaneo manual.
- Los hardlinks reales se comprueban por dispositivo/inode; audio y pistas se verifican desde el cliente.
- Espacio libre, concurrencia y limpieza tienen reglas que no rompen biblioteca ni seeding.
- Existe una copia independiente y una restauración de configuración probada.

Los [pendientes técnicos](TODO.md) no son una bitácora de adquisiciones. Los pasos ya comprobados están en las guías canónicas.
