#!/usr/bin/env python3
"""Local SRT batch bookkeeping. No browser, network, credentials, or video edits.

Python 3.10+. Preview by default; prepare/accept/install require --apply to write.
All working data must stay in the owning module's ignored exports/ directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile

LIMIT = 20
MAX_FILE = 8 * 1024 * 1024
MAX_ARCHIVE = 100 * 1024 * 1024
VIDEO_SUFFIXES = {'.mkv', '.mp4', '.m4v', '.avi', '.ts', '.webm'}


def key(name):
    return unicodedata.normalize('NFC', name).casefold()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    if not isinstance(name, str) or name in {'', '.', '..'} or any(c in name for c in '/\\\0'):
        raise ValueError('Unsafe filename')
    return name


def module_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / 'scripts/extract-embedded-subtitles.py').is_file():
            return parent
    raise ValueError('Keep this skill inside its media-server module')


def local_run(path):
    path = Path(path).expanduser().absolute()
    exports = (module_root() / 'exports').resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(exports) or path.resolve() == exports:
        raise ValueError('Working directory must be beneath media-server/exports, without symlinks')
    # Do not accept a symlink at any existing intermediate directory.
    for parent in (path, *path.parents):
        if parent == exports.parent:
            break
        if parent.is_symlink():
            raise ValueError('Working directory contains a symlink')
    return path.resolve()


def read_srt(raw):
    if not raw or len(raw) > MAX_FILE:
        raise ValueError('Empty or oversized SRT')
    content = raw.decode('utf-8-sig').replace('\r\n', '\n').strip()
    cue_re = re.compile(r'^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3}) --> (\d{2,}):([0-5]\d):([0-5]\d),(\d{3})(?: .*)?$')
    cues, texts = [], []
    for number, block in enumerate(re.split(r'\n[ \t]*\n', content), 1):
        lines = block.splitlines()
        timing = cue_re.fullmatch(lines[1]) if len(lines) >= 3 else None
        if not timing or lines[0] != str(number) or not '\n'.join(lines[2:]).strip():
            raise ValueError(f'Invalid or empty SRT cue {number}')
        values = list(map(int, timing.groups()))
        ms = lambda a: ((a[0] * 60 + a[1]) * 60 + a[2]) * 1000 + a[3]
        start, end = ms(values[:4]), ms(values[4:])
        if end < start:
            raise ValueError(f'Negative duration in cue {number}')
        cues.append((number, start, end))
        texts.append('\n'.join(lines[2:]).strip())
    return cues, texts


def write_new(path, raw):
    if path.is_symlink() or path.exists():
        raise FileExistsError(f'Refusing overwrite: {path.name}')
    with path.open('xb') as handle:
        handle.write(raw)


def publish(path, raw):
    """No-clobber atomic publish; filesystem must support same-directory links."""
    fd, temporary = tempfile.mkstemp(prefix='.subtitle-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def prepare(source, run, apply=False, batch_size=LIMIT):
    if not 1 <= batch_size <= LIMIT:
        raise ValueError('Batch size must be between 1 and 20')
    source = Path(source).resolve(strict=True)
    run = local_run(run)
    if not source.is_dir() or run.is_relative_to(source) or source.is_relative_to(run):
        raise ValueError('Source and working directory must be separate')
    if run.exists():
        raise FileExistsError('Run already exists; use status/resume, not prepare again')
    files = sorted(source.glob('*.en.srt'), key=lambda p: key(p.name))
    if not files:
        raise ValueError('No English *.en.srt files found; pass one season directory')
    seen, records = set(), []
    for path in files:
        safe_name(path.name)
        if path.is_symlink() or not path.is_file() or key(path.name) in seen:
            raise ValueError('Duplicate normalized name or source symlink')
        seen.add(key(path.name))
        raw = path.read_bytes()
        cues, _ = read_srt(raw)
        records.append({'name': path.name, 'output_name': path.name[:-len('.en.srt')]+'.es.srt',
                        'sha256': digest(raw), 'cues': len(cues)})
    batches = [{'id': index // batch_size + 1, 'files': records[index:index+batch_size]}
               for index in range(0, len(records), batch_size)]
    summary = {'files': len(records), 'batch_sizes': [len(b['files']) for b in batches], 'run': str(run)}
    if not apply:
        return summary
    run.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.prepare-', dir=run.parent))
    try:
        for batch in batches:
            inputs = staging / f"batch-{batch['id']:03d}" / 'input'
            inputs.mkdir(parents=True)
            for entry in batch['files']:
                raw = (source / entry['name']).read_bytes()
                if digest(raw) != entry['sha256']:
                    raise ValueError('Source changed during preparation')
                write_new(inputs / entry['name'], raw)
        manifest = {'schema': 1, 'source': str(source), 'total': len(records),
                    'provider': 'Google (Free)', 'target': 'es', 'batches': batches}
        write_new(staging / 'manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode())
        staging.rename(run)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return summary


def load_run(run):
    run = local_run(run)
    if (run / 'manifest.json').is_symlink():
        raise ValueError('Manifest must not be a symlink')
    manifest = json.loads((run / 'manifest.json').read_text())
    if manifest.get('schema') != 1 or manifest.get('target') != 'es':
        raise ValueError('Unsupported manifest')
    seen, total = set(), 0
    for index, batch in enumerate(manifest['batches'], 1):
        if batch['id'] != index or not 1 <= len(batch['files']) <= LIMIT:
            raise ValueError('Invalid batch partition')
        folder = run / f'batch-{index:03d}'
        if folder.is_symlink() or (folder / 'input').is_symlink():
            raise ValueError('Batch/input directory must not be a symlink')
        for entry in batch['files']:
            name, output = safe_name(entry['name']), safe_name(entry['output_name'])
            if not name.endswith('.en.srt') or output != name[:-len('.en.srt')]+'.es.srt' or key(name) in seen:
                raise ValueError('Invalid or duplicate manifest filename')
            seen.add(key(name))
            path = run / f'batch-{index:03d}' / 'input' / name
            if path.is_symlink() or digest(path.read_bytes()) != entry['sha256']:
                raise ValueError('Frozen English source changed')
            total += 1
    if total != manifest['total'] or not total:
        raise ValueError('Manifest count mismatch')
    return run, manifest


def batch_data(run, batch_id):
    run, manifest = load_run(run)
    if not 1 <= batch_id <= len(manifest['batches']):
        raise ValueError('Unknown batch')
    batch = manifest['batches'][batch_id-1]
    folder = run / f'batch-{batch_id:03d}'
    if folder.is_symlink() or (folder / 'input').is_symlink():
        raise ValueError('Batch directory must not be a symlink')
    return run, batch, folder


def incoming_files(path, expected):
    path = Path(path)
    if path.stat().st_size > MAX_ARCHIVE:
        raise ValueError('Download is too large')
    if not zipfile.is_zipfile(path):
        if len(expected) != 1 or path.suffix.lower() != '.srt':
            raise ValueError('Expected a ZIP, or one SRT for a one-file batch')
        if key(path.name) not in expected:
            raise ValueError('Singleton download filename does not match this batch')
        return {key(path.name): path.read_bytes()}
    incoming = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 100:
            raise ValueError('Too many ZIP entries')
        size = 0
        for member in members:
            name = member.filename
            parts = PurePosixPath(name).parts
            if '\\' in name or name.startswith('/') or '..' in parts or '\0' in name:
                raise ValueError('Unsafe ZIP path')
            mode = (member.external_attr >> 16) & 0o170000
            if stat.S_ISLNK(mode) or (member.flag_bits & 1):
                raise ValueError('ZIP symlink or encryption is not allowed')
            if member.is_dir():
                continue
            if name == '.DS_Store' or (parts and parts[0] == '__MACOSX'):
                continue
            safe_name(name)  # Website output must be a flat set, not arbitrary folders.
            if not name.lower().endswith('.srt') or key(name) not in expected or key(name) in incoming:
                raise ValueError('Unexpected or duplicate ZIP filename')
            size += member.file_size
            if member.file_size > MAX_FILE or size > MAX_ARCHIVE:
                raise ValueError('Uncompressed ZIP contents exceed limits')
            incoming[key(name)] = archive.read(member)
    if set(incoming) != set(expected):
        raise ValueError('Missing translations; batch is not complete')
    return incoming


def accept(run, batch_id, download, apply=False):
    run, batch, folder = batch_data(run, batch_id)
    expected = {key(e['output_name']): e for e in batch['files']}
    incoming = incoming_files(download, expected)
    validated, report = {}, []
    for name, entry in expected.items():
        raw = incoming[name]
        cues, texts = read_srt(raw)
        original = (folder / 'input' / entry['name']).read_bytes()
        original_cues, original_texts = read_srt(original)
        if cues != original_cues:
            raise ValueError(f"Cue numbering/timing changed: {entry['output_name']}")
        if texts == original_texts:
            raise ValueError(f"All text is unchanged; review translation: {entry['output_name']}")
        validated[entry['output_name']] = raw
        report.append({'name': entry['output_name'], 'sha256': digest(raw), 'cues': len(cues),
                       'unchanged_text_cues': sum(a == b for a,b in zip(texts, original_texts))})
    output = folder / 'output'
    receipt = folder / 'receipt.json'
    if output.exists() or output.is_symlink() or receipt.exists() or receipt.is_symlink():
        raise FileExistsError('Batch already accepted or partial; inspect/resume without overwriting it')
    summary = {'batch': batch_id, 'validated': len(validated), 'timings_unchanged': True}
    if not apply:
        return summary
    stage = Path(tempfile.mkdtemp(prefix='.validate-', dir=folder))
    try:
        for name, raw in validated.items():
            write_new(stage / name, raw)
        download_path = Path(download)
        write_new(folder / ('download.zip' if zipfile.is_zipfile(download_path) else 'download.srt'), download_path.read_bytes())
        stage.rename(output)
        write_new(receipt, (json.dumps({'files': report}, ensure_ascii=False, indent=2)+'\n').encode())
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return summary


def status(run):
    run, manifest = load_run(run)
    batches, completed = [], 0
    for batch in manifest['batches']:
        folder = run / f"batch-{batch['id']:03d}"
        receipt = folder / 'receipt.json'
        done = False
        if receipt.exists():
            if receipt.is_symlink() or (folder / 'output').is_symlink():
                raise ValueError('Receipt/output must not be a symlink')
            records = json.loads(receipt.read_text())['files']
            actual = {key(p.name) for p in (folder / 'output').iterdir()}
            expected = {key(e['output_name']) for e in batch['files']}
            if actual != expected or {key(r['name']) for r in records} != expected or len(records) != len(expected):
                raise ValueError('Accepted output set changed')
            for record in records:
                path = folder / 'output' / safe_name(record['name'])
                if path.is_symlink() or digest(path.read_bytes()) != record['sha256']:
                    raise ValueError('Accepted translation changed')
            done = True
            completed += len(batch['files'])
        batches.append({'id': batch['id'], 'count': len(batch['files']), 'complete': done,
                        'input_files': [str(folder / 'input' / e['name']) for e in batch['files']]})
    return {'expected': manifest['total'], 'validated': completed,
            'complete': completed == manifest['total'], 'batches': batches}


def install(run, library, apply=False):
    run, manifest = load_run(run)
    if not status(run)['complete']:
        raise ValueError('Cannot install an incomplete season')
    library = Path(library).expanduser().absolute()
    if not library.is_dir() or library.is_symlink():
        raise ValueError('Library must be an existing season directory, not a symlink')
    library = library.resolve()
    if library.is_relative_to(run) or run.is_relative_to(library):
        raise ValueError('Library and run must be separate')
    videos = {}
    for path in library.iterdir():
        if path.suffix.lower() in VIDEO_SUFFIXES:
            videos.setdefault(key(path.stem), []).append(path)
    plan = []
    for batch in manifest['batches']:
        for entry in batch['files']:
            matches = videos.get(key(entry['name'][:-len('.en.srt')]), [])
            if len(matches) != 1 or matches[0].is_symlink() or not matches[0].is_file():
                raise ValueError('Video basename changed, missing, or ambiguous; review mapping')
            video = matches[0]
            target = video.with_suffix('.es.srt')
            raw = (run / f"batch-{batch['id']:03d}" / 'output' / entry['output_name']).read_bytes()
            exists = target.exists()
            if target.is_symlink() or (exists and target.read_bytes() != raw):
                raise FileExistsError(f'Existing Spanish subtitle preserved: {target.name}')
            plan.append((target, raw, exists))
    summary = {'files': len(plan), 'new': sum(not x[2] for x in plan), 'existing_identical': sum(x[2] for x in plan)}
    if apply:
        for target, raw, exists in plan:
            if not exists:
                publish(target, raw)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--source', required=True, type=Path)
    prepare_parser.add_argument('--run', required=True, type=Path)
    prepare_parser.add_argument('--batch-size', type=int, default=LIMIT)
    prepare_parser.add_argument('--apply', action='store_true')
    accept_parser = commands.add_parser('accept')
    accept_parser.add_argument('--run', required=True, type=Path)
    accept_parser.add_argument('--batch', required=True, type=int)
    accept_parser.add_argument('--download', required=True, type=Path)
    accept_parser.add_argument('--apply', action='store_true')
    status_parser = commands.add_parser('status')
    status_parser.add_argument('--run', required=True, type=Path)
    install_parser = commands.add_parser('install')
    install_parser.add_argument('--run', required=True, type=Path)
    install_parser.add_argument('--library', required=True, type=Path)
    install_parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = prepare(args.source, args.run, args.apply, args.batch_size)
    elif args.command == 'accept':
        result = accept(args.run, args.batch, args.download, args.apply)
    elif args.command == 'status':
        result = status(args.run)
    else:
        result = install(args.run, args.library, args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        raise SystemExit(f'Error: {error}')
