#!/usr/bin/env bash
# Ejecutar dentro de la VM Debian como root. No configura red ni discos.
set -euo pipefail
export LC_ALL=C
export DEBIAN_FRONTEND=noninteractive

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ $(id -u) == 0 ]] || fail 'Se requiere root dentro de la VM, no en la Mac.'
[[ ! -d /etc/pve ]] || fail 'No ejecutar en el host Proxmox.'
[[ -r /etc/os-release ]] || fail 'No se encuentra /etc/os-release.'
. /etc/os-release
[[ ${ID:-} == debian && ${VERSION_ID:-} == 13 ]] || fail 'Solo se validó Debian 13.'
[[ $(hostname) == "${EXPECTED_HOSTNAME:-media-server}" ]] || fail 'Hostname inesperado.'
[[ $(dpkg --print-architecture) == amd64 ]] || fail 'Solo se validó amd64.'

for package in docker.io docker-compose docker-doc podman-docker containerd runc; do
    state=$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || true)
    [[ $state != installed ]] || fail "Paquete potencialmente incompatible: $package. Revisar, no quitar automáticamente."
done

apt-get update
apt-get install -y ca-certificates curl gpg openssh-server sudo python3 qemu-guest-agent iputils-arping psmisc

work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
backup="/var/backups/media-server/base-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 0700 "$backup"
install -d -m 0755 /etc/apt/keyrings
curl --fail --show-error --silent --location --proto '=https' --tlsv1.2 \
    https://download.docker.com/linux/debian/gpg -o "$work/docker.asc"
gpg --batch --show-keys --with-fingerprint "$work/docker.asc"
if [[ -f /etc/apt/keyrings/docker.asc ]]; then
    cp -a /etc/apt/keyrings/docker.asc "$backup/"
fi
install -m 0644 "$work/docker.asc" /etc/apt/keyrings/docker.asc

cat > "$work/docker.sources" <<'SOURCES'
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: trixie
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
SOURCES
if [[ -f /etc/apt/sources.list.d/docker.sources ]]; then
    cmp -s "$work/docker.sources" /etc/apt/sources.list.d/docker.sources \
        || fail 'Ya existe una fuente Docker distinta; revisar manualmente.'
fi
install -m 0644 "$work/docker.sources" /etc/apt/sources.list.d/docker.sources
apt-get update

# Primera ejecución: resolver candidatos stable y fijarlos en esta transacción.
# Reproducción: exportar estas cinco versiones usando el registro verificado.
candidate() {
    local value
    value=$(apt-cache policy "$1" | awk '/Candidate:/ {print $2}')
    [[ -n $value && $value != '(none)' ]] || fail "Sin candidato APT para $1."
    printf '%s' "$value"
}
ce=${DOCKER_CE_VERSION:-$(candidate docker-ce)}
cli=${DOCKER_CLI_VERSION:-$(candidate docker-ce-cli)}
containerd=${CONTAINERD_VERSION:-$(candidate containerd.io)}
buildx=${DOCKER_BUILDX_VERSION:-$(candidate docker-buildx-plugin)}
compose=${DOCKER_COMPOSE_VERSION:-$(candidate docker-compose-plugin)}
apt-get install -y "docker-ce=$ce" "docker-ce-cli=$cli" "containerd.io=$containerd" \
    "docker-buildx-plugin=$buildx" "docker-compose-plugin=$compose"

# Solo inicializar esta política si el administrador no tiene una propia.
install -d -m 0755 /etc/docker
if [[ ! -e /etc/docker/daemon.json ]]; then
    cat > /etc/docker/daemon.json <<'DAEMON'
{
  "log-driver": "local",
  "log-opts": {"max-size": "10m", "max-file": "3"}
}
DAEMON
    chmod 0644 /etc/docker/daemon.json
    dockerd --validate --config-file=/etc/docker/daemon.json
    systemctl restart docker
else
    printf '%s\n' 'daemon.json existente: se conserva sin sobrescribir.'
fi

systemctl enable --now ssh docker containerd
systemctl start qemu-guest-agent
systemctl enable --now fstrim.timer
systemctl is-active ssh docker containerd qemu-guest-agent
docker version
docker compose version
[[ $(docker info --format '{{.LoggingDriver}}') == local ]] \
    || fail 'Revisar política de logs: el driver efectivo no es local.'

install -d -m 0755 /var/lib/media-server/provisioning
python3 - <<'PY'
import datetime, json, pathlib, subprocess
packages = ["ca-certificates", "curl", "gpg", "openssh-server", "sudo", "python3",
            "qemu-guest-agent", "iputils-arping", "psmisc", "docker-ce", "docker-ce-cli",
            "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"]
versions = {}
for package in packages:
    versions[package] = subprocess.check_output(
        ["dpkg-query", "-W", "-f=${Version}", package], text=True).strip()
data = {"captured_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "os": "debian-13", "architecture": "amd64", "packages": versions}
path = pathlib.Path("/var/lib/media-server/provisioning/packages.json")
path.write_text(json.dumps(data, indent=2) + "\n")
path.chmod(0o644)
print("Versiones registradas:", path)
PY

printf '%s\n' 'Base preparada. No se cambiaron IP, contraseñas, sudoers, discos ni grupos de usuarios.'
printf '%s\n' 'Docker se administra con sudo; no se otorgó acceso al socket al usuario normal.'
