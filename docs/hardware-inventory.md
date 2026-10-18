# Hardware Inventory

**Status:** Partial · **Observed:** 2026-10-14, zona horaria America/Argentina/Buenos_Aires · **Updated:** 2026-10-17.

**Addendum 2026-10-15:** se conectó un segundo HDD, WDC WD20EZRZ-00Z5HB0 de 2 TB, asignado por `by-id` a `media-server` como `scsi1`. Tras autorización explícita recibió GPT/ext4 y montaje `/data` por UUID, comprobado tras reinicio. DSM mantiene su WD20EZRX sin cambios. Ver [Storage Guide](../media-server/docs/storage-guide.md) para estado/SMART; las tablas de almacenamiento, uso y salud siguientes conservan la fotografía inicial del 14 de octubre.

Este documento reúne el relevamiento del hardware conectado y los datos físicos confirmados por el propietario, identificando su evidencia. Hay HDD adicionales pendientes de conectar; consultar [Planned Hardware](planned-hardware.md). Los valores de uso, temperatura y salud son una fotografía, no mediciones continuas.

## Scope and Evidence

Lecturas por SSH de `pveversion`, `lscpu`, `dmidecode`, `free`, `lsblk`, `df`, `pvesm`, `lvs`, SMART, PCI y systemd. No se montaron discos, ejecutaron reparaciones, instalaron paquetes ni iniciaron self-tests. La única modificación remota fue autorizar la clave SSH solicitada.

El inventario automático permanece en `.local/inventory/`, ignorado. Este resumen no incluye números de serie, MACs ni direcciones privadas de red.

## Host Platform

| Component | Observed value |
| --- | --- |
| Nodo | `pve`, único nodo relevado |
| Proxmox | `pve-manager/9.2.21`, build `4f6e0ac86f9e8c7f` |
| Sistema | Debian GNU/Linux 13.7, trixie |
| Kernel activo | `7.0.14-23-pve` |
| Plataforma DMI | Fabricante `By O.E.M.`, producto `H81M` |
| Motherboard DMI | Fabricante `By O.E.M.`, producto `H81BD3G` |
| CPU | Intel Core i5-4440 @ 3.10 GHz; máximo informado 3.30 GHz |
| Topología | 1 socket, 4 núcleos, 4 hilos; sin SMT activo |
| Arquitectura / virtualización | x86_64 / VT-x |
| RAM instalada | 2 × 8 GB DDR3 Kingston |
| RAM visible por Linux | 16.687.304.704 bytes, aproximadamente 15,54 GiB |
| Swap | 8 GiB; sin uso en la captura inicial |
| GPU observada | Intel integrada, familia Haswell; sin GPU dedicada observada |
| IOMMU | 13 grupos detectados; no implica que cualquier passthrough sea adecuado |

Los identificadores genéricos DMI no bastan para garantizar modelo comercial, capacidad máxima de RAM, ranuras disponibles o soporte hot-plug. Esos puntos requieren inspección física/documentación de la placa.

## Memory Modules

| Slot | Module | Size | Reported speed | Configured speed |
| --- | --- | --- | --- | --- |
| ChannelA-DIMM0 | Kingston KHX1866C10D3/8G | 8 GB | 1333 MT/s | 1600 MT/s |
| ChannelB-DIMM0 | Kingston KHX1600C10D3/8G | 8 GB | 1600 MT/s | 1600 MT/s |

El primer módulo presenta una diferencia entre `Speed` y `Configured Memory Speed` informada por firmware. No se cambió BIOS ni se diagnosticó un fallo por esa discrepancia.

## Power Supply

Datos de la unidad instalada confirmados por el propietario; no detectados por el inventario SSH ni verificados mediante un ensayo eléctrico.

| Field | Value |
| --- | --- |
| Marca / modelo | LNZ XS550-PS |
| Potencia declarada | 550 W nominales |
| Color | Negro |
| Certificación | Sin certificación, según el propietario |

