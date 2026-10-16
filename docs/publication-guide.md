# Public Repository Guide

**Status:** Reviewed publication policy and initial snapshot · **Remote:** [jdfesa/homelab](https://github.com/jdfesa/homelab), branch `main` · **Reviewed:** 2026-10-16.

## Scope and Ownership

Un servidor físico Proxmox, **un repositorio `homelab`**. El README raíz muestra hardware, mapa e índice; cada VM/LXC tiene carpeta propia. DSM y media-server son los dos huéspedes elegidos para el mapa. No se añade un LXC ficticio ni la VM experimental al mapa de servicios permanentes; el inventario histórico no se borra.

La revisión es de los archivos locales candidatos a Git, no una auditoría de exposición de red, autorización para modificar servidores ni garantía de seguridad total. No se cambió la contraseña de ningún servicio. Al revisar, la raíz no tenía `.git`: no había índice/historial/remoto de este proyecto que limpiar.

## Review Findings

| Material | Resultado / tratamiento |
| --- | --- |
| `.local/` de raíz y módulos | Contiene inventarios, notas SSH, URLs del sitio, evidencia/API y acceso temporal histórico; **ignorado**, no leer/copiar sus valores a archivos públicos |
| `tmp/`, backups, exports y secrets | Exclusión heredable a cualquier módulo; las reglas anteriores ancladas sólo a raíz no cubrían todos los huéspedes futuros |
| Runtime multimedia | Appdata, descargas, datos, caches, estado torrent excluidos por `media-server/.gitignore`; las bases SQLite/DB están excluidas desde la raíz para todos los módulos |
| `.env` y archivos `*.env` reales | Excluidos; `.env.example` y `*.env.example` siguen visibles como plantillas sin valores privados |
| Claves/tokens detectables en texto público | No se encontraron otras coincidencias reales en la revisión; se inspeccionaron falsos positivos de rangos IP de código, fixtures y texto de ayuda. El detector es limitado, no prueba ausencia absoluta |
| Contraseña real del ejemplo qBit | **Excepción pública deliberada, confirmada dos veces por el propietario**, incluida al preparar este repositorio público; ver abajo |
| Capturas |29PNG existentes revisados con OCR heurístico y referencias visuales aprobadas; sin claves visibles detectadas. Formulario qBit conserva una IP LAN por solicitud de inclusión; la ayuda de Prowlarr contiene además una IP de ejemplo. No se modificaron imágenes en esta revisión |
| PDF de consulta | Conservado por indicación del usuario como documento público de terceros; origen indicado en [catálogo](../resources/sources.md). No confundirlo con inventarios privados ni atribuirle nuestra licenciaMIT |
| Topología, versiones, puertos y modelos de hardware | Datos descriptivos publicados intencionalmente para reproducibilidad. No son contraseñas, pero revelan características del laboratorio; no demuestran filtrado o ausencia de exposiciónWAN |
| Artefactos del SO/editor | `.DS_Store`, bytecode/caches Python, virtualenvs y node_modules excluidos; no excluir indiscriminadamente JSON/YAML/PNG/PDF y perder documentación útil |

No se instaló ni ejecutó un detector especializado de historial. Los29PNG/1PDF no los analiza el preflight textual; futuras capturas o cambios requieren revisión visual/OCR de nuevo. Ni una captura redacted ni un chequeo verde prueban una descarga/importación/reproducción real.

## Explicit Public Exceptions

1. **[Ejemplo qBittorrent](../media-server/docs/qbittorrent.md#laboratory-login-example):** contiene la credencial real elegida para este laboratorio. El propietario pidió conservarla también en GitHub público después de ofrecer trasladarla a privado. Quien lea el repo podrá conocerla y quien tenga acceso al servicio podría probarla. No reutilizarla en otros servicios ni afirmar que el repositorio está libre de credenciales reales. No se repite el valor en scripts, Compose, JSON, esta guía ni informes de escaneo.
2. **[Formulario qBit aprobado](../media-server/docs/radarr.md#reviewed-qbittorrent-client-form--test-passed):** imagen original con IP LAN específica. Una IP privada no autentica por sí sola ni es globalmente enrutable, pero revela parte del mapa. El texto reutilizable y el catálogo mantienen `<IP_DE_LA_VM>`.
3. **Material de terceros:** el PDF aportado se mantiene como referencia pública por indicación del usuario. Se preserva su autoría; no se declara bajo MIT ni se inventa una licencia original. Revisar los términos del autor si se necesita reutilizarlo aparte.

La primera excepción no permite publicar otras contraseñas, API keys, cookies, hashes de autenticación ni inventarios. Un `.gitignore` ignora archivos completos, no un campo dentro de una guía; por eso no sirve para ocultar esa contraseña y conservar el resto del mismo archivo.

## Ignore Ownership

- **[Raíz](../.gitignore):** reglas comunes heredables para `.local`, private/secrets/backups/exports/tmp, claves, entornos reales, bases SQLite/DB, dumps/discos virtuales, caches y temporales.
- **[Media server](../media-server/.gitignore):** runtime y formatos específicos de sus aplicaciones.
- **DSM:** hereda las reglas comunes; no necesita duplicarlas en otro `.gitignore` sin un formato propio que añadir.
- No crear un `.gitignore` en cada subcarpeta por rutina. Añadir uno cuando haya reglas específicas; verificar que las plantillas/manifiestos/locks/guías sigan visibles.
- No usar `git add -f` para saltar estas guardas. Las reglas no sustituyen revisar contenidos.

[Git documenta](https://git-scm.com/docs/gitignore) que los patrones de subdirectorios pueden precisar los superiores, y que `.gitignore` no afecta a archivos ya seguidos. Una filtración requiere actuar sobre la credencial y revisar historial/copias, no sólo borrar el texto visible: [procedimiento de GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

## Local Preflight

Desde la raíz, Python3 y Git; sin acceso a servidores ni dependencia de RTK:

```sh
python3 scripts/check-publication.py --acknowledge-public-lab-password
sh scripts/run-tests.sh
```

En el entorno Codex envolver los comandos con `rtk proxy` según las instrucciones locales. La opción de reconocimiento es necesaria mientras el ejemplo real permanezca; **sin ella el preflight bloquea esa credencial**. No poner su valor en argumentos.

El script usa metadatos Git descartables fuera del proyecto para comprobar las reglas reales, sin inicializar esta carpeta ni depender de ignores globales del autor. Revisa candidatos de texto, patrones comunes y credenciales literales en configuraciones/tablas. Si existe Git, alerta archivos ya seguidos a pesar del ignore y examina también blobs del índice para detectar secretos staged aunque el archivo de trabajo se haya limpiado. Nunca imprime los valores encontrados.

**Límites:** no analiza historial de commits, formatos binarios, todas las variantes de secretos ni exposición del servidor. Reporta binarios para revisión manual. El flag sólo reconoce la tabla de contraseña del apartado canónico qBit, no desactiva las demás comprobaciones.

## First Publication Checklist

1. Releer hallazgos/excepciones y revisar cambios de texto, capturas y metadata; no publicar evidencia privada ni credenciales distintas de la excepción.
2. Ejecutar preflight y suite. Revisar qué queda candidato a Git y que las plantillas necesarias no se hayan ignorado.
3. Confirmar cuenta y nombre GitHub. **Destino elegido por el propietario: `jdfesa/homelab`, público, branch `main`.** API y `ls-remote` verificaron remoto vacío antes del primer commit. No sobrescribir un `origin` diferente.
4. Sólo si este proyecto aún no tiene `.git`, inicializarlo; si ya existe, conservar su historial y revisar lo que contiene:

   ```sh
   git init -b main
   git status --short --ignored
   ```

5. Preparar el índice y **revisarlo antes de confirmar/publicar**:

   ```sh
   git add .
   python3 scripts/check-publication.py --acknowledge-public-lab-password
   git diff --cached --stat
   git diff --cached --check
   git diff --cached
   ```

   El diff incluye intencionalmente el ejemplo qBit, no debería incluir otras claves. No pegar diffs no revisados en chats/issues. Complementar con un detector de secretos especializado; revisar historial si ya hay commits. No confundir estos comandos documentados con acciones ejecutadas por esta preparación.

6. Comprobar identidad Git local, licencia, contenido y destino; entonces crear el commit. No cambiar identidad global automáticamente:

   ```sh
   git commit -m "Document homelab architecture and reproducible media setup"
   ```

7. Crear un repositorio **público vacío** en la cuenta elegida y agregar su URL por SSH o HTTPS sin tokens incrustados. Ejemplo a sustituir, sólo si no hay remote:

   ```sh
   git remote add origin https://github.com/jdfesa/homelab.git
   git push -u origin main
   ```

8. Revisar en GitHub los dos Mermaid, enlaces/capturas, archivos visibles y exclusiones. Activar/revisar las protecciones de secretos disponibles; no presumir que detectarán una contraseña genérica de laboratorio. Actualizar fecha/destino y resultados realmente verificados.

**Registro de esta primera publicación:** el propietario confirmó el destino y autorizó inicializar Git, crear commits graduales con Conventional Commits en inglés y hacer un único push al final. Se reutiliza la identidad Git existente con email noreply; no se cambian valores globales. La revisión inicial sin Git fue una etapa anterior, no el estado actual. Este documento registra el procedimiento previo al push; comprobar el resultado con los comandos siguientes, sin confundir una receta escrita con verificación remota:

```sh
git status --short --branch
git log --oneline --reverse
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Tras el push, el SHA remoto de main debe coincidir con HEAD y no debe haber archivos pendientes en el árbol público. La evidencia de ejecución con timestamps pertenece a `.local/`, no contiene credenciales y no se sube como inventario privado.

## License

El propietario eligió **MIT para el código y documentación propios**, con aviso `2026 homelab contributors` en [LICENSE](../LICENSE), sin inventar su nombre legal. El material de terceros conserva sus términos/atribución, incluido el PDF de consulta y los productos documentados; no se relicencia por estar en esta carpeta. [GitHub explica el propósito de licenciar un repositorio](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).

## Keep This Review Current

Al añadir una VM/LXC, actualizar su README, mapa/tabla raíz e inventario compartido; no crear otro repositorio. Al añadir un servicio, actualizar su guía/módulo y diagramas/checkpoints pertinentes. Repetir la revisión de privacidad antes de cada push, especialmente después de agregar capturas, backups o scripts de recuperación. Ignorar un archivo no es hacerle backup: conservar los privados por separado con acceso restringido.
