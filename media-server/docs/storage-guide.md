# Storage Guide

**Status:** GPT/ext4 mounted and guard verified / Applications pending · **Updated:** 2026-10-16.

## Scope

Esta guía registra primero la asignación en sólo lectura y después la preparación del HDD multimedia. El usuario autorizó explícitamente **borrar sólo el WD20EZRZ de 2 TB, crear GPT + ext4 y montarlo en `/data`**, excluyendo DSM y su HDD. Indicó que los datos anteriores estaban respaldados; ese backup externo no se auditó de forma independiente.

Los scripts reutilizables están en [scripts/](../scripts/README.md), con README interno que identifica destino, propósito y guardas. Los valores privados no están embebidos en el código público.

## Current Prepared State

- `scsi1` por `by-id`, `cache=none`, IO thread, `backup=0`; **actualmente `ro=0`** y serial virtual `media-hdd-2tb`.
- GPT y una partición Linux `media-data`, inicio en sector 2048 (1 MiB); ext4 label `media-data`, bloques de 4096 bytes, journaling conservado.
- Perfil `largefile`: 1.907.840 inodes, aproximadamente un inode/MiB; reserva de bloques 1%. Controlar bytes e inodes antes de ampliar bibliotecas.
- `/data` RW por UUID en fstab, opciones `defaults,noatime,nodev,nosuid,noexec,nofail,x-systemd.device-timeout=10s`, fsck pass `2`.
- Directorios `downloads/{movies,tv}` y `media/{movies,tv}`: root:media, GID2000, modo `2770`. `lost+found` pertenece al filesystem, no a una biblioteca.
- Aproximadamente 1,80 TiB disponibles en la comprobación inicial; espacio/inodes variarán con el contenido y la inicialización del filesystem.
- Docker protegido por dependencia de `data.mount` y comprobación UUID/ext4/RW. No se desplegaron aplicaciones multimedia.

## Initial Read-only Attachment

La siguiente tabla conserva la **primera etapa**, anterior a la autorización de formato. El modo RO y NTFS aquí descritos ya fueron reemplazados por el estado anterior:

| Setting | Verified value |
| --- | --- |
| Target | VM `media-server`, ID de referencia `102` |
| Physical HDD | WDC WD20EZRZ-00Z5HB0, 2.000.398.934.016 bytes, aproximadamente 1,82 TiB |
| Mapping | Disco entero por ruta estable `/dev/disk/by-id/…`; identidad completa sólo en evidencia privada |
| Slot / controller | `scsi1` / `virtio-scsi-single` |
| IO thread / cache | Activado / `none` |
| Read-only | **`ro=1` temporal**, también comprobado dentro de Debian |
| Guest serial | `media-hdd-2tb`, identificador virtual para distinguirlo del disco del SO |
| Backup flag | `backup=0`; no confundir backup de configuración con copia del contenido físico |
| Existing layout | Tabla DOS/MBR y partición NTFS existentes; tabla sin cambios antes/después |
| Mount | Ninguno, ni en Proxmox ni en Debian |
| Activation | Hotplug comprobado por Guest Agent, sin apagar ni reiniciar VMs |
| Protected VM | DSM: configuración idéntica antes/después, mismo PID e instante de inicio del proceso, estado running |

El disco de DSM es un **WD20EZRX**, no el WD20EZRZ asignado aquí. Ambos tienen 2 TB: el tamaño no identifica el destino. Dentro de Debian aparece como disco QEMU y no con el modelo físico WD; identificarlo por el serial virtual y correlacionarlo con el mapping privado del host. No depender de `/dev/sdb`, aunque ése fuera el nombre observado en esta ejecución.

La inspección SMART del HDD nuevo informó PASSED, 37.488 horas, 31 °C y cero sectores reasignados, pendientes, no corregibles y errores CRC. No se inició un test de superficie ni una escritura de prueba. Este resultado no garantiza vida útil ni sustituye un backup.

## Initial Attachment Preconditions

Ejecutar la asignación **en Proxmox**, nunca dentro de Debian, y adaptar IDs/dispositivos al equipo real. No volver a añadir el mismo disco si ya está asignado.

