# Post-install Guide

**Status:** Base, storage and dedicated SSH verified / Jellyfin setup complete, automation pending · **Updated:** 2026-10-16.

## Verified State

Se comprobó la VM 102 desde el canal SSH ya confiable de Proxmox y su Guest Agent:

- GRUB PC instalado y `/boot/grub/grub.cfg` presente; el destino exacto elegido en el instalador no quedó capturado.
- Debian 13.7 `amd64`, kernel `6.12.111+deb13-amd64`, hostname `media-server`, 2 vCPU y 4 GiB asignados.
- Durante la preparación base sólo estaban el disco virtual del SO de 64 GiB y el CD. Posteriormente el HDD de 2 TB se asignó, recibió GPT/ext4 y se montó en `/data`; SO y swap permanecen en el disco virtual. Ver [Storage Guide](storage-guide.md) y [Scripts README](../scripts/README.md).
- Contraseña de root bloqueada; usuario inicial UID/GID 1000 con `sudo`, sin reglas `NOPASSWD` ni pertenencia al grupo `docker`.
- `qemu-guest-agent` **ya estaba instalado y activo** antes del bootstrap. Comunicación con Proxmox probada.
- SSH, Docker, containerd y Guest Agent activos, cero unidades fallidas.
- Zona horaria `America/Argentina/Buenos_Aires`, NTP sincronizado y `fstrim.timer` habilitado.
- IPv4 estática terminada en `.104` aplicada, validada y persistente tras reinicio, con gateway y resolución correctos.
- `hello-world` correcto y eliminado con `--rm`; ningún contenedor persistente o aplicación multimedia desplegada.
- Único puerto TCP en escucha observado: SSH 22. No se publicaron API Docker, paneles multimedia ni reglas NAT/WAN.

La preparación inicial no reinició VMs. Posteriormente se hicieron dos reinicios controlados sólo de `media-server` para habilitar escritura y verificar persistencia de GPT/ext4 y `/data`. No se desconectó el ISO, activó arranque automático ni modificó/reinició DSM. La secuencia de almacenamiento y la guarda Docker están en Storage Guide.

## Package Setup

Se ejecutó [scripts/bootstrap-debian.sh](../scripts/bootstrap-debian.sh) como root **dentro de Debian**, mediante el Guest Agent. Rechaza Proxmox, otro hostname o un sistema distinto de Debian 13 amd64. No cambia red, discos, contraseñas, sudoers ni grupos; no hace un upgrade general ni elimina paquetes incompatibles automáticamente.

| Component | Verified version |
| --- | --- |
| Docker Engine / CLI | 29.9.1 |
| Docker Compose plugin | 5.6.0 |
| containerd.io | 2.4.2 |
| Docker Buildx plugin | 0.38.0 |
| QEMU Guest Agent | `1:10.0.13+ds-0+deb13u1` |
| psmisc / fuser | `23.7-2`, añadido posteriormente como requisito de almacenamiento |

[base-packages.lock.json](../base-packages.lock.json) registra las versiones completas de los paquetes explícitos. También se prepararon CA, curl, gpg y arping, manteniendo SSH, sudo y Python. APT instala sus dependencias/recomendaciones normales: este lock no es un snapshot de todos los paquetes.

Docker se instaló desde su repositorio oficial HTTPS, con clave APT en `/etc/apt/keyrings/docker.asc` y fuente `/etc/apt/sources.list.d/docker.sources`, no con `curl | sh`.

### Reproduction

Los siguientes comandos son para una terminal **dentro de la VM**, desde una copia revisada de este módulo; no ejecutarlos en Proxmox ni en la Mac. RTK se usa para los comandos locales de la Mac y no es dependencia del huésped.

```sh
sudo bash scripts/bootstrap-debian.sh
```

Esa forma resuelve candidatos de Docker stable y fija sus versiones en la transacción. Para reproducir las versiones verificadas aquí:

```sh
sudo env \
  DOCKER_CE_VERSION='5:29.9.1-1~debian.13~trixie' \
  DOCKER_CLI_VERSION='5:29.9.1-1~debian.13~trixie' \
  CONTAINERD_VERSION='2.4.2-2~debian.13~trixie' \
  DOCKER_BUILDX_VERSION='0.38.0-1~debian.13~trixie' \
  DOCKER_COMPOSE_VERSION='5.6.0-1~debian.13~trixie' \
  bash scripts/bootstrap-debian.sh
```

Comprobar disponibilidad futura en APT: el lock no preserva los `.deb` ni fija todas las dependencias. El script conserva una configuración Docker existente; no usarlo para sobrescribir decisiones del administrador ni actualizar producción a ciegas.

### Logging and Privileges

Se inicializó `/etc/docker/daemon.json` con driver `local`, **3 archivos de 10 MiB por contenedor**, y se comprobó el driver efectivo. No es una cuota global para imágenes, volúmenes o el disco. Docker aplica esta política a contenedores nuevos.

