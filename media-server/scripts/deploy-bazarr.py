#!/usr/bin/env python3
"""First Bazarr deployment only, with private Forms bootstrap and providers disabled."""
import argparse
import getpass
import hashlib
import secrets
import sys
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
import urllib.error
import urllib.parse

APPDATA = Path('/srv/media-server/appdata/bazarr')
STACK = Path('/srv/media-server/compose/bazarr')
VERSION = '1.6.2'
IMAGE_VERSION = 'v1.6.2-ls368'
IMAGE = 'lscr.io/linuxserver/bazarr@sha256:e3313a245b92d7c055e2a8e370b54bc1aeb4b3b4c36420ce18809a6e87c687b2'


def run(*args, timeout=90):
    # Never emit raw logs or config.yaml; both can contain secrets.
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout).stdout


def validate_configuration(config, addresses):
    if config.get('name') != 'media-bazarr' or set(config['services']) != {'bazarr'}:
        raise ValueError('Only the reviewed Bazarr project is in scope')
    service = config['services']['bazarr']
    if service['image'] != IMAGE or not re.fullmatch(r'lscr.io/linuxserver/bazarr@sha256:[a-f0-9]{64}', service['image']):
        raise ValueError('Require the reviewed LinuxServer immutable image digest')
    if any(service.get(k) for k in ('privileged', 'devices', 'network_mode', 'user', 'cap_add', 'entrypoint', 'command', 'pid', 'ipc', 'volumes_from')):
        raise ValueError('Do not override init or use elevated capabilities, host networking or devices')
    if service.get('environment') != {'PUID': '1000', 'PGID': '2000', 'UMASK': '002', 'TZ': 'America/Argentina/Buenos_Aires'}:
        raise ValueError('Require reviewed identity and environment; no forced auth overrides')
    volumes = service.get('volumes', [])
    expected = {'/config': str(APPDATA), '/data/media': '/data/media'}
    if len(volumes) != 2 or {v['target'] for v in volumes} != set(expected):
        raise ValueError('Require NVMe config and only the existing library bind')
    for volume in volumes:
        if (volume.get('type') != 'bind' or volume['source'] != expected[volume['target']]
                or volume.get('read_only', False) or volume.get('bind', {}).get('create_host_path') is not False):
            raise ValueError('Require existing writable NVMe /config and HDD /data/media; no downloads mount')
    if 'no-new-privileges:true' not in service.get('security_opt', []):
        raise ValueError('Require no-new-privileges')
    ports = service.get('ports', [])
    if len(ports) != 1:
        raise ValueError('Only TCP6767 WebUI is in scope')
    port = ports[0]
    address = ipaddress.ip_address(port['host_ip'])
    if (address.version != 4 or not any(address in ipaddress.ip_network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
            or str(address) not in addresses or int(port['published']) != 6767
            or port['target'] != 6767 or port.get('protocol', 'tcp') != 'tcp'):
        raise ValueError('Require TCP6767 on an assigned private LAN IPv4')
    return service, str(address)


def initial_configuration(username, password):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', username) or len(password) < 20:
        raise ValueError('Require a valid username and a unique password of at least 20 characters')
    # JSON is valid YAML. Match Bazarr 1.6.2 native Forms format; never reuse this
    # upstream MD5 format for our own authentication implementation.
    return {
        'auth': {'type': 'form', 'username': username,
                 'password': hashlib.md5(password.encode('utf-8')).hexdigest(),
                 'apikey': secrets.token_hex(16)},
        'general': {'port': 6767, 'flask_secret_key': secrets.token_hex(32),
                    'auto_update': False, 'use_sonarr': False, 'use_radarr': False,
                    'use_jellyfin': False, 'enabled_providers': [],
                    'single_language': False, 'use_embedded_subs': True,
                    'upgrade_subs': False, 'upgrade_manual': False,
                    'use_postprocessing': False, 'utf8_encode': True,
                    'subfolder': 'current', 'concurrent_jobs': 1},
        'subsync': {'use_subsync': False},
        'analytics': {'enabled': False},
    }


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


def first_start_verification(address, seed):
    base = f'http://{address}:6767'
    path = '/api/system/status'
    request = urllib.request.Request(base + path, headers={'X-API-KEY': seed['auth']['apikey']})
    with urllib.request.urlopen(request, timeout=15) as response:
        status = json.load(response)['data']
    if status.get('bazarr_version', '').lstrip('v') != VERSION:
        raise RuntimeError('Unexpected running Bazarr version')
    try:
        urllib.request.urlopen(base + path, timeout=15)
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise RuntimeError('Unexpected unauthenticated API result') from None
    else:
        raise RuntimeError('API unexpectedly accessible without credentials')
    login = urllib.parse.urlencode({'action': 'login', 'username': seed['auth']['username'],
                                   'password': 'invalid-bootstrap-probe'}).encode()
    try:
        urllib.request.urlopen(base + '/api/system/account', data=login, timeout=15)
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise RuntimeError('Unexpected invalid Forms login result') from None
    else:
        raise RuntimeError('Forms unexpectedly accepted an invalid credential')
    return {'version': status['bazarr_version'], 'authentication': 'form',
            'unauthenticated_api_rejected': True, 'invalid_forms_login_rejected': True,
            'providers_enabled': False, 'integrations_configured': False}


def verify_media_paths():
    data = Path('/data')
    for target in ('/data/media/movies', '/data/media/tv'):
        path = Path(target)
        if (path.resolve() != path or not path.is_dir() or path.stat().st_gid != 2000
                or path.stat().st_dev != data.stat().st_dev or path.stat().st_mode & 0o020 == 0):
            raise RuntimeError('Missing/unsafe existing movie directory or different filesystem')
    if shutil.disk_usage('/').free < 2 * 1024**3 or shutil.disk_usage('/data').free < 1024**3:
        raise RuntimeError('Insufficient free space; do not start this first deployment')


def verify_container_storage(cid):
    # Unique hidden probes only: no existing media/subtitle is modified.
    probe = r"""set -eu
for directory in /data/media/movies /data/media/tv; do
  file=$(mktemp "$directory/.bazarr-write-probe.XXXXXXXX")
  trap 'rm -f "$file"' EXIT HUP INT TERM
  printf 'bazarr-storage-probe' > "$file"
  rm "$file"
  trap - EXIT HUP INT TERM
done
printf 'library-write-ok\n'
"""
    output = run('docker', 'exec', '--user', '1000:2000', cid, '/bin/sh', '-c', probe)
    if output.strip() != 'library-write-ok':
        raise RuntimeError('Container library permission probe failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--compose-file', required=True)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--password-stdin', action='store_true', help='Private pipe only; never a command-line password')
    args = parser.parse_args()
    if not args.apply:
        parser.error('No changes without explicit --apply')
    if os.geteuid() != 0 or Path('/etc/pve').exists() or socket.gethostname() != 'media-server':
        raise RuntimeError('Run as root only inside the media-server Debian VM')
    if 'ID=debian' not in Path('/etc/os-release').read_text().splitlines():
        raise RuntimeError('Expected Debian')
    password = sys.stdin.readline().rstrip('\r\n') if args.password_stdin else getpass.getpass('New Bazarr password: ')
    seed = initial_configuration(args.username, password)
    del password
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
    if run('docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=media-bazarr').strip():
        raise RuntimeError('Existing Bazarr Compose project requires review')
    verify_media_paths()
    with socket.socket() as probe:
        probe.bind((address, 6767))
    for path in (Path('/srv/media-server'), Path('/srv/media-server/appdata'), Path('/srv/media-server/compose')):
        directory(path)
    directory(APPDATA, 1000, 2000, 0o750)
    if APPDATA.stat().st_dev != Path('/').stat().st_dev or APPDATA.stat().st_dev == Path('/data').stat().st_dev:
        raise RuntimeError('Appdata must stay on OS/NVMe, not HDD')
    directory(APPDATA / 'config', 1000, 2000, 0o750)
    with (APPDATA / 'config/config.yaml').open('x') as stream:
        os.fchown(stream.fileno(), 1000, 2000)
        os.fchmod(stream.fileno(), 0o600)
        stream.write(json.dumps(seed, indent=2) + '\n')
    directory(STACK)
    shutil.copyfile(source, STACK / 'compose.yaml')
    shutil.copyfile(environment, STACK / '.env')
    os.chmod(STACK / 'compose.yaml', 0o644)
    os.chmod(STACK / '.env', 0o600)
    compose = ('docker', 'compose', '--project-directory', str(STACK), '-f', str(STACK / 'compose.yaml'))
    run(*compose, 'config', '--quiet')
    run('/usr/local/sbin/check-media-storage')
    run(*compose, 'up', '-d', '--wait', '--wait-timeout', '180', '--pull', 'never', timeout=210)
    cid = run(*compose, 'ps', '-q', 'bazarr').strip()
    verification = first_start_verification(address, seed)
    verify_container_storage(cid)
    info = json.loads(run('docker', 'inspect', cid))[0]
    print(json.dumps({'deployed': True, 'image': service['image'], 'stack': str(STACK),
                      'url': f'http://{address}:6767', 'healthy': info['State']['Health']['Status'] == 'healthy',
                      'api': verification, 'appdata_on_nvme': True,
                      'library_write_probe_verified': True, 'subtitle_download_verified': False,
                      'movies_and_integrations_configured': False}, indent=2))


if __name__ == '__main__':
    main()
