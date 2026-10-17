# Service Access

Los servicios desplegados comparten la IP LAN de la VM Debian y se distinguen por su puerto publicado. Sustituir `<IP_DE_LA_VM>` por el valor de la instalación, no por la IP del contenedor ni la de Proxmox.

| Servicio | URL de referencia | Guía |
| --- | --- | --- |
| Jellyfin | `http://<IP_DE_LA_VM>:8096` | [Biblioteca/reproducción](jellyfin.md) |
| qBittorrent | `http://<IP_DE_LA_VM>:8080` | [Transferencias](qbittorrent.md) |
| Prowlarr | `http://<IP_DE_LA_VM>:9696` | [Fuentes](prowlarr.md) |
| Radarr | `http://<IP_DE_LA_VM>:7878` | [Películas](radarr.md) |
| Sonarr | `http://<IP_DE_LA_VM>:8989` | [Series](sonarr.md) |
| Bazarr | `http://<IP_DE_LA_VM>:6767` | [Subtítulos EN/ES](bazarr.md) |

Los valores coinciden con los manifiestos actuales. El navegador usa el **puerto publicado en la VM**; no debe deducirse sólo del valor predeterminado del software.

## File Sharing

Samba es un servicio nativo de Debian, no otra WebUI ni un contenedor. Finder utiliza **TCP445** y los recursos `smb://<IP_DE_LA_VM>/Movies` y `smb://<IP_DE_LA_VM>/TV`, con usuario registrado y contraseña SMB propia. [Configuración y copia de contenido existente](samba.md).

Las URLs reales permanecen en `.local/service-access.md`, fuera de Git. No incluir contraseñas/API keys en URLs. Al cambiar un puerto o desplegar otro servicio, actualizar su guía, manifiesto y catálogo local.

## Environment Files and Login Sessions

Los `.env` de Compose **sí se conservan**: contienen la IP de publicación y la imagen fijada. No configuran por sí solos el login de la aplicación ni mantienen la sesión del navegador. [Docker](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).

No añadir un almacén `.env` genérico de credenciales para acelerar la recuperación. Las aplicaciones ya conservan sus ajustes en appdata privado; respaldarlo coherentemente. La [limpieza periódica de torrents](torrent-cleanup.md) usa un cliente acotado y un archivo privado propio para esa necesidad repetitiva, **separado** de los `.env` de despliegue. [Orden y recuperación](../RUNBOOK.md).

Git excluye `.local/`, `.env`, `.env.*` y `*.env`; permite `.env.example` y `*.env.example` fuera de carpetas privadas. Las plantillas no deben contener secretos. Antes de escribir un archivo privado, comprobar desde la raíz:

```sh
git check-ignore --no-index -v -- media-server/.local/site.env  # debe estar ignorado
git ls-files -- media-server/.local/site.env                  # debe quedar vacío
```

Permisos privados `0700`/`0600`; no imprimir claves, incluirlas en URLs ni usar `git add -f`. Un ignore no protege lo ya versionado ni sustituye un backup. [Reglas de publicación](../../docs/publication-guide.md#ignore-ownership).

## Private Address Is Not Authentication

Una IP privada no es una credencial ni abre acceso desde Internet por publicarla. Tampoco sustituye autenticación o controles de red: un router/proxy u otra vía puede hacer alcanzable el servicio. Usar placeholders aquí minimiza datos del sitio y facilita reutilizar la guía; no es una medida de autenticación. [RFC1918](https://www.rfc-editor.org/rfc/rfc1918#section-3).

No abrir puertos del router por documentar estos accesos. Sustituir los placeholders por los valores de cada instalación.
