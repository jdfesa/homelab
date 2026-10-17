# SMB Library Access

Samba nativo de Debian permite copiar contenido existente desde Finder directamente a las bibliotecas. No pasa por qBittorrent, Prowlarr, Radarr ni Sonarr; **Sonarr no es requisito para copiar series existentes**.

| Share | Dirección de referencia | Ruta en Debian | Vista en Jellyfin |
| --- | --- | --- | --- |
| **Movies** | `smb://<IP_DE_LA_VM>/Movies` | `/data/media/movies` | `/media/movies` |
| **TV** | `smb://<IP_DE_LA_VM>/TV` | `/data/media/tv` | `/media/tv` |

Los nombres de recursos y configuraciones están en inglés. No compartir `/data` entero, `downloads`, appdata, homes, impresoras ni dispositivos físicos.

## Execution Model and Python

Samba se instaló como **servicio nativo `smbd` de Debian**; Python no sirve los archivos ni tiene que quedar ejecutándose. Se utilizó Python temporalmente para comprobar identidad/montaje, ejecutar los comandos de esta guía, escribir y validar la configuración, realizar probes pequeños y comparar el estado protegido antes/después. Ese transporte administrativo entró por SSH a Proxmox y ejecutó Python dentro de Debian mediante `qm guest exec`.

Los wrappers de esa intervención contienen valores del sitio y no son un instalador portable: permanecen fuera de Git. **No son necesarios para reproducir el procedimiento**; los comandos siguientes se ejecutan directamente en Debian. Los archivos reutilizables que sí se conservan son la [plantilla Samba](../config/samba/smb.conf.example), el [drop-in systemd](../config/samba/media-storage.conf) y la [guarda Python de almacenamiento](../scripts/check-media-storage.py), instalada como `/usr/local/sbin/check-media-storage`.

### Open the Debian Terminal

