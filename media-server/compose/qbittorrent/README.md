# Qbittorrent Compose Module

Cliente fijado por digest, config NVMe y sólo downloads en HDD; rutas/categorías e integración Radarr comprobadas.

- [Guía canónica](../../docs/qbittorrent.md): requisitos, despliegue, configuración y validación.
- [Manifest](compose.yaml), [environment template](.env.example), [image lock](image-lock.json).

Sólo este servicio; no guardar runtime, bases de datos ni secretos en el módulo. El instalador de primer despliegue rechaza estado existente.