1. Confirmar VM destino, disco virtual del SO y controlador; slot `scsi1` libre, sin lock ni cambios pendientes.
2. Revalidar el nuevo HDD por modelo, serie, capacidad y symlink `by-id`. Resolver también aliases WWN para no asignar un dispositivo ya usado bajo otro nombre.
3. Revisar todos los huéspedes, storage, fstab/crypttab, montajes, swap, usuarios abiertos y holders (RAID/LVM). Detenerse si el HDD o sus particiones están en uso. No montar ni reparar el disco de DSM desde el host.
4. Consultar SMART del disco nuevo sin cambiar parámetros. Revisar cualquier alerta antes de continuar.
5. Guardar copia privada de las configuraciones de ambas VMs, tabla de particiones, estado/proceso de DSM e inventario del huésped. En la ejecución actual se guardaron en un directorio root-only bajo `/root/media-server-provisioning/` y en `media-server/.local/` del proyecto.
6. Obtener el digest actual de configuración de la VM destino; usarlo como guarda contra cambios concurrentes.

## Assignment Command

El comando de asignación inicial tuvo esta forma, con valores privados comprobados. **No repetir ahora** sobre el disco ya preparado. Es una plantilla, no un script de descubrimiento ni de borrado:

```sh
# En Proxmox. Completar previamente las tres variables con los valores verificados.
: "${MEDIA_VMID:?Falta VM destino verificada}"
: "${MEDIA_DISK_BY_ID:?Falta ruta by-id verificada}"
: "${CONFIG_DIGEST:?Falta digest actual de la VM}"
qm set "$MEDIA_VMID" --digest "$CONFIG_DIGEST" --scsi1 \
  "${MEDIA_DISK_BY_ID},backup=0,cache=none,iothread=1,ro=1,serial=media-hdd-2tb"
```

No se habilitaron Discard/TRIM ni emulación SSD en el HDD. La configuración del disco virtual del SO no se cambió. El modo de sólo lectura es una protección temporal deliberada hasta autorizar la preparación del nuevo filesystem.

Hotplug funcionó en esta VM: no se requirió apagado. Si en una reproducción no funciona, revisar el estado y los cambios pendientes antes de considerar una parada controlada de **la VM multimedia**, nunca apagar DSM por este motivo. No recurrir a un apagado forzado automáticamente.

## Initial Attachment Evidence

- Configuración persistente de VM102 contiene `scsi1` con la ruta `by-id` esperada; el resto de opciones anteriores permanece igual.
- Guest Agent devuelve exactamente un disco con serial `media-hdd-2tb`, capacidad esperada, `RO=true`, NTFS detectado y ningún montaje en el disco o sus particiones.
- La tabla de particiones del HDD antes/después coincide. La comprobación es de metadatos y no una comparación completa de todos los archivos personales.
- Configuración DSM idéntica byte a byte y proceso de VM sin reinicio. No se cambió su disco, boot, red ni almacenamiento.
- El script específico y el resultado con IDs/seriales viven sólo en `media-server/.local/attach-hdd.py` y `hdd-attachment-result.json`. No publicar esos archivos ni copiar seriales/huellas a esta guía.
- En esa primera etapa sólo se verificó asignación en caliente/configuración; la preparación y prueba de reinicio se completaron después, como se detalla más abajo. La automatización de aplicaciones aún no funciona.

Los puntos anteriores describen lo verificado al asignar por primera vez, no el estado posterior al formato. La automatización de aplicaciones sigue sin desplegarse.

## Preparation Scripts and Executed Steps

### Enable Writes on Proxmox

Se ejecutó [set-media-disk-writable.py](../scripts/set-media-disk-writable.py) con ID destino/protegido distintos, ruta física `by-id`, modelo, serie y tamaño exactos. Exige `--apply` y que `scsi1` sea el disco RO esperado; revisa SMART, montajes, holders y referencias de otros huéspedes.

