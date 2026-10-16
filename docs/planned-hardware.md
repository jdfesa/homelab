# Planned Hardware

**Status:** Pending discovery · **Updated:** 2026-10-14.

**Addendum 2026-10-15:** un HDD WD20EZRZ de 2 TB ya fue conectado, relevado y preparado como GPT/ext4 `/data` en `media-server`; no debe contarse entre los pendientes de esta tabla. Ver [Storage Guide](../media-server/docs/storage-guide.md). Cantidad/modelos de cualquier disco restante siguen por confirmar.

El usuario tiene HDD adicionales todavía sin conectar. Este registro evita confundir hardware disponible físicamente con discos ya utilizables por Proxmox.

## Pending Devices

| Item | Quantity | Capacity / model | Connection | Intended role |
| --- | --- | --- | --- | --- |
| HDD adicionales | Por confirmar | Por relevar | Pendiente | Sin decidir: datos, backup u otro uso según salud y contenido |

No se presupone que estén vacíos, sanos, sean iguales o aptos para RAID. No se decidió comprar hardware.

## Discovery Checklist

Al conectar cada dispositivo, en una ventana de mantenimiento coordinada:

1. Identificar modelo, capacidad, interfaz y bahía; mantener el serial solo en notas privadas si se necesita mapear físicamente.
2. Registrar SMART, horas, temperatura, sectores reasignados/pendientes y errores de enlace.
3. Inspeccionar particiones y firmas sin montarlas en escritura ni importarlas automáticamente a un pool.
4. Determinar si contiene datos que deban preservarse y quién es su propietario actual.
5. Confirmar conexiones, alimentación, temperatura y estabilidad.
6. Repetir la captura de inventario y actualizar [Hardware Inventory](hardware-inventory.md).
7. Recién entonces comparar destinos de backup, almacenamiento independiente y alternativas con redundancia.

No ejecutar formateo, `wipefs`, creación de pools/RAID, reparaciones o pruebas largas sin aprobación específica. Tampoco reiniciar el servidor o asumir soporte hot-plug como parte del relevamiento.

## Design Dependencies

- Un disco adicional puede permitir una copia físicamente independiente; no demuestra una estrategia de backup completa.
- Más discos en la misma máquina no protegen por sí solos frente a robo, incendio, errores de administración o compromiso del host.
- Elegir RAID requiere conocer capacidad, salud y objetivos de disponibilidad; RAID no reemplaza backup.
- La estrategia final dependerá también de la cantidad real de datos de DSM y de qué servicios se incorporen.
