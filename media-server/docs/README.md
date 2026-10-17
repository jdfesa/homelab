# Media Server Documentation

Entrada breve: [RUNBOOK](../RUNBOOK.md). Consultar únicamente la guía/sección del paso en curso; este índice es una referencia, no una lista que deba cargarse completa. No repetir pasos destructivos sobre una instalación preparada.

| Guía | Uso |
| --- | --- |
| [Setup](setup-guide.md) | Crear la VM e instalar Debian |
| [Post-install](post-install-guide.md) | Paquetes, red, SSH y recuperación |
| [Storage](storage-guide.md) | HDD, ext4/UUID, permisos y guardas |
| [Jellyfin](jellyfin.md) | Despliegue, bibliotecas y reproducción |
| [SMB library access](samba.md) | Copiar contenido existente desde Finder mediante Movies/TV |
| [qBittorrent](qbittorrent.md) | Cliente, rutas/categorías y recuperación WebUI acotada |
| [Prowlarr](prowlarr.md) | Fuentes comprobadas e integración con Radarr |
| [Sonarr](sonarr.md) | Primer despliegue, perfil HD, conexiones y límite de adopción |
| [Radarr](radarr.md) | Raíz, cliente, perfil HD/idiomas y renombrado |
| [Bazarr](bazarr.md) | Perfil EN/ES, proveedor, búsquedas autónomas y aviso a Jellyfin |
| [Everyday workflow](workflow.md) | Dónde añadir y dónde ver contenido |
| [Validation](validation.md) | Verificar transferencia, importación, hardlink y reproducción |
| [Service access](service-access.md) | Puertos y URLs reutilizables |
| [Stack plan](stack-plan.md) | Responsabilidades, montajes y límites de integración |
| [Design decisions](decision-log.md) | Criterios de diseño que explican la configuración |

Una guía canónica por servicio. Manifiestos y locks en `compose/`, herramientas probadas en `scripts/`, tests locales en `tests/`. Las notas de sesión, pruebas parciales e inventarios de descargas no forman parte de esta documentación pública.
