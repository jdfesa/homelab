# Stack Guide

**Status:** Shared conventions only · **Updated:** 2026-10-15.

Este documento define requisitos transversales, no contiene manifests ni estado operativo de una VM. Cada servicio real vive en `<workload>/compose/<service>/`, dentro de su VM/LXC dueño. No crear un `docker/` global paralelo. El estado concreto se consulta en el README y roadmap del módulo correspondiente.

## Stack Requirements

Cada stack debe incluir `compose.yaml`, `.env.example` sin secretos, README de entrada y guía operativa según necesidad. Documentar:

- Versión exacta o política explícita de actualización; no actualizar automáticamente datos críticos al empezar.
- Puertos y a qué interfaces/redes se publican.
- Datos persistentes y bases de datos; fuera de Git.
- Variables requeridas, sin contraseñas reales ni valores locales privados.
- Backup consistente, restauración, health check y prueba de aceptación.
- Actualización y rollback, contemplando migraciones de esquema.

## Isolation

Elegir VM/LXC y aislamiento según cada carga, no asumir una VM de aplicaciones global. Mantener bases de datos sin exposición general cuando no la necesitan. Un dashboard o reverse proxy no sustituye autenticación ni reglas de acceso.

No montar sockets de Docker, directorios del host, dispositivos o shares con permisos amplios sin justificarlo. Verificar requisitos oficiales al elegir cada aplicación.