1. Guardar configuraciones y estado/proceso DSM en backup root-only bajo `/root/media-server-provisioning/`.
2. Apagar limpiamente sólo VM102 (`qm shutdown`, timeout 90 s, `forceStop=0`). Sin apagado forzado ni cambios a DSM.
3. Verificar configuración sin cambios concurrentes y bloque sin usuarios abiertos.
4. Cambiar sólo `ro=1` por `ro=0` mediante digest de configuración, iniciar VM102 y verificar el disco RW con Guest Agent. Todavía NTFS sin montar en ese momento.

Plantilla de reproducción **en Proxmox**, una sola vez antes del formato y con variables privadas verificadas:

```sh
python3 set-media-disk-writable.py --apply --node "$NODE" \
  --vmid "$MEDIA_VMID" --protected-vmid "$DSM_VMID" \
  --disk-by-id "$MEDIA_DISK_BY_ID" --expected-host-serial "$MEDIA_DISK_SERIAL" \
  --expected-model "$MEDIA_DISK_MODEL" --expected-bytes "$MEDIA_DISK_BYTES"
```

### Install the Required Safety Tool

El primer intento del preparador abortó **antes de borrar** porque faltaba `fuser`. Dentro de Debian se ejecutaron `apt-get update` y `apt-get install -y psmisc`: instalado `psmisc` 23.7-2, un paquete nuevo y cero upgrades. `sfdisk`, `e2fsprogs` y `util-linux` ya estaban disponibles. El bootstrap/lock/README de scripts ahora registran ese requisito; no se reejecutó todo el bootstrap ni se actualizaron versiones Docker.

### Create GPT and ext4 Inside Debian

Los scripts revisados se copiaron por stdin del Guest Agent a `/root/media-server-scripts/` (root-only) dentro de Debian. El código canónico queda en el repositorio. Comando ejecutado **dentro del huésped**, nunca en Proxmox:

```sh
# Destructivo. No repetir para reparar un montaje ni sobre una biblioteca existente.
python3 /root/media-server-scripts/prepare-media-storage.py --apply \
  --confirm-erase media-hdd-2tb --expected-bytes 2000398934016 \
  --guard-source /root/media-server-scripts/check-media-storage.py
```

[prepare-media-storage.py](../scripts/prepare-media-storage.py) comprueba root/hostname/Debian y rechaza Proxmox, serial/tamaño incorrectos, disco RO, NTFS inesperado, montajes/swap/holders/procesos abiertos, contenedores activos, colisiones de GID, fstab o `/data` existente con datos. Sin `--apply` no hace cambios y con estado previo rechaza repetir un formato.

Secuencia aplicada:

1. Backup root-only bajo `/var/backups/media-server/storage-…/` de fstab, tabla anterior, inventario y scripts. **No es copia de los archivos NTFS.**
2. `sfdisk --lock=yes --wipe=always --wipe-partitions=always` con entrada GPT y una partición Linux en sector 2048; esperar udev y verificar tabla/partición. Se eliminó la firma NTFS.
3. `mkfs.ext4 -L media-data -m 1 -T largefile -E nodiscard,lazy_itable_init=1,lazy_journal_init=0` sobre la partición nueva. Journaling conservado; no se escribió cero sobre todos los sectores ni se hizo una prueba destructiva de superficie.
4. Leer UUID, escribir fstab atómicamente preservando SO/swap/CD, verificar sintaxis y montar `/data` RW comprobando UUID/ext4.
5. Crear grupo `media` GID2000 y directorios acordados con setgid `2770`. No se añadieron usuarios al grupo: identidades/permisos de contenedores se concretarán al desplegar.
6. Probar un hardlink con UID1000/GID2000, sin root ni grupos suplementarios: mismo dispositivo/inode, linkcount2 y supervivencia del segundo nombre al borrar el primero; limpiar archivos de prueba.
7. Guardar estado/UUID root-only en `/var/lib/media-server/provisioning/storage.json`, instalar guarda y reiniciar Docker sin contenedores activos.

Es un formato lógico, **no un borrado seguro de todos los bytes**. El perfil `largefile` reduce densidad de inodes para este uso multimedia; no adoptar opciones que desactiven integridad para optimizar.

## Mount Safety

