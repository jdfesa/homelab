# Operations Runbook

**Updated:** 2026-10-14 · **Default:** Read-only discovery.

## Access Check

Desde la Mac, en la raíz del proyecto:

```sh
rtk proxy ssh -o BatchMode=yes -o ConnectTimeout=10 proxmox-homelab 'hostname; pveversion'
```

Si aparece un error de clave de host, parar y confirmar identidad mediante consola/un canal confiable. No borrar entradas de `known_hosts` automáticamente. Si falla la autenticación, no insistir con claves o contraseñas ajenas: verificar alias y clave dedicada.

## Inventory Refresh

```sh
rtk proxy sh scripts/collect-inventory.sh
```

El script usa la configuración SSH local, transmite el colector por stdin y guarda un JSON con fecha UTC en `.local/inventory/`. Requiere RTK y SSH en la Mac; Python estándar y las utilidades relevadas en Proxmox. No copia ni instala el script en el servidor.

Opcionalmente admite otro alias SSH simple como primer argumento. No guarda passwords ni necesita un `.env` con credenciales.

Después de capturar:

1. Revisar `errors`: campos ausentes por fallo no equivalen a cero ni a ausencia de un servicio.
2. Comparar cambios de discos, huéspedes, capacidad, RAM y SMART.
3. Revisar los nombres de recursos y cualquier detalle privado antes de transferir información a documentos públicos.
4. Actualizar estado/fecha y separar observaciones de propuestas.
5. Mantener los JSON completos privados; no versionarlos para evitar trabajo de revisión.

La captura actual no releva el interior de VMs/LXC, topología del router, configuraciones completas de firewall ni permisos/autenticación de aplicaciones. Para esos puntos se requieren lecturas específicas y autorización/acceso adecuados.

## Local Verification

```sh
rtk proxy sh scripts/run-tests.sh
rtk proxy sh -n scripts/collect-inventory.sh
rtk proxy python3 -m py_compile scripts/inventory_host.py
```

Los tests no conectan al servidor. Cubren omisión de MAC/serial/rutas físicas de huéspedes, seriales DMI, UUIDs/logs LVM, mensajes SMART y stderr. Son una defensa limitada: los nombres arbitrarios de recursos siguen siendo potencialmente privados.

## Hardware Changes

Seguir [Planned Hardware](planned-hardware.md). Coordinar previamente cualquier apagado, cableado o reinicio. Después de conectar dispositivos, relevar sin formatear ni importar pools automáticamente. Guardar el mapeo de serial a bahía solo en notas locales si hace falta.

El colector SMART no inicia pruebas cortas/largas y evita despertar discos en standby. Si SMART queda incompleto por eso o por permisos, registrar el motivo; no declarar el dispositivo sano por ausencia de resultados.

## Backup Planning

No ejecutar un backup masivo de DSM a `local` sin revisar discos incluidos, tamaño y destino: la raíz libre ronda 78 GiB y el HDD físico tiene 2 TB brutos. Las posibilidades dependen de datos usados, compresión y cobertura real, aún pendientes.

Para diseñar el primer backup:

1. Identificar datos críticos, configuración y sistema que se desea poder recuperar.
2. Definir destino independiente del disco origen, espacio y retención.
3. Comprobar qué discos incluye Proxmox y cómo respaldar datos desde DSM de forma consistente.
4. Guardar credenciales/llaves de recuperación fuera del servidor y fuera del repo.
5. Hacer una restauración de muestra en un destino seguro que no sobrescriba la VM/datos originales.
6. Recién después automatizar y verificar notificaciones de fallo.

Proxmox diferencia modos de backup, consistencia y herramientas de restauración; un job no demuestra restaurabilidad. [Documentación oficial de vzdump](https://github.com/proxmox/pve-docs/blob/master/vzdump.adoc).

## Change Checklist

Antes de cambios que escriban configuración, discos o afecten disponibilidad:

- Objetivo y alcance aprobados; copia/backup apropiado.
- Acceso de consola y rollback verificados.
- Compatibilidad/versiones investigadas y notas de mantenimiento.
- Una aplicación/dispositivo a la vez.
- Test de aceptación y actualización de inventario/decision log.

Reinicios, upgrades de Proxmox/DSM, reparaciones mdraid/LVM, activación de firewall, formateos y despliegues de servicios **no** forman parte de una captura de inventario.
