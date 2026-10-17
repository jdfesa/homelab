# Jellyfin Compose Module

Imagen oficial fijada, config/cache NVMe y biblioteca RO; despliegue y reproducción LAN comprobados.

- [Guía canónica](../../docs/jellyfin.md): requisitos, despliegue, configuración y validación.
- [Manifest](compose.yaml), [environment template](.env.example), [image lock](image-lock.json).

Sólo este servicio; no guardar runtime, bases de datos ni secretos en el módulo. El instalador de primer despliegue rechaza estado existente.
