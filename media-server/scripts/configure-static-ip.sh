#!/usr/bin/env bash
# Ejecutar por consola/Guest Agent dentro de Debian; cambia la IP de ens18.
# Los valores privados se suministran por variables, nunca se versionan aquí.
set -euo pipefail
export LC_ALL=C
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ ${1:-} == --apply ]] || fail 'Usar --apply con NETWORK_INTERFACE, NETWORK_ADDRESS, NETWORK_GATEWAY, NETWORK_DNS y NETWORK_DHCP_EXCLUDED=yes.'
[[ $(id -u) == 0 && ! -d /etc/pve ]] || fail 'Ejecutar como root en la VM, no en Proxmox.'
[[ $(hostname) == "${EXPECTED_HOSTNAME:-media-server}" ]] || fail 'Hostname inesperado.'
[[ ${NETWORK_DHCP_EXCLUDED:-} == yes ]] || fail 'Confirmar exclusión o reserva DHCP antes de configurar IP estática.'
export NETWORK_INTERFACE=${NETWORK_INTERFACE:?}
export NETWORK_ADDRESS=${NETWORK_ADDRESS:?}
export NETWORK_GATEWAY=${NETWORK_GATEWAY:?}
export NETWORK_DNS=${NETWORK_DNS:?}
python3 - <<'PY'
import ipaddress, os, re
interface = os.environ['NETWORK_INTERFACE']
if not re.fullmatch(r'[A-Za-z0-9_.-]+', interface):
    raise SystemExit('Nombre de interfaz inválido')
address = ipaddress.IPv4Interface(os.environ['NETWORK_ADDRESS'])
gateway = ipaddress.IPv4Address(os.environ['NETWORK_GATEWAY'])
if gateway not in address.network or gateway == address.ip:
    raise SystemExit('Gateway fuera de la red o igual al host')
if address.ip in (address.network.network_address, address.network.broadcast_address):
    raise SystemExit('Dirección de red/broadcast no válida para el host')
for server in os.environ['NETWORK_DNS'].split():
    ipaddress.ip_address(server)
PY
iface=$NETWORK_INTERFACE
address=${NETWORK_ADDRESS%/*}
ip link show dev "$iface" >/dev/null
[[ -f /etc/dhcpcd.conf ]] || fail 'No se encuentra la configuración dhcpcd validada para este huésped.'
pgrep -x dhcpcd >/dev/null || fail 'No hay proceso dhcpcd; revisar gestor de red antes de continuar.'
if ! ip -4 -o addr show dev "$iface" | grep -Fq "inet $NETWORK_ADDRESS "; then
    arping -D -q -I "$iface" -c 3 -w 5 "$address" \
        || fail 'La prueba ARP detectó un posible conflicto o falló; no se cambió la red.'
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup="/var/backups/media-server/network-$stamp"
unit="media-server-network-rollback-$stamp"
install -d -m 0700 "$backup"
cp -a /etc/dhcpcd.conf "$backup/dhcpcd.conf"
cp -a /etc/resolv.conf "$backup/resolv.conf"
cat > "$backup/rollback.sh" <<ROLLBACK
#!/bin/sh
set -eu
cp -a '$backup/dhcpcd.conf' /etc/dhcpcd.conf
/usr/sbin/dhcpcd --rebind '$iface'
ROLLBACK
chmod 0700 "$backup/rollback.sh"
systemd-run --quiet --unit="$unit" --on-active=180s /bin/sh "$backup/rollback.sh"
export MEDIA_NETWORK_BACKUP=$backup
export MEDIA_NETWORK_ROLLBACK_UNIT=$unit
python3 - <<'PY'
import os, pathlib
path=pathlib.Path('/etc/dhcpcd.conf')
begin='# BEGIN media-server managed static IPv4'
end='# END media-server managed static IPv4'
text=path.read_text()
if begin in text:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise SystemExit('Bloque gestionado ambiguo; revisar manualmente')
    prefix, remainder=text.split(begin,1)
    _, suffix=remainder.split(end,1)
    text=prefix+suffix
if any(line.strip().startswith('static ip_address=') for line in text.splitlines()):
    raise SystemExit('Hay una dirección estática ajena al bloque gestionado; no sobrescribir')
block='\n'.join([begin, 'interface '+os.environ['NETWORK_INTERFACE'],
    'static ip_address='+os.environ['NETWORK_ADDRESS'],
    'static routers='+os.environ['NETWORK_GATEWAY'],
    'static domain_name_servers='+' '.join(os.environ['NETWORK_DNS'].split()), end])
path.write_text(text.rstrip()+'\n\n'+block+'\n')
path.chmod(0o644)
state=pathlib.Path('/var/lib/media-server/provisioning/network-change.json')
state.parent.mkdir(parents=True, exist_ok=True)
import json
state.write_text(json.dumps({'rollback_unit':os.environ['MEDIA_NETWORK_ROLLBACK_UNIT'],
    'backup':os.environ['MEDIA_NETWORK_BACKUP'], 'verification':'pending'},indent=2)+'\n')
state.chmod(0o600)
PY
/usr/sbin/dhcpcd --rebind "$iface"
printf 'Aplicación solicitada; rollback automático en 180 s: %s.timer\n' "$unit"
printf '%s\n' 'Verificar IP, gateway, DNS y acceso desde otro equipo antes de cancelar ese timer.'
printf 'Backup de recuperación: %s\n' "$backup"
