# Homelab — Criterios de trabajo

## Documentación que aporta valor

- Usar siempre nombres en inglés para recursos, carpetas compartidas, identificadores y configuraciones; la explicación al usuario puede estar en español.
- Para nuevas cuentas administrativas de servicios, usar `<service>-admin` (por ejemplo `bazarr-admin`). El propietario establece las contraseñas, únicas por servicio; no migrar otras cuentas sin solicitud.
- El repositorio es una guía reproducible, **no una transcripción de conversaciones ni una bitácora del agente**.
- Publicar configuraciones finales verificadas, pasos ejecutados con éxito, requisitos, límites conocidos, resolución de problemas y tips que ayuden a repetir el resultado.
- No publicar pedidos individuales de contenido, listas de descargas, torrents/hashes, velocidades, contadores de cola, autorizaciones conversacionales, próximos clics ni cronologías de sesión.
- Mantener un solo procedimiento canónico por servicio. Los README enlazan; no repiten el historial en README, roadmap, TODO y JSON.
- Documentar límites relevantes sin presentar planes como funcionalidad instalada. Los pendientes públicos deben ser breves y técnicos, no tareas por cada película o serie.

## Lectura progresiva y reconstrucción

- En `media-server`, empezar por `RUNBOOK.md` y `TODO.md`; abrir después sólo la sección de la guía necesaria. No cargar todo `docs/`, capturas o evidencia privada por rutina.
- Mantener el runbook breve: orden, motivo, requisito y enlace. Comandos específicos en la receta canónica; no duplicarlos ni conservar una nueva bitácora de pasos.
- Diferenciar primer despliegue de restauración. No prometer reconstrucción en minutos sin una restauración probada y cronometrada; Git/Compose no sustituyen appdata ni backup del contenido.

## Temporal frente a reutilizable

- Guardar notas de trabajo, handoffs, investigación no adoptada, pruebas incompletas y capturas transitorias en **`tmp/<modulo>/`**, excluido de Git. Consultarlas para continuar; no trasladarlas enteras a las guías al cerrar un turno.
- Usar `.local/` para valores persistentes del sitio y evidencia privada. `tmp/` no es un almacén seguro de credenciales.
- Promover a `scripts/` sólo herramientas reutilizables y probadas, con destino de ejecución, parámetros, guardas y límites documentados. Los scripts de una descarga o intervención concreta permanecen locales.
- Las pruebas del repo validan contratos y comportamiento reproducible, no que una descarga concreta exista o conserve cierto progreso.

## Capturas y diagramas

- Conservar capturas reales útiles de la configuración final o de un paso necesario para reproducirla; no publicar cada pantalla intermedia.
- No presentar imágenes generadas/editadas como prueba de una configuración real.
- Los diagramas deben explicar dónde empieza el usuario y cómo circula el trabajo, diferenciando lo comprobado de lo pendiente, sin nombres de adquisiciones personales.

## Seguridad y validación

- No cambiar servicios, descargas, discos, red ni credenciales para hacer una limpieza documental. Preservar trabajo previo y archivar antes de retirar evidencia.
- No repetir preparación destructiva ni intervenir en DSM para avanzar el módulo multimedia.
- Mantener secretos y datos del sitio fuera de ejemplos nuevos; usar placeholders. No ampliar excepciones existentes de publicación.
- Antes de crear un archivo de credenciales, comprobar con Git que su ruta está ignorada y no está ya seguida. Separar credenciales del cliente API de los `.env` de despliegue; no imprimir secretos al validar acceso.
- Prefijar comandos de shell con `rtk`, según las instrucciones RTK del entorno.
- Ejecutar las pruebas pertinentes y `git diff --check`. No hacer commit/push sin solicitud.
