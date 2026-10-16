# Session Handoff

**Status:** Radarr account/root and Prowlarr/Knaben sync verified. Radarr → qBittorrent Test + Save confirmed by UI; profiles/naming and real import/playback pending · **Updated:** 2026-10-16.

## Start Here Next Time

Trabajar desde **`media-server/`**, no dispersar archivos en la raíz homelab. Leer este checkpoint, [README](../README.md), [Roadmap](../ROADMAP.md) y [Scripts README](../scripts/README.md). Los documentos describen el último estado verificado; al retomar, comprobar que siga vigente antes de escribir o desplegar.

**No volver a formatear, reinstalar Debian ni repetir el bootstrap. No tocar DSM.** Ya se completaron y verificaron base y almacenamiento; Jellyfin ya está desplegado y healthy; qBittorrent también desplegado; Prowlarr desplegado/healthy con autenticación completada y Knaben guardado/habilitado; Radarr desplegado/healthy con cuenta Forms/Enabled verificada; Sonarr e importación/playback reales pendientes; conexiones Prowlarr→Radarr→qBit configuradas.

## Last Verified State

| Area | State at session close |
| --- | --- |
| Platform | VM102 `media-server`, Debian13.7 amd64, 2vCPU/4GiB, SO virtual64GiB sobre NVMe |
| Base | SSH, Guest Agent, Docker29.9.1 y Compose5.6.0 activos; versiones completas en el lock |
| Administrative access | Pública dedicada instalada para UID1000; SSH directo `publickey` y host key estricta verificados. Sin sudo sin contraseña, grupo Docker ni pública root. Rotación privada de contraseña pendiente |
| Network | IPv4 fija terminada en `.104`, conservada tras reinicio; detalles completos sólo privados |
| Media disk | Sólo WD20EZRZ2TB, por `by-id` en `scsi1`, RW; GPT+ext4 montado por UUID en `/data` |
| Directories | `/data/downloads/{movies,tv}` y `/data/media/{movies,tv}`, root:media, GID2000, modo2770 |
| Safety | Docker requiere montaje y UUID/ext4/RW correctos; prueba negativa en namespace privado aprobada |
| Verification | Reinicio postformato correcto; hardlinks de filesystem probados con UID1000/GID2000 sin root. Revalidación no destructiva del 2026-10-16 correcta, cero unidades fallidas; no nuevo reinicio ni nueva prueba negativa de montaje |
| DSM | Sin cambios; configuración y proceso de VM100 se conservaron. Su HDD WD20EZRX no se tocó |
| Applications | Jellyfin12.2.0 configurado; qBittorrent5.2.4 con login/cambio de clave confirmados, sin descarga manual; Prowlarr2.6.5.5623 con1AppRadarr/FullSync yKnaben sincronizado; Radarr6.4.4.10685 con cuenta/raíz verificadas,1 indexador Knaben (Prowlarr),1 cliente qBittorrent Enabled por captura tras Save;0películas en última API anterior. Última salud API previa al Save: DownloadClientCheck; posterior no consultada. Importación/playback no verificados |
| Clients | Tablet y computadoras LAN confirmadas; sistema de tablet y compatibilidad de códecs pendientes de revisar |
| Repository | Módulo autocontenido; última suite completa:77 tests (19 compartidos+58 del módulo). Instalador y contrato Compose Jellyfin conservados |

El nombre `sdX` del HDD cambió al reiniciar. Identificar siempre por mapping/serial y UUID; **no copiar destinos de los logs históricos**. El probe de hardlinks no sustituye la prueba futura de importación Radarr/Sonarr. No se probó desconexión física del HDD ni restauración de backup.

## Immediate Next Step