El directorio `/data` subyacente del SO quedó modo `000` antes de montar. Eso no frena a root por sí solo: Docker tiene este drop-in en `/etc/systemd/system/docker.service.d/media-storage.conf`:

```ini
[Unit]
RequiresMountsFor=/data
BindsTo=data.mount
After=data.mount

[Service]
ExecStartPre=/usr/local/sbin/check-media-storage
```

[check-media-storage.py](../scripts/check-media-storage.py), instalado en esa ruta, exige UUID esperado/ext4/RW. `nofail` mantiene Debian recuperable si falta el HDD; las dependencias y el chequeo bloquean Docker sin el volumen correcto. Aplica sólo a **esta VM multimedia dedicada**, no al host ni a DSM.

Se ejecutó [verify-media-storage.py](../scripts/verify-media-storage.py):

```sh
# Dentro de Debian, como root; no formatea.
python3 /root/media-server-scripts/verify-media-storage.py --probe-missing-mount
```

Verificó fstab/UUID, permisos, journal ext4, dependencias Docker, servicios y espacio. La ausencia de montaje se probó **sólo en un namespace hijo privado**: la guarda rechazó el caso y `/data` subyacente estaba vacío. El montaje global y Docker siguieron activos; no se desconectó físicamente el HDD.

La prueba de hardlinks es del filesystem/permisos, **no todavía una importación real Radarr/Sonarr**. Después se ejecutó `qm reboot 102 --timeout 90` desde Proxmox, sin cambios pendientes, y se repitió la verificación: `/data`, UUID, permisos, Docker y servicios base correctos; IP fija conservada y cero unidades fallidas.

**Hallazgo importante:** el nombre `sdX` del HDD cambió tras reiniciar, pero el montaje por UUID siguió correcto. Los campos device/partition de los logs del formateador son observaciones históricas; no usarlos como destinos para futuras operaciones. Se hicieron dos reinicios controlados de VM102 (habilitar escritura y probar persistencia); ninguno de DSM.

## Rollback Boundary

Después del formato no existe rollback automático del contenido anterior: guardar una tabla no recupera los archivos. Ante un fallo, usar consola/Guest Agent para inspeccionar UUID, fstab, `data.mount` y logs; **no repetir el preparador ni quitar guardas para descargar al SO**.

Antes de retirar el mapping, detener servicios y desmontar controladamente dentro de la VM. No hacer hot-unplug de un filesystem activo. Las copias de configuración permiten revisar diferencias, no restaurarlas a ciegas sobre cambios posteriores. No se probó desconexión física del HDD.

## Remaining Work and Evidence

- Evidencia privada: `enable-write-result.json`, `storage-format-preflight-missing-fuser.json`, `storage-format-result.json` y `storage-verification-result.json` en `media-server/.local/`; UUID reales sólo allí, fstab y estado root-only de la VM.
- Evidencia adicional de persistencia: `storage-post-reboot-result.json`, con verificación repetida después del reinicio.
- Pública SSH instalada y conexión directa verificada el 2026-10-16; ver [Post-install Guide](post-install-guide.md). Pendientes: rotación privada de contraseña, despliegue e importaciones reales, política de seeding/limpieza y backup/restore independiente.

La estructura ya existe, pero sin contenido ni aplicaciones. Ver [Roadmap](../ROADMAP.md) para aceptación completa y [Stack Plan](stack-plan.md) para servicios. `backup=0`: snapshots/copia de configuración no equivalen a backup del HDD.

## References

- [Proxmox VM documentation](https://github.com/proxmox/pve-docs/blob/master/qm.adoc) — discos, VirtIO SCSI y opciones de VM.
- La sintaxis `scsi[n]`, `ro`, `cache`, `iothread`, `backup` y `serial` se contrastó también con `qm help set --verbose` en el Proxmox instalado.
- [sfdisk](https://man7.org/linux/man-pages/man8/sfdisk.8.html) — GPT, alineación y firmas.
- [mke2fs](https://man7.org/linux/man-pages/man8/mke2fs.8.html) — perfil de inodes, reserva e inicialización ext4.
