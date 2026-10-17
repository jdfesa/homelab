#!/usr/bin/env python3
"""Finite, fail-closed torrent maintenance. Run on Debian; dry-run by default.

Only qBittorrent's API can remove payloads. This program never unlinks media.
See docs/torrent-cleanup.md before configuring or enabling --apply.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import http.cookiejar
import ipaddress
import json
import logging
import logging.handlers
import math
import os
from pathlib import Path, PurePosixPath
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

VERSION = 2
COMPLETE_AGE = 3600
STALLED_AGE = 86400
MIN_DAILY_PROGRESS = .05  # Five percentage points of the selected payload.
NEAR_COMPLETE_PROGRESS = .90
NEAR_COMPLETE_AGE = 7 * 86400
MAX_GAP = 7 * 3600  # Six-hour timer, with bounded scheduling tolerance.
MAX_SAMPLES = 128  # Extra manual runs may delay a decision, never shorten a window.
MEDIA = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.mpg', '.mpeg', '.ts', '.m2ts', '.wmv', '.webm'}
LIBRARIES = {'movies': '/data/media/movies', 'tv': '/data/media/tv'}
HASH = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')


class Refused(Exception):
    """Only constant, credential-free reason codes may be used as messages."""


def need(condition, reason):
    if not condition:
        raise Refused(reason)


def number(value):
    need(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'invalid_number')
    return value


def private_file(path):
    path = Path(path)
    s = path.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_uid == os.geteuid()
         and not s.st_mode & 0o077 and s.st_nlink == 1, 'unsafe_private_file')
    return path


def private_input(path):
    """Accept manager-provided read-only credentials, not relaxed ordinary files."""
    path = Path(path)
    directory = os.environ.get('CREDENTIALS_DIRECTORY')
    if directory and path.parent == Path(directory) and path.parent.is_relative_to('/run/credentials'):
        s = path.lstat()
        need(path.name in ('settings.json', 'storage.json') and '..' not in path.parts
             and not path.is_symlink() and stat.S_ISREG(s.st_mode) and s.st_nlink == 1
             and s.st_uid in (0, os.geteuid()) and stat.S_IMODE(s.st_mode) in (0o400, 0o440)
             and bool(os.statvfs(path).f_flag & os.ST_RDONLY), 'unsafe_systemd_credential')
        return path
    return private_file(path)


def private_dir(path):
    path = Path(path)
    need(path.is_absolute(), 'absolute_private_directory_required')
    # systemd DynamicUser StateDirectory/LogsDirectory may resolve into private/.
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = path.resolve(strict=True)
    s = path.stat()
    need(s.st_uid == os.geteuid() and not s.st_mode & 0o077, 'unsafe_private_directory')
    return path


def atomic_json(path, data):
    path = Path(path)
    if path.exists() or path.is_symlink():
        private_file(path)
    fd, name = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, sort_keys=True, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        d = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(d)
        finally:
            os.close(d)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class StrictHandler(logging.handlers.RotatingFileHandler):
    def _open(self):
        path = Path(self.baseFilename)
        if path.exists() or path.is_symlink():
            private_file(path)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        return os.fdopen(fd, self.mode, encoding=self.encoding, errors=self.errors)

    def handleError(self, record):
        raise Refused('audit_write_failed') from None


class Audit:
    def __init__(self, directory, apply=False, max_bytes=10 * 1024 * 1024, backups=5):
        self.directory = private_dir(directory)
        self.path = self.directory / 'audit.jsonl'
        for p in self.directory.glob('audit.jsonl*'):
            private_file(p)
        self.handler = StrictHandler(self.path, maxBytes=max_bytes, backupCount=backups, encoding='utf-8')
        os.chmod(self.path, 0o600)
        self.run_id = uuid.uuid4().hex
        self.mode = 'apply' if apply else 'dry-run'

    def emit(self, event, torrent=None, **fields):
        row = {'time': dt.datetime.now(dt.timezone.utc).isoformat(), 'run_id': self.run_id,
               'mode': self.mode, 'event': event, **fields}
        if torrent:
            row.update(hash=torrent['hash'], name=str(torrent.get('name', ''))[:512])
        record = logging.LogRecord('cleanup', logging.INFO, '', 0,
                                   json.dumps(row, ensure_ascii=True, allow_nan=False), (), None)
        self.handler.emit(record)
        self.handler.flush()
        os.fsync(self.handler.stream.fileno())
        fd = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def close(self):
        self.handler.close()


def validate_url(value):
    u = urllib.parse.urlsplit(value)
    need(u.scheme in ('http', 'https') and u.hostname and not u.username and not u.password
         and not u.query and not u.fragment and u.path in ('', '/'), 'unsafe_service_url')
    # No redirects or credentials to an arbitrary remote host. Resolve once per request too.
    try:
        addresses = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    except OSError:
        raise Refused('service_dns_failed') from None
    need(addresses and all(ipaddress.ip_address(a[4][0]).is_private
                           or ipaddress.ip_address(a[4][0]).is_loopback for a in addresses), 'nonprivate_service_url')
    return value.rstrip('/')


def load_config(path):
    cfg = json.loads(private_input(path).read_text())
    need(set(cfg) == {'qbittorrent', 'radarr', 'sonarr', 'jellyfin', 'expected_hostname'}, 'invalid_config_keys')
    need(isinstance(cfg['expected_hostname'], str) and cfg['expected_hostname'], 'hostname_required')
    for service in ('qbittorrent', 'radarr', 'sonarr', 'jellyfin'):
        item = cfg[service]
        keys = {'url', 'username', 'password'} if service == 'qbittorrent' else {'url', 'api_key'}
        need(isinstance(item, dict) and set(item) == keys, 'invalid_service_config')
        need(all(isinstance(v, str) and v and not v.startswith('<') for v in item.values()), 'unconfigured_service')
        item['url'] = validate_url(item['url'])
    return cfg


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Refused('http_redirect_refused')


class API:
    def __init__(self, config, service):
        self.config = config
        self.service = service
        self.base = validate_url(config['url'])
        self.jar = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                 urllib.request.HTTPCookieProcessor(self.jar), NoRedirect())

    def call(self, path, query=None, method='GET', form=None, raw=False):
        need(path.startswith('/') and '?' not in path and not path.startswith('//'), 'invalid_api_path')
        validate_url(self.base)
        url = self.base + path
        if query:
            url += '?' + urllib.parse.urlencode(query)
        headers = {'Referer': self.base + '/'}
        if self.service in ('radarr', 'sonarr'):
            headers['X-Api-Key'] = self.config['api_key']
        elif self.service == 'jellyfin':
            headers['Authorization'] = ('MediaBrowser Client="Torrent Cleanup", Device="Debian", '
                'DeviceId="torrent-cleanup", Version="1", Token=' + json.dumps(self.config['api_key']))
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        try:
            with self.client.open(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=15) as r:
                need(r.status in (200, 202, 204), 'unexpected_http_status')
                body = r.read(8 * 1024 * 1024 + 1)
                need(len(body) <= 8 * 1024 * 1024, 'api_response_too_large')
                if raw:
                    return body
                return json.loads(body) if body else None
        except (urllib.error.URLError, OSError, ValueError):
            # urllib exceptions can embed a credential-bearing URL; never echo them.
            raise Refused('api_request_failed') from None

    def login(self):
        body = self.call('/api/v2/auth/login', method='POST', form={
            'username': self.config['username'], 'password': self.config['password']}, raw=True)
        port = urllib.parse.urlsplit(self.base).port or (443 if self.base.startswith('https:') else 80)
        need(body in (b'', b'Ok.') and any(c.name in ('SID', f'QBT_SID_{port}') for c in self.jar), 'qbit_login_failed')
        # Cookie presence alone is not proof of authentication.
        need(self.call('/api/v2/app/version', raw=True).startswith(b'v'), 'qbit_session_not_authenticated')


def checked_path(path, root, exists=False):
    p, r = Path(path), Path(root)
    need(p.is_absolute() and '..' not in p.parts and p != r and p.is_relative_to(r), 'path_outside_allowed_root')
    current = Path(p.anchor)
    for part in p.parts[1:]:
        current /= part
        need(not current.is_symlink(), 'symlink_in_payload_path')
    need(p.resolve(strict=False).is_relative_to(r), 'resolved_path_outside_root')
    if exists:
        need(p.is_file() and not p.is_symlink(), 'file_not_present')
    return p


def valid_torrent(t):
    need(isinstance(t, dict) and HASH.fullmatch(t.get('hash', '')), 'invalid_torrent_hash')
    for key in ('amount_left', 'progress', 'added_on', 'downloaded', 'completed', 'time_active', 'dlspeed'):
        number(t[key])
    need(type(t['completion_on']) is int and t['completion_on'] >= -1, 'invalid_completion_time')
    need(t['progress'] <= 1 and isinstance(t['state'], str), 'invalid_torrent_status')


def manifest(t, files, properties):
    need(isinstance(files, list) and files, 'metadata_or_files_missing')
    bases = {t['save_path']}
    if properties.get('download_path'):
        bases.add(properties['download_path'])
    for base in bases:
        need(Path(base).is_absolute() and Path(base).is_relative_to('/data/downloads'), 'unsafe_download_base')
        checked_path(str(Path(base) / '.cleanup-path-probe'), '/data/downloads')
    checked_path(t['content_path'], '/data/downloads')
    rows = []
    seen = set()
    for f in files:
        name = f['name']
        need(isinstance(name, str) and name and not PurePosixPath(name).is_absolute()
             and '..' not in PurePosixPath(name).parts and '\\' not in name, 'unsafe_file_name')
        need(name not in seen, 'duplicate_file_name')
        seen.add(name)
        size, progress, priority = number(f['size']), number(f['progress']), number(f['priority'])
        need(progress <= 1 and type(size) is int, 'invalid_file_status')
        paths = set()
        for base in bases:
            p = checked_path(str(Path(base) / name), '/data/downloads')
            paths.update((str(p), str(p) + '.!qB'))
        for p in paths:
            checked_path(p, '/data/downloads')
        rows.append({'name': name, 'size': size, 'progress': progress, 'priority': priority,
                     'media': PurePosixPath(name).suffix.lower() in MEDIA, 'paths': sorted(paths)})
    return rows


def fingerprint(t, rows):
    stable = [t['hash'], t['added_on'], t['category'], t['save_path'], t['content_path'],
              [(f['name'], f['size'], f['priority'], f['paths']) for f in rows]]
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def at_least(value, minimum):
    # Preserve exact thresholds despite floating point subtraction, not UI rounding.
    return value >= minimum or math.isclose(value, minimum, rel_tol=0, abs_tol=1e-12)


def useful_progress(rows):
    wanted = [f for f in rows if f['priority'] > 0 and f['size'] > 0]
    total = sum(f['size'] for f in wanted)
    need(total > 0, 'no_wanted_payload')
    return sum(f['size'] * f['progress'] for f in wanted) / total


def validate_observation(record):
    need(isinstance(record, dict) and set(record) == {'fingerprint', 'boot_id', 'last_seen', 'downloaded',
         'completed', 'active', 'file_progress', 'progress', 'healthy', 'samples', 'near_complete_since'},
         'invalid_observation')
    need(isinstance(record['fingerprint'], str) and isinstance(record['boot_id'], str)
         and type(record['healthy']) is bool, 'invalid_observation')
    for key in ('last_seen', 'downloaded', 'completed', 'active', 'progress'):
        number(record[key])
    need(record['progress'] <= 1 and isinstance(record['file_progress'], list)
         and record['file_progress'], 'invalid_observation')
    for value in record['file_progress']:
        need(number(value) <= 1, 'invalid_observation')
    samples = record['samples']
    need(isinstance(samples, list) and 1 <= len(samples) <= MAX_SAMPLES, 'invalid_observation')
    previous = None
    for sample in samples:
        need(isinstance(sample, dict) and set(sample) == {'time', 'progress'}, 'invalid_observation')
        number(sample['time'])
        need(number(sample['progress']) <= 1, 'invalid_observation')
        if previous:
            need(0 < sample['time'] - previous['time'] <= MAX_GAP
                 and sample['progress'] >= previous['progress'], 'invalid_observation')
        previous = sample
    need(samples[-1]['time'] == record['last_seen'] and samples[-1]['progress'] == record['progress'],
         'invalid_observation')
    near = record['near_complete_since']
    need((near is None and not at_least(record['progress'], NEAR_COMPLETE_PROGRESS))
         or (near is not None and number(near) <= record['last_seen']
             and at_least(record['progress'], NEAR_COMPLETE_PROGRESS)), 'invalid_observation')


def progress_assessment(record):
    """Use a real sample at/before 24h; never invent progress between observations."""
    now, progress = record['last_seen'], record['progress']
    anchors = [s for s in record['samples'] if s['time'] <= now - STALLED_AGE]
    start = anchors[-1] if anchors else record['samples'][0]
    near = record['near_complete_since']
    delta = progress - start['progress']
    fields = {'window_start': start['time'], 'window_end': now, 'window_seconds': now - start['time'],
              'progress_start_percent': start['progress'] * 100, 'progress_end_percent': progress * 100,
              'delta_percentage_points': delta * 100, 'minimum_delta_percentage_points': MIN_DAILY_PROGRESS * 100,
              'required_window_seconds': STALLED_AGE, 'near_complete_since': near,
              'near_complete_age_seconds': now - near if near is not None else None,
              'near_complete_required_seconds': NEAR_COMPLETE_AGE}
    if not record['healthy']:
        reason = 'inactive_or_unhealthy'
    elif near is not None and now - near < NEAR_COMPLETE_AGE:
        reason = 'near_complete_grace'
    elif not anchors:
        reason = 'insufficient_history'
    elif at_least(delta, MIN_DAILY_PROGRESS):
        reason = 'sufficient_progress'
    else:
        reason = 'observed_daily_progress_below_minimum'
    return {'eligible': reason == 'observed_daily_progress_below_minimum', 'reason': reason, **fields}


def observation(t, rows, previous, now, healthy, boot_id):
    """Rolling useful-progress samples plus an independent near-complete grace clock."""
    fp = fingerprint(t, rows)
    progress = useful_progress(rows)
    record = {'fingerprint': fp, 'last_seen': now, 'boot_id': boot_id, 'progress': progress,
              'downloaded': t['downloaded'], 'completed': t['completed'], 'active': t['time_active'],
              'file_progress': [f['progress'] for f in rows], 'near_complete_since':
              now if at_least(progress, NEAR_COMPLETE_PROGRESS) else None}
    eligible = (healthy and t['state'] in ('stalledDL', 'downloading') and t['amount_left'] > 0
                and t['progress'] < 1 and progress < 1 and not t.get('force_start', False))
    samples = []
    if previous:
        validate_observation(previous)
        gap = now - previous['last_seen']
        same_data = (previous['fingerprint'] == fp and gap >= 0
                     and len(previous['file_progress']) == len(rows)
                     and previous['downloaded'] <= t['downloaded'] and previous['completed'] <= t['completed']
                     and all(a <= b for a, b in zip(previous['file_progress'], record['file_progress'])))
        # Calendar grace survives pauses, outages and boots, but not changed/lost data or rollback.
        if same_data and record['near_complete_since'] is not None and previous['near_complete_since'] is not None:
            record['near_complete_since'] = previous['near_complete_since']
        if (eligible and same_data and previous['boot_id'] == boot_id and gap <= MAX_GAP
                and previous['healthy'] and gap - 120 <= t['time_active'] - previous['active'] <= gap + 120):
            samples = previous['samples'][:]
    if samples and samples[-1]['time'] == now:
        samples.pop()
    samples.append({'time': now, 'progress': progress})
    # Retain the nearest predecessor plus real samples from the last 24h.
    anchors = [s for s in samples if s['time'] <= now - STALLED_AGE]
    record['samples'] = ((anchors[-1:] if anchors else [])
                         + [s for s in samples if s['time'] > now - STALLED_AGE])[-MAX_SAMPLES:]
    record['healthy'] = eligible
    return record, progress_assessment(record)['eligible']


def load_state(path):
    state = json.loads(private_file(path).read_text())
    need(isinstance(state, dict) and set(state) == {'version', 'observations', 'pending'}
         and type(state['version']) is int and state['version'] in (1, VERSION)
         and isinstance(state['observations'], dict) and isinstance(state['pending'], dict), 'invalid_state')
    migrated = state['version'] != VERSION
    if migrated:
        # V1 has no daily samples or near-complete clock. Preserve uncertain mutations, not guesses.
        state = {'version': VERSION, 'observations': {}, 'pending': state['pending']}
    return state, migrated


def complete_eligible(t, rows, now):
    wanted = [f for f in rows if f['priority'] > 0 and f['size'] > 0]
    return (t['state'] in {'uploading', 'stalledUP', 'queuedUP', 'stoppedUP'}
            and not t.get('force_start', False) and t['progress'] == 1 and t['amount_left'] == 0
            and 0 < t['added_on'] <= t['completion_on'] <= now - COMPLETE_AGE
            and bool(wanted) and all(f['progress'] == 1 for f in wanted)
            and any(f['media'] for f in wanted))


def partial_safe(rows):
    need(any(f['media'] and f['priority'] > 0 for f in rows), 'no_wanted_media')
    # Include unselected media: qBit deleteFiles=true also removes those files.
    need(not any(f['media'] and f['progress'] == 1 and f['size'] > 0 for f in rows), 'mixed_complete_media')
    for f in rows:
        for name in f['paths']:
            p = checked_path(name, '/data/downloads')
            if p.exists():
                s = p.stat()
                need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'shared_or_nonregular_payload')


class Runner:
    def __init__(self, apis, audit, state_path, apply=False, max_actions=5, policy='both', clock=time.time, sleep=time.sleep,
                 boot_id=None, connectivity=None):
        self.apis, self.q, self.audit = apis, apis['qbittorrent'], audit
        self.state_path, self.apply, self.max_actions, self.policy = Path(state_path), apply, max_actions, policy
        self.clock, self.sleep = clock, sleep
        self.boot_id = boot_id or Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.connectivity = connectivity or internet_healthy
        self.state = {'version': VERSION, 'observations': {}, 'pending': {}}
        self.migrated = False
        if self.state_path.exists():
            self.state, self.migrated = load_state(self.state_path)
        self.jelly_paths = None
        self.actions = 0

    def save(self):
        atomic_json(self.state_path, self.state)

    def torrents(self):
        rows = self.q.call('/api/v2/torrents/info')
        need(isinstance(rows, list), 'invalid_torrent_list')
        hashes = [t.get('hash') for t in rows]
        need(len(hashes) == len(set(hashes)), 'duplicate_torrent_hash')
        for t in rows:
            valid_torrent(t)
        return rows

    def current(self, hash_):
        rows = self.q.call('/api/v2/torrents/info', {'hashes': hash_})
        need(isinstance(rows, list) and len(rows) == 1 and rows[0].get('hash') == hash_, 'torrent_changed_or_missing')
        valid_torrent(rows[0])
        t = rows[0]
        files = self.q.call('/api/v2/torrents/files', {'hash': hash_})
        props = self.q.call('/api/v2/torrents/properties', {'hash': hash_})
        need(isinstance(props, dict), 'invalid_properties')
        return t, manifest(t, files, props)

    def page(self, service, path, query=None):
        result, total = [], None
        for page in range(1, 101):
            options = {**(query or {}), 'page': page, 'pageSize': 250}
            if path.endswith('/history'):
                options.update(sortKey='date', sortDirection='descending')
            data = self.apis[service].call(path, options)
            need(isinstance(data, dict) and isinstance(data.get('records'), list), 'invalid_arr_page')
            count = number(data['totalRecords'])
            need(type(count) is int and (total is None or total == count), 'arr_page_changed')
            total = count
            result += data['records']
            if len(result) >= total:
                need(len(result) == total, 'invalid_arr_page_count')
                return result
            need(data['records'], 'empty_arr_page')
        raise Refused('arr_pagination_limit')

    def jellyfin_paths(self):
        if self.jelly_paths is not None:
            return self.jelly_paths
        paths, offset, expected = set(), 0, None
        for _ in range(100):
            data = self.apis['jellyfin'].call('/Items', {'Recursive': 'true', 'Fields': 'Path',
                'IncludeItemTypes': 'Movie,Episode', 'StartIndex': offset, 'Limit': 500,
                'EnableImages': 'false', 'EnableUserData': 'false'})
            need(isinstance(data, dict) and isinstance(data.get('Items'), list), 'invalid_jellyfin_page')
            total = number(data['TotalRecordCount'])
            need(type(total) is int and (expected is None or total == expected), 'jellyfin_page_changed')
            expected = total
            for item in data['Items']:
                if item.get('Path') and not item.get('IsFolder') and not item.get('IsPlaceHolder', False):
                    paths.add(item['Path'])
            offset += len(data['Items'])
            if offset >= total:
                need(offset == total, 'invalid_jellyfin_page_count')
                self.jelly_paths = paths
                return paths
            need(data['Items'], 'empty_jellyfin_page')
        raise Refused('jellyfin_pagination_limit')

    def imported(self, t, rows):
        service = 'radarr' if t['category'] == 'movies' else 'sonarr'
        history = self.page(service, '/api/v3/history', {'downloadId': t['hash'].upper()})
        events = []
        for item in history:
            if str(item.get('downloadId', '')).lower() != t['hash'] or item.get('eventType') != 'downloadFolderImported':
                continue
            try:
                date = dt.datetime.fromisoformat(item['date'].replace('Z', '+00:00'))
                need(date.tzinfo is not None, 'invalid_import_timezone')
                timestamp = date.timestamp()
            except (KeyError, ValueError, TypeError):
                raise Refused('invalid_import_date') from None
            if timestamp >= t['added_on']:
                events.append(item['data'])
        need(events, 'import_history_missing')
        destinations = []
        for f in rows:
            if not (f['media'] and f['size'] > 0 and f['priority'] > 0):
                continue
            matches = [e for e in events if e.get('droppedPath') in f['paths']]
            need(matches, 'not_all_media_imported')
            verified = False
            for event in matches:
                src = checked_path(event['droppedPath'], '/data/downloads', exists=True)
                dst = checked_path(event.get('importedPath', ''), LIBRARIES[t['category']], exists=True)
                a, b = src.stat(), dst.stat()
                # Current stack uses hardlinks. Do not guess file identity from titles/sizes alone.
                if a.st_size == f['size'] == b.st_size and (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino):
                    destinations.append('/media/' + str(dst.relative_to('/data/media')))
                    verified = True
                    break
            need(verified, 'current_hardlink_import_unverified')
        need(destinations and all(p in self.jellyfin_paths() for p in destinations), 'jellyfin_discovery_pending')

    def queue(self, t):
        service = 'radarr' if t['category'] == 'movies' else 'sonarr'
        rows = self.page(service, '/api/v3/queue', {'includeUnknownMovieItems': 'true', 'includeUnknownSeriesItems': 'true'})
        matches = [r for r in rows if str(r.get('downloadId', '')).lower() == t['hash']]
        need(matches and all(type(r.get('id')) is int for r in matches), 'managed_queue_match_required')
        # One episode/pack can appear multiple times with the same queue id.
        return service, sorted({r['id'] for r in matches})

    def no_shared_payload(self, target, rows):
        paths = {p for f in rows for p in f['paths']}
        content = Path(target['content_path'])
        for other in self.torrents():
            if other['hash'] == target['hash']:
                continue
            op = checked_path(other['content_path'], '/data/downloads')
            need(not (op == content or op.is_relative_to(content) or content.is_relative_to(op)), 'overlapping_torrent_content')
            _, other_rows = self.current(other['hash'])
            need(not paths.intersection(p for f in other_rows for p in f['paths']), 'cross_seed_payload')

    def same(self, old, old_rows, new, new_rows, allow_progress=False):
        need(fingerprint(old, old_rows) == fingerprint(new, new_rows), 'torrent_identity_changed')
        if allow_progress:
            need(new['downloaded'] >= old['downloaded'] and new['completed'] >= old['completed']
                 and new['amount_left'] <= old['amount_left'] and new['completion_on'] == old['completion_on']
                 and all(a['progress'] <= b['progress'] for a, b in zip(old_rows, new_rows)), 'progress_regressed')
        else:
            need(all(old[k] == new[k] for k in ('downloaded', 'completed', 'amount_left', 'completion_on'))
                 and [f['progress'] for f in old_rows] == [f['progress'] for f in new_rows], 'progress_changed')
        need(not new.get('force_start') and 'cleanup-keep' not in
             [x.strip() for x in new.get('tags', '').split(',')], 'torrent_excluded')

    def recheck_slow(self, t, rows, stopped=False):
        need(t['state'] in (('stoppedDL',) if stopped else ('stalledDL', 'downloading'))
             and (not stopped or t['dlspeed'] == 0), 'slow_conditions_changed')
        baseline = self.state['observations'].get(t['hash'])
        need(baseline is not None, 'slow_history_missing')
        # Only this service's confirmed stop may stand in for an active state.
        checked = {**t, 'state': 'downloading'} if stopped else t
        fresh, eligible = observation(checked, rows, baseline, self.clock(), True, self.boot_id)
        need(eligible, 'slow_conditions_changed')
        self.audit.emit('revalidated', t, policy='stalled', **progress_assessment(fresh))

    def invalidate_history(self, hash_):
        record = self.state['observations'].get(hash_)
        if record is None:
            return
        try:
            validate_observation(record)
        except (Refused, KeyError, TypeError, ValueError):
            self.state['observations'].pop(hash_, None)
            return
        # Keep identity-bound calendar grace, but never count a failed run toward a daily window.
        record['healthy'] = False
        record['samples'] = record['samples'][-1:]

    def mutate(self, t, rows, policy):
        hash_ = t['hash']
        action_id = uuid.uuid4().hex
        delete_data = policy == 'stalled'
        # Durable pending first. A crash/ambiguous mutation blocks automatic retry on later runs.
        self.audit.emit('intent', t, action_id=action_id, policy=policy, delete_files=delete_data)
        self.state['pending'][hash_] = {'action_id': action_id, 'policy': policy, 'time': self.clock()}
        self.save()
        submitted, stopped = False, False
        try:
            current, current_rows = self.current(hash_)
            self.same(t, rows, current, current_rows, allow_progress=delete_data)
            if not delete_data:
                need(complete_eligible(current, current_rows, self.clock()), 'complete_conditions_changed')
                self.jelly_paths = None
                self.imported(current, current_rows)
            else:
                self.recheck_slow(current, current_rows)
                partial_safe(current_rows)
                self.no_shared_payload(current, current_rows)
                service, queue_ids = self.queue(current)
                # Quiesce before data deletion, then verify the entire payload again.
                self.q.call('/api/v2/torrents/stop', method='POST', form={'hashes': hash_}, raw=True)
                stopped = True
                for _ in range(10):
                    current, current_rows = self.current(hash_)
                    if current['state'] == 'stoppedDL' and current['dlspeed'] == 0:
                        break
                    self.sleep(.5)
                need(current['state'] == 'stoppedDL' and current['dlspeed'] == 0, 'stop_not_confirmed')
                self.same(t, rows, current, current_rows, allow_progress=True)
                self.recheck_slow(current, current_rows, stopped=True)
                partial_safe(current_rows)
                stopped_t, stopped_rows = current, current_rows
                # Only the selected failed release; never change global retry settings or search replacements.
                for queue_id in queue_ids:
                    self.apis[service].call('/api/v3/queue/' + str(queue_id), {
                        'removeFromClient': 'false', 'blocklist': 'true', 'skipRedownload': 'true',
                        'changeCategory': 'false'}, method='DELETE', raw=True)
                self.audit.emit('release_blocklisted_no_search', t, action_id=action_id)
                current, current_rows = self.current(hash_)
                need(current['state'] == 'stoppedDL' and current['dlspeed'] == 0, 'torrent_restarted_concurrently')
                self.same(stopped_t, stopped_rows, current, current_rows)
                self.recheck_slow(current, current_rows, stopped=True)
                partial_safe(current_rows)
                self.no_shared_payload(current, current_rows)
            self.audit.emit('delete_request', t, action_id=action_id, delete_files=delete_data)
            submitted = True  # Set before request: timeout may mean it was accepted.
            self.q.call('/api/v2/torrents/delete', method='POST', form={
                'hashes': hash_, 'deleteFiles': 'true' if delete_data else 'false'}, raw=True)
            for _ in range(10):
                remaining = self.q.call('/api/v2/torrents/info', {'hashes': hash_})
                need(isinstance(remaining, list), 'invalid_delete_verification')
                files_left = delete_data and any(Path(p).exists() for f in rows for p in f['paths'])
                if not remaining and not files_left:
                    break
                self.sleep(.5)
            need(not remaining, 'entry_removal_unconfirmed')
            need(not files_left, 'payload_removal_unconfirmed')
            self.audit.emit('confirmed', t, action_id=action_id, policy=policy, delete_files=delete_data)
            del self.state['pending'][hash_]
            self.state['observations'].pop(hash_, None)
            self.save()
        except Exception:
            # Keep pending even when only the stop/blocklist was attempted; never silently retry.
            self.audit.emit('ambiguous_or_failed', t, action_id=action_id, request_submitted=submitted,
                            stopped=stopped, reason='manual_review_required')
            raise

    def run(self):
        self.audit.emit('run_started', policy=self.policy, state_version=VERSION)
        if self.migrated:
            self.audit.emit('state_migrated', from_version=1, to_version=VERSION,
                            reason='fresh_daily_samples_required_pending_preserved')
            self.save()
            self.migrated = False
        need(self.q.call('/api/v2/app/version', raw=True).strip() == b'v5.2.4', 'unreviewed_qbit_version')
        torrents = self.torrents()
        managed = [t for t in torrents if t.get('category') in LIBRARIES]
        self.state['observations'] = {k: v for k, v in self.state['observations'].items()
                                      if k in {t['hash'] for t in managed}}
        if not managed:
            self.save()
            self.audit.emit('run_finished', candidates=0, actions=0, pending_actions=len(self.state['pending']))
            need(not self.state['pending'], 'pending_action_requires_review')
            return
        health = self.q.call('/api/v2/transfer/info')
        healthy = (isinstance(health, dict) and health.get('connection_status') in ('connected', 'firewalled')
                   and number(health.get('dht_nodes', 0)) > 0)
        if any(t['state'] in ('stalledDL', 'downloading') for t in managed):
            healthy = healthy and self.connectivity()
        candidates = 0
        for original in managed:
            hash_ = original['hash']
            if hash_ in self.state['pending']:
                self.audit.emit('skip', original, reason='pending_action_requires_review')
                continue
            try:
                need(not original.get('force_start') and 'cleanup-keep' not in
                     [x.strip() for x in original.get('tags', '').split(',')], 'torrent_excluded')
                t, rows = self.current(hash_)
                need(t['category'] == original['category'], 'category_changed')
                now = self.clock()
                obs, stalled = observation(t, rows, self.state['observations'].get(hash_), now, healthy, self.boot_id)
                self.state['observations'][hash_] = obs
                self.save()
                assessment = progress_assessment(obs)
                policy = None
                if self.policy in ('both', 'completed') and complete_eligible(t, rows, now):
                    self.imported(t, rows)
                    policy = 'completed'
                elif self.policy in ('both', 'stalled') and stalled:
                    partial_safe(rows)
                    self.no_shared_payload(t, rows)
                    self.queue(t)
                    # A manager outage or filesystem mismatch cannot be treated as a dead torrent.
                    for service in ('radarr', 'sonarr'):
                        status = self.apis[service].call('/api/v3/system/status')
                        need(isinstance(status, dict) and status.get('version'), 'manager_unavailable')
                    policy = 'stalled'
                if not policy:
                    if self.policy in ('both', 'stalled') and t['progress'] < 1:
                        self.audit.emit('retained', t, policy='stalled', **assessment)
                    continue
                candidates += 1
                detail = {'reason': 'complete_imported_in_jellyfin'} if policy == 'completed' else assessment
                self.audit.emit('candidate', t, policy=policy, **detail,
                                completion_age_seconds=now-t['completion_on'] if policy == 'completed' else None,
                                delete_files=policy == 'stalled')
                if self.apply and self.actions < self.max_actions:
                    self.actions += 1
                    self.mutate(t, rows, policy)
                elif self.apply:
                    self.audit.emit('skip', t, reason='action_limit_reached')
            except (Refused, OSError, ValueError, KeyError, TypeError) as exc:
                self.invalidate_history(hash_)
                self.save()
                self.audit.emit('skip', original, reason=str(exc) if isinstance(exc, Refused) else 'safety_check_failed')
                # An uncertain mutation is not a routine skip: fail the unit for operator attention.
                if hash_ in self.state['pending']:
                    raise Refused('pending_action_requires_review') from None
        self.save()
        self.audit.emit('run_finished', candidates=candidates, actions=self.actions,
                        pending_actions=len(self.state['pending']))
        need(not self.state['pending'], 'pending_action_requires_review')


def internet_healthy():
    """Independent HTTPS probes; never send service credentials to connectivity targets."""
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    for url in ('https://www.debian.org/', 'https://www.qbittorrent.org/'):
        try:
            with client.open(urllib.request.Request(url, method='HEAD'), timeout=5) as response:
                if response.status == 200:
                    return True
        except (OSError, Refused, urllib.error.URLError):
            pass
    return False


def check_storage():
    directory = os.environ.get('CREDENTIALS_DIRECTORY')
    source = Path(directory) / 'storage.json' if directory else Path('/var/lib/media-server/provisioning/storage.json')
    state = json.loads(private_input(source).read_text())
    result = subprocess.run(['findmnt', '--json', '--mountpoint', '/data', '-o', 'TARGET,FSTYPE,UUID,OPTIONS'],
                            capture_output=True, text=True, check=True, timeout=15)
    mounts = json.loads(result.stdout).get('filesystems', [])
    need(len(mounts) == 1, 'storage_mount_missing')
    mount = mounts[0]
    options = mount.get('options', '').split(',')
    # The shipped unit checks the real RW mount using a privileged read-only
    # ExecStartPre, then intentionally gives this process a read-only /data bind.
    isolated_readonly = bool(directory) and bool(os.statvfs('/data').f_flag & os.ST_RDONLY)
    need(mount.get('target') == '/data' and mount.get('fstype') == 'ext4'
         and mount.get('uuid') == state['filesystem_uuid']
         and ('rw' in options or (isolated_readonly and 'ro' in options)), 'storage_guard_failed')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True, help='Private JSON; never deployment .env')
    p.add_argument('--state-dir', type=Path, default=Path('/var/lib/torrent-cleanup'))
    p.add_argument('--log-dir', type=Path, default=Path('/var/log/torrent-cleanup'))
    p.add_argument('--policy', choices=('both', 'completed', 'stalled'), default='both')
    p.add_argument('--max-actions', type=int, default=5)
    p.add_argument('--apply', action='store_true', help='Allow stop/blocklist/removal; default is observation only')
    p.add_argument('--acknowledge-pending', metavar='HASH', help='After manual review, clear one pending action; never resumes or removes a torrent')
    args = p.parse_args(argv)
    audit = None
    os.umask(0o077)
    try:
        need(sys.platform == 'linux' and Path('/etc/debian_version').exists(), 'debian_execution_required')
        need(1 <= args.max_actions <= 20, 'invalid_action_limit')
        cfg = load_config(args.config)
        need(socket.gethostname() == cfg['expected_hostname'], 'unexpected_hostname')
        check_storage()
        state_dir = private_dir(args.state_dir)
        audit = Audit(args.log_dir, args.apply)
        lock_path = state_dir / 'run.lock'
        if lock_path.exists() or lock_path.is_symlink():
            private_file(lock_path)
        fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as lock:
            private_file(lock_path)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused('run_already_active') from None
            if args.acknowledge_pending:
                need(HASH.fullmatch(args.acknowledge_pending), 'invalid_torrent_hash')
                state_path = state_dir / 'state.json'
                state, migrated = load_state(state_path)
                need(args.acknowledge_pending in state['pending'], 'pending_action_not_found')
                if migrated:
                    audit.emit('state_migrated', from_version=1, to_version=VERSION,
                               reason='fresh_daily_samples_required_pending_preserved')
                audit.emit('pending_acknowledged', hash=args.acknowledge_pending,
                           action_id=state['pending'][args.acknowledge_pending]['action_id'])
                del state['pending'][args.acknowledge_pending]
                state['observations'].pop(args.acknowledge_pending, None)
                atomic_json(state_path, state)
            else:
                apis = {s: API(cfg[s], s) for s in ('qbittorrent', 'radarr', 'sonarr', 'jellyfin')}
                apis['qbittorrent'].login()
                Runner(apis, audit, state_dir / 'state.json', args.apply, args.max_actions, args.policy).run()
        print('torrent-cleanup: finished; mode=' + ('apply' if args.apply else 'dry-run') + '; inspect private audit log')
        return 0
    except Exception as exc:
        reason = str(exc) if isinstance(exc, Refused) else 'runtime_or_configuration_error'
        if audit:
            with contextlib.suppress(Exception):
                audit.emit('run_failed', reason=reason)
        print('torrent-cleanup: REFUSED: ' + reason, file=sys.stderr)
        return 1
    finally:
        if audit:
            audit.close()


if __name__ == '__main__':
    sys.exit(main())
