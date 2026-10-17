# Media Server — Build and Recovery Runbook

**Leer primero este archivo.** Abrir sólo la sección del paso necesario. [Pendientes reales](TODO.md) · [Uso cotidiano](docs/workflow.md).

## Choose the Route

| Situación | Ruta |
| --- | --- |
| VM dañada, HDD sano y backup privado disponible | Recuperar la VM/configuración y verificar el HDD existente. **No formatear ni ejecutar instaladores de primer despliegue sobre estado restaurado.** Restauración aún no ensayada. |
| HDD averiado | Reemplazar sólo el disco correcto; preparar el nuevo montaje/UUID y recuperar los archivos desde otra copia. El backup del SO no recupera los videos. |
| Sin backup de configuración / instalación nueva | Seguir el orden siguiente. Habrá que configurar cuentas e integraciones: todavía no existe una reconstrucción completamente automática. |

**Objetivo:** recuperar servicios sin repetir toda la configuración. **Estado actual:** no hay un tiempo de recuperación medido ni backup/restauración independiente probados. Instalar Debian y recuperar terabytes queda fuera de una promesa de minutos.

## Installation Order

Orden operativo, no dependencias estrictas entre cada fila. Usar imágenes fijadas, no `latest`.

| Paso | Qué instalar/configurar | Por qué / receta canónica |
| --- | --- | --- |
| 1 | VM Debian, red/SSH, Docker/Compose | Base común. [VM](docs/setup-guide.md) y [bootstrap/red](docs/post-install-guide.md). |
| 2 | HDD `/data`, grupo media GID2000, guarda UUID/ext4/RW | Antes de cualquier app. [Almacenamiento](docs/storage-guide.md#current-prepared-state). Preparador destructivo **sólo para un disco nuevo confirmado**, nunca para adoptar una biblioteca existente. |
| 3 | Jellyfin | Ya permite reproducir contenido existente; biblioteca RO. [Instalador y bibliotecas](docs/jellyfin.md#deployment). |
| 4 | Samba, opcional para copiar desde otros equipos | Comparte Movies/TV; no interviene en las descargas automáticas. [Configuración nativa](docs/samba.md#reproduce-on-the-existing-debian-vm). |
| 5 | qBittorrent | Descargas en `/data/downloads`; sin acceso a biblioteca. [Primer despliegue](docs/qbittorrent.md#first-deployment-recipe). |
| 6 | Prowlarr | Fuentes para los gestores. [Primer despliegue](docs/prowlarr.md#first-deployment-recipe). |
| 7 | Radarr y Sonarr | Organizan películas/series; conectar Prowlarr + qBit. [Radarr](docs/radarr.md#5-first-deployment-recipe), [Sonarr](docs/sonarr.md#first-deployment). Adopción existente probada; adquisición nueva pendiente. |
| 8 | Bazarr | Usa el inventario de los gestores para EN/ES. [Despliegue, perfil, proveedor y aviso Jellyfin](docs/bazarr.md#first-deployment); búsqueda autónoma EN/ES. |
| 9 | Validar, no seguir sumando servicios | Archivo importado por hardlink, reproducción, idiomas y detección en Jellyfin. [Prueba del flujo](docs/validation.md). Inicializar bibliotecas; monitor de episodios probado. |

Los `deploy-*.py` son de **primer arranque**, exigen `--apply` y rechazan appdata existente. No restauran todas las integraciones. No borrar estado para hacerlos pasar. Cada guía contiene su comando; no ejecutar todo el índice en secuencia.

## What Makes the Next Setup Fast

| Conservar | Qué permite recuperar |
| --- | --- |
| **Git:** Compose, locks, scripts, plantillas y políticas | Infraestructura y versiones conocidas; no usuarios, bases de datos o claves reales. |
| **Backup privado de la VM/SO o configuración coherente:** appdata, Compose con `.env` reales, red, montaje/guardas y Samba/passdb | Usuarios, perfiles, claves, integraciones y estado del cliente. Appdata está en `/srv/media-server/appdata`; runtime Compose en `/srv/media-server/compose`. |
| **Copia independiente del HDD:** `/data/media` y, si se quiere reanudar, `/data/downloads` | Videos/subtítulos y datos de descargas. El HDD actual tiene `backup=0`: no está incluido en la copia del disco del SO. |

Respaldar bases de datos coherentemente, conservar propietarios/permisos y hardlinks, y probar una restauración aislada. Una copia en el mismo disco y un hardlink no son protección frente a su avería. Preferir la copia de VM para recuperar el conjunto. [Referencia Proxmox](https://github.com/proxmox/pve-docs/blob/master/vzdump.adoc).

**Falta cerrar:** destino independiente, backup consistente, recuperación no destructiva del HDD existente, restauración de muestra y tiempo medido. Hasta comprobarlo, no prometer «un comando / pocos minutos». [Seguimiento único](TODO.md).

## Environment and Git Rules

- **Conservar los `.env` de Compose:** ya sirven para IP e imagen. Plantillas sin secretos en Git; valores reales privados. **No añadir ahora otros `.env` de acceso ni un cliente API:** no aceleran esta reconstrucción y duplicarían credenciales. Reconsiderarlo sólo con una necesidad repetitiva concreta.
- En Git: `compose/`, `scripts/`, `config/`, políticas, guías y capturas útiles. **Fuera:** `.local/`, `.env` reales, claves/cookies, DB/appdata, backups, torrents, descargas, videos y `tmp/`. [Reglas raíz](../.gitignore) y [del módulo](.gitignore).
- Antes de guardar secretos, comprobar ruta ignorada y no seguida. `.gitignore` no cifra ni respalda archivos y no oculta lo ya versionado. [Accesos y comprobación](docs/service-access.md#environment-files-and-login-sessions).
- No cambiar rutas al restaurar: `/data/downloads` y `/data/media`; gestores con bind común para hardlinks. No usar descargas como biblioteca Jellyfin ni repetir formateos. DSM queda fuera.