Se administra Docker con `sudo`. No se agregó el usuario al grupo `docker`, que otorga privilegios equivalentes a root, ni se publicó el socket por TCP. No se instalaron Portainer, actualizadores automáticos o aplicaciones multimedia.

## Static IPv4

El usuario solicitó **`.104`** y confirmó su reserva/exclusión DHCP. No se inspeccionó el router de forma independiente. Dirección completa, gateway, MAC y datos de conexión se mantienen en `media-server/.local/`, no en archivos públicos.

Se conservó **ifupdown + dhcpcd**, interfaz `ens18`, sin instalar otro gestor o resolvedor. `/etc/network/interfaces` conserva `iface ens18 inet dhcp` porque invoca dhcpcd; el perfil `static ip_address` de `/etc/dhcpcd.conf` hace estática la IPv4 sin solicitar una concesión DHCPv4. IPv6 conserva su autoconfiguración previa.

[scripts/configure-static-ip.sh](../scripts/configure-static-ip.sh) aplica estos pasos:

1. Exigir `--apply`, variables válidas y `NETWORK_DHCP_EXCLUDED=yes`.
2. Detectar duplicados mediante ARP antes de escribir.
3. Respaldar configuración/resolver en un directorio root-only bajo `/var/backups/media-server/`.
4. Programar rollback automático a **180 segundos** con systemd.
5. Escribir el bloque marcado de IPv4 estática, gateway y DNS y solicitar relectura de dhcpcd.
6. Comprobar externamente ping, MAC y TCP 22; dentro de Debian verificar dirección, ruta, gateway, DNS y servicios.
7. Cancelar el timer **solo tras verificar**; conservar el backup. En la ejecución actual estas pruebas pasaron y se canceló el timer.

### Reproduction and Recovery

Copiar [.env.example](../.env.example) a `media-server/.local/site.env` del proyecto, completarlo privadamente y transferirlo por un canal apropiado. No versionar el archivo completado ni adivinar gateway/DNS.

Aplicar **desde consola o Guest Agent**, no desde el SSH que depende de la IP anterior:

```sh
# Dentro de Debian; sustituir la ruta privada del archivo.
sudo bash -c 'set -a; . "$1"; set +a; bash "$2" --apply' \
  _ /ruta/privada/site.env scripts/configure-static-ip.sh
```

Tras validar desde otro equipo, leer `/var/lib/media-server/provisioning/network-change.json` y detener el `<rollback_unit>.timer` exacto allí indicado. Si no se cancela, revierte a los 180 segundos. Para recuperación manual usar consola/Guest Agent y el `rollback.sh` del backup registrado. No cambiar la red del host Proxmox para resolver la del huésped.

## SSH Identity and Authorization

El primer SSH a la dirección DHCP detectó una entrada antigua incompatible en `known_hosts`. No se borró ni ignoró: se verificó la huella Ed25519 del huésped por Guest Agent a través de Proxmox y coincidió con la ofrecida por SSH.

Se creó una clave Ed25519 dedicada en la Mac, sin copiar la privada al repositorio, y un registro privado de identidad del huésped. La clave no tiene passphrase: proteger la Mac y evaluar una passphrase según el uso deseado.

**Ejecutado y verificado el 2026-10-16, con autorización explícita:** instalada sólo la pública dedicada para el usuario Debian, UID1000. No se copió la privada a Debian ni al repositorio. Se usó [install-ssh-public-key.py](../scripts/install-ssh-public-key.py) dentro del huésped por Guest Agent, después de comprobar hostname, usuario y huella del servidor contra el registro local confiable.

- El instalador exige `--apply`, hostname y UID esperados; valida una pública Ed25519, conserva bytes de claves previas y no duplica una clave existente ni elimina sus restricciones. Rechaza symlinks, propietarios inesperados y permisos de escritura inseguros.
- Se creó `.ssh` con modo0700 y `authorized_keys` con modo0600, ambos del usuario. La nueva entrada impide agent forwarding y X11 forwarding. Antes del reemplazo atómico se guardó contenido/metadata anterior bajo `/var/backups/media-server/ssh-key-<timestamp>-<suffix>/`, protegido para root. En esta VM no existía previamente `.ssh`.
- La prueba directa desde la Mac confirmó autenticación `publickey`, hostname e identidad UID1000 usando el perfil privado, `BatchMode=yes` y comprobación estricta de host key. No requirió contraseña ni se ignoró `known_hosts`.
- Se comprobó que `sudo -n true` falla, el usuario no pertenece a `docker` y no puede escribir al socket Docker. No se cambiaron sudoers, grupos ni contraseñas; tampoco se concedió una clave a root.
- Hash del archivo y configuración efectiva `sshd`, grupos, `/data`, servicios y configuración/proceso DSM coinciden antes/después. No se reiniciaron VMs ni SSH.

