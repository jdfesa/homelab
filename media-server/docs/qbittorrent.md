# qBittorrent Service Guide

**Status:** Deployed and healthy; LAN/API verified; Radarr client Test + Save confirmed by UI; real download/import pending; no manual download started · **Updated:** 2026-10-16.

## Purpose and Scope

Cliente de descargas de esta VM. Sonarr y Radarr le enviarán trabajos cuando se integren; Jellyfin reproduce la biblioteca organizada, no las descargas incompletas. El usuario eligió continuar con este cliente antes de aportar un archivo manual de prueba. **No se agrega ningún torrent en este despliegue.**

## Version and Deployment Files

- qBittorrent **5.2.4**, imagen mantenida por **LinuxServer.io** (no una imagen oficial del proyecto qBittorrent).
- Build `5.2.4_v2.0.15-ls480`, linux/amd64; digest inmutable en [image lock](../compose/qbittorrent/image-lock.json).
- [Compose](../compose/qbittorrent/compose.yaml), [plantilla privada](../compose/qbittorrent/.env.example) y [script de primer despliegue](../scripts/deploy-qbittorrent.py).
- Sin actualizaciones automáticas. Un tag `latest` se usó sólo para descubrir/inspeccionar la imagen; no queda en el manifiesto desplegado.

## Storage, Identity and Network

| Element | Configuration |
| --- | --- |
| Runtime Compose | `/srv/media-server/compose/qbittorrent/compose.yaml` y `.env` privado |
| Appdata NVMe | `/srv/media-server/appdata/qbittorrent` → `/config` RW |
| Descargas HDD | `/data/downloads` → `/data/downloads` RW, sin cambiar rutas entre aplicaciones |
| Ruta por defecto | `/data/downloads/` |
| Incompletos | `/data/downloads/incomplete/`, habilitada, en el mismo HDD |
| Categoría movies | `/data/downloads/movies` |
| Categoría tv | `/data/downloads/tv` |
| Aplicación | PUID1000, PGID2000 (`media`), UMASK002 |
| Inicialización | s6 arranca root y baja al UID/GID de la aplicación; no copiar `user`/`cap_drop: ALL` de Jellyfin |
| WebUI | TCP8080 publicado únicamente en IPv4 privada de la VM; valor real en `.local/` |
| Peer port | 6881 interno, **sin publicar TCP/UDP al host en esta etapa** |
| Router | UPnP/NAT-PMP BitTorrent OFF y WebUI UPnP OFF desde antes del primer arranque; sin reglas router |

El modo inicial sin puerto entrante puede limitar conectividad con peers; no equivale a bloquear conexiones salientes. Evaluar conectividad/rendimiento con una descarga autorizada antes de decidir cambios. No se configuró VPN ni anonimato de tráfico. Autenticación y protecciones CSRF/Host header/clickjacking permanecen activas; sin excepciones localhost/subred. Ningún puerto WebUI se expone deliberadamente a Internet.

Sólo recibe acceso al árbol de descargas, **no a `/data/media`**, socket Docker ni discos/dispositivos. La guarda UUID/ext4/RW existente se comprueba antes de desplegar. Los datos de configuración no deben terminar en el HDD ni en Git. El nuevo directorio `incomplete` se crea sin modificar recursivamente permisos de datos existentes.

## First Deployment Recipe

**Destino de ejecución: root dentro de Debian media-server**, no la Mac ni Proxmox. Este procedimiento no instala Debian, no formatea el HDD, no modifica SSH y no reinicia DSM. Requiere base/storage ya preparados, UID1000, grupo media2000 y directorios `downloads/{movies,tv}`.

1. Revisar el lock y el manifiesto. Completar una copia privada de `.env.example`: `QBITTORRENT_BIND_ADDRESS` es la IPv4 asignada en la LAN; conservar `QBITTORRENT_IMAGE` por digest.
2. Obtener esa imagen y comprobar plataforma y label del lock. No sustituirla automáticamente por `latest`.
3. Copiar el script, manifiesto y entorno al directorio root de scripts de la VM. El entorno contiene valores de sitio; modo0600, fuera de documentación pública.
4. Ejecutar el instalador **una sola vez sobre estado ausente**:

```sh
python3 /root/media-server-scripts/deploy-qbittorrent.py --apply \
  --compose-file /root/media-server-scripts/qbittorrent-compose.yaml \
  --env-file /root/media-server-scripts/qbittorrent.env
```