1. **Foco solicitado: Jellyfin y reproducción.** La pública SSH ya está instalada/probada. El usuario rechazó reiterar cambios de contraseña como condición de avance: no pedir ni modificar credenciales del sistema, no insistir con tareas de acceso. Indicará sus cuentas de Jellyfin directamente en la interfaz cuando corresponda.
2. **Revalidar sólo si cambió el entorno o al retomar otra sesión:** VM/Guest Agent, UUID y RW de `/data`, servicios y guarda ya fueron comprobados el 2026-10-16. Se puede usar el verificador de Debian; ver [Storage Guide](storage-guide.md). No ejecutar preparador de discos ni reinstalar la clave sólo para comprobar conexión. No conceder pública root, sudo sin contraseña ni acceso al grupo Docker.
3. **Jellyfin terminado:** nombre `Media Server`, cuentaejemplo `jellyfin-admin`, interfaz/metadatosEnglish y regiónArgentina. Shows `/media/tv` y Movies `/media/movies`; referencias visuales finales en [guía canónica](jellyfin.md). API pública confirma `StartupWizardCompleted=true` el 2026-10-16. Permiso remoto **ON por elección expresa del usuario**; no revertir sugerencia anterior ni configurar router/VPN/proxy.
4. **Servicio elegido antes de la prueba manual: qBittorrent**, antes de prueba manual de reproducción. [Guía propia](qbittorrent.md), Compose/lock/script y contrato local conservados; LinuxServer5.2.4 desplegado/healthy, HTTP200 LAN/API403 anónima, rutas/categorías y ambosUPnPOFF verificados. Primer ingreso confirmado por captura del formulario; destino película indicado `/data/downloads/movies`, categoría movies e incompletos `/data/downloads/incomplete`; posteriormente verificados por API en la recuperación descrita abajo; datos temporales sólo en `.local/qbittorrent-initial-login.txt` modo0600, no leer/imprimir secretos en chat. No repetir instalador. Usuario confirma que NO inició descarga y que SÍ cambió contraseña qBit. Tras el reset posterior, el propietario pidió documentar únicamente la credencial elegida de qBit como [ejemplo del laboratorio](qbittorrent.md#laboratory-login-example); excepción expresa, no publicar otras claves. Archivo temporal previo ya no se trata como credencial vigente.
5. **Paso actual: perfiles/renombrado de Radarr; conexión qBittorrent completada.**
   - Cuenta Forms/Enabled y raíz `/data/media/movies` verificadas: no repetir alta ni raíz.
   - **App Radarr guardada en Prowlarr con Full Sync**, confirmada por usuario, captura original y API sólo lectura. Knaben ya está registrado en Radarr como **Knaben (Prowlarr)**, Torrent/Torznab, con RSS, Automatic Search e Interactive Search activados. No recrear la App ni duplicar el indexador.
   - Última consulta API **antes del Save de qBit:**1indexador/0clientes/0películas y DownloadClientCheck; los dos avisos anteriores de indexadores habían desaparecido. **Después, UI confirma1 cliente qBittorrent Enabled tras Save**; no hubo nueva consulta API/Health. [Receta y evidencia](radarr.md#saved-application-and-verified-knaben-synchronization).
   - **Recuperación qBit completada por solicitud del usuario:** antes no lograba login; IP/puerto alcanzables desde Radarr. Reset sólo de WebUI con backup privado, mismo contenedor reiniciado, credencial compatible elegida por usuario, documentada después como ejemplo por su solicitud expresa. Login fresco204; categorías/rutas y0torrents preservados; otros3contenedores intactos. [Método y evidencia](qbittorrent.md#webui-login-recovery--explicit-scoped-reset). No repetir reset ni leer temporal vieja.
   - **Cliente completado:** formulario aprobado con API Key vacía/HostIPVM/8080/SSL OFF/admin/categoría movies y ambos Remove OFF; Test verde y luego Save confirmados por capturas originales. Ahora1 cliente qBittorrent Enabled, Remote Path Mappings vacío. [Evidencia](radarr.md#saved-qbittorrent-client--ui-confirmation). No repetir Test/Save/reset ni crear otro cliente. **Siguiente intervención:** Radarr → Settings → Profiles; revisar captura antes de elegir perfil/límites, luego renombrado y película E2E.
   - Después: perfiles/renombrado y película E2E; audio original con inglés como fallback, subtítulos ES/EN seleccionables. Sonarr/subtítulos después;1337x/EZTV/FlareSolverr siguen TODO.
   - Originales de Prowlarr con API key excluidos; referencia anonimizada anterior etiquetada como editada con IA. Capturas de Apps y cliente qBit originales. Formulario qBit conserva IP LAN por solicitud de inclusión; texto reutilizable con placeholders. En esta actualización documental no se ejecutó ninguna operación runtime; el reset/POST Test anteriores constan en su registro.
6. **Documentación:** cada servicio tiene guía propia en `docs/<servicio>.md`; Compose sólo despliegue/README/lock/template. Mantener estado real y capturas finales, sin duplicar guías. Actualizar también diagrama/tabla del README, roadmap, TODO y vm-config al cerrar cada checkpoint; distinguir Test, Save y prueba real. Actualizar el [catálogo de accesos](service-access.md) con cada servicio/puerto y su copia privada `.local/service-access.md` con URLs reales. Una IP privada no es credencial; la separación público/local es por reutilización y minimizar datos del sitio, no una barrera de seguridad.
7. **Aceptar reproducción después:** probar película y episodio autorizados desde tablet/computadora cuando exista contenido. No marcar playback/automatización completos por tener contenedores healthy.

La reanudación no autoriza publicar paneles en Internet, conceder otros accesos, comprar hardware ni repetir formatos. La autorización de la pública dedicada ya fue ejecutada; validar por separado cualquier cambio de alcance.

## Later Milestones

- Revisar perfiles/renombrado y validar una película; raíz, Prowlarr/Knaben y cliente qBit Test+Save ya confirmados. Sonarr después; FlareSolverr y fuentes bloqueadas siguen TODO; guía propia por servicio en docs. No exigir descarga manual previa. Clave permanente qBit confirmada por usuario; no abrir tareas de sistema ni solicitar secretos en chat.
- Definir fuentes autorizadas, idioma/calidad/tamaño, seeding/limpieza, espacio libre y concurrencia.
- Probar importaciones reales con hardlinks: un bind mount común `/data` en Radarr/Sonarr y comparación dispositivo/inode, no sólo tamaño/hash.
- Documentar versiones/integraciones sin otros secretos (única excepción: ejemplo qBit pedido por propietario), backup independiente y restauración de muestra; el HDD físico no queda respaldado automáticamente por copiar la VM.
- Libros y música después de completar películas/series. El objetivo sigue siendo las cuatro capas, no sólo Jellyfin con cargas manuales.

## Files and Private Evidence

- [VM reference](../vm-config.json) y [package lock](../base-packages.lock.json): estado público y versiones; no exports Proxmox ejecutables.
- [Post-install Guide](post-install-guide.md), [Storage Guide](storage-guide.md) y [Decision Log](decision-log.md): pasos ejecutados, seguridad y límites.
- `media-server/.local/`: ubicación **actual** de valores y evidencia privados. La antigua `.local/media-server/` de la raíz ya no existe.
- Dentro de esa carpeta: `connection-notes.md`, `ssh_config`, `known_hosts`, `site.env`, resultados de base/red/HDD/formato/verificación/post-reinicio y `ssh-key-installation-*.json`, `ssh-direct-verification-result.json`, `ssh-postflight-verification-result.json`, `ssh-key-authentication.log`. No publicar ni copiar sus valores a documentación pública.
- El perfil SSH local apunta al nuevo `known_hosts`; los logs conservan rutas históricas por auditoría. La clave privada de autenticación permanece fuera del repositorio, bajo la cuenta administradora de la Mac.
- Dentro de Debian: scripts revisados en `/root/media-server-scripts/`, estado UUID en `/var/lib/media-server/provisioning/storage.json`, verificador de arranque en `/usr/local/sbin/check-media-storage`. Estas rutas son del servidor, no del repositorio.
- [Shared sources catalog](../../resources/sources.md): referencias aportadas; no instrucciones para ejecutar sin revisar.

## Local Validation and Resume Checklist

Desde este módulo: `python3 -m unittest discover -s tests -v` (58 pruebas). Desde homelab: `sh scripts/run-tests.sh` (77 pruebas al cierre). No requieren root/SSH ni ejercitan discos reales. En el entorno del agente, envolver comandos con RTK según las instrucciones del repositorio.

- [x] Leer checkpoint y comprobar estado real sin modificarlo (2026-10-16).
- [x] Instalar pública SSH aprobada y comprobar identidad/acceso directo `publickey`, sin aumentar privilegios del usuario (2026-10-16).
- [x] Usuario confirma organización de un Compose por servicio; continuar multimedia sin más tareas de acceso.
- [x] Jellyfin desplegado: imagen oficial12.2 por digest, UID1000:GID2000, appdataNVMe, mediaRO, healthy y HTTP200 LAN.
- [x] Asistente y bibliotecas completos: API y captura, Media Server, English/Argentina, permiso remotoON.
- [x] Radarr desplegado con módulo/guía/script propios y67tests locales; cuenta/raíz y Prowlarr verificadas; cliente qBit Test + Save confirmado por UI, capturas originales; aceptación E2E pendiente.
- [ ] Probar reproducción y actualizar roadmap/guía con evidencia revisada.

## Repository Publication Preparation — 2026-10-16

El propietario confirmó un solo Proxmox/un solo repo, mapa raíz DSM+media-server sin XP de prueba y MIT para contenido propio. Nuevos ignores heredables y preflight local con10tests compartidos adicionales; total77 (19+58). [Guía pública](../../docs/publication-guide.md). La credencial qBit se conserva como excepción pública por elección reiterada, sin cambios runtime. PDF público de terceros conservado y atribuido, fuera de nuestra licencia. El propietario confirmó [jdfesa/homelab](https://github.com/jdfesa/homelab) público y autorizó commits graduales/ordenados con Conventional Commits en inglés y un único push final. Origin y main están configurados; el remoto se verificó vacío al comenzar. Consultar `git status`, `git log` y `git ls-remote origin refs/heads/main` para comprobar el checkpoint Git antes de nuevas publicaciones. No usar force ni repetir el primer despliegue por clonar la documentación. Este trabajo de repositorio no avanza perfiles/renombrado ni aceptación multimedia.
