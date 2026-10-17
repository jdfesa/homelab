# Radarr Compose Module

Gestor de películas fijado por digest; config NVMe, bind común /data e importación por hardlink comprobados.

- [Guía canónica](../../docs/radarr.md): requisitos, despliegue, configuración y validación.
- [Manifest](compose.yaml), [environment template](.env.example), [image lock](image-lock.json).

Sólo este servicio; no guardar runtime, bases de datos ni secretos en el módulo. El instalador de primer despliegue rechaza estado existente.
