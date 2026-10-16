#!/usr/bin/env python3
"""Explicit, backed-up WebUI credential reset for this module's empty qBit lab.

Run as root in Debian. Password: getpass or stdin, never a command-line argument.
Only the existing qBittorrent container is stopped/started; no image pull/recreate.
"""
import argparse
import base64
import configparser
from datetime import datetime, timezone
import fcntl
import getpass
import hashlib
import http.cookiejar
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

CONTAINER = 'media-qbittorrent-qbittorrent-1'
PROJECT = 'media-qbittorrent'
IMAGE = 'lscr.io/linuxserver/qbittorrent@sha256:97333cc1ccf903e0bbcd8eb67e3332e4970e9c1ecabe145e499e9c0847ebcaed'
APPDATA = Path('/srv/media-server/appdata/qbittorrent')
CONFIG = APPDATA / 'qBittorrent/qBittorrent.conf'
BACKUPS = Path('/var/lib/media-server/backups/qbittorrent-webui-reset')
AUTH_KEYS = {'WebUI\\Username', 'WebUI\\Password_PBKDF2'}
OTHERS = ['media-jellyfin-jellyfin-1', 'media-prowlarr-prowlarr-1', 'media-radarr-radarr-1']


def command(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=45)
    if p.returncode:
        raise RuntimeError('Administrative command failed; raw output withheld')
    return p.stdout


def inspect(name):
    return json.loads(command(['docker', 'inspect', name]))[0]


def identity(value):
    return (value['Id'], value['Image'], value['State']['StartedAt'], value['RestartCount'])


def validate_credentials(username, password):
    if len(username) < 3 or any(c in username for c in ':\r\n\x00'):
        raise ValueError('Username needs at least 3 characters and no colon/newline/NUL')
    if len(password) < 6 or any(c in password for c in '\r\n\x00'):
        raise ValueError('Password needs at least 6 characters and no newline/NUL')


def encoded_password(password, salt=None):
    salt = secrets.token_bytes(16) if salt is None else salt
    if len(salt) != 16:
        raise ValueError('Expected a 16-byte salt')
    digest = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 100000, 64)
    payload = base64.b64encode(salt).decode() + ':' + base64.b64encode(digest).decode()
    return '@ByteArray(' + payload + ')'


def settings(text):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_string(text)
    return {(section, key): value for section in parser.sections() for key, value in parser.items(section)}


def replace_auth(text, username, password):
    before = settings(text)
    if 'Preferences' not in {section for section, _ in before}:
        raise ValueError('Missing Preferences section')
    replacement = {'WebUI\\Username': username, 'WebUI\\Password_PBKDF2': encoded_password(password)}
    lines, in_preferences = [], False
    for line in text.splitlines(keepends=True):
        if line.strip().startswith('[') and line.strip().endswith(']'):
            in_preferences = line.strip() == '[Preferences]'
            lines.append(line)
            if in_preferences:
                lines.extend(key + '=' + value + '\n' for key, value in replacement.items())
        elif in_preferences and line.partition('=')[0].strip() in AUTH_KEYS:
            continue
        else:
            lines.append(line)
    after_text = ''.join(lines)
    after = settings(after_text)
    without_auth = lambda values: {k: v for k, v in values.items() if not (k[0] == 'Preferences' and k[1] in AUTH_KEYS)}
    if without_auth(before) != without_auth(after):
        raise ValueError('Refusing changes outside the two WebUI credential settings')
    return after_text


