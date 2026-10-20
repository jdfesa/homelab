# Torrent Cleanup

Mantenimiento periódico del cliente, no limpieza general de discos. [Script](../scripts/torrent-cleanup.py), [unidades systemd](../config/torrent-cleanup/) y [pruebas sintéticas](../tests/test_torrent_cleanup.py). Un ejecutable con dos políticas independientes; **simulación por defecto**. Las pruebas locales no demuestran que esté instalado o activo en una VM.

**Estado verificado:** revisión actual instalada en Debian, con progreso mínimo, gracia semanal y estado v2. Migración y muestras persistentes comprobadas inicialmente en simulación. Código instalado contrastado con la fuente revisada; timer habilitado cada seis horas y ejecución programada con `--apply`/salida 0 comprobada. El **Stop nativo de 60 minutos** está guardado y su detención real verificada, conservando la entrada, las rutas y el manifiesto de archivos.

**Acciones habilitadas:** override `--apply` verificado para **ambas políticas** de retiro, sin acortar sus plazos. Configuración activa y salida 0 no demuestran que haya habido borrados. El retiro real de completos se validó en la revisión anterior; faltan comprobar ventanas reales de 24 h/gracia semanal y borrado seguro de parciales con esta revisión. El Stop nativo no ejecuta ninguna de esas eliminaciones.

## Native Seeding Stop

**Dos responsabilidades independientes:** qBittorrent detiene el seeding después de una hora; el script decide cuándo es seguro retirar la entrada. La detención **no espera** la importación en Radarr/Sonarr ni la detección en Jellyfin. Si falta esa validación, el torrent puede permanecer **detenido**, con sus archivos conservados, sin seguir compartiendo indefinidamente.

En qBittorrent **5.2.4**, configurar en **Settings → BitTorrent → Seeding Limits** el tiempo total de seeding en **60 minutos** y la acción **Stop torrent**. Equivalente en `app/setPreferences`:

| Campo | Valor |
| --- | --- |
| `max_seeding_time_enabled` | `true` |
| `max_seeding_time` | `60` |
| `max_ratio_act` | `0` (`Stop`) |

