# Native Service Setup

**Status:** Installed — systemd active, internal healthcheck and LAN browser rendering verified. English clock, service restart and nine local icons confirmed by HTTP hashes and browser appearance.

**Updated:** 2026-10-19.

## Scope and Access

Primer despliegue nativo después de la [creación del LXC](installation-guide.md). No instala Docker, no usa helpers de terceros ni modifica los servicios enlazados. No es una restauración ensayada ni un instalador automático: los bloques resumen operaciones del despliegue realizado, con placeholders para los valores del sitio.

La administración utiliza el SSH **ya autenticado** de Proxmox y `pct exec`. No necesita la contraseña de `root` del LXC ni habilitar un acceso SSH nuevo dentro del huésped. Requiere privilegios administrativos en Proxmox; no implica que una VM permita el mismo acceso.

Desde el Mac:

```sh
rtk proxy ssh -o BatchMode=yes -o StrictHostKeyChecking=yes proxmox-homelab
```

En Proxmox, comprobar `pct status 103`, `pct config 103` y `pct exec 103 -- hostname`; entrar con `pct exec 103 -- bash`. Adaptar ID y alias a otro despliegue. `rtk` se usa en el Mac, no se presupone instalado en el host/huésped. **APT, Node y Homepage se instalan dentro del LXC, no en Proxmox.**

## Runtime Policy

