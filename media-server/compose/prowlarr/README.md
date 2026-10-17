# Prowlarr Compose Module

Gestor de fuentes con config NVMe, sin HDD; Knaben/The Pirate Bay y sincronización Radarr comprobados.

- [Guía canónica](../../docs/prowlarr.md): requisitos, despliegue, configuración y validación.
- [Manifest](compose.yaml), [environment template](.env.example), [image lock](image-lock.json).

Sólo este servicio; no guardar runtime, bases de datos ni secretos en el módulo. El instalador de primer despliegue rechaza estado existente.
