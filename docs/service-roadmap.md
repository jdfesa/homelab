# Service Roadmap

**Status:** Cross-workload exploration / Not an operational rollout · **Updated:** 2026-10-15.

El objetivo es ganar comodidad con menos mantenimiento, no instalar todos los servicios de una lista. Este catálogo conserva ideas compartidas y estimaciones históricas, no el estado operativo actual. El trabajo multimedia concreto sigue únicamente su [Roadmap](../media-server/ROADMAP.md); futuros despliegues tendrán el suyo en su propio módulo.

## Safety Foundation

Antes de almacenar nuevos datos importantes:

1. Relevar DSM por dentro y conocer qué datos ya contiene.
2. Conectar e inventariar los HDD pendientes, sin borrar datos.
3. Elegir un destino independiente de backup y comprobar una restauración real.
4. Revisar filtrado de red y aislamiento del huésped legacy.
5. Medir el impacto del enlace de 100 Mb/s antes de cargas masivas.

La estrategia de discos queda abierta hasta completar el inventario. No se aprobó crear RAID/ZFS ni reemplazar DSM.

## Candidate Services

Los presupuestos de RAM son **estimaciones iniciales propias**, no promesas de rendimiento ni mínimos upstream, salvo donde se cita un requisito concreto. No se suman para instalar todo simultáneamente.

| Area | Candidate | Everyday benefit | Initial placement / budget | Dependencies |
| --- | --- | --- | --- | --- |
| Archivos y Mac | Reutilizar SMB / Time Machine de DSM si es compatible | Archivos en Finder y copias de la Mac | DSM existente; cuota según datos | Validar DSM, espacio libre y restauración; no duplicar otro NAS sin motivo |
| Backup de datos | Restic u otra herramienta según compatibilidad | Copias versionadas/cifradas fuera del disco origen | Agente/trabajo separado, no una app siempre pesada | Destino, retención, claves de recuperación y pruebas |
| Acceso remoto | Tailscale | Entrar a servicios desde fuera de casa | Huésped de infraestructura o dispositivos; ~256–512 MiB orientativos | Cuenta, MFA, ACLs; no publicar Proxmox en WAN |
| DNS doméstico | AdGuard Home | Reducir anuncios/trackers y facilitar nombres locales | LXC no privilegiado dedicado; ~256–512 MiB orientativos | Diseño DNS/router; probar primero un dispositivo y prever recuperación |
| Estado de servicios | Uptime Kuma | Alertas cuando una aplicación deja de responder | VM de apps / Compose; ~512 MiB–1 GiB orientativos | Canal de notificación y checks; no sustituye monitor externo del host |
| Documentos | Paperless-ngx | Buscar facturas, garantías y trámites por texto | VM de apps / Compose; ~2–3 GiB orientativos | Idioma OCR, archivos + BD, backup consistente; limitar concurrencia |
| Fotos | Immich | Biblioteca y carga de fotos desde el celular | VM Linux / Compose; reservar al menos 6 GiB según upstream | Dimensionar biblioteca, SSD para PostgreSQL y carga inicial; no migrar la única copia |
| Domótica | Home Assistant OS | Automatizaciones y control local | VM dedicada; mínimo upstream 2 GiB / 2 vCPU, ampliar según integraciones | Dispositivos reales, radios Zigbee/Thread si hacen falta y backup de configuración |
| Multimedia | Jellyfin | Biblioteca privada para TV y otros clientes | Huésped a definir; presupuesto según direct play/transcoding | Codecs/clientes, red y acceso a GPU; no prometer varios streams 4K |
| Acceso cómodo | Homepage, cuando haya suficientes apps | Portal único con enlaces y estado | VM de apps; ~256–512 MiB orientativos | No confundir dashboard con autenticación de los servicios |

## Verified Upstream Constraints

