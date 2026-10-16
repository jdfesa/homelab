# Media Server TODO

**Updated:** 2026-10-16. Seguimiento de tareas concretas aplazadas; las fases y demás hitos siguen en el [Roadmap](ROADMAP.md). Los procedimientos por servicio viven en `docs/`.

## Prowlarr — Recuperar acceso a 1337x

- [ ] **Pendiente, no descartado:** conseguir que `1337x` funcione desde Prowlarr. El usuario decidió retomarlo después; la validación continúa usando Knaben y Radarr.

**Último resultado:** con Base Url `https://1337x.to/`, Save devolvió `Unable to access 1337x.to, blocked by CloudFlare Protection.` Una consulta posterior confirmó cero indexadores guardados. Ver [diagnóstico y captura del intento](docs/prowlarr.md#1337x-save-attempt--cloudflare-blocked); no es una configuración funcional aprobada.

### Al retomarlo

- [ ] Revalidar versiones/definición y reproducir el problema de acceso mediante **Test**, conservando el error sin exponer secretos.
- [ ] Evaluar una solución compatible con Prowlarr; **FlareSolverr es un candidato, no una solución ya elegida ni garantizada**.
- [ ] Si se añade un servicio auxiliar, preparar su propio `compose/<servicio>/` y `docs/<servicio>.md`, con imagen fijada, persistencia y red documentadas; no modificar router/VPN/DSM como efecto secundario.
- [ ] Para una eventual integración FlareSolverr, comprobar alcance entre contenedores, etiquetas coincidentes en proxy/indexador e IP de salida común según la [FAQ oficial](https://github.com/Servarr/Wiki/blob/master/prowlarr/faq.md#can-i-use-flaresolverr-indexers).
- [ ] Obtener **Test exitoso**, guardar sin forzar y confirmar que `1337x` permanece en el listado y sigue superando Test.
- [ ] Actualizar la guía Prowlarr, captura final aprobada, `vm-config.json` y handoff con la solución realmente probada, versiones y fecha. Recién entonces cerrar esta tarea.

**Límite:** no marcarlo resuelto por guardar un indexador que sigue fallando ni por tener un contenedor auxiliar healthy. Los bloqueos del sitio pueden cambiar; no se promete éxito antes de verificarlo.

## Prowlarr — Verificar acceso a EZTV

- [ ] Resolver el intento de EZTV antes de considerarlo una segunda fuente funcional. Error visible: `Unable to access eztv1.xyz, blocked by CloudFlare Protection.` API posterior confirma que no está guardado. Ver [diagnóstico y captura](docs/prowlarr.md#eztv-attempt--cloudflare-at-eztv1xyz).
- [x] Comprobar las URLs disponibles: **el usuario confirmó que el bloqueo ocurre en todas**, incluida la primera `https://eztvx.to/`. La captura conservada muestra específicamente `eztv1.xyz`; los demás resultados fueron reportados en texto. No pedir que repita esas pruebas ahora.
- [ ] Evaluar una solución al bloqueo junto al pendiente1337x, sin forzar Save ni instalar automáticamente un resolver.
- [ ] Tras resolver el acceso, obtener Test exitoso, guardar y confirmar EZTV habilitado junto a Knaben; actualizar guía/estado y cerrar este pendiente.

## FlareSolverr — Evaluación pendiente

- [ ] Decidir si incorporar **FlareSolverr** para intentar recuperar1337x y EZTV. **Prioridad recomendada por el agente:** después de una primera prueba del flujo completo con Knaben; el usuario autorizó avanzar primero con Radarr; no autorizó desplegar FlareSolverr ahora.
- [ ] Si se decide desplegarlo, crear su módulo Compose y guía propios, fijar imagen/versión, verificar red entre contenedores, tags coincidentes e IP de salida común según la FAQ enlazada arriba. No modificar router/VPN como efecto secundario.
- [ ] Validar cada indexador afectado por separado con Test y guardado real. Un contenedor FlareSolverr healthy no prueba que Cloudflare haya sido resuelto; conservar los pendientes hasta comprobarlos.

## Trabajo actual

**Knaben** guardado/habilitado, confirmado por UI y API; es la única fuente guardada. Todas las URLs de **EZTV** están bloqueadas según el usuario. **Radarr ya está desplegado y healthy**, con guía/Compose/script propios y probe de filesystem aprobado; cuenta Forms/Enabled ya guardada y verificada; raíz `/data/media/movies` registrada/accesible con captura y API; Knaben(Prowlarr) ya sincronizado y verificado en Radarr; qBit desde Radarr ya superaTest y quedó guardado/habilitado por captura; falta revisar perfiles/renombrado y probar una película hasta Jellyfin. Sonarr después.1337x/EZTV y FlareSolverr siguen pendientes; no hace falta sumar otro indexador para intentar esta validación. Ver [guía Radarr](docs/radarr.md).

## Radarr — Próximos checkpoints del flujo

- [x] Cuenta y raíz `/data/media/movies` verificadas.
- [x] Prowlarr Full Sync y Knaben registrados en Radarr.
- [x] Cliente qBittorrent: Test correcto y Save confirmado por UI; categoría `movies`, sin Remote Path Mapping. Ver [capturas y receta](docs/radarr.md#73-radarr--qbittorrent).
- [ ] Revisar perfil de calidad/idioma y límites de tamaño con el usuario; audio original primero, inglés como fallback.
- [ ] Definir/verificar renombrado y conservación de datos para la primera prueba.
- [ ] Validar búsqueda → descarga → importación/hardlink → escaneo y reproducción Jellyfin con una película autorizada.
- [ ] Registrar salud posterior al Save y evidencia real sin asumir resultados a partir del Test.
- [ ] Después: Sonarr, subtítulos ES/EN seleccionables y aceptación de episodio; backup independiente/restore siguen en el roadmap.
