# Technical Gaps

Pendientes del sistema, no tareas por título. Al resolverlos, incorporar el procedimiento probado en su guía y retirar el pendiente.

- [ ] **Series:** registrar la colección copiada sin búsqueda/redescarga y validar una adquisición nueva iniciada por Sonarr. La adopción de descargas previas por hardlink ya está probada.
- [ ] **Retiro de torrents (después de Sonarr):** evaluar script/API + timer con cadencia por acordar (30–60 min). Retirar sólo entradas, sin borrar archivos: completos hace ≥1 h con importación confirmada; incompletos tras 24 h sin progreso real. Excluir pausas/colas y fallos de red, coordinar con Radarr/Sonarr para evitar redescargas y probar primero en simulación.
- [ ] **Subtítulos ([guía](docs/bazarr.md)):** registrar colección SMB sin búsqueda/redescarga y con perfiles; comprobar aviso automático con una película. SRT manuales en series gestionadas, OpenSubtitles.com y aviso a Jellyfin ya probados con episodios; respetar cuotas. Upgrades y autosync permanecen OFF.
- [ ] **Operación:** acordar espacio libre mínimo, concurrencia y límites de seeding; definir por separado la limpieza de archivos conservando la biblioteca.
- [ ] **Reconstrucción rápida:** destino de backup independiente, copia coherente de VM/configuración y del contenido por separado; probar recuperación del HDD existente sin formatear, restauración aislada y medir tiempo. Los instaladores actuales no restauran integraciones; cerrar esa brecha antes de prometer pocos minutos. [Runbook](RUNBOOK.md).
- [ ] **Fuentes bloqueadas:** recuperar acceso a 1337x/EZTV sólo con Test y guardado verificados. FlareSolverr no está desplegado ni garantiza resolver los bloqueos.

No repetir pruebas de URLs sin nueva evidencia ni instalar herramientas auxiliares sólo para acumular servicios. Investigación, ensayos y seguimiento temporal permanecen fuera de Git.
