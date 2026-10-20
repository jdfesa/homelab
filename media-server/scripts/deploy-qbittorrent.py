#!/usr/bin/env python3
"""First deployment only: reviewed qBittorrent module, without adding torrents."""
import argparse
import grp
import http.cookiejar
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


APPDATA = Path('/srv/media-server/appdata/qbittorrent')
STACK = Path('/srv/media-server/compose/qbittorrent')
INITIAL_LOGIN = Path('/root/media-server-scripts/qbittorrent-initial-login.txt')


def run(*args, timeout=90):
    # Never emit captured application logs: startup logs contain a temporary secret.
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout).stdout


def validate_configuration(config, addresses):
    if config.get('name') != 'media-qbittorrent' or set(config['services']) != {'qbittorrent'}:
        raise ValueError('Only the reviewed qBittorrent project is in scope')
    service = config['services']['qbittorrent']
    if not re.fullmatch(r'lscr.io/linuxserver/qbittorrent@sha256:[a-f0-9]{64}', service['image']):
        raise ValueError('Require the reviewed LinuxServer immutable image digest')
    if any(service.get(k) for k in ('privileged', 'devices', 'network_mode', 'user', 'cap_add', 'entrypoint', 'command')):
        raise ValueError('Do not override init, elevate capabilities or use host networking/devices')
    env = service.get('environment', {})
    expected_env = {'PUID': '1000', 'PGID': '2000', 'UMASK': '002',
                    'TZ': 'America/Argentina/Buenos_Aires', 'WEBUI_PORT': '8080', 'TORRENTING_PORT': '6881'}
    if env != expected_env:
        raise ValueError('Require reviewed identity, umask and ports without extra environment')
    expected = {'/config': str(APPDATA), '/data/downloads': '/data/downloads'}
    volumes = service.get('volumes', [])
    if len(volumes) != 2 or {v['target'] for v in volumes} != set(expected):
        raise ValueError('Only config and downloads mounts are allowed')
    for volume in volumes:
        if (volume.get('type') != 'bind' or volume['source'] != expected[volume['target']]
                or volume.get('read_only', False) or volume.get('bind', {}).get('create_host_path') is not False):
            raise ValueError('Require existing NVMe config and writable HDD downloads binds')
    if 'no-new-privileges:true' not in service.get('security_opt', []):
        raise ValueError('Require no-new-privileges')
    ports = service.get('ports', [])
    if len(ports) != 1:
        raise ValueError('Publish only the WebUI, no incoming peer ports in this phase')
    port = ports[0]
    address = ipaddress.ip_address(port['host_ip'])
    if (address.version != 4 or not address.is_private or address.is_loopback or address.is_unspecified
            or str(address) not in addresses or int(port['published']) != 8080
            or port['target'] != 8080 or port.get('protocol', 'tcp') != 'tcp'):
        raise ValueError('Require TCP8080 on an assigned private LAN IPv4')
    return service, str(address)


