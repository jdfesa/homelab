#!/bin/sh
# Captura privada. No copia el script al host ni crea archivos remotos.
set -eu
umask 077
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
host=${1:-proxmox-homelab}
case "$host" in
    ''|-*|*[!a-zA-Z0-9._@-]*) echo 'Host/alias SSH inválido' >&2; exit 2 ;;
esac
mkdir -p "$repo/.local/inventory"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
output="$repo/.local/inventory/host-$stamp.json"
temp=$(mktemp "$repo/.local/inventory/.capture.XXXXXX")
trap 'rm -f "$temp"' EXIT HUP INT TERM
rtk proxy ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 \
    "$host" 'LC_ALL=C python3 -' < "$repo/scripts/inventory_host.py" > "$temp"
rtk proxy python3 -m json.tool "$temp" > /dev/null
mv "$temp" "$output"
printf 'Inventario privado guardado: %s\n' "$output"