- HTTP directo desde la **LAN de confianza**, sin contraseña web, sólo enlaces y fecha/hora local. Sin tokens, consultas API a otros servicios ni monitorización remota.
- `HOSTNAME=<homepage-ip>`, puerto `3000`. Allowlist explícito de nombres/IP con puerto, nunca `*`. El alias `homepage` sólo sirve para clientes que puedan resolverlo; no se creó un registro DNS.
- `HOMEPAGE_AUTH_ENABLED=false` es una elección explícita para esta primera versión. El allowlist **no es autenticación ni firewall**; su rechazo HTTP desde un cliente sigue pendiente de comprobación.
- No se configuraron WAN, NAT, reverse proxy, TLS ni nuevas reglas de firewall. No publicar este acceso en Internet. Revisar autenticación, TLS y alcance de red antes de añadir exposición o integraciones sensibles. [Controles oficiales de acceso](https://gethomepage.dev/installation/).

## 1. Prepare Debian

Se creó el snapshot local `before-homepage-v260` antes de los cambios. Es un punto de retorno en el mismo almacenamiento, **no un backup independiente**; su restauración no se ensayó. No restaurarlo ni repetirlo automáticamente en un huésped con cambios posteriores.

Dentro del **LXC**, como `root`, actualizar el índice y revisar la simulación antes de aplicar:

```sh
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
apt-get update
apt-get -s upgrade
apt-get -y -o Dpkg::Options::=--force-confold upgrade
apt-get -y install --no-install-recommends ca-certificates curl git xz-utils python3 make g++ time
dpkg --audit
systemctl --failed --no-pager
```

La simulación observada no eliminaba paquetes; actualización y herramientas finalizaron correctamente, con auditoría dpkg limpia y ninguna unidad fallida en esa comprobación. Revisar siempre el resultado real de futuras actualizaciones.

## 2. Pin Source and Toolchain

Versiones y hashes completos: [source-lock.json](../config/source-lock.json). Homepage `v2.6.0`, Node `22.23.3` para `linux-x64`, pnpm `10.34.7`. No usar `latest`, regenerar el lock ni ejecutar `curl | bash`.

Dentro del **LXC**, en un destino nuevo:

```sh
useradd --system --user-group --home-dir /var/lib/homepage --shell /usr/sbin/nologin homepage
install -d -m 0750 /var/lib/homepage/build /var/log/homepage-setup
test ! -e /var/lib/homepage/build/v2.6.0
git clone --branch v2.6.0 --depth 1 https://github.com/gethomepage/homepage.git /var/lib/homepage/build/v2.6.0
cd /var/lib/homepage/build/v2.6.0
test "$(git rev-parse HEAD)" = 51cc1684f9f34a7877ed462b8f94c9cc687b4dde
chown -R homepage:homepage /var/lib/homepage
```

Si el usuario o los destinos ya existen, detenerse y revisar; no borrarlos ni repetir el primer despliegue como actualización. Después del cambio de propietario, consultar Git como `homepage`; no añadir excepciones globales `safe.directory`.

Descargar y verificar **antes de extraer**, dentro del **LXC**:

```sh
install -d -m 0755 /var/cache/homepage /opt/homepage-toolchain
cd /var/cache/homepage
curl --fail --location --retry 3 --proto '=https' --tlsv1.2 https://nodejs.org/dist/v22.23.3/node-v22.23.3-linux-x64.tar.xz -o node-v22.23.3-linux-x64.tar.xz
curl --fail --location --retry 3 --proto '=https' --tlsv1.2 https://nodejs.org/dist/v22.23.3/SHASUMS256.txt -o node-SHASUMS256.txt
grep ' node-v22.23.3-linux-x64.tar.xz$' node-SHASUMS256.txt | sha256sum --check --strict
curl --fail --location --retry 3 --proto '=https' --tlsv1.2 https://registry.npmjs.org/pnpm/-/pnpm-10.34.7.tgz -o pnpm-10.34.7.tgz
sha256sum node-v22.23.3-linux-x64.tar.xz pnpm-10.34.7.tgz
```

Contrastar ambos SHA-256 con el lock versionado. También se verificó el SHA-512 de pnpm contra `integrity` del registro oficial. **No continuar si hay un mismatch**. Los hashes no sustituyen una auditoría del código/dependencias.

```sh
test ! -e /opt/homepage-toolchain/node-v22.23.3-linux-x64
test ! -e /opt/homepage-toolchain/pnpm-10.34.7
tar --extract --xz --file node-v22.23.3-linux-x64.tar.xz --directory /opt/homepage-toolchain --no-same-owner
install -d -m 0755 /opt/homepage-toolchain/pnpm-10.34.7
tar --extract --gzip --file pnpm-10.34.7.tgz --directory /opt/homepage-toolchain/pnpm-10.34.7 --strip-components=1 --no-same-owner
export PATH=/opt/homepage-toolchain/node-v22.23.3-linux-x64/bin:/usr/sbin:/usr/bin:/sbin:/bin
node --version
node /opt/homepage-toolchain/pnpm-10.34.7/bin/pnpm.cjs --version
sha256sum /var/lib/homepage/build/v2.6.0/pnpm-lock.yaml
```

El hash del lock de dependencias también debe coincidir con `source-lock.json`. Node/pnpm quedan aislados en `/opt/homepage-toolchain`, sin reemplazar ejecutables del sistema.

## 3. Build with Temporary Memory

Se usaron temporalmente **2048 MiB de RAM**, sólo en este LXC, conservando un núcleo y 1024 MiB de límite swap. El límite habitual vuelve a **1024 MiB**. No apagar otros servicios por rutina para hacer entrar el build.

Ejecutar el bloque en una sesión **Bash dedicada del host Proxmox**, no dentro del huésped. Comprueba destino, aislamiento y margen disponible. El trap restaura RAM al salir o fallar; no sobrevive a una caída del host o `SIGKILL`, por lo que hay que comprobar el valor al reconectar.

```bash
set -eu
test "$(pct exec 103 -- hostname)" = homepage
test "$(pct config 103 | awk '/^unprivileged:/{print $2}')" = 1
test "$(pct config 103 | awk '/^memory:/{print $2}')" = 1024
test "$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)" -ge 3072
restore() { pct set 103 --memory 1024 >/dev/null; }
trap restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
pct set 103 --memory 2048
pct exec 103 -- bash -se <<'GUEST'
cd /var/lib/homepage/build/v2.6.0
test "$(runuser -u homepage -- git rev-parse HEAD)" = 51cc1684f9f34a7877ed462b8f94c9cc687b4dde
export PATH=/opt/homepage-toolchain/node-v22.23.3-linux-x64/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/var/lib/homepage CI=true NEXT_TELEMETRY_DISABLED=1
export NODE_OPTIONS=--max-old-space-size=1536
export NEXT_PUBLIC_VERSION=v2.6.0 NEXT_PUBLIC_REVISION=51cc1684f9f34a7877ed462b8f94c9cc687b4dde
export NEXT_PUBLIC_BUILDTIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
runuser -u homepage -- node /opt/homepage-toolchain/pnpm-10.34.7/bin/pnpm.cjs install --frozen-lockfile --ignore-scripts --reporter append-only > /var/log/homepage-setup/dependencies.log 2>&1
/usr/bin/time -v -o /var/log/homepage-setup/build-time.txt runuser -u homepage -- node /opt/homepage-toolchain/pnpm-10.34.7/bin/pnpm.cjs run build > /var/log/homepage-setup/build.log 2>&1
test -f .next/standalone/server.js
GUEST
exit
```

`exit` cierra esa sesión Bash y ejecuta el trap, no apaga el LXC. Después, comprobar `pct config 103`: `memory: 1024`. La vuelta a 1024 también se verificó antes de desplegar. Si un paso falla, consultar los logs privados y no continuar con una salida incompleta.

Se omiten scripts de instalación de dependencias y se ejecuta explícitamente el build como usuario no privilegiado. El resultado es `.next/standalone/server.js`, no un servidor de desarrollo. [Instalación desde fuente](https://gethomepage.dev/installation/source/), [release fijada](https://github.com/gethomepage/homepage/releases/tag/v2.6.0).

## 4. Prepare Private Configuration

Desde el clon del repositorio, comprobar las rutas **antes** de crear archivos reales:

```sh
rtk git check-ignore homepage/.local/runtime/homepage.env homepage/.local/runtime/services.yaml
rtk git ls-files -- homepage/.local/
```

La segunda consulta debe estar vacía. Copiar privadamente `homepage.env.example` y `services.yaml.example` desde [config](../config/README.md) a `homepage/.local/runtime/`, con permisos `0600`, y reemplazar todos los placeholders. No introducir credenciales en URLs. El entorno lo lee systemd: **no ejecutarlo con `source`**.

Transferir por el canal administrativo existente a `/var/lib/homepage/staging/` dentro del LXC, con directorio `0700`:

| Repository input | Guest staging path |
| --- | --- |
| `homepage/config/settings.yaml` | `config/settings.yaml` |
| `homepage/config/widgets.yaml` | `config/widgets.yaml` |
| `homepage/config/homepage.service` | `config/homepage.service` |
| `homepage/config/source-lock.json` | `config/source-lock.json` |
| Private `homepage.env` | `runtime/homepage.env` |
| Private `services.yaml` | `runtime/services.yaml` |
| `homepage/icons/` PNGs, `icons-lock.json` and `LICENSE.txt` | `icons/` |

Staging es entrada temporal, no runtime ni backup. La reconstrucción usa templates de Git y valores aportados por el propietario, no archivos descartables de `tmp/`.

## 5. Install Production Release

Dentro del **LXC**, como `root`, con build completo y las entradas anteriores:

```sh
set -eu
test "$(hostname)" = homepage
test -f /var/lib/homepage/build/v2.6.0/.next/standalone/server.js
test ! -e /opt/homepage/releases/v2.6.0
test ! -e /opt/homepage/current
test ! -e /etc/homepage
test ! -e /etc/systemd/system/homepage.service
install -d -m 0755 /opt/homepage/releases/v2.6.0
cp -a /var/lib/homepage/build/v2.6.0/.next/standalone/. /opt/homepage/releases/v2.6.0/
cp -a /var/lib/homepage/build/v2.6.0/public /opt/homepage/releases/v2.6.0/public
cp -a /var/lib/homepage/build/v2.6.0/.next/static /opt/homepage/releases/v2.6.0/.next/static
test ! -e /opt/homepage/releases/v2.6.0/public/icons
install -d -m 0755 /opt/homepage/releases/v2.6.0/public/icons
for file in /var/lib/homepage/staging/icons/*.png /var/lib/homepage/staging/icons/icons-lock.json /var/lib/homepage/staging/icons/LICENSE.txt; do
  install -m 0644 -o root -g root "$file" /opt/homepage/releases/v2.6.0/public/icons/
done
chown -R root:root /opt/homepage/releases/v2.6.0
chmod -R go-w /opt/homepage/releases/v2.6.0
install -d -m 0750 -o homepage -g homepage /var/cache/homepage/runtime/next
test ! -e /opt/homepage/releases/v2.6.0/.next/cache
ln -s /var/cache/homepage/runtime/next /opt/homepage/releases/v2.6.0/.next/cache
ln -s releases/v2.6.0 /opt/homepage/current
install -d -m 0750 -o root -g homepage /etc/homepage
for name in docker kubernetes proxmox; do printf '{}\n' > "/etc/homepage/$name.yaml"; done
printf '[]\n' > /etc/homepage/bookmarks.yaml
: > /etc/homepage/custom.css
: > /etc/homepage/custom.js
install -m 0640 /var/lib/homepage/staging/config/settings.yaml /etc/homepage/settings.yaml
install -m 0640 /var/lib/homepage/staging/config/widgets.yaml /etc/homepage/widgets.yaml
install -m 0640 /var/lib/homepage/staging/runtime/services.yaml /etc/homepage/services.yaml
chown root:homepage /etc/homepage/*.yaml /etc/homepage/custom.css /etc/homepage/custom.js
chmod 0640 /etc/homepage/*.yaml /etc/homepage/custom.css /etc/homepage/custom.js
install -m 0600 -o root -g root /var/lib/homepage/staging/runtime/homepage.env /etc/homepage/homepage.env
install -m 0644 /var/lib/homepage/staging/config/homepage.service /etc/systemd/system/homepage.service
install -m 0644 /var/lib/homepage/staging/config/source-lock.json /opt/homepage/source-lock.json
systemd-analyze verify /etc/systemd/system/homepage.service
systemctl daemon-reload
systemctl enable --now homepage.service
```

La [unidad versionada](../config/homepage.service) ejecuta Node + standalone, sin pnpm/build en runtime. Código y configuración son de `root`, no modificables por la aplicación. Se crean todos los archivos base antes del arranque para evitar su generación automática sobre un directorio de sólo lectura.

El usuario/grupo `homepage` no tiene login interactivo, capabilities ni escalada de privilegios; filesystem protegido y cache separado. `LOG_TARGETS=stdout` evita escribir logs en `/etc/homepage`. `MemoryHigh=512M` y `MemoryMax=768M` dejan margen al sistema dentro de 1 GiB; no son memoria reservada. No activar `MemoryDenyWriteExecute` sin evaluar el JIT de Node.

## Presentation Inputs

El reloj de `config/widgets.yaml` fija `locale: en-US`, fecha completa con día de la semana y hora de 12 horas con AM/PM. Sólo cambia el widget: conserva `language: es` en los ajustes generales y no fuerza otra zona horaria del navegador. El propietario confirmó el formato en el portal después de aplicar el siguiente procedimiento y reiniciar sólo Homepage. Referencia: [Date & Time de Homepage](https://gethomepage.dev/widgets/info/datetime/).


### English Clock on an Existing Deployment

En la consola del **LXC**, como `root`, crear una copia privada antes de editar; las copias anteriores se conservan numeradas:

```sh
install -d -m 0700 /var/backups/homepage &&
cp -a --backup=numbered /etc/homepage/widgets.yaml /var/backups/homepage/widgets.before-en.yaml &&
cat /etc/homepage/widgets.yaml
```

Aplicar el widget de forma atómica conservando propietario/permisos y reiniciar únicamente el servicio. La guarda de hostname corresponde a este módulo; adaptar a otro despliegue:

```sh
(
set -e
test "$(hostname)" = homepage
test -f /var/backups/homepage/widgets.before-en.yaml

cat > /etc/homepage/widgets.yaml.new <<'EOF'
- datetime:
    text_size: xl
    locale: en-US
    format:
      dateStyle: full
      timeStyle: short
      hourCycle: h12
EOF

chown root:homepage /etc/homepage/widgets.yaml.new
chmod 0640 /etc/homepage/widgets.yaml.new
mv /etc/homepage/widgets.yaml.new /etc/homepage/widgets.yaml

systemctl restart homepage.service
systemctl is-active homepage.service
)
```

Comprobar `active` y recargar el portal: día de la semana/mes en inglés y hora con AM/PM. Si falla un paso, detenerse y revisar el error antes de continuar. La copia es un punto de retorno local del widget, no un backup independiente ni una restauración ya ensayada.

### Infrastructure Links

La plantilla incluye Proxmox, ProxMenux Monitor y DSM en `Infrastructure`, separados de las seis aplicaciones `Media`. Son enlaces de navegación: no instalan servicios ni proporcionan autenticación o consultas API a los destinos. Los nueve accesos están aplicados al portal y el propietario confirmó su actualización, con `homepage.service` activo después del reinicio. En otra instalación, sustituir `<proxmenux-monitor-url>` y `<dsm-url>` en el archivo privado con sus URLs completas, incluido esquema y puerto. La aparición de una tarjeta no comprueba la autenticación o disponibilidad de su destino.

### Local Icons

Los nueve PNG y su licencia se conservan en [homepage/icons](../icons/README.md), procedentes de descargas aportadas por el propietario desde [Homarr Labs — Dashboard Icons](https://github.com/homarr-labs/dashboard-icons). Se revisaron visualmente, se comprobó su estructura PNG/CRC y se registraron sus hashes SHA-256 en [icons-lock.json](../icons/icons-lock.json), sin editar bytes ni nombres. El commit de origen no fue comprobado independientemente; el manifiesto lo declara, sin inventar una versión fijada.

La plantilla utiliza únicamente rutas locales `/icons/<filename>.png`, incluyendo `proxmenu.png` para ProxMenux Monitor y `synology-dsm.png` para DSM. El contrato de despliegue copia PNG, manifiesto y licencia al `public/icons/` de la release nativa; propietario `root`, directorio `0755`, archivos `0644`. Las URLs y el reloj permanecen intactos. No se requiere otro servidor web, Docker, un helper externo ni acceso SSH directo al huésped.

**Estado comprobado:** integración aplicada, `homepage.service` activo y nueve respuestas HTTP de PNG verificadas contra los hashes del manifiesto. Se conservó una copia privada de `services.yaml` antes del cambio. El propietario confirmó los nueve logos en el navegador y aportó la [captura real del estado actual](../README.md#current-snapshot), conservada sin editar. El portal y su captura se actualizan cuando cambian los servicios, VMs o contenedores; esa vista no demuestra disponibilidad ni autenticación de los destinos.

Para un primer despliegue, transferir el directorio versionado `homepage/icons/` al staging indicado en la tabla de entradas; el bloque de instalación incorpora PNG, manifiesto y licencia antes del primer arranque. Después de una actualización de release hay que volver a incorporar estos assets: no forman parte del código upstream ni se descargan automáticamente. No repetir la integración inicial sobre una carpeta `public/icons/` ya existente sin revisarla.

Después de incorporar archivos públicos nuevos, reiniciar sólo `homepage.service` y comprobar que cada `/icons/<filename>.png` responde con el mismo hash. La guía de reconstrucción depende de los archivos versionados, no de tarballs o instaladores descartables de una intervención. El mecanismo de retorno ante fallo del instalador no tuvo que activarse y su restauración no se ensayó. No hay fallback CDN ni tareas de actualización automática de logos.

## Verification and Resource Evidence

| Check | Observed result |
| --- | --- |
| Unit syntax / activation | Verificación sin errores, `active/running`, habilitada dentro de Debian |
| Identity / protections | `User=homepage`, `Group=homepage`, `NoNewPrivileges=yes`, `ProtectSystem=strict` |
| Listener | `<homepage-ip>:3000` en la comprobación IPv4, no `0.0.0.0` |
| HTTP inside LXC | `GET /api/healthcheck` correcto; texto `up` |
| LAN browser | Portal y reloj en inglés confirmados por el propietario; tres tarjetas Infrastructure (Proxmox, ProxMenux Monitor, DSM) y seis Media, con los nueve iconos locales visibles |
| Service restart | Reinicios manuales confirmados con el reloj y los iconos; no se reinició el huésped |
| Local icons | Nueve PNG servidos por HTTP con hash SHA-256 coincidente; servicio `active` y copia previa de `services.yaml` conservada |
| Initial service memory | `MemoryCurrent=118648832` bytes (~113 MiB), después del primer healthcheck; no prueba bajo carga |
| Build peak / time | RSS máximo `1412344 KiB` (~1,35 GiB), `2:16.82`, salida 0; sólo build, no tiempo total de despliegue/restauración |
| Guest RAM after build | Restaurada y verificada en `1024 MiB` antes del despliegue |
| Disk margin | Unos `4,3 GiB` libres antes de copiar el standalone; falta medir espacio final y margen para otra release |

Dentro del huésped se verificó con `systemctl is-active homepage.service`, `systemctl show homepage.service`, `ss -lntp '( sport = :3000 )'` y `curl --fail http://<homepage-ip>:3000/api/healthcheck`, usando la IP real. Con bind específico no asumir respuesta en `localhost`.

**Aceptación pendiente:** destinos de los enlaces, rechazo de Host no permitido, reinicio del huésped, logs y memoria bajo uso representativo. La confirmación visual del portal no acredita que cada aplicación enlazada esté accesible ni que sus credenciales funcionen.

`homepage.service` está habilitado dentro de Debian; **Start at boot del LXC en Proxmox sigue desactivado**. Son controles distintos: el primero inicia la aplicación cuando arranca el huésped; no enciende el LXC tras reiniciar el host. No se definieron políticas de encendido/apagado.

## Maintenance and Recovery Limits

- Editar enlaces/presentación en `/etc/homepage` como administrador, conservando permisos; no modificar el código de la release. Cambios de entorno/unidad requieren reiniciar el servicio; el reinicio manual de Homepage se comprobó al aplicar el reloj, no un reboot del huésped ni recuperación automática ante fallos.
- Diagnóstico: `journalctl -u homepage.service --no-pager`, estado systemd, disco y eventos de memoria. Conservar salidas privadas fuera de Git.
- Actualizar requiere revisar changelog/seguridad, fijar versiones y hashes nuevos, recompilar en destino separado con margen de RAM/disco y repetir comprobaciones. No sobrescribir la release activa durante el build ni usar `pnpm update` como procedimiento. El cambio/retorno entre releases no está ensayado.
- Respaldar `/etc/homepage`, incluido el entorno privado, y el lock antes de cambios. Git, staging, cache y snapshot en el mismo disco no son una copia independiente. Sin restauración probada ni tiempo de recuperación garantizado.
- Las advertencias LVM de creación tienen diagnóstico separado; instalar Homepage no las corrige ni justifica modificar discos del host.