[Referencia comercial aportada por el propietario](https://www.mercadolibre.com.ar/fuente-de-alimentacion-para-pc-lnz-xs550-ps-550w-negra/p/MLA43933347). Los 550 W declarados no son una medición del consumo real del servidor ni una validación de potencia entregada, eficiencia o protecciones.

## Connected Storage

| Device | Model | Raw capacity | Current role |
| --- | --- | --- | --- |
| NVMe | Micron 2500 / MTFDKBA512QGN-1BN1AABGA | 512.110.190.592 bytes (~512 GB / 476,94 GiB) | Proxmox, raíz y discos virtuales en LVM-thin |
| SATA HDD | WDC WD20EZRX-22D8PB0 | 2.000.398.934.016 bytes (~2 TB / 1,82 TiB) | Disco físico asignado a DSM como `sata1` |

### Proxmox Storage

| Storage | Layout | Capacity / usage at observation |
| --- | --- | --- |
| `local` | Directorio `/var/lib/vz` sobre la raíz ext4 | Raíz ~94 GiB útiles, ~11 GiB usados, ~78 GiB disponibles |
| `local-lvm` | Thin pool `pve/data` | 347,90 GiB; datos usados 1,01%; metadata 0,52% |
| `pve/root` | LV ext4 | 96 GiB de volumen bruto; los valores de `df` son menores por estructura/reserva del filesystem |
| `pve/swap` | LV swap | 8 GiB |

`local` y `local-lvm` comparten el mismo NVMe: no son dos discos ni destinos independientes de backup. El espacio de thin pool libre no se suma de nuevo a la capacidad física del NVMe. Un disco virtual de 32 GiB tampoco significa 32 GiB físicamente escritos.

### DSM Disk Ownership

La VM 100 tiene un disco virtual de arranque de 3,5 GiB y acceso al HDD físico de 2 TB. En el host se observan:

- Particiones Synology con `md0`, `md1` y `md2` ensamblados.
- VG `vg1`, LV `volume_1` de aproximadamente 1832 GiB, identificado como Btrfs.
- Advertencia LVM: cabecera PV antigua en `/dev/md2`.
- Ningún mount de ese volumen de datos en la salida inicial de `df`.

**No montar, reparar ni escribir esos volúmenes desde Proxmox mientras DSM usa el disco.** El ensamblado de RAID/LVM por el host merece una revisión controlada de ownership, después de respaldar datos; no se alteró durante el inventario. Los miembros y slots de mdraid no prueban redundancia física: hoy se observó un solo HDD.

El tamaño/ocupación real del volumen dentro de DSM está **pendiente**, no se deduce del tamaño del LV.

## Disk Health Snapshot

| Indicator | WD HDD | Micron NVMe |
| --- | --- | --- |
| SMART health | PASSED | PASSED |
| Power-on hours | 39.041 | 632 |
| Temperature | 32 °C | 29 °C |
| Reallocated / pending / uncorrectable sectors | 0 / 0 / 0 | No aplica a esos atributos ATA |
| UDMA CRC errors | 0 | No aplica |
| Load cycles | 215.478 | No aplica |
| Wear percentage used | No informado | 0% reportado |
| Media / error-log entries | No evaluado aquí como contador NVMe | 0 / 0 |
| Unsafe shutdowns | No informado | 39 |

SMART PASSED no garantiza que un disco no falle. Las horas del HDD refuerzan la prioridad del backup; no prueban por sí solas una avería. Los apagados inseguros del NVMe ameritan revisar energía y hábitos de apagado, sin inferir la causa ni afirmar que el disco tenga corrupción.

## Network

| Component | Observed value |
| --- | --- |
| Controlador | Realtek RTL810xE PCI Express Fast Ethernet |
| Interfaz física | `nic0` |
| Bridge principal | `vmbr0` |
| Link | 100 Mb/s, full-duplex, conectado |
| Capacidad anunciada por la NIC | 10/100 Mb/s |

100 Mb/s equivalen a un techo teórico de 12,5 MB/s antes de overhead. No se ejecutó un benchmark. Es un límite relevante para copias, backups, fotos y varios streams compartiendo el enlace. Cambiar solo un cable o switch no convierte esta NIC 10/100 en Gigabit; evaluar NIC compatible y el recorrido completo de red cuando se defina la necesidad.

## Open Questions

- HDD adicionales: cantidad, capacidad, salud, interfaces y datos existentes.
- Modelo físico de placa, ranuras/puertos libres, gabinete y ventilación.
- Red física completa y dispositivos que consumirán servicios.
- Consumo eléctrico real, UPS y necesidad de disponibilidad continua.
- Versión, paquetes, shares, capacidad libre y respaldos dentro de DSM.