**Key-only probado no significa contraseñas deshabilitadas globalmente.** El cliente probado sólo permite pública; el servidor conserva `PasswordAuthentication yes`, `KbdInteractiveAuthentication no`, `StrictModes yes` y `PermitRootLogin without-password`. La contraseña root está bloqueada, pero eso no equivale a `PermitRootLogin no`. No se modificó la política global de autenticación en este paso.

### Reproduction and Recovery

Sólo para un usuario y pública aprobados, copiar el script revisado y **únicamente la pública** a un directorio root del huésped. Ejecutar como root **en Debian**, nunca en Proxmox ni en la Mac, sustituyendo el usuario y UID por los previamente comprobados:

```sh
python3 /root/media-server-scripts/install-ssh-public-key.py \
  --apply --expected-hostname media-server \
  --user '<DEBIAN_USER>' --expected-uid 1000 \
  --public-key-file /root/media-server-scripts/approved-ssh-key.pub
```

Para comprobar una instalación existente, **no hace falta reinstalar la clave**. Desde `media-server/` en la Mac:

```sh
ssh -F .local/ssh_config -o BatchMode=yes media-server 'hostname; id'
```

El perfil privado contiene la identidad y host key fijada. No aceptar otra huella sin verificarla por consola/Guest Agent. Para recuperación, mantener ese canal disponible; consultar `before.json` y el backup registrado. Si se revoca acceso, retirar sólo la entrada de la huella dedicada después de revisar cambios posteriores; no restaurar ciegamente un archivo antiguo que pueda borrar otras claves.

Resultados, huellas y rutas exactas están en `.local/ssh-key-installation-*.json`, `ssh-direct-verification-result.json`, `ssh-postflight-verification-result.json` y `ssh-key-authentication.log`, no en documentación pública. Formato/opciones de claves y comprobación de identidad: [OpenSSH sshd](https://man.openbsd.org/sshd.8#AUTHORIZED_KEYS_FILE_FORMAT) y [OpenSSH ssh](https://man.openbsd.org/ssh.1).

## Credential Hygiene

Nota histórica separada del flujo multimedia: el usuario no solicita cambios de credenciales del sistema; no insistir ni condicionar Jellyfin/automatización a esta tarea. No se realizó rotación por el agente.

La contraseña temporal fue expuesta en el chat y es muy débil. **No se guarda en archivos, guía ni memoria y no se necesitó para operar por Guest Agent.** Cambiarla privadamente desde la consola con `passwd`, sin enviarla al chat. No deshabilitar el acceso actual antes de comprobar otro y confirmar recuperación.

Ahora también puede cambiarse desde una Terminal **privada** de la Mac: desde `media-server/`, ejecutar `ssh -t -F .local/ssh_config media-server passwd`. Introducir la contraseña actual y la nueva sólo en esa Terminal, nunca en el chat ni en herramientas del agente. **Rotación pendiente de confirmación del usuario**; no se marca realizada por haber instalado una clave.

## Remaining Acceptance Checks

- [x] Primer arranque, hostname, Guest Agent y servicios base verificados.
- [x] IPv4 estática aplicada; validaciones de red correctas y rollback cancelado.
- [x] Docker/Compose oficiales, versiones registradas y `hello-world` correcto.
- [x] Recibir autorización explícita para la pública dedicada, preservando claves y sin root SSH.
- [x] Instalar la pública dedicada y comprobar conexión SSH key-only, preservando claves y privilegios.
- [ ] Cambiar contraseña temporal desde un canal privado.
- [x] Probar reinicio controlado y persistencia de red, montaje UUID y servicios.
- [ ] Diseñar backups y probar restauración.
- [x] Asignar HDD nuevo por `by-id` en sólo lectura y verificarlo sin montaje/formato ni cambios en DSM.
- [x] Preparar HDD autorizado con GPT/ext4, directorios/permisos y guardas de montaje; prueba de hardlinks del filesystem sin root.
- [x] Jellyfin desplegado, healthy, LAN HTTP200, asistente y bibliotecas completados; ver [guía del servicio](jellyfin.md).
- Consultar el [estado comprobado del módulo](../ROADMAP.md) y sus [pendientes técnicos](../TODO.md) antes de desplegar otro servicio; no repetir instalaciones ya realizadas.

## References

- [Docker Engine on Debian](https://docs.docker.com/engine/install/debian/).
- [Docker local logging driver](https://docs.docker.com/engine/logging/drivers/local/).
- [Debian dhcpcd.conf](https://manpages.debian.org/trixie/dhcpcd-base/dhcpcd.conf.5.en.html).
- [Debian network setup](https://www.debian.org/doc/manuals/debian-reference/ch05.en.html).