Releer `app/preferences` para comprobar los valores guardados. Mantener los límites alternativos de ratio e inactividad deshabilitados si se pretende detener por esta hora y no antes. **Nunca elegir Remove torrent ni Remove torrent and its content**: esa retirada eludiría las guardas del script. [Contrato de preferencias 5.2.4](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/webui/api/appcontroller.cpp#L805-L835).

El contador nativo suma tiempo con el contenido seleccionado completo y disponible, sin pausa, incluso sin peers; **no** cuenta sólo los segundos de subida efectiva. Pausas, colas o cliente apagado pueden extender el plazo de reloj desde el 100%. qBittorrent revisa sus límites aproximadamente cada **10 segundos**: no depende del timer de limpieza de seis horas ni garantiza una detención exacta al segundo 3600. [Contador utilizado](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/base/bittorrent/torrentimpl.cpp#L930-L938), [semántica de libtorrent](https://www.libtorrent.org/reference-Torrent_Status.html#finished_duration) y [revisión nativa](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/base/bittorrent/sessionimpl.cpp#L580-L587).

Comprobar también los límites **efectivos**: un override del torrent o de su categoría puede sustituir el global, y los criterios de seeding enviados por Arr al añadir una descarga pueden fijar un tiempo propio. Los torrents forzados quedan fuera de los límites nativos; no usar **Force Start** para el flujo automático. Mantener **Remove Completed/Remove Failed OFF** en los gestores. La política Completed del script acepta `stoppedUP`, pero sigue exigiendo edad mínima, historial, hardlinks y Jellyfin antes de retirar sólo la entrada. [Herencia de límites](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/base/bittorrent/torrentimpl.cpp#L1387-L1415), [exclusión de forzados y acción Stop](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/base/bittorrent/sessionimpl.cpp#L2208-L2254).

## Rules and Safety Boundary

| Política | Requisitos | Acción con `--apply` |
| --- | --- | --- |
| Completed | Archivos seleccionados completos, cero bytes pendientes, ≥1 h desde `completion_on`, importación de todos los videos seleccionados correlacionada por `downloadId`, hardlinks actuales y rutas detectadas en Jellyfin | Retirar únicamente la entrada, `deleteFiles=false`. Conservar descarga y biblioteca. |
| Stalled / slow, menos del 90% | Ventana observada de al menos 24 h con avance **menor de cinco puntos porcentuales**, estado `stalledDL` o `downloading`, cliente/conectividad operativos y correspondencia en la cola del gestor | Detener y revalidar; bloquear sólo esa entrega sin iniciar reemplazo; retirar entrada y parciales con `deleteFiles=true`. |
| Stalled / slow, desde el 90% y menos del 100% | La misma ventana de avance insuficiente **y al menos siete días desde la primera detección válida al 90% o más** | La misma retirada de parciales, sólo si siguen cumpliéndose todas las protecciones. |

Los cinco puntos se calculan sobre el payload **seleccionado**, ponderando el progreso por el tamaño de cada archivo. No es un 5% relativo del porcentaje actual, un promedio simple de archivos ni un umbral de velocidad instantánea. Los bytes transferidos por sí solos no demuestran avance útil. Avances pequeños **no reinician** la ventana diaria ni la semana. El 90% exacto queda protegido; exactamente cinco puntos en la ventana son suficientes para conservar. Se usa precisión de API con una tolerancia numérica mínima y conservadora, no el porcentaje redondeado de la WebUI.

### Boundary Examples

Ejemplos sintéticos; siempre sujetos a observaciones saludables y demás guardas:

| Situación | Resultado |
| --- | --- |
| 0% → 0,01% o 20% → 24% en 24 h | Avance insuficiente; puede ser candidato. |
| 20% → 25% en 24 h | Conservar: cumple cinco puntos. |
| Cruza del 89% al 90% | Empieza la protección semanal; no borrar por parciales. |
| Sigue al 95% antes de siete días desde la detección ≥90% | Conservar aunque no avance. |
| Tras siete días sigue incompleto y avanzó menos de cinco puntos en la ventana diaria | Puede ser candidato; no es una orden de borrado incondicional. |
| Tras siete días avanzó del 90% al 95% en la última ventana | Conservar: el vencimiento no anula el progreso suficiente. |
| Llega al 100%, incluso antes de vencer la semana | Aplicar sólo la regla Completed; nunca borrar como parcial. El Stop nativo tras una hora es independiente; si falta importar/detectar, conservar entrada y archivos detenidos. |

Por encima del 95%, una descarga incompleta ya no puede sumar cinco puntos sin completar: vencida la semana y con una ventana válida, quedará como candidata si no terminó, salvo otra protección. La semana concede ese margen final; no promete conservación indefinida por pequeños avances.

Sólo categorías `movies` y `tv`. Excluir forzados, etiqueta **`cleanup-keep`**, estados desconocidos, pausas/colas de descarga, verificaciones, traslados, metadatos ausentes, errores, rutas ambiguas, symlinks y contenido compartido entre torrents. Un paquete incompleto con **cualquier video completo**, incluso no seleccionado, no se elimina automáticamente, **aunque venza la semana**. Parciales con hardlinks se excluyen. No recorrer ni borrar carpetas padre a mano.

Los completos requieren eventos `downloadFolderImported` posteriores al alta actual y mismo dispositivo/inode/tamaño entre origen y biblioteca. Una coincidencia de título, un episodio importado o tamaño similar no valida el paquete. **Copias sin hardlink, historial purgado o importaciones no correlacionadas quedan para revisión**, aunque sean reproducibles. Jellyfin se comprueba por ruta exacta: `/data/media` en Debian corresponde a `/media` en el contenedor.

Esta versión revisa qBittorrent **5.2.4** y rechaza otra versión hasta revisar su contrato. El **Stop nativo** descrito arriba es compatible; el borrado nativo por seeding y Remove Completed/Remove Failed de los gestores deben seguir **OFF** para no introducir otra política de limpieza. Instalar el script no autoriza cambiar límites ni credenciales.

## Scheduling and Resource Use

El [timer](../config/torrent-cleanup/torrent-cleanup.timer) programa las 00/06/12/18 **según la zona horaria de Debian**, con tolerancia de cinco minutos y recuperación de una ejecución omitida al arrancar. El proceso Python termina después de cada revisión; no mantiene un bucle residente. systemd no lanza otra instancia de la misma unidad mientras sigue activa; un lock protege también ejecuciones manuales.

- Sin torrents gestionados, termina sin consultar los gestores/Jellyfin ni probar conectividad exterior.
- Límite de cinco acciones por corrida, diez minutos, 192 MiB y cuota CPU del 25%; prioridad reducida. Los límites no son una medición de consumo real.
- El mínimo de una hora de Completed no implica retiro exacto al minuto 60: normalmente puede esperar otra revisión, hasta unas seis horas adicionales, más la tolerancia del timer/importación. Esa espera no prolonga el seeding si el Stop nativo ya se cumplió.
- La ventana diaria necesita una línea base persistente y normalmente cuatro intervalos saludables de seis horas. Nunca se deducen las 24 h anteriores de `added_on`, de un 0% visible ni de `last_activity`, que incluye subida.
- Con tolerancias del timer no hay una muestra exactamente a las 24 h: se toma la muestra real más cercana **anterior o igual** al límite. La ventana puede abarcar hasta 31 h; se exige menos de cinco puntos en **todo** ese intervalo, sin interpolar ni prorratear. Es conservador: puede demorar un descarte, no inventar una falta de progreso dentro de las últimas 24 h.
- Se guardan hasta 128 muestras por torrent. Muchas ejecuciones manuales muy frecuentes pueden desplazar el ancla y obligar a esperar más historia; nunca habilitan un descarte antes de tiempo.
- Pausas, fallos de servicios/conectividad, reinicio del huésped, tiempo activo insuficiente o huecos mayores de siete horas invalidan la continuidad diaria. Cambios de selección/ruta/identidad, regresión de datos/contadores o retroceso del reloj también obligan a comparar una línea base nueva. No contar períodos sin evidencia saludable.
- La semana es **tiempo transcurrido**, no siete corridas ni siete días desde el alta. Su inicio se conserva entre procesos y ante pausas, huecos o reinicios si identidad, datos y reloj siguen siendo compatibles; aun así se exige una ventana diaria saludable antes de descartar. Cambiar el payload, perder datos/contadores o retroceder el reloj reinicia conservadoramente esa referencia. Una descarga ya ≥90% en la primera observación recibe la semana desde ese momento, sin retroactividad.
- La conectividad se contrasta con qBit/DHT y una respuesta HTTPS de Debian o qBittorrent, tanto para `stalledDL` como para `downloading`; no se envían credenciales a esos sitios. Son observaciones puntuales, **no monitorización continua ni prueba de ausencia mundial de fuentes**. «Progreso insuficiente» describe el criterio de descarte, no su causa.

## Install in Observation Mode

**Destino: Debian media-server, con `sudo` del administrador existente. No ejecutar como root en la Mac/Proxmox.** Requiere Python 3.13, systemd 257, grupo `media`, guarda de almacenamiento ya instalada y servicios configurados. No crea cuentas administrativas de aplicaciones, modifica sudoers/SSH, reinicia contenedores ni prepara discos.

1. Revisar el script y ejecutar la suite local. Copiar los tres archivos revisados a Debian en un directorio de fuentes. No copiar la biblioteca ni appdata.
2. Preparar privadamente una copia de [credentials.json.example](../config/torrent-cleanup/credentials.json.example), con URL LAN de cada servicio, credencial qBit y claves API vigentes. Las claves deben permitir las consultas necesarias; las de Arr se usan también para la retirada seleccionada sin redescarga. **No usar `.env` de Compose ni secretos en argv/URLs.** Si la copia está en un checkout administrativo, comprobar primero `git check-ignore` y `git ls-files` como en [Service Access](service-access.md#environment-files-and-login-sessions). El destino `/etc` debe quedar fuera de cualquier worktree.
3. Dentro de Debian, desde ese directorio de fuentes, sustituir sólo la ruta del archivo privado:

```sh
sudo install -d -m 0755 /usr/local/libexec/media-server
sudo install -m 0755 torrent-cleanup.py /usr/local/libexec/media-server/torrent-cleanup.py
sudo install -d -m 0700 /etc/media-server/torrent-cleanup
sudo install -m 0600 /path/to/private/credentials.json /etc/media-server/torrent-cleanup/credentials.json
sudo install -m 0644 torrent-cleanup.service /etc/systemd/system/torrent-cleanup.service
sudo install -m 0644 torrent-cleanup.timer /etc/systemd/system/torrent-cleanup.timer
sudo systemd-analyze verify /etc/systemd/system/torrent-cleanup.service /etc/systemd/system/torrent-cleanup.timer
sudo systemctl daemon-reload
sudo systemctl start torrent-cleanup.service
sudo systemctl enable --now torrent-cleanup.timer
```

Es una receta para **primera instalación revisada**, no una orden de sobrescribir una instalación activa. Si existen archivos/unidades, comparar y respaldar privadamente antes de actualizar; conservar configuración, estado y logs. Un fallo no justifica borrar appdata ni retirar guardas.

### Upgrade an Existing Installation

Actualización v1 → v2 comprobada en simulación, sin reinstalar servicios ni cambiar accesos:

1. Verificar hashes del código/unidades y el override efectivo. Parar sólo el timer y exigir la unidad inactiva; dejar terminar una corrida, no interrumpir una posible mutación. Un lock protege la captura coherente del estado.
2. Respaldar privadamente código, estado, unidades, override y auditoría: directorio root `0700`, archivos `0600`, fuera de Git y sin sobrescribir copias previas. Conservar los permisos originales en la evidencia. No modificar ni copiar credenciales a fuentes temporales.
3. Archivar y retirar únicamente el override `--apply` previamente revisado; recargar systemd y comprobar que `ExecStart` efectivo **no contiene `--apply`** ni hay otros drop-ins inesperados. No instalar código nuevo heredando acciones activas.
4. Reemplazar atómicamente sólo el script con la fuente revisada, propietario root/modo `0755`, y verificar el hash instalado. Mantener las unidades y las credenciales existentes.
5. Arrancar una vez la unidad y comprobar `Result=success`, salida 0, `mode=dry-run`, migración, muestras y ningún evento de mutación. Contrastar también entradas de qBit, biblioteca y credenciales. Reanudar el timer sólo tras una comprobación exitosa, conservando la simulación; ante fallo, dejarlo detenido y revisar backup/journal, sin restaurar `--apply` automáticamente.

No repetir el instalador de primera vez. El primer uso de v2 descarta únicamente las observaciones v1: no contienen muestras diarias ni inicio de gracia que puedan convertirse con fiabilidad. **Conserva los marcadores `pending`**, exige historia nueva y registra `state_migrated`. Versiones de estado desconocidas se rechazan. No restaurar un estado antiguo para ocultar una mutación pendiente ni prometer rollback cambiando sólo el código.

`credentials.json.example` es una plantilla pública: conservar sus placeholders en Git. El archivo real `/etc/media-server/torrent-cleanup/credentials.json` contiene únicamente el acceso qBit y las claves API de Radarr, Sonarr y Jellyfin; no necesita credenciales de SSH/sudo, Proxmox, Samba ni del resto de servicios. Una instalación ya configurada no requiere volver a enviarlas ni rellenar el ejemplo.

El servicio usa **DynamicUser + SupplementaryGroups=media**, credenciales de systemd y `/data` sólo lectura desde su proceso. No añadir el administrador SSH al grupo media ni ejecutarlo permanentemente como root para evitar errores de acceso. qBit conserva su bind sólo de descargas; las eliminaciones se solicitan mediante su API, no escribiendo desde Python a la biblioteca. Los permisos del SO no restringen por sí solos las capacidades de esas claves API.

La guarda existente se ejecuta como `ExecStartPre=+...`: sólo esa comprobación de lectura usa privilegios para verificar el montaje **real** UUID/ext4/RW antes del aislamiento. El proceso Python conserva su usuario restringido y revalida UUID/ext4 dentro del montaje RO que ve su namespace; no confundir ese RO deliberado con un disco del host pasado a sólo lectura. No retirar el `ExecStartPre` ni cambiar el montaje real para hacer pasar la comprobación.

**Permisos de instalación:** el directorio de código y el script necesitan `0755`; las unidades, `0644`. Las credenciales mantienen directorio `0700`/archivo `0600`. Una `umask 077` puede convertir un `mkdir`/`open` solicitado como `0755` en `0700` si un instalador no fija después el modo explícito: el usuario restringido no podrá abrir el script y Python puede salir con código 2 antes de empezar. Usar los modos de la receta, verificar propietarios/hashes antes de reparar y no aplicar `chmod -R`, ampliar permisos de `/etc` ni cambiar el servicio a root.

`LoadCredential` puede entregar al proceso copias de root `0440` en un montaje de sólo lectura bajo `/run/credentials`. El lector acepta esa representación únicamente dentro de `CREDENTIALS_DIRECTORY`, sin symlinks/hardlinks adicionales, sin permiso para otros y con montaje verificado RO. **No** relajar a `0440` los archivos de configuración/estado/log ordinarios: permanecen privados `0600`. No cambiar propietarios o permisos de las credenciales gestionadas para sortear el control.

## Verify and Explicitly Enable Removal

```sh
sudo systemctl status torrent-cleanup.service --no-pager
sudo systemctl list-timers torrent-cleanup.timer --no-pager
sudo journalctl -u torrent-cleanup.service -n 30 --no-pager
sudo less /var/log/torrent-cleanup/audit.jsonl
```

El log debe indicar `mode=dry-run`. Verificar autenticación de las cuatro aplicaciones, guarda UUID, acceso de lectura del grupo media, motivos de candidatos/exclusiones y persistencia de estado entre corridas. No probar borrado de un archivo real para demostrar que la simulación es segura.

Sólo después de revisar esa evidencia, habilitar explícitamente acciones con `sudo systemctl edit torrent-cleanup.service`:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /usr/local/libexec/media-server/torrent-cleanup.py --config %d/settings.json --apply
```

Recargar con `sudo systemctl daemon-reload`; el timer usará el modo nuevo en su próxima ejecución. No hace falta reiniciar qBit/Arr/Jellyfin ni iniciar una limpieza inmediata. `--policy completed` o `--policy stalled` permite limitar una ejecución revisada a una política; por defecto evalúa ambas. El identificador `stalled` de v2 incluye también las transferencias lentas activas. No reducir los umbrales para acelerar una prueba.

Para una ejecución manual deliberada en Debian, `sudo systemctl start torrent-cleanup.service` ejecuta una vez **el modo configurado**: con el override `--apply`, puede retirar entradas o borrar parciales elegibles. Conserva el aislamiento de la unidad y no cambia el timer. Revisar después el resultado y la auditoría; no ejecutar Python como root fuera de la unidad, forzar umbrales ni repetir automáticamente ante un fallo.

## Private Audit and Recovery

- Estado: `/var/lib/torrent-cleanup/state.json`. Log: `/var/log/torrent-cleanup/audit.jsonl`. Directorios `0700`/archivos `0600`, resueltos por systemd bajo sus directorios privados cuando corresponde. No publicar esos archivos, sus nombres de contenido ni claves.
- JSONL incluye fecha UTC, corrida/acción, torrent, política, motivo, umbral observado, modo, conservación/borrado solicitado y resultado. Guardar la intención duraderamente **antes** de la mutación; si falla auditoría/estado, no iniciar el borrado.
- Para incompletos, `retained` explica `insufficient_history`, `near_complete_grace`, `sufficient_progress` o `inactive_or_unhealthy`. `window_start`/`window_end` son segundos Unix; se registran duración real, porcentajes inicial/final, `delta_percentage_points`, mínimo exigido e inicio/edad de gracia cuando corresponde. Así se distingue falta de muestras de un avance suficiente; `skip` indica una guarda o fallo adicional.
- Rotación: 10 MiB por archivo y cinco copias (`.1`–`.5`), aproximadamente 60 MiB máximos para ese conjunto; no es retención indefinida ni un número garantizado de días. Conservar una copia privada aparte si se necesita auditoría más antigua.
- `candidate` no es un borrado; `delete_request` tampoco. `confirmed` exige que la entrada ya no esté y, para parciales, que los archivos conocidos hayan desaparecido. No se publican supuestos bytes recuperados. Errores de API no imprimen respuestas, URLs sensibles, cookies ni claves.
- Antes de borrar parciales, qBit se detiene y se vuelve a comprobar el paquete. Se admite el avance ocurrido hasta detenerlo, pero se recalculan ventana y gracia con esos datos: alcanzar cinco puntos o cruzar el 90% impide borrar. `revalidated` registra esas comprobaciones. Tras la detención se exige estabilidad, cero velocidad y ausencia de reinicio concurrente antes de pedir el borrado.
- Arr recibe `removeFromClient=false`, `blocklist=true`, `skipRedownload=true`, `changeCategory=false`: no se lanza una búsqueda ni se cambia la política global. **Puede quedar detenido/bloqueado si algo falla o cambian las condiciones después de iniciar la acción.** Incluso una revalidación fallida puede dejar `pending`; requiere revisión, no reanudar o repetir automáticamente.
- Una operación incierta permanece en `pending`, devuelve error y bloquea el reintento de ese torrent. Revisar qBit, cola/blocklist de Arr, archivos y log. La API no ofrece una eliminación condicional atómica: no operar manualmente esos mismos torrents ni ejecutar otros limpiadores durante una corrida.
- Tras resolver manualmente el estado, con el timer detenido y las rutas/permisos correctos, `--acknowledge-pending <HASH>` permite reconocer **una** acción. No reanuda, redescarga ni elimina nada; elimina esa marca pendiente y reinicia su observación. No usarlo como parche automático de errores.
- Detener el timer: `sudo systemctl disable --now torrent-cleanup.timer`. Esto no interrumpe un servicio ya en ejecución. Parar el servicio durante una mutación puede dejar una acción pendiente; revisar antes de continuar. Para volver a simulación, retirar sólo el override `--apply` después de revisarlo, recargar systemd y mantener el estado.

No hay rollback de parciales ya borrados. El retiro de completos **no libera su espacio**: conserva los originales y la biblioteca. Copia de seguridad/restauración de appdata y contenido sigue siendo otra tarea del [runbook](../RUNBOOK.md).

## Validation and Sources

Desde la raíz del repositorio:

```sh
python3 -m unittest discover -s media-server/tests -p test_torrent_cleanup.py -v
sh scripts/run-tests.sh
git diff --check
```

Las pruebas usan clientes falsos y fixtures temporales; no contactan servicios ni dependen del inventario personal. Cubren avance marginal/exactamente cinco puntos, ponderación/selección, ventanas móviles con tolerancia, límite de muestras, gracia del 90%/siete días, pausas/huecos/reinicios, migración con `pending`, transferencias activas y cambios durante el stop, además de paquetes mixtos, rutas/links, API/auth, paginación, fallos, auditoría, límites y unidades en simulación. El arranque real de esta revisión y su estado deben verificarse separadamente en Debian.

- [qBittorrent 5.2.4: API de torrents](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/webui/api/torrentscontroller.cpp) y [contrato general](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-5.0)). La versión actual usa cookie `QBT_SID_<port>` y login204; no asumir sólo el antiguo `SID`/`Ok.`.
- [API Sonarr](https://github.com/Sonarr/Sonarr/tree/develop/src/Sonarr.Api.V3) y [Radarr](https://github.com/Radarr/Radarr/tree/develop/src/Radarr.Api.V3); contrastar también el esquema de la versión instalada antes de actualizar.
- [Autorización Jellyfin](https://gist.github.com/nielsvanvelzen/ea047d9028f676185832e51ffaf12a6f): `Authorization: MediaBrowser ... Token="..."`; no habilitar autenticación heredada para compatibilizar un cliente nuevo.
- [Timers systemd](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html), [credenciales](https://systemd.io/CREDENTIALS/) y [rotación Python](https://docs.python.org/3/library/logging.handlers.html#rotatingfilehandler).
