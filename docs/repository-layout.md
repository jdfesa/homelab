# Repository Layout

**Status:** Workload ownership rules applied · **Updated:** 2026-10-15.

## Reference and Scope

**Un único servidor físico Proxmox y un único repositorio `homelab`, confirmado por el usuario.** Cada VM o LXC se documenta en un módulo autocontenido con README propio. No crear repositorios separados para los huéspedes de este mismo laboratorio. La raíz sólo indexa; aquí no se dispersan recetas de una VM entre documentos generales. Crear módulos de trabajo reales, no carpetas vacías por anticipado.

## Directory Roles

| Path | Role | Versioned |
| --- | --- | --- |
| `README.md` | Entrada pública y resumen del estado real, en inglés | Sí |
| `docs/` | Inventario del host, políticas y convenciones realmente compartidas; README índice | Sí |
| `scripts/` | Inventario transversal y runner local de pruebas; README índice | Sí |
| `tests/` | Pruebas comunes de inventario/privacidad/estructura; README índice | Sí |
| `resources/` | Referencias compartidas, sin convertirlas en instrucciones; README índice | Revisar antes de publicar material de terceros |
| `<workload>/` | VM/LXC con README, roadmap, guías, scripts y pruebas propios | Sí, sin runtime ni secretos |
| `<workload>/.local/` | Evidencia privada, valores del sitio y notas de esa VM/LXC | No |
| `.local/` | Inventarios privados del host y notas compartidas de acceso | No |
| `tmp/` | Archivos temporales de trabajo | No |
| `backups/`, `exports/`, `private/` | Reservados para material privado si se usa | No |

`tmp/` existe localmente y está completamente ignorado. Git no conserva carpetas vacías; no agregar un `.gitkeep` dentro para forzar su publicación. Scripts que lo necesiten deben crearlo si falta en un clon futuro.

## Writing Conventions

- `README.md` en inglés.
- Resto de documentos: cuerpo en español; títulos y encabezados en inglés.
- Nombres de documentos en inglés `kebab-case`: `hardware-inventory.md`, no `inventario_hardware.md`.
- Identificadores técnicos/nombres oficiales conservan su forma original.
- `README.md`, `ROADMAP.md`, archivos fuente, `compose.yaml` y `.env.example` conservan sus nombres técnicos.
- Usar Markdown como fuente; generar PDF/Word solo si se necesita, sin reemplazar el archivo editable.
- En cada documento cambiante, indicar fecha, alcance y estado: observed, proposed, pending o completed.
- No presentar una app candidata como installed ni inferir capacidades de una VM solo por su nombre.

## Workload Module Contract

Cada VM/LXC tiene su propio directorio. `media-server/` aplica esta estructura; añadir subdirectorios sólo cuando contienen material útil:

```text
<workload>/
├── README.md             # Entrada, estado real, orden de lectura y comandos seguros
├── ROADMAP.md            # Objetivo, fases, pendientes y aceptación
├── docs/                 # Instalación, operaciones y decisiones específicas; README
├── scripts/              # Automatización específica revisada; README
├── tests/                # Pruebas específicas; README
├── images/               # Capturas propias revisadas, si aportan evidencia
├── compose/              # Sólo al incorporar servicios reales
├── .env.example          # Plantilla sin valores privados
├── .gitignore            # Guardas del runtime del módulo
└── .local/               # Datos del sitio y evidencia privada, ignorados
```

El módulo [DSM](../dsm/README.md) registra por ahora sólo lo observado y lo que falta; no inventa una instalación interna. El mapa principal sólo muestra DSM y media-server por decisión del usuario; no incluye la VM experimental ni un LXC no configurado.

El README de una VM debe permitir a otra persona entender qué está comprobado, qué falta, qué scripts son destructivos y desde dónde se ejecutan. Un cambio específico se documenta en ese módulo; el índice global sólo necesita actualización cuando cambian ownership, recursos o navegación. No duplicar versiones, cronologías y pasos operativos en varios índices.

En runtime, `.env`, volúmenes y bases de datos quedan fuera de Git. Compose irá en `<workload>/compose/<service>/`, con `compose.yaml`, `.env.example` y guía/README de ese servicio; nada de manifests vacíos o una segunda copia en un `docker/` global. Ver [Stack Guide](stack-guide.md).

### Media Server Module

El módulo [media-server](../media-server/README.md) contiene sus guías/decisiones en `docs/`, scripts y pruebas propios. `vm-config.json` es referencia, no export nativo ni provisionador. Su evidencia privada vive en `media-server/.local/`; la regla `.local/` de Git protege también futuros módulos. Las claves privadas de autenticación siguen fuera del repositorio.

## Validation

Desde el módulo: `python3 -m unittest discover -s tests -v`. Desde homelab: `sh scripts/run-tests.sh` ejecuta pruebas comunes y las suites de módulos con README. El runner no conecta a servidores ni realiza aprovisionamiento; prueba guardas y rutas de rechazo sin `--apply`, no acciones reales. Las pruebas comunes comprueban enlaces públicos, READMEs y ubicación de pruebas por módulo; ignoran evidencia privada/runtime.

## Growth Rules

Crear `proxmox/`, automatización o módulos adicionales cuando haya configuración revisada que mantener, no como decoración. No exportar `/etc/pve` completo para poblar el repo: puede incluir claves, tokens y otros secretos.

Evitar generar un repo grande de ejemplos nunca probados. Para cada carpeta nueva debe existir contenido útil y un motivo; documentar también qué todavía no sabemos.

## Publication Ownership

Las reglas comunes de `.gitignore` se heredan a cualquier nivel; añadir ignores de módulo sólo para runtime/formats específicos, no por cantidad de carpetas. Conservar plantillas y locks útiles. Ver [Public Repository Guide](publication-guide.md) y ejecutar el preflight local antes de publicar. La excepción pública qBit está documentada ahí; el resto de secretos/runtime siguen privados. El [LICENSE](../LICENSE) cubre contenido propio, no material de terceros.