def atomic_write(path, data, metadata):
    fd, name = tempfile.mkstemp(prefix='.webui-reset-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fchown(handle.fileno(), metadata.st_uid, metadata.st_gid)
            os.fchmod(handle.fileno(), stat.S_IMODE(metadata.st_mode))
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def wait_healthy(container):
    for _ in range(45):
        state = inspect(container)['State']
        if state.get('Health', {}).get('Status') == 'healthy':
            return
        time.sleep(2)
    raise RuntimeError('qBittorrent did not become healthy')


def login_ok(status, body):
    return (status == 204 and not body.strip()) or (status == 200 and body.strip() == b'Ok.')


def verify_api(address, username, password):
    base = 'http://' + address + ':8080'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    body = urllib.parse.urlencode({'username': username, 'password': password}).encode()
    request = urllib.request.Request(base + '/api/v2/auth/login', data=body, headers={'Referer': base + '/', 'Content-Type': 'application/x-www-form-urlencoded'})
    with opener.open(request, timeout=15) as response:
        status, result = response.status, response.read()
    if not login_ok(status, result):
        raise RuntimeError('Fresh login rejected; no credentials printed')
    def read(path):
        with opener.open(base + '/api/v2/' + path, timeout=15) as response:
            return json.load(response)
    preferences, categories, torrents = read('app/preferences'), read('torrents/categories'), read('torrents/info')
    expected = {'movies': '/data/downloads/movies', 'tv': '/data/downloads/tv'}
    if any(categories.get(name, {}).get('savePath') != path for name, path in expected.items()):
        raise RuntimeError('Category paths do not match the reviewed lab')
    if torrents or preferences.get('save_path', '').rstrip('/') != '/data/downloads' or preferences.get('web_ui_username') != username:
        raise RuntimeError('Unexpected torrent count, path or username')
    result = {'fresh_login_http_status': status, 'torrent_count': len(torrents), 'categories_verified': expected,
              'username_verified': username, 'save_path_verified': preferences['save_path']}
    with opener.open(urllib.request.Request(base + '/api/v2/auth/logout', data=b'', headers={'Referer': base + '/'}), timeout=15) as response:
        response.read()
    return result


def reset(username, password):
    validate_credentials(username, password)
    if os.geteuid() != 0 or 'ID=debian' not in Path('/etc/os-release').read_text():
        raise RuntimeError('Run as root inside the existing Debian VM')
    command(['/usr/local/sbin/check-media-storage'])
    if CONFIG.is_symlink() or CONFIG.resolve() != CONFIG or not CONFIG.is_file():
        raise RuntimeError('Expected existing regular configuration without symlinks')
    if any(APPDATA.rglob('*.torrent')) or any(APPDATA.rglob('*.fastresume')):
        raise RuntimeError('This reset recipe is restricted to the empty lab; review existing jobs first')
    target = inspect(CONTAINER)
    labels = target['Config'].get('Labels', {})
    if target['Config']['Image'] != IMAGE or labels.get('com.docker.compose.project') != PROJECT or labels.get('com.docker.compose.service') != 'qbittorrent':
        raise RuntimeError('Unexpected container/image/project')
    mounts = {(x['Source'], x['Destination'], x['RW']) for x in target['Mounts']}
    if mounts != {(str(APPDATA), '/config', True), ('/data/downloads', '/data/downloads', True)}:
        raise RuntimeError('Unexpected mounts')
    ports = target['HostConfig']['PortBindings']
    if set(ports) != {'8080/tcp'} or len(ports['8080/tcp']) != 1:
        raise RuntimeError('Unexpected published ports')
    binding = ports['8080/tcp'][0]
    address = binding['HostIp']
    ip = ipaddress.IPv4Address(address)
    if binding['HostPort'] != '8080' or not ip.is_private or ip.is_loopback or ip.is_unspecified:
        raise RuntimeError('Expected a private LAN binding')
    if target['State'].get('Health', {}).get('Status') != 'healthy':
        raise RuntimeError('Expected a healthy running qBittorrent before reset')
    others = {name: identity(inspect(name)) for name in OTHERS}
    report = {'scope': 'qBittorrent WebUI only', 'password_recorded': False, 'reset_completed': False}
    original = metadata = backup = None
    try:
        command(['docker', 'stop', '--time', '30', target['Id']])
        metadata = CONFIG.stat()
        original = CONFIG.read_bytes()
        changed = replace_auth(original.decode('utf-8'), username, password)
        BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
        if BACKUPS.is_symlink() or BACKUPS.resolve() != BACKUPS:
            raise RuntimeError('Unexpected backup directory')
        os.chmod(BACKUPS, 0o700)
        backup = BACKUPS / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        backup.mkdir(mode=0o700)
        (backup / 'qBittorrent.conf').write_bytes(original)
        os.chmod(backup / 'qBittorrent.conf', 0o600)
        atomic_write(CONFIG, changed.encode('utf-8'), metadata)
        command(['docker', 'start', target['Id']])
        wait_healthy(target['Id'])
        report.update(verify_api(address, username, password))
        unchanged = all(identity(inspect(name)) == value for name, value in others.items())
        if not unchanged:
            raise RuntimeError('Other container identity changed during operation')
        report.update({'reset_completed': True, 'backup_directory': str(backup), 'other_containers_unchanged': True,
                       'container_id_preserved': inspect(CONTAINER)['Id'] == target['Id'], 'healthy': True})
        return report
    except Exception:
        # Keep a failed write/login from leaving the service in an unknown state.
        if original is not None:
            command(['docker', 'stop', '--time', '30', target['Id']])
            atomic_write(CONFIG, original, metadata)
        command(['docker', 'start', target['Id']])
        wait_healthy(target['Id'])
        raise RuntimeError('Reset failed; original configuration restored and qBittorrent restarted. Check private backup; raw errors withheld.') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--username', default='admin')
    parser.add_argument('--password-stdin', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit('No changes without explicit --apply')
    if args.password_stdin:
        password = sys.stdin.readline().rstrip('\r\n')
    else:
        password = getpass.getpass('New qBittorrent WebUI password: ')
        if password != getpass.getpass('Confirm password: '):
            raise SystemExit('Password confirmation differs; nothing changed')
    validate_credentials(args.username, password)
    lock = os.open('/run/lock/media-server-qbittorrent-webui-reset.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(json.dumps(reset(args.username, password)))
    except Exception as error:
        print(json.dumps({'reset_completed': False, 'error_type': type(error).__name__, 'message': str(error) if isinstance(error, (ValueError, RuntimeError)) else 'Private diagnostic needed; raw exception withheld'}))
        raise SystemExit(1)
    finally:
        os.close(lock)


if __name__ == '__main__':
    main()
