# Installed Services

**Observed:** Host 2026-10-14 / Media VM 2026-10-15 / DSM RAM owner-confirmed 2026-10-19 · **Scope:** Host Proxmox y huéspedes; interior de `media-server` verificado por Guest Agent, DSM/XP pendientes.

## Guest Inventory

| ID | Name | State | vCPU | RAM | Disks | Startup |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | DSM | Running | 2, CPU `host` | 3072 MiB; confirmado por el propietario | 3,5 GiB en `local-lvm` + HDD físico de 2 TB | `onboot=1` |
| 101 | WinXPProSP3 | Stopped | 1, `x86-64-v2-AES` | 2048 MiB | 32 GiB en `local-lvm` + medio de instalación | No se observó `onboot=1` |
| 102 | media-server | Running | 2, CPU `host` | 4096 MiB | 64 GiB SCSI en `local-lvm`, Discard/IO thread; HDD físico 2 TB `scsi1`, GPT/ext4 RW en `/data` | Arranque automático no configurado durante la preparación |

No se observaron huéspedes LXC. Las asignaciones de vCPU son compartidas, no núcleos físicos reservados; la VM apagada no consume su asignación de RAM como una VM encendida.

### DSM

Entrada del huésped: [módulo DSM](../dsm/README.md). RAM actual de 3 GiB y funcionamiento normal reportados por el propietario; no se realizó una nueva consulta al host ni una prueba de carga. Los snapshots históricos de inventario conservan sus valores originales. Su README separa alcance observado de configuración interna pendiente.

- NIC VirtIO en `vmbr0`, `firewall=1` en la configuración.
- Disco de arranque SATA con `cache=writeback`; configuración observada, no elección validada aquí.
- Disco físico completo asignado por ruta estable `by-id`; su serial se omitió de la documentación.
- QEMU guest agent no configurado.
- Pendientes: versión real de DSM, modelo emulado/loader, paquetes, shares, usuarios, uso del volumen y backups internos.

El nombre de una VM no prueba qué aplicaciones contiene. No se accedió a DSM con credenciales internas ni se leyó contenido personal del HDD.

### Media Server

Estado, versiones, almacenamiento y pasos de reproducción pertenecen exclusivamente al [módulo media-server](../media-server/README.md). Este inventario conserva sólo su asignación de recursos para ver el conjunto del host; no duplicar aquí sus procedimientos ni cronología.

### Windows XP

**Registro histórico de una prueba**, excluida por el usuario del mapa raíz y de módulos permanentes; no se eliminó la VM ni se alteró su estado.

- NIC RTL8139 en el bridge de la LAN, con flag `firewall=1`.
- `ostype=l26` en Proxmox: inconsistente con el nombre del huésped, pendiente de confirmar/corregir en mantenimiento.
- El SO interno no se verificó arrancándolo. Si efectivamente es Windows XP, su soporte terminó y no debe tratarse como un endpoint seguro. [Microsoft](https://www.microsoft.com/en-us/security/blog/2013/08/15/the-risk-of-running-windows-xp-after-support-ends-april-2014/).
- Mantener apagada hasta definir su uso y aislamiento. No se cambió su red ni estado.

## Host Software

| Software | Version / evidence | Interpretation |
| --- | --- | --- |
| Proxmox VE | Metapaquete 9.2.0; manager 9.2.21 | Hipervisor instalado y operativo |
| QEMU / KVM | `pve-qemu-kvm` 11.0.3-4 | Runtime de las VMs |
| LXC | `lxc-pve` 7.0.0-2 | Soporte instalado; sin huéspedes observados |
| LVM2 | 2.03.31-2+pmx1 | Storage principal en LVM-thin |
| mdadm | 4.4-11 | Arrays de Synology visibles en el host |
| Btrfs tools | 6.14-1 | Utilidades; no implica que el volumen DSM esté montado |
| SMART tools | smartmontools 7.5-pve2 | Disponible; daemon activo |
| ProxMenux Monitor | `proxmenux-monitor.service`, active/running | Dashboard adicional; versión pendiente |
| log2ram | Unidad active/exited; `/var/log` en tmpfs de 512 MiB | Personalización existente, no creada en este relevamiento |
| Proxmox Backup Client | 4.2.8-1 | Cliente/utilidades, no prueba un PBS configurado |
| WireGuard tools | 1.0.20210914-3 | Paquete instalado, túneles no relevados |
| ZFS tools | 2.4.4-pve1 | Paquetes instalados; pools no relevados |

En el listado de paquetes inspeccionado no aparecieron Docker, Podman o Tailscale en el host. Esto no afirma nada sobre las aplicaciones internas de DSM ni sobre instalaciones no gestionadas por dpkg.

## Running Services

Se observaron 32 servicios running y cero unidades fallidas en la captura. Entre ellos:

- Proxmox: `pveproxy`, `pvedaemon`, `pvestatd`, `pvescheduler`, `pve-cluster`, `qmeventd` y `spiceproxy`.
- Infraestructura: SSH, chrony, cron, journald, KSM, LVM/device mapper, mdmonitor y smartmontools.
- Otros: ProxMenux Monitor, rpcbind, utilidades NFS, postfix local y zfs-zed.
- Ambos daemons de firewall presentes: que estén running no significa que filtren tráfico.

## Listening Ports

| Port | Service / evidence | Observed bind |
| --- | --- | --- |
| TCP 22 | SSH | Interfaces generales, IPv4/IPv6 |
| TCP 8006 | Proxmox web/API | Interfaces generales |
| TCP 8008 | Proceso Python; coincide con el monitor observado, asociación pendiente de confirmar | Interfaces generales |
| TCP 3128 | SPICE proxy | Interfaces generales |
| TCP/UDP 111 | rpcbind | Interfaces generales, IPv4/IPv6 |
| TCP 25 / 85 | Correo local / daemon API interno | Loopback |

Un bind general no prueba que el puerto sea accesible desde Internet: no se inspeccionaron NAT, router o exposición WAN. Verificar autenticación y alcance del monitor antes de permitir acceso remoto.

## Firewall and Backups

- `pve-firewall status`: `disabled/running`.
- Opciones de firewall de datacenter y nodo: sin valores explícitos en las consultas realizadas.
- nftables: cero tablas y cero reglas observadas.
- iptables/ip6tables: cero reglas; políticas base observadas `ACCEPT`.
- Por tanto, **no se observó filtrado de firewall del host**. El flag `firewall=1` de las NICs no lo reemplaza.
- Jobs de backup Proxmox: cero.
- Archivos de backup en `local`: ninguno listado.
- Backups dentro de DSM, destinos externos o trabajos manuales: **no verificados**, no afirmar que no existen.

No se activó firewall, eliminó servicios ni programó backups durante el inventario.