- Synology documenta Time Machine por SMB, con usuario/permisos y cuota. Es un candidato, no una funcionalidad ya comprobada en nuestra VM. [Synology](https://kb.synology.com/es-mx/DSM/tutorial/How_to_back_up_files_from_Mac_to_Synology_NAS_with_Time_Machine).
- Restic contempla backups cifrados, almacenamiento local/remoto y verificación; falta elegir integración y destino. [Restic](https://restic.net/).
- Tailscale conecta dispositivos mediante una red privada cifrada y normalmente evita port forwarding. Requiere su servicio de coordinación/cuenta: no describirlo como totalmente independiente de terceros. [Tailscale](https://tailscale.com/docs/concepts/what-is-tailscale).
- AdGuard Home filtra a nivel DNS: no bloquea todos los anuncios, incluidos los que comparten dominio con el contenido. [AdGuard Home](https://github.com/AdguardTeam/AdGuardHome#known-limitations).
- Uptime Kuma ofrece checks y notificaciones; su directorio de datos necesita almacenamiento local, no NFS. Un monitor en el mismo Proxmox no puede avisar por sí solo si todo el servidor se apaga. [Uptime Kuma](https://github.com/louislam/uptime-kuma).
- Paperless-ngx indexa documentos y realiza OCR. Empezar por un flujo simple sin enviar documentos a proveedores externos de IA. [Paperless-ngx](https://docs.paperless-ngx.com/).
- Immich pide mínimo 6 GB de RAM y recomienda 8 GB; PostgreSQL debe usar SSD local, no un share de red. Upstream recomienda una VM completa en lugar de Docker dentro de LXC. [Immich](https://docs.immich.app/install/requirements/).
- Home Assistant documenta un mínimo de 2 GB y 2 vCPU para la VM. [Home Assistant](https://www.home-assistant.io/installation/linux/).
- La transcodificación de Jellyfin depende de codecs y GPU; no asumir aceleración moderna por detectar una iGPU Haswell. Probar direct play y compatibilidad antes de planificar transcodificación. [Jellyfin](https://jellyfin.org/docs/general/administration/hardware-selection/).
- Homepage centraliza enlaces/widgets; agregarlo cuando aporte más que una carpeta de marcadores. [Homepage](https://gethomepage.dev/).

Fuentes consultadas el 2026-10-14; volver a revisar requisitos y releases al elegir una instalación.

## Resource Envelope

Con 15,54 GiB visibles, un escenario **orientativo, no aprobado**, podría ser:

| Workload | RAM planning |
| --- | --- |
| Reserva de host/cache/margen | ~3 GiB |
| DSM actual | 4 GiB |
| VM Debian para aplicaciones livianas | 2 GiB inicialmente, ampliable a 4 GiB |
| Home Assistant, si se elige | 2 GiB inicialmente |
| Windows XP cuando se encienda | 2 GiB adicionales |

Con apps a 4 GiB, ese ejemplo suma ~13 GiB sin XP o ~15 GiB con XP: el segundo deja poco margen. Immich con 6–8 GiB no debe agregarse a ese escenario sin redistribuir RAM/cargas. Las importaciones de fotos y OCR compiten por los mismos cuatro hilos de CPU. Primero incorporar una carga, medir y luego elegir la siguiente.

## Deployment Proposal

**Propuesta, no configuración existente:** mantener Proxmox para virtualización; agrupar stacks Compose en una VM Debian cuando se elijan apps; aislar DNS si se vuelve infraestructura crítica; Home Assistant OS en su propia VM si resulta útil. No instalar Docker directamente en el hipervisor como paso implícito.

El almacenamiento de bases de datos puede aprovechar el NVMe. Los datos grandes podrían residir en DSM o discos nuevos solo después de resolver ownership, salud y backup. No compartir directamente el disco físico de DSM entre dos huéspedes/host.

## Adoption Gate

Para cada incorporación definir:

- Problema concreto que elimina y qué uso actual complementa/reemplaza.
- Recursos, puertos, permisos, datos y dependencias.
- Instalación reproducible con versión elegida y documentación oficial actual.
- Backup + restauración, actualización manual inicial y rollback.
- Una prueba de aceptación cotidiana, antes de incorporar datos únicos o afectar a toda la red.

Evitar por ahora un stack de IA pesado, automatizaciones sin objetivo, Kubernetes o reemplazar todos los servicios cloud de golpe. Son temas posibles, no prioridades impuestas por el repositorio de referencia.
