# qBittorrent Service Guide

Cliente de transferencia del flujo de películas, desplegado y probado con Radarr. No organiza la biblioteca: recibe trabajos del gestor y descarga en el HDD.

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

Para magnets/torrents añadidos directamente en la WebUI, revisar **Category + Save at**: con el modo Manual comprobado, elegir categoría no garantiza aplicar su carpeta. [Tabla de rutas, registro en el gestor e importación](workflow.md#add-a-torrent-manually). Un torrent al 100% no equivale a un archivo incorporado a Jellyfin.

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

1. Abrir `http://<IP_DE_LA_VM>:8080` y entrar con la credencial inicial privada.
2. En Tools → Options → Web UI, elegir una contraseña permanente propia; conservar autenticación y protecciones habilitadas.
3. En Downloads, comprobar destino `/data/downloads` e incompletos `/data/downloads/incomplete`.
4. Verificar categorías `movies` → `/data/downloads/movies` y `tv` → `/data/downloads/tv`.
5. Usar la misma credencial vigente al configurar el cliente en Radarr. Su campo API Key queda vacío.

No guardar secretos en argumentos, URLs, Compose o capturas. No utilizar logs completos como mecanismo de entrega de la contraseña temporal. Un reinicio puede cambiar esa temporal si no se reemplazó.

## Laboratory Login Example

Ejemplo de los campos de acceso; elegir una contraseña única en cada instalación:

| Campo | Valor de ejemplo |
| --- | --- |
| Username | `admin` |
| Password | `adminadmin` |

**No reutilizar estos valores en otros servicios ni en una instalación nueva.** Mantener las contraseñas y API keys propias fuera del repositorio.

## WebUI Login Recovery — Explicit Scoped Reset

El [script de recuperación](../scripts/reset-qbittorrent-webui.py) fue probado para la imagen fijada y un laboratorio **sin metadatos de torrents**. Requiere autorización para cambiar la credencial y rechaza trabajos existentes. No forzar sus guardas ni usarlo sobre un cliente poblado.

Como root en Debian, con el script revisado en `/root/media-server-scripts/`:

```sh
python3 /root/media-server-scripts/reset-qbittorrent-webui.py --apply --username admin
```

La contraseña se introduce por getpass, nunca en argv. El script valida contenedor/imagen/montajes, detiene sólo qBit, respalda privadamente el config y cambia únicamente Username/Password_PBKDF2 con escritura atómica. Reinicia el mismo contenedor y comprueba login fresco, rutas/categorías y preservación de otros servicios; intenta rollback si falla. No borra appdata, reinstala servicios ni deshabilita autenticación. Actualizar después la credencial en sus integraciones.

## Normal Operation

Añadir películas desde Radarr, no desde el cliente como rutina. Descarga completa, importación y alta en Jellyfin son etapas distintas. [Validación](validation.md).

- `stalledDL`: falta progreso de descarga; revisar disponibilidad y peers reales.
- `stalledUP`: puede ser una descarga completa sin subida activa; no confundirlo con fallo de descarga.
- qBit5.2.4 puede devolver JSON de resultados en `torrents/add`, no el antiguo texto `Ok.`. Confirmar la acción por infohash antes de reintentar: un error del parser no revierte un alta aceptada.

## Operation, Updates and Recovery

Operar desde `/srv/media-server/compose/qbittorrent/` dentro de Debian. Antes de actualizar, detener sólo este servicio y guardar copia privada consistente de appdata, manifiesto y entorno. Las sesiones/estado de torrents contienen datos sensibles. El contenido del HDD requiere copia independiente; backup de appdata no lo incluye.

La política de seeding/limpieza debe conservar biblioteca y torrents activos. No borrar archivos directamente para liberar espacio sin revisar los enlaces y el gestor. Restauración independiente aún no probada.

El mantenimiento periódico tiene una [receta canónica de limpieza](torrent-cleanup.md): dos reglas, auditoría privada, timer de seis horas y simulación por defecto. No confundir código probado localmente con un timer instalado o borrado habilitado en la VM.

## Primary Sources

- [LinuxServer qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/).
- [qBittorrent WebUI API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-5.0)). La respuesta concreta debe contrastarse con la versión instalada.