El script valida manifiesto y montaje, rechaza stack/appdata/credencial ya existentes, crea sólo directorios de esta app y `incomplete`, escribe configuración inicial antes de arrancar, valida Compose y espera health. Luego usa la API autenticada para comprobar rutas/protecciones/cliente vacío y crear las dos categorías. No crea torrents, indexadores ni integraciones.

La contraseña temporal de inicio se guarda en un archivo root0600: `/root/media-server-scripts/qbittorrent-initial-login.txt`. **No imprimir logs completos:** contienen ese secreto. El transporte administrativo puede entregarla al usuario mediante un archivo local privado0600, nunca en chat, capturas o esta guía. Fallar a mitad no habilita sobreescribir estado: inspeccionar primero lo creado y no borrar appdata para reintentar a ciegas.

## User Interface Steps

1. Abrir la dirección LAN de la VM en el puerto **8080**.
2. Entrar inicialmente con username **`admin`** y la contraseña temporal del archivo privado. No es la cuenta de Debian ni la de Jellyfin.
3. En **Tools → Options → WebUI**, sección **Authentication**, conservar username `admin` y elegir la contraseña permanente directamente en **Password**. Pulsar **Save**. No publicar su valor por defecto; la excepción expresa del propietario para este laboratorio se registra en [Laboratory Login Example](#laboratory-login-example).
4. Mantener desmarcados los bypass de autenticación y la opción UPnP de WebUI. Conservar protecciones CSRF, clickjacking y Host header.
5. En **Downloads**, comprobar las rutas de la tabla. En **Connection**, mantener UPnP/NAT-PMP desmarcado. Las categorías `movies`/`tv` deben aparecer con las rutas indicadas.
6. Informar que el login/guardado terminaron; aportar capturas sin contraseñas cuando revisemos opciones. Sólo las finales aprobadas se incorporarán aquí, igual que en Jellyfin.

**Estado de estas acciones de interfaz:** el usuario ingresó, cambió la contraseña inicial y confirmó que **no inició la descarga manual**. Tras un problema de login, autorizó la recuperación acotada descrita abajo y luego pidió registrar la credencial vigente como ejemplo del laboratorio. Radarr ya supera Test y su cliente quedó guardado/habilitado por captura. No confundir estos checkpoints con una descarga real ni inferirlos sólo porque el contenedor esté healthy.

## Password Lifecycle — Reproducible Procedure

**Estado confirmado por el usuario:** ya cambió la contraseña de qBittorrent después de su primer ingreso. No se cambió ninguna contraseña de Debian ni de Jellyfin.

1. En una instalación nueva con esta imagen, la cuenta inicial es `admin` y qBittorrent genera una **contraseña temporal** en el arranque. No asumir una contraseña universal ni copiar claves de tutoriales.
2. El instalador obtiene esa credencial sin imprimir logs completos y la entrega en un archivo privado0600. Es únicamente para el acceso inicial; el archivo usado en esta instalación **ya no debe tratarse como credencial vigente** tras el cambio confirmado.
3. En **Tools → Options → WebUI → Authentication**, escribir la contraseña elegida en **Password** y pulsar **Save**. La versión5.2.4 exige **al menos6 caracteres**; una más corta será rechazada, no es un problema de la IP. Se conserva en appdata de la aplicación; no en el Compose ni en `.env` público. El usuario confirmó el cambio inicial; la recuperación posterior autorizada se documenta abajo.
4. Usar desde entonces la contraseña permanente; normalmente conservarla en el gestor personal, fuera de la guía. Para este laboratorio existe la [excepción expresa del propietario](#laboratory-login-example). No volver a intentar la credencial temporal anterior ni reejecutar el instalador para recuperarla.
5. Al conectar Radarr/Sonarr, introducir la cuenta de qBittorrent y su contraseña **vigente** en sus pantallas. Documentar campos y prueba sin divulgar otros secretos. Elegir otra contraseña o cambiarla posteriormente exige actualizar esos clientes, no reinstalar servicios.
6. Un backup consistente y privado de appdata preserva configuración/autenticación; restauración aún pendiente de prueba. Recrear el contenedor conservando appdata no es crear una instalación nueva. Si no se eligiera una contraseña permanente, la temporal puede cambiar con los reinicios según la imagen; no basar integraciones en ella.

La regla general es registrar **cómo establecer y utilizar los secretos**, no publicar sus valores. La siguiente excepción se limita a la credencial de demostración elegida expresamente por el propietario; API keys, sesiones, exports, hashes y contraseñas de otros servicios siguen fuera del repositorio público.

## Laboratory Login Example

**Ejemplo usado en este laboratorio, documentado por pedido expreso de su propietario:**

| Campo | Valor de ejemplo |
| --- | --- |
| Username | `admin` |
| Password | `adminadmin` |

Estos valores coinciden con el acceso real elegido después del reset; **no son una contraseña universal ni el valor inicial de la imagen**. En otra instalación, crear la credencial propia mediante el procedimiento anterior y usarla también en Radarr/Sonarr. Radarr mantiene su campo **API Key vacío** al autenticarse con esta cuenta.

**Advertencia:** quien lea el repositorio podrá conocer esta contraseña. Etiquetarla como ejemplo no la protege; es una elección de laboratorio, no una recomendación para producción o acceso público a Internet. No se cambia ninguna credencial por documentarla ni se extiende esta excepción a otros servicios. El valor se mantiene sólo aquí, no en Compose, scripts ni `vm-config.json`.

## WebUI Login Recovery — Explicit Scoped Reset

**Ejecutado y verificado el2026-10-16 por solicitud expresa del usuario.** No es otro despliegue ni un paso obligatorio del laboratorio. El usuario no lograba ingresar a qBit y Radarr mostraba `Unable to connect to qBittorrent`. La IP/puerto respondían desde el contenedor de Radarr: WebUI HTTP200, API403 sin autenticar. Ambos contenedores estaban healthy; se comprobó únicamente la presencia de una credencial persistida, sin publicar su hash ni intentar recuperar su valor.

El usuario autorizó un reset **sólo de esta WebUI**, manteniendo username **`admin`** y eligió una contraseña compatible con el mínimo de la aplicación. Posteriormente solicitó anotarla como [ejemplo del laboratorio](#laboratory-login-example). La credencial temporal del despliegue inicial queda como registro histórico, no como acceso vigente. No se cambiaron cuentas Debian/SSH/Jellyfin/Prowlarr/Radarr ni se abrieron puertos o desactivaron comprobaciones de autenticación.

### Reproduce the Scoped Recovery

Usar [reset-qbittorrent-webui.py](../scripts/reset-qbittorrent-webui.py) sólo con autorización para restablecer este acceso. **Destino: root dentro de Debian**, no la Mac ni Proxmox. Copiar el script revisado a `/root/media-server-scripts/`, modo700. La receta está limitada a la imagen fijada5.2.4, proyecto/montajes/puerto LAN de este módulo y un laboratorio **sin metadatos de torrents existentes**; si encuentra trabajos, se detiene antes de parar el servicio y exige revisar otro procedimiento.

```sh
python3 /root/media-server-scripts/reset-qbittorrent-webui.py --apply --username admin
```

El script solicita la nueva contraseña y su confirmación con **getpass**, sin eco. No escribir secretos en argumentos, historial de shell, Compose ni archivos públicos. El modo `--password-stdin` existe para transporte privado controlado; en esta ejecución se verificó Guest Agent stdin con datos no secretos antes de enviar la credencial, sin ponerla en argv.

1. Valida el montaje guardado, contenedor/imagen/montajes/puerto, ausencia de trabajos y estado previo. Registra la identidad de los otros tres contenedores.
2. Para **sólo qBittorrent** y crea un backup consistente y privado de `qBittorrent.conf`: directorio0700 y archivo0600 bajo `/var/lib/media-server/backups/qbittorrent-webui-reset/<fecha>/`.
3. Sustituye únicamente **WebUI Username y Password_PBKDF2**, preservando el resto de opciones y owner/mode del archivo, mediante escritura atómica. El formato PBKDF2 SHA512/100000/salt16 se contrastó con el código de la versión fijada; no se borra appdata, no se habilitan bypasses y no se reinstala nada.
4. Inicia el **mismo contenedor**, espera health y verifica un login fresco, rutas/categorías y cero torrents. Comprueba que los otros contenedores conserven ID/imagen/inicio/restarts. Si falla una escritura o verificación, intenta restaurar la configuración original y volver a iniciar qBit; no repetir ciegamente una ejecución fallida.
5. Actualiza la credencial en las integraciones que la utilicen, **no reinstala esos servicios**. En esta ejecución Radarr todavía no tenía un cliente guardado; faltaba actualizar el formulario abierto y dar Test → Save.

### Verified Recovery Result

- Backup privado creado; misma identidad de contenedor qBit, healthy después del reinicio deliberado.
- **Login fresco HTTP204**, usuario `admin`; cookie/sesión y contraseña no exportadas en los informes de ejecución. El ejemplo público posterior es la excepción solicitada arriba.
- **0 torrents**, `movies` → `/data/downloads/movies`, `tv` → `/data/downloads/tv` y destino base `/data/downloads` conservados.
- Jellyfin, Prowlarr y Radarr conservaron identidad/imagen/inicio/restarts. No se reinició la VM.
- **Test no guardado de Radarr HTTP200** con la nueva credencial y el mismo Host/Port. Después, el usuario aportó captura del Test verde y de qBittorrent **Enabled tras Save**; ver [evidencia del cliente guardado](radarr.md#saved-qbittorrent-client--ui-confirmation). Esto no prueba una descarga/importación.
- Evidencia filtrada privada: `.local/qbittorrent-webui-reset-result.json` y `.local/radarr-qbittorrent-post-reset-test.json`, modo0600. La creación del backup no demuestra restauración completa ni backup externo; el rollback real no tuvo que ejercitarse.

No repetir este reset ahora: ya está completado. Para entrar, usar la credencial elegida en esta recuperación; no la temporal vieja. Fuentes primarias: [mínimo de longitud en5.2.4](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/webui/api/appcontroller.cpp), [formato PBKDF2 de5.2.4](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/base/utils/password.cpp).

## Automated Workflow — Normal Use

El flujo acordado **no requiere buscar torrents manualmente ni configurar fuentes de películas dentro de qBittorrent**. Prowlarr centraliza indexadores; Radarr (películas) y Sonarr (series) consultan esas fuentes, seleccionan versiones según perfiles y envían trabajos al cliente. qBittorrent descarga; Radarr/Sonarr importan y organizan en la biblioteca, buscando hardlinks cuando corresponde; Jellyfin escanea/reproduce. La búsqueda del título se inicia en Radarr/Sonarr, no en Jellyfin ni en la ventana manual del cliente.

**Conexión Radarr completada:** Prowlarr/Knaben sincronizados y cliente qBit probado/guardado/habilitado en Radarr. La [receta exacta por campo](radarr.md#73-radarr--qbittorrent) registra API Key vacía, categoría `movies` y limpieza automática inicialmente desactivada, con capturas antes/después de Save. **Siguiente:** perfiles/renombrado de Radarr y primera película E2E; Sonarr después. No repetir reset ni alta del cliente.

La descarga manual mencionada antes sólo sería una prueba opcional, **no un requisito para continuar ni el modo de uso final**. El usuario pidió mantener el flujo organizado/automatizado; no insistir con cargas manuales. Si el formulario manual sigue abierto sin agregar torrent, se puede cerrar sin pulsar Download; si ya se agregó, no borrar datos ni cambiarlo sin revisar su estado. El usuario confirmó después que **no inició esa descarga**; no pedir completarla para continuar.

## Manual Movie Download Form — Optional Test Only

Referencia de una prueba manual opcional, no paso obligatorio. Revisión del formulario **antes** de pulsar **Download**; no prueba descarga iniciada ni terminada. La ruta `/data/downloads` es válida y está en el HDD, pero para una película usar su subcarpeta:

| Field | Value for this test |
| --- | --- |
| Torrent Management Mode | `Manual`, conservar |
| Category | Seleccionar `movies` |
| Save files to location | `/data/downloads/movies`, comprobar después de seleccionar categoría y corregir si no cambia |
| Use another path for incomplete torrent | Marcado |
| Save path de incompletos | `/data/downloads/incomplete`, conservar |
| Otras opciones | No modificar para esta revisión |

Estas son indicaciones para completar el formulario, **aún pendientes de confirmación del usuario**. No usar `/media/movies` ni `/data/media/movies` como destino del cliente; Radarr organizará/importará la biblioteca cuando se configure. Esta descarga manual no se incorpora automáticamente a Jellyfin por estar en downloads.

El formulario mostró **Unknown free**. No afirmar disco lleno ni descartar el aviso a partir de la captura: comprobar montaje, espacio y permisos sin iniciar torrents. La comprobación read-only de esta sesión quedó en `.local/qbittorrent-save-path-check.json`; es evidencia puntual, no monitorización continua. No se archiva esta captura intermedia como referencia final aprobada: contiene una ruta pendiente de ajustar y datos del torrent.

## Verification Record

**Despliegue y verificación completados el 2026-10-16:**

- Imagen por digest inspeccionada; API confirma **5.2.4**, contenedor healthy, cero reinicios.
- WebUI HTTP200 desde la Mac en la LAN; API anónima `/api/v2/app/preferences` devuelve403.
- Sólo TCP8080 publicado en IPv4 privada; montajes efectivos son `/config` y `/data/downloads`, ambos RW.
- Proceso `qbittorrent-nox` con UID1000:GID2000 verificado, s6 inicializa root como documentado. Appdata pertenece al filesystem del SO y es distinto del HDD.
- API autenticada confirma UPnP/NAT-PMP y WebUIUPnP OFF, bypass localhost/subred OFF, protecciones CSRF/Host header/clickjacking ON, ruta default e incompletos correctos.
- Categorías `movies` y `tv` creadas y leídas de vuelta con sus rutas; **cero torrents**.
- Probe temporal UID1000:GID2000 de escritura/lectura/borrado en descargas pasó y quedó limpio; biblioteca no montada. No se probó descarga de contenido.
- Guarda `/data` correcta; cero unidades systemd fallidas; Jellyfin sigue healthy. Configuración y proceso de DSM sin cambios.
- Credencial inicial entregable en archivo local privado0600, sin publicarla en guía/chat. **Primer login confirmado posteriormente por captura del formulario de agregar torrent.** El cambio inicial fue confirmado sin registrar su valor; la recuperación y el ejemplo de acceso posterior se documentan en sus secciones, no sustituyen este registro histórico.

**Incidencia de instalación resuelta:** la aplicación arrancó bien, pero el primer verificador esperaba el texto legacy `Ok.`. qBittorrent5.2.4 devuelve **HTTP204 sin cuerpo** para login correcto. Se corrigió el verificador con test de regresión y se ejecutaron sólo API/probes/categorías sobre el contenedor existente, **sin reinstalar ni borrar estado**. La consulta autenticada posterior confirmó el login. Fuente: [AuthController5.2.4](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/webui/api/authcontroller.cpp).

Evidencia privada en `.local/qbittorrent-deployment-20261016T043442Z.json` y `.local/qbittorrent-verification-result.json`. Las pruebas locales de contrato también pasan, pero no reemplazan esta evidencia runtime. **El servicio ya existe: no repetir el instalador de primer despliegue.**

No dar por verificados una descarga real, hardlinks Radarr/Sonarr, streaming, reinicio completo de VM ni backup/restore por superar este listado.

## Operation, Updates and Recovery

Administrar desde el directorio runtime y validar el montaje antes de iniciar. Ejemplos dentro de Debian con privilegios administrativos existentes:

```sh
cd /srv/media-server/compose/qbittorrent
docker compose ps
docker compose config --quiet
/usr/local/sbin/check-media-storage
docker compose stop
docker compose up -d --wait --pull never
```

No ejecutar el instalador de primer despliegue como método de actualización. Antes de cambiar versión: parar únicamente qBittorrent, guardar copia consistente de appdata, manifiesto y entorno privados, revisar cambios y actualizar digest/lock deliberadamente. Rollback puede requerir **restaurar appdata de esa versión**, no sólo cambiar imagen. No borrar volúmenes/descargas para corregir login o montaje.

Backup: la configuración incluye credenciales, sesiones y estado de torrents; copia privada cifrada o con acceso restringido. El HDD físico y los contenidos descargados requieren política independiente; no quedan respaldados automáticamente con el disco virtual de la VM. Destino/retención y restauración de muestra aún pendientes. La política de seeding, limpieza, límites y espacio libre se acordará al integrar los gestores, no se inventa en este paso.

## Primary Sources

- [LinuxServer qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/) — variables, rutas y primer acceso.
- [qBittorrent release5.2.4](https://github.com/qbittorrent/qBittorrent/releases/tag/release-5.2.4) — versión upstream.
- [WebUI API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29) — login, preferencias y categorías.
- [Port forwarding implementation](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/base/bittorrent/portforwarderimpl.cpp) — clave `Network/PortForwardingEnabled`.
- [Session settings](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/base/bittorrent/sessionimpl.cpp) — rutas modernas `BitTorrent/Session`.
- [Preferences](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.4/src/base/preferences.cpp) — autenticación y UPnP WebUI son opciones separadas.