def initial_configuration(address):
    # Modern 5.2 keys verified against the pinned upstream release, not legacy guesses.
    ipaddress.ip_address(address)
    return f'''[AutoRun]
enabled=false
program=

[BitTorrent]
Session\\DefaultSavePath=/data/downloads/
Session\\TempPath=/data/downloads/incomplete/
Session\\TempPathEnabled=true
Session\\Port=6881
Session\\UseCategoryPathsInManualMode=true
Session\\GlobalMaxRatio=-1
Session\\GlobalMaxSeedingMinutes=60
Session\\GlobalMaxInactiveSeedingMinutes=-1
Session\\ShareLimitAction=Stop

[LegalNotice]
Accepted=true

[Network]
PortForwardingEnabled=false

[Preferences]
WebUI\\Address=*
WebUI\\Port=8080
WebUI\\ServerDomains={address};localhost;127.0.0.1
WebUI\\Username=admin
WebUI\\UseUPnP=false
WebUI\\LocalHostAuth=true
WebUI\\AuthSubnetWhitelistEnabled=false
WebUI\\CSRFProtection=true
WebUI\\ClickjackingProtection=true
WebUI\\HostHeaderValidation=true
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


def write_new(path, text, uid=0, gid=0, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'w') as stream:
        os.fchown(stream.fileno(), uid, gid)
        stream.write(text)


def login_response_accepted(status, body):
    # 5.2.4 returns HTTP204 with no body; older compatible API uses HTTP200/Ok.
    # A subsequent authenticated preferences request must still succeed.
    return (status == 204 and not body.strip()) or (status == 200 and body.strip() == 'Ok.')


def verify_api(address, password):
    base = f'http://{address}:8080'
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def api(path, form=None, with_status=False):
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        request = urllib.request.Request(base + '/api/v2/' + path, data=data,
                                         headers={'Origin': base, 'Referer': base + '/'})
        with opener.open(request, timeout=10) as response:
            body = response.read().decode()
            return (response.status, body) if with_status else body
    try:
        api('app/preferences')
    except urllib.error.HTTPError as error:
        if error.code != 403:
            raise RuntimeError('Unexpected anonymous API status') from None
    else:
        raise RuntimeError('Refusing unauthenticated WebUI API access')
    if not login_response_accepted(*api('auth/login', {'username': 'admin', 'password': password}, with_status=True)):
        raise RuntimeError('Initial application login failed; credentials not emitted')
    try:
        prefs = json.loads(api('app/preferences'))
        expected = {'upnp': False, 'web_ui_upnp': False, 'bypass_local_auth': False,
                    'bypass_auth_subnet_whitelist_enabled': False, 'web_ui_csrf_protection_enabled': True,
                    'web_ui_host_header_validation_enabled': True, 'web_ui_clickjacking_protection_enabled': True,
                    'temp_path_enabled': True,
                    # Stop seeding independently of guarded library import/removal.
                    # No ratio/inactivity trigger may stop a new seed before its hour.
                    'max_ratio_enabled': False, 'max_ratio': -1,
                    'max_seeding_time_enabled': True, 'max_seeding_time': 60,
                    'max_inactive_seeding_time_enabled': False, 'max_inactive_seeding_time': -1,
                    'max_ratio_act': 0}
        if any(prefs.get(k) != v for k, v in expected.items()):
            raise RuntimeError('Effective API settings differ from reviewed router/authentication/seeding policy')
        for key, path in {'save_path': '/data/downloads', 'temp_path': '/data/downloads/incomplete'}.items():
            if prefs.get(key, '').rstrip('/') != path:
                raise RuntimeError('Effective download path differs from HDD contract')
        if api('app/version').strip() != 'v5.2.4':
            raise RuntimeError('Unexpected application version')
        if json.loads(api('torrents/info')):
            raise RuntimeError('Expected an empty client; no torrent creation is in scope')
        for name in ('movies', 'tv'):
            api('torrents/createCategory', {'category': name, 'savePath': '/data/downloads/' + name})
        categories = json.loads(api('torrents/categories'))
        for name in ('movies', 'tv'):
            if categories.get(name, {}).get('savePath', '').rstrip('/') != '/data/downloads/' + name:
                raise RuntimeError('Category path verification failed')
        return {'version': '5.2.4', 'torrents': 0, 'anonymous_api_rejected': True,
                'settings_verified': expected, 'categories': categories}
    finally:
        api('auth/logout', {})


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
    if any(p.exists() or p.is_symlink() for p in (STACK, APPDATA, INITIAL_LOGIN)):
        raise RuntimeError('First deployment only; refusing existing state or credentials')
    source = Path(args.compose_file).resolve(strict=True)
    environment = Path(args.env_file).resolve(strict=True)
    config = json.loads(run('docker', 'compose', '--env-file', str(environment), '-f', str(source), 'config', '--format', 'json'))
    addresses = {entry['local'] for interface in json.loads(run('ip', '-j', '-4', 'address', 'show'))
                 for entry in interface.get('addr_info', [])}
    service, address = validate_configuration(config, addresses)
    image = json.loads(run('docker', 'image', 'inspect', service['image']))[0]
    if (image['Architecture'] != 'amd64' or image['Os'] != 'linux'
            or image['Config']['Labels'].get('org.opencontainers.image.version') != '5.2.4_v2.0.15-ls480'):
        raise RuntimeError('Unexpected image platform/version label')
    if run('docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=media-qbittorrent').strip():
        raise RuntimeError('Existing qBittorrent Compose project requires review')
    for target in ('/data/downloads', '/data/downloads/movies', '/data/downloads/tv'):
        path = Path(target)
        if not path.is_dir() or path.resolve() != path or path.stat().st_gid != 2000:
            raise RuntimeError('Missing/unsafe existing downloads directory')
    with socket.socket() as probe:
        probe.bind((address, 8080))
    for path in (Path('/srv/media-server'), Path('/srv/media-server/appdata'), Path('/srv/media-server/compose')):
        directory(path)
    directory(APPDATA, 1000, 2000, 0o750)
    if APPDATA.stat().st_dev == Path('/data').stat().st_dev:
        raise RuntimeError('Appdata must stay on the OS/NVMe filesystem')
    directory(APPDATA / 'qBittorrent', 1000, 2000, 0o750)
    write_new(APPDATA / 'qBittorrent/qBittorrent.conf', initial_configuration(address), 1000, 2000)
    # Only this new incomplete directory; never recurse/chown existing downloads or libraries.
    incomplete = Path('/data/downloads/incomplete')
    if incomplete.exists() or incomplete.is_symlink():
        raise RuntimeError('Review existing incomplete directory before first deployment')
    incomplete.mkdir(mode=0o2770)
    os.chown(incomplete, 0, 2000)
    os.chmod(incomplete, 0o2770)
    directory(STACK)
    shutil.copyfile(source, STACK / 'compose.yaml')
    shutil.copyfile(environment, STACK / '.env')
    os.chmod(STACK / 'compose.yaml', 0o644)
    os.chmod(STACK / '.env', 0o600)
    compose = ('docker', 'compose', '--project-directory', str(STACK), '-f', str(STACK / 'compose.yaml'))
    run(*compose, 'config', '--quiet')
    run('/usr/local/sbin/check-media-storage')
    run(*compose, 'up', '-d', '--wait', '--wait-timeout', '180', '--pull', 'never', timeout=210)
    cid = run(*compose, 'ps', '-q', 'qbittorrent').strip()
    logs = run('docker', 'logs', cid)
    match = re.search(r'temporary password is provided for this session:\s*(\S+)', logs)
    if not match:
        raise RuntimeError('Initial credential not found; logs intentionally not emitted')
    password = match[1]
    write_new(INITIAL_LOGIN, f'URL: http://{address}:8080\nUsername: admin\nTemporary password: {password}\n\nChoose your permanent application password in Tools > Options > WebUI.\nDo not share this file or include it in screenshots.\n')
    verification = verify_api(address, password)
    run('docker', 'exec', '--user', '1000:2000', cid, '/bin/sh', '-c',
        'set -eu; umask 002; f=$(mktemp /data/downloads/.qbittorrent-permission-probe.XXXXXX); test -r "$f"; rm -- "$f"; test ! -e /data/media')
    ps = json.loads(run(*compose, 'ps', '--format', 'json'))
    print(json.dumps({'deployed': True, 'image': service['image'], 'stack': str(STACK),
                      'url': f'http://{address}:8080', 'compose_ps': ps, 'api': verification,
                      'hdd_write_probe_verified': True, 'media_not_mounted': True,
                      'private_initial_login_file': str(INITIAL_LOGIN)}, indent=2))


if __name__ == '__main__':
    main()