Desde la carpeta `media-server/` en la Mac, con el perfil SSH privado ya preparado según la [guía de acceso SSH](post-install-guide.md#ssh-identity-and-authorization):

```sh
rtk proxy ssh -t -F .local/ssh_config media-server
```

Esperar al prompt de Debian y ejecutar allí los comandos `sudo` de esta guía, **uno por uno**. RTK se utiliza en la Mac, no es dependencia del huésped. No juntar el cambio de contraseña con otros comandos entre comillas; si el shell queda esperando una comilla sin cerrar, cancelar con `Ctrl+C` y comenzar de nuevo.

## Configuration

- Debian13, paquetes `samba` y `smbclient`: versión comprobada `2:4.22.11+dfsg-0+deb13u1`, sin un contenedor adicional.
- [Plantilla smb.conf](../config/samba/smb.conf.example): autenticación local `tdbsam`, SMB3 con cifrado requerido y firma obligatoria, sólo TCP445.
- Escucha únicamente IPv4 LAN asignada y loopback. Allowlist de la subred LAN y localhost; no acceso guest ni NetBIOS. `nmbd` queda enmascarado.
- Sólo el usuario explícito de `valid users` accede a Movies/TV. `force group = media` aplica GID2000 dentro de esos recursos: **no requiere añadir al usuario al grupo Unix media** ni cambiar permisos de toda la colección.
- Nuevos archivos UID1000:GID2000, modo0660; directorios2770. Los directorios existentes mantienen sus permisos. No `chmod777`, chown/chmod recursivos ni cambios de contraseña Debian.
- Compatibilidad Apple mediante `fruit streams_xattr`; metadatos en streams y resource forks en archivos AppleDouble. No usar `fruit:resource=stream` con `streams_xattr` sobre ext4 por sus límites de tamaño. [Samba vfs_fruit](https://www.samba.org/samba/docs/current/man-html/vfs_fruit.8.html).
- [Drop-in de smbd](../config/samba/media-storage.conf): depende de `data.mount`, se detiene si éste desaparece y exige la guarda UUID/ext4/RW existente antes de iniciar.
- Jellyfin conserva su montaje **de sólo lectura**. La escritura ocurre mediante Samba, no mediante el reproductor.

## Reproduce on the Existing Debian VM

Primera instalación de Samba, no reparación de un servidor con recursos existentes. Ejecutar dentro de Debian con `sudo`, no en Proxmox ni en la Mac. Requiere usuario no-root UID1000, grupo media GID2000, directorios ya preparados y la guarda de almacenamiento instalada. Si ya existe una configuración Samba, revisarla y respaldarla antes: no sustituirla ciegamente.

1. Comprobar montaje/permisos y bloquear el arranque con valores predeterminados durante la instalación:

   ```sh
   sudo /usr/local/sbin/check-media-storage
   sudo stat -c '%U:%G %a %n' /data /data/media /data/media/movies /data/media/tv
   sudo systemctl mask smbd.service nmbd.service
   sudo apt-get update
   sudo apt-get install -y --no-install-recommends --no-remove samba smbclient
   ```

   Los cuatro directorios deben ser `root:media 2770`. El paquete crea un grupo vacío `sambashare`; esto no concede acceso al usuario. En Debian13 los VFS utilizados están en `samba`, sin necesitar el paquete de transición `samba-vfs-modules`. [Notas de Debian](https://www.debian.org/releases/trixie/release-notes/issues.html#samba-vfs-modules).

2. Respaldar la configuración predeterminada que instaló el paquete, fuera de la biblioteca:

   ```sh
   SMB_BACKUP=$(sudo mktemp -d /var/backups/media-server/samba-XXXXXXXX)
   sudo cp -a /etc/samba/smb.conf "$SMB_BACKUP/smb.conf"
   ```

   El directorio creado por `mktemp` queda protegido para root. Preparar una copia privada de la plantilla y sustituir **todos** los placeholders antes de instalarla:

   | Placeholder | Valor que debe comprobarse |
   | --- | --- |
   | `<LAN_ADDRESS_CIDR>` | IPv4 privada asignada a Debian con su prefijo; no una IP de Docker o Proxmox |
   | `<LAN_NETWORK_CIDR>` | Subred local autorizada que contiene al cliente y al servidor |
   | `<SMB_USER>` | Usuario Debian existente, no-root, UID1000 |

   No publicar el archivo completado ni introducir contraseñas en él. Conservar los nombres **Movies** y **TV**, las dos rutas y el grupo `media`. `hosts allow`, `bind interfaces only` y `valid users` son controles distintos; una IP privada no sustituye autenticación. [smb.conf](https://www.samba.org/samba/docs/current/man-html/smb.conf.5.html).

   Instalar la copia completada; `<REVIEWED_SMB_CONF>` es su ruta absoluta **dentro de Debian**, no la plantilla con placeholders:

   ```sh
   sudo install -o root -g root -m 0644 '<REVIEWED_SMB_CONF>' /etc/samba/smb.conf
   ```

3. Instalar el drop-in de almacenamiento. `<MODULE_DIR>` representa la ruta absoluta de una copia del módulo `media-server` en Debian:

   ```sh
   sudo install -d -o root -g root -m 0755 /etc/systemd/system/smbd.service.d
   sudo install -o root -g root -m 0644 '<MODULE_DIR>/config/samba/media-storage.conf' /etc/systemd/system/smbd.service.d/media-storage.conf
   ```

   La configuración y el drop-in quedan root:root0644; los secretos de Samba permanecen en su passdb privado, no en Git. El drop-in contiene:

   ```ini
   [Unit]
   Requires=data.mount
   After=data.mount network-online.target
   Wants=network-online.target
   BindsTo=data.mount

   [Service]
   ExecStartPre=/usr/local/sbin/check-media-storage
   ```

4. Comprobar antes de iniciar:

   ```sh
   sudo testparm -s
   sudo systemctl daemon-reload
   sudo systemctl disable nmbd.service
   sudo /usr/local/sbin/check-media-storage
   sudo systemctl unmask smbd.service
   sudo systemctl enable --now smbd.service
   sudo systemctl is-active smbd.service
   sudo ss -lntp 'sport = :445'
   ```

   Deben aparecer únicamente loopback IPv4 y la IPv4 LAN elegida; no `0.0.0.0`, IPv6 ni interfaces Docker. No abrir puertos del router, modificar las reglas de Docker ni reiniciar otros servicios.

5. En esa Terminal Debian **privada**, establecer la contraseña SMB **antes** de habilitar la cuenta. Elegir una de estas dos operaciones:

   **Cuenta SMB nueva**, para un usuario Linux que ya existe:

   ```sh
   sudo smbpasswd -a '<SMB_USER>'
   ```

   **Cuenta SMB existente**, para cambiar su contraseña:

   ```sh
   sudo smbpasswd '<SMB_USER>'
   ```

   Después de establecerla correctamente, habilitar la cuenta:

   ```sh
   sudo smbpasswd -e '<SMB_USER>'
   ```

   **`smbpasswd -e` sólo habilita: no establece, cambia ni sincroniza una contraseña.** No sustituye ninguno de los dos comandos anteriores.

   | Prompt | Qué introducir |
   | --- | --- |
   | `[sudo] password for ...` | Contraseña del usuario **Debian**, para autorizar `sudo`; no la de la Mac |
   | `New SMB password` | Nueva contraseña elegida para acceder desde Finder |
   | `Retype new SMB password` | Repetir exactamente esa nueva contraseña SMB |

   Es normal que no aparezcan caracteres al escribir. Introducir contraseñas sólo en esos prompts, nunca en argumentos, URLs, historial, chat o screenshots. La contraseña SMB es independiente de la de Debian/Jellyfin y no cambia ninguna de ellas. [smbpasswd](https://manpages.debian.org/trixie/samba-common-bin/smbpasswd.8.en.html).

## Copy from Finder

1. En la misma LAN, abrir **Finder → Go → Connect to Server** (`⌘K`).
2. Conectar a `smb://<IP_DE_LA_VM>/Movies` o `smb://<IP_DE_LA_VM>/TV`.
3. Elegir **Registered User** y usar el usuario autorizado y su contraseña **SMB**, no las credenciales de Jellyfin.
4. **Copiar**, no mover, una primera carpeta. No reemplazar archivos existentes sin revisarlos. Esperar a que termine antes de escanear/reproducir.
5. Comprobar reproducción y subtítulos en Jellyfin; conservar el original hasta verificar la copia. Si no aparece, usar **Dashboard → Scheduled Tasks → Scan Media Library**, cuyo funcionamiento está comprobado.

[Conexión a servidores desde Finder](https://support.apple.com/guide/mac-help/connect-your-mac-to-shared-computers-and-servers-mchlp1140/mac).

Organización recomendada, con nombres ilustrativos, no títulos que deban descargarse:

```text
Movies/
  Movie Name (2020)/
    Movie Name (2020).mkv
    Movie Name (2020).en.srt
    Movie Name (2020).es.srt
TV/
  Show Name (2020)/
    Season 01/
      Show Name (2020) S01E01.mkv
      Show Name (2020) S01E01.en.srt
      Show Name (2020) S01E01.es.srt
```

Cada película en su carpeta; series por temporada y episodios `SxxEyy`. Los subtítulos externos comparten el nombre base del video, con idioma `.en`/`.es`. No hace falta añadir una nueva raíz en Jellyfin: son las mismas bibliotecas existentes. [Películas](https://jellyfin.org/docs/general/server/media/movies/), [series](https://jellyfin.org/docs/general/server/media/shows/).

Esto **no incorpora automáticamente la colección a Radarr/Sonarr**. Si después se quiere administrarla con ellos, importar la biblioteca existente antes de buscar, evitando descargas duplicadas. No mover/renombrar manualmente archivos de torrents activos o ya gestionados para completar ese otro flujo.

## Verification and Limits

Comprobados mediante SMB autenticado en ambos recursos: crear carpeta, subir/recuperar bytes idénticos, renombrar y eliminar **sólo el probe**, permisos1000:2000/0660 y2770, lectura dentro del contenedor Jellyfin y limpieza final. Acceso anónimo rechazado, listeners acotados y montaje/guarda confirmados. No se modificaron archivos multimedia existentes.

Confirmados el acceso autenticado desde Finder, la copia de una película existente y su reproducción desde Jellyfin. Esto valida ese recorrido de ingreso manual; no garantiza la sincronización de cada pista de subtítulos, que debe comprobarse por separado.

Los recursos son RW: borrar desde Finder **borra esa entrada de la biblioteca**; no es lo mismo que retirar un torrent con sus archivos conservados. No hay papelera/recuperación Samba ni backup independiente configurados. Copiar contenido puede consumir espacio adicional; no eliminar originales basándose sólo en que la transferencia terminó.

## Troubleshooting and Recovery

- **Connection refused:** verificar `smbd`, puerto445, IPv4 asignada y guarda de montaje antes de cambiar permisos.
- **Authentication failed:** usar Registered User, usuario correcto y contraseña SMB. Si sólo se ejecutó `smbpasswd -e`, establecer primero la contraseña con `sudo smbpasswd '<SMB_USER>'`; la clave introducida ante `sudo` no se convierte en clave SMB. Verificar cuenta habilitada con `sudo pdbedit -L -v -u '<SMB_USER>'`, sin opciones que exporten hashes. No habilitar guest para resolverlo.
- **Permission denied:** comprobar `valid users`, `force group`, GID2000 y permisos de los archivos afectados. No añadir grupos generales ni aplicar cambios recursivos a toda la colección.
- **Credenciales antiguas en Finder:** expulsar el recurso y reconectar con el usuario correcto; revisar la entrada concreta del llavero si continúa reutilizando una contraseña anterior.
- **Archivo no visible en Jellyfin:** comprobar copia completa, nombre/ruta y lectura; usar el [diagnóstico de biblioteca](validation.md#library-discovery).

Para deshabilitar sólo SMB: `sudo systemctl disable --now smbd.service`. Esto no borra biblioteca ni detiene Docker. Para restaurar una configuración previa, detener Samba, revisar cambios posteriores, recuperar sólo su configuración/drop-in/passdb de una copia coherente y validar antes de arrancar. No purgar paquetes ni reemplazar archivos privados a ciegas como rollback.
