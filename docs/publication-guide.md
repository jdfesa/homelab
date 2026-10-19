# Public Repository Guide

**Status:** Publication safeguards and repository CI definition · **Remote:** [jdfesa/homelab](https://github.com/jdfesa/homelab), branch `main` · **Reviewed:** 2026-10-18.

## Scope and Ownership

Un servidor físico Proxmox, **un repositorio `homelab`**. El README raíz muestra hardware, mapa e índice; cada VM/LXC tiene carpeta propia. DSM y media-server son los dos huéspedes elegidos para el mapa. No se añade un LXC ficticio ni la VM experimental al mapa de servicios permanentes; el inventario histórico no se borra.

La revisión cubre candidatos locales e índice Git; el historial requiere un análisis separado. No es una auditoría de exposición de red, autorización para modificar servidores ni garantía de seguridad total. No se cambia la contraseña de un servicio por hacer una revisión documental.

## Review Findings

| Material | Resultado / tratamiento |
| --- | --- |
| `.local/` de raíz y módulos | Contiene inventarios, notas SSH, URLs del sitio, evidencia/API y acceso temporal histórico; **ignorado**, no leer/copiar sus valores a archivos públicos |
| `tmp/`, backups, exports y secrets | Exclusión heredable a cualquier módulo; las reglas anteriores ancladas sólo a raíz no cubrían todos los huéspedes futuros |
| Runtime multimedia | Appdata, descargas, datos, caches, estado torrent excluidos por `media-server/.gitignore`; las bases SQLite/DB están excluidas desde la raíz para todos los módulos |
| `.env` y archivos `*.env` reales | Excluidos; `.env.example` y `*.env.example` siguen visibles como plantillas sin valores privados |
| Claves/tokens detectables en texto público | No se encontraron otras coincidencias reales en la revisión; se inspeccionaron falsos positivos de rangos IP de código, fixtures y texto de ayuda. El detector es limitado, no prueba ausencia absoluta |
| Ejemplo de acceso qBit | Valores sólo en su sección canónica; no duplicarlos ni reutilizarlos en otras instalaciones |
| Capturas | Las nuevas capturas multimedia se revisan visualmente; no basta el preflight textual. Se conservan los formularios originales con valores enmascarados y las excepciones específicas indicadas debajo; no se regeneran imágenes como evidencia |
| PDF de consulta | Conservado por indicación del usuario como documento público de terceros; origen indicado en [catálogo](../resources/sources.md). No confundirlo con inventarios privados ni atribuirle nuestra licenciaMIT |
| Topología, versiones, puertos y modelos de hardware | Datos descriptivos publicados intencionalmente para reproducibilidad. No son contraseñas, pero revelan características del laboratorio; no demuestran filtrado o ausencia de exposiciónWAN |
| Artefactos del SO/editor | `.DS_Store`, bytecode/caches Python, virtualenvs y node_modules excluidos; no excluir indiscriminadamente JSON/YAML/PNG/PDF y perder documentación útil |

Los binarios no los analiza el preflight textual; futuras capturas o cambios requieren revisión visual/OCR de nuevo. Complementar con un detector especializado de secretos, incluyendo los commits que se van a publicar. Ni una captura redacted ni un chequeo verde prueban una descarga/importación/reproducción real. Los resultados de ejecución se guardan en el área privada, no como inventario público.

## Explicit Public Exceptions

1. **[Ejemplo qBittorrent](../media-server/docs/qbittorrent.md#laboratory-login-example):** ilustra los campos de acceso. Elegir contraseñas únicas; no reutilizar los valores publicados ni repetirlos en scripts, Compose, JSON o informes de escaneo.
2. **[Formulario de torrent manual](../media-server/docs/workflow.md#worked-example-manual-season):** la captura completa original se conserva por elección explícita del propietario, en lugar de recortes. Muestra nombre/hash del torrent del ejemplo; no son credenciales de autenticación. Excepción limitada a esa imagen, no a publicar una colección ni otros hashes.
3. **Material de terceros:** el PDF aportado se mantiene como referencia pública por indicación del usuario. Se preserva su autoría; no se declara bajo MIT ni se inventa una licencia original. Revisar los términos del autor si se necesita reutilizarlo aparte.

El ejemplo no permite publicar contraseñas propias, API keys, cookies, hashes de autenticación ni inventarios. Un `.gitignore` ignora archivos completos, no campos individuales dentro de una guía.

## Ignore Ownership

- **[Raíz](../.gitignore):** reglas comunes heredables para `.local`, private/secrets/backups/exports/tmp, claves, entornos reales, bases SQLite/DB, dumps/discos virtuales, caches y temporales.
- **[Media server](../media-server/.gitignore):** runtime y formatos específicos de sus aplicaciones.
- Las copias nativas `config.xml`, `config.yaml`, `smb.conf` y bases Samba `*.tdb`/`*.ldb` también se ignoran en media-server; pueden contener claves/hashes. La plantilla `smb.conf.example` permanece visible.
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

En el entorno Codex envolver los comandos con `rtk proxy` según las instrucciones locales. La opción de reconocimiento es necesaria mientras la tabla del ejemplo permanezca; **sin ella el preflight bloquea esos valores**. No ponerlos en argumentos.

El script usa metadatos Git descartables fuera del proyecto para comprobar las reglas reales, sin inicializar esta carpeta ni depender de ignores globales del autor. Revisa candidatos de texto, patrones comunes y credenciales literales en configuraciones/tablas. Si existe Git, alerta archivos ya seguidos a pesar del ignore y examina también blobs del índice para detectar secretos staged aunque el archivo de trabajo se haya limpiado. Nunca imprime los valores encontrados.

**Límites:** no analiza historial de commits, formatos binarios, todas las variantes de secretos ni exposición del servidor. Reporta binarios para revisión manual. El flag sólo reconoce la tabla de contraseña del apartado canónico qBit, no desactiva las demás comprobaciones.

Con Gitleaks instalado, comprobar también el historial **después de los commits y antes del push**:

```sh
gitleaks git . --log-opts=--all --redact=100
```

Un resultado sin hallazgos no invalida las excepciones públicas conocidas: los detectores no reconocen todas las contraseñas genéricas ni leen los pixels de las capturas. No ejecutar un escaneo de todo el directorio privado ni subirlo a un servicio externo para validar archivos que no van a publicarse.

## Repository CI

El [workflow compartido](../.github/workflows/ci.yml) valida el repositorio en `push`, `pull_request` y ejecución manual. Es tooling transversal, no un servicio del homelab ni parte de una VM/LXC. Su primera ejecución alojada requiere publicar el workflow; las comprobaciones locales no prueban un resultado en GitHub Actions.

Un único job `Repository checks` usa un runner de GitHub `ubuntu-24.04` y Python 3.13:

1. Checkout completo del historial, sin persistir credenciales.
2. El preflight existente con reconocimiento exclusivo del ejemplo canónico de laboratorio; no amplía las excepciones de publicación.
3. [Gitleaks 8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) sobre el historial Git completo, con redacción del 100% y sin aceptar comentarios `gitleaks:allow`. Descarga el binario oficial Linux x64, verifica SHA-256 antes de extraerlo y elimina la herramienta temporal al terminar. No usa baselines ni añade excepciones al escáner.
4. Las pruebas comunes y de cada módulo mediante el runner existente. La integración sintética FFmpeg se omite si no están disponibles `ffmpeg`/`ffprobe`; no se trata como una validación de reproducción del servidor.

Las acciones oficiales están fijadas a commits completos; el escáner a versión y checksum. Al actualizarlos, verificar las referencias upstream y repetir la validación local. El job tiene permisos `contents: read`, límite de 15 minutos y cancela ejecuciones anteriores de la misma referencia. No utiliza secretos del homelab, SSH, runners propios, despliegues ni artefactos de informes.

Las fuentes privadas ignoradas no forman parte del checkout. Si un archivo privado ya está seguido, el preflight debe fallar: no excluirlo del escaneo para obtener un resultado verde. Los logs del preflight omiten valores y Gitleaks redacta los secretos; no subir reportes sin revisar ni habilitar trazas que impriman credenciales.

**Límites:** Actions se ejecuta después de recibir los commits; un fallo no impide su publicación ni configura por sí solo una regla de integración obligatoria. GitHub confirmó Secret Scanning y Push Protection habilitados en este repositorio en la revisión indicada; no se cambiaron esos ajustes. Mantener los controles locales antes del push y la revisión manual de imágenes/PDFs. Ninguna comprobación garantiza detectar todo dato personal o contraseña arbitraria. [Push Protection](https://docs.github.com/en/code-security/concepts/secret-security/push-protection).

Los comandos de [Local Preflight](#local-preflight) permiten repetir las comprobaciones fuera de GitHub. Para validar además la sintaxis del workflow con [actionlint](https://github.com/rhysd/actionlint), ejecutar `actionlint .github/workflows/ci.yml` con una versión instalada y revisada. Las [pruebas de contrato](../tests/test_ci.py) comprueban límites de permisos, eventos, pins, historial, checksum y redacción sin acceder a red ni secretos. No sustituyen ejecutar el workflow alojado.

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
   git add -- media-server/
   python3 scripts/check-publication.py --acknowledge-public-lab-password
   git diff --cached --stat
   git diff --cached --check
   git diff --cached
   ```

   Añadir soporte raíz relacionado sólo tras revisarlo, con rutas explícitas; no usar `git add -f`. El diff incluye intencionalmente el ejemplo qBit, no debería incluir otras claves. No pegar diffs no revisados en chats/issues. Complementar con un detector de secretos especializado; revisar historial si ya hay commits. No confundir estos comandos documentados con acciones ejecutadas por esta preparación.

6. Comprobar identidad Git local, licencia, contenido y destino; entonces crear el commit. No cambiar identidad global automáticamente:

   ```sh
   git commit -m "docs(media-server): document verified workflows and recovery"
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
