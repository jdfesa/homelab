#!/usr/bin/env python3
"""First Sonarr deployment only; no accounts, series, searches or integrations added."""
import argparse
import grp
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import urllib.request
import xml.etree.ElementTree as ET

APPDATA = Path('/srv/media-server/appdata/sonarr')
STACK = Path('/srv/media-server/compose/sonarr')
VERSION = '4.0.20.3014'
IMAGE_VERSION = '4.0.20.3014-ls329'
IMAGE = 'lscr.io/linuxserver/sonarr@sha256:aae7c64ef13a4055c5b00607d5f2a2997d5a03304eb96e1930f9665728192e75'


def run(*args, timeout=90):
    # Never emit raw logs or config.xml; both can contain secrets.
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout).stdout


def validate_configuration(config, addresses):
    if config.get('name') != 'media-sonarr' or set(config['services']) != {'sonarr'}:
        raise ValueError('Only the reviewed Sonarr project is in scope')
    service = config['services']['sonarr']
    if service['image'] != IMAGE or not re.fullmatch(r'lscr.io/linuxserver/sonarr@sha256:[a-f0-9]{64}', service['image']):
        raise ValueError('Require the reviewed LinuxServer immutable image digest')
    if any(service.get(k) for k in ('privileged', 'devices', 'network_mode', 'user', 'cap_add', 'entrypoint', 'command', 'pid', 'ipc', 'volumes_from')):
        raise ValueError('Do not override init or use elevated capabilities, host networking or devices')
    if service.get('environment') != {'PUID': '1000', 'PGID': '2000', 'UMASK': '002', 'TZ': 'America/Argentina/Buenos_Aires'}:
        raise ValueError('Require reviewed identity and environment; no forced auth overrides')
    volumes = service.get('volumes', [])
    expected = {'/config': str(APPDATA), '/data': '/data'}
    if len(volumes) != 2 or {v['target'] for v in volumes} != set(expected):
        raise ValueError('Require NVMe config and ONE common /data bind for hardlinks')
    for volume in volumes:
        if (volume.get('type') != 'bind' or volume['source'] != expected[volume['target']]
                or volume.get('read_only', False) or volume.get('bind', {}).get('create_host_path') is not False):
            raise ValueError('Require existing writable NVMe /config and single HDD /data; no split mounts')
    if 'no-new-privileges:true' not in service.get('security_opt', []):
        raise ValueError('Require no-new-privileges')
    ports = service.get('ports', [])
    if len(ports) != 1:
        raise ValueError('Only TCP8989 WebUI is in scope')
    port = ports[0]
    address = ipaddress.ip_address(port['host_ip'])
    if (address.version != 4 or not any(address in ipaddress.ip_network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
            or str(address) not in addresses or int(port['published']) != 8989
            or port['target'] != 8989 or port.get('protocol', 'tcp') != 'tcp'):
        raise ValueError('Require TCP8989 on an assigned private LAN IPv4')
    return service, str(address)


def initial_configuration():
    # Do not force AuthenticationMethod via environment: the user completes native first-run setup.
    # AuthenticationRequired stays Enabled, including local addresses after Forms is selected.
    return '''<Config>
  <BindAddress>*</BindAddress>
  <Port>8989</Port>
  <EnableSsl>False</EnableSsl>
  <LaunchBrowser>False</LaunchBrowser>
  <AuthenticationRequired>Enabled</AuthenticationRequired>
  <Branch>main</Branch>
  <UpdateAutomatically>False</UpdateAutomatically>
  <UpdateMechanism>Docker</UpdateMechanism>
  <LogLevel>info</LogLevel>
  <InstanceName>Sonarr</InstanceName>
</Config>
'''


def directory(path, uid=0, gid=0, mode=0o755):
    if path.resolve() != path:
        raise ValueError('Refusing symlink directory')
    if not path.exists():
        path.mkdir(mode=mode)
        os.chown(path, uid, gid)
        os.chmod(path, mode)
    info = path.stat()
    if not path.is_dir() or (info.st_uid, info.st_gid) != (uid, gid) or info.st_mode & 0o022:
        raise ValueError('Unexpected directory ownership/permissions: ' + str(path))


def first_start_verification(address):
    # Read the locally generated API key without printing or saving it in reports.
    xml = ET.parse(APPDATA / 'config.xml').getroot()
    key = xml.findtext('ApiKey')
    if not key:
        raise RuntimeError('Generated API key missing; config not emitted')
    base = f'http://{address}:8989'
    def api(path):
        request = urllib.request.Request(base + '/api/v3/' + path, headers={'X-Api-Key': key})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    status = api('system/status')
    if status.get('version') != VERSION:
        raise RuntimeError('Unexpected running Sonarr version')
    counts = {name: len(api(name)) for name in ('series', 'indexer', 'downloadclient', 'rootfolder')}
    if any(counts.values()):
        raise RuntimeError('Expected empty first installation; do not modify existing series or integrations')
    return {'version': status['version'], 'counts': counts,
            'authentication_required': xml.findtext('AuthenticationRequired'),
            'authentication_method': xml.findtext('AuthenticationMethod', 'None'),
            'user_authentication_setup_pending': True}


def verify_media_paths():
    data = Path('/data')
    for target in ('/data/downloads/tv', '/data/media/tv'):
        path = Path(target)
        if (path.resolve() != path or not path.is_dir() or path.stat().st_gid != 2000
                or path.stat().st_dev != data.stat().st_dev or path.stat().st_mode & 0o020 == 0):
            raise RuntimeError('Missing/unsafe existing episode directory or different filesystem')
    if shutil.disk_usage('/').free < 2 * 1024**3 or shutil.disk_usage('/data').free < 1024**3:
        raise RuntimeError('Insufficient free space; do not start this first deployment')


def verify_container_storage(cid):
    # Tiny hidden files under the application identity; not a video import.
    # Never delete a pre-existing destination if ln fails. All created probes are removed.
    probe = r"""set -eu
src=$(mktemp /data/downloads/tv/.sonarr-storage-probe.XXXXXXXX)
dst=/data/media/tv/$(basename "$src")
linked=no
trap 'rm -f "$src"; if [ "$linked" = yes ]; then rm -f "$dst"; fi' EXIT HUP INT TERM
printf 'sonarr-storage-probe' > "$src"
ln "$src" "$dst"
linked=yes
[ "$(stat -c %d:%i "$src")" = "$(stat -c %d:%i "$dst")" ]
[ "$(stat -c %h "$src")" -ge 2 ]
printf 'filesystem-hardlinks-ok\n'
"""
    output = run('docker', 'exec', '--user', '1000:2000', cid, '/bin/sh', '-c', probe)
    if output.strip() != 'filesystem-hardlinks-ok':
        raise RuntimeError('Container filesystem hardlink/permission probe failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--compose-file', required=True)
    parser.add_argument('--env-file', required=True)
    args = parser.parse_args()
    if not args.apply:
        parser.error('No changes without explicit --apply')
    if os.geteuid() != 0 or Path('/etc/pve').exists() or socket.gethostname() != 'media-server':
        raise RuntimeError('Run as root only inside the media-server Debian VM')
    if 'ID=debian' not in Path('/etc/os-release').read_text().splitlines():
        raise RuntimeError('Expected Debian')
    run('/usr/local/sbin/check-media-storage')
    if grp.getgrnam('media').gr_gid != 2000:
        raise RuntimeError('Expected existing media GID2000')
    if any(p.exists() or p.is_symlink() for p in (STACK, APPDATA)):
        raise RuntimeError('First deployment only; refusing existing stack or appdata')
    source = Path(args.compose_file).resolve(strict=True)
    environment = Path(args.env_file).resolve(strict=True)
    config = json.loads(run('docker', 'compose', '--env-file', str(environment), '-f', str(source), 'config', '--format', 'json'))
    addresses = {entry['local'] for interface in json.loads(run('ip', '-j', '-4', 'address', 'show'))
                 for entry in interface.get('addr_info', [])}
    service, address = validate_configuration(config, addresses)
    image = json.loads(run('docker', 'image', 'inspect', service['image']))[0]
    if (image['Architecture'] != 'amd64' or image['Os'] != 'linux'
            or image['Config']['Labels'].get('org.opencontainers.image.version') != IMAGE_VERSION):
        raise RuntimeError('Unexpected image platform/version label')
    if run('docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=media-sonarr').strip():
        raise RuntimeError('Existing Sonarr Compose project requires review')
    verify_media_paths()
    with socket.socket() as probe:
        probe.bind((address, 8989))
    for path in (Path('/srv/media-server'), Path('/srv/media-server/appdata'), Path('/srv/media-server/compose')):
        directory(path)
    directory(APPDATA, 1000, 2000, 0o750)
    if APPDATA.stat().st_dev != Path('/').stat().st_dev or APPDATA.stat().st_dev == Path('/data').stat().st_dev:
        raise RuntimeError('Appdata must stay on OS/NVMe, not HDD')
    with (APPDATA / 'config.xml').open('x') as stream:
        os.fchown(stream.fileno(), 1000, 2000)
        os.fchmod(stream.fileno(), 0o600)
        stream.write(initial_configuration())
    directory(STACK)
    shutil.copyfile(source, STACK / 'compose.yaml')
    shutil.copyfile(environment, STACK / '.env')
    os.chmod(STACK / 'compose.yaml', 0o644)
    os.chmod(STACK / '.env', 0o600)
    compose = ('docker', 'compose', '--project-directory', str(STACK), '-f', str(STACK / 'compose.yaml'))
    run(*compose, 'config', '--quiet')
    run('/usr/local/sbin/check-media-storage')
    run(*compose, 'up', '-d', '--wait', '--wait-timeout', '180', '--pull', 'never', timeout=210)
    cid = run(*compose, 'ps', '-q', 'sonarr').strip()
    verification = first_start_verification(address)
    verify_container_storage(cid)
    info = json.loads(run('docker', 'inspect', cid))[0]
    print(json.dumps({'deployed': True, 'image': service['image'], 'stack': str(STACK),
                      'url': f'http://{address}:8989', 'healthy': info['State']['Health']['Status'] == 'healthy',
                      'api': verification, 'appdata_on_nvme': True,
                      'filesystem_hardlink_probe_verified': True, 'application_import_verified': False,
                      'series_and_integrations_configured': False}, indent=2))


if __name__ == '__main__':
    main()
