#!/usr/bin/env python3
"""Read embedded English subtitles; write local SRT copies grouped by season.

Python 3.10+, ffmpeg and ffprobe must be available on the machine running this.
Preview by default; --apply writes only beneath --output. Never edits media,
downloads, subtitle timing, or service settings. Bitmap subtitles need OCR and
are rejected. Untagged languages are not guessed. Existing files are preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


VIDEO_SUFFIXES = {".mkv", ".mp4", ".m4v", ".avi", ".ts", ".webm"}
TEXT_CODECS = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}
EPISODE = re.compile(
    r"(?<![A-Za-z0-9])S(?P<season>\d{1,2})E(?P<episode>\d{1,3})(?!\d)", re.I
)
TIMING = re.compile(
    r"^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3}) --> "
    r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})(?: .*)?$"
)


def run(command: list[str], timeout: int = 120) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ValueError(result.stderr.strip()[-1500:] or f"Exit {result.returncode}")
    return result.stdout


def probe(path: Path, executable: str) -> list[dict]:
    data = json.loads(run([
        executable, "-v", "error", "-select_streams", "s",
        "-show_entries", "stream=index,codec_name:stream_tags=language,title:"
        "stream_disposition=default,forced,hearing_impaired", "-of", "json", str(path),
    ]))
    return data.get("streams", [])


def choose_stream(streams: list[dict]) -> dict:
    candidates = []
    for stream in streams:
        tags = stream.get("tags", {})
        flags = stream.get("disposition", {})
        language = str(tags.get("language", "")).strip().lower()
        title = str(tags.get("title", "")).lower()
        if language not in {"eng", "en", "english"}:
            continue
        if flags.get("forced") or any(word in title for word in ("forced", "commentary")):
            continue
        candidates.append(stream)
    if not candidates:
        raise ValueError("No explicitly tagged, full-dialogue English subtitle track")
    text = [s for s in candidates if s.get("codec_name") in TEXT_CODECS]
    if not text:
        raise ValueError("English subtitles are bitmap/unsupported; SRT requires OCR")

    def rank(stream: dict) -> tuple[int, int]:
        flags = stream.get("disposition", {})
        return (not bool(flags.get("hearing_impaired")), bool(flags.get("default")))

    best = max(rank(s) for s in text)
    selected = [s for s in text if rank(s) == best]
    if len(selected) != 1:
        raise ValueError("Ambiguous English tracks; inspect/select before extracting")
    return selected[0]


def discover(source: Path, seasons: set[int]) -> list[tuple[Path, int]]:
    source = source.resolve(strict=True)
    videos = []
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError(f"Source symlink is not permitted: {path}")
        match = EPISODE.search(path.stem)
        if not match:
            raise ValueError(f"Cannot identify SxxEyy: {path.name}")
        season = int(match["season"])
        if not seasons or season in seasons:
            videos.append((path, season))
    videos.sort(key=lambda item: (item[1], item[0].name.casefold()))
    if not videos:
        raise ValueError("No matching episodes found")
    found = {season for _, season in videos}
    if seasons - found:
        raise ValueError(f"No videos found for seasons {sorted(seasons - found)}")
    return videos


def targets(videos: list[tuple[Path, int]], output: Path) -> list[tuple[Path, Path]]:
    output = output.resolve()
    planned = []
    seen = set()
    for source, season in videos:
        target = output / f"Season {season:02d}" / (source.stem + ".en.srt")
        key = str(target).casefold()
        if key in seen:
            raise ValueError(f"Output name collision: {target.name}")
        seen.add(key)
        if target.parent.is_symlink() or target.is_symlink():
            raise ValueError(f"Output symlink is not permitted: {target}")
        if not target.resolve().is_relative_to(output):
            raise ValueError(f"Output escapes destination: {target}")
        planned.append((source, target))
    return planned


def inspect_srt(path: Path) -> dict:
    raw = path.read_bytes()
    content = raw.decode("utf-8-sig").replace("\r\n", "\n").strip()
    cues = re.split(r"\n[ \t]*\n", content) if content else []
    first_start = last_end = None
    for expected, cue in enumerate(cues, 1):
        lines = cue.splitlines()
        match = TIMING.fullmatch(lines[1]) if len(lines) >= 3 else None
        if not match or not lines[0].isdigit() or int(lines[0]) != expected:
            raise ValueError(f"Invalid SRT cue {expected}: {path.name}")
        numbers = list(map(int, match.groups()))
        milliseconds = lambda n: ((n[0] * 60 + n[1]) * 60 + n[2]) * 1000 + n[3]
        start, end = milliseconds(numbers[:4]), milliseconds(numbers[4:])
        if end < start:
            raise ValueError(f"Negative-duration SRT cue {expected}")
        if first_start is None:
            first_start = start
        last_end = max(last_end or 0, end)
    if not cues:
        raise ValueError(f"Empty SRT: {path.name}")
    return {"cues": len(cues), "first_start_ms": first_start,
            "last_end_ms": last_end, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def extract(source: Path, target: Path, stream: dict, executable: str) -> dict:
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Refusing to overwrite {target}")
    before = source.stat()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".extract-", suffix=".srt", dir=target.parent)
    os.close(fd)
    staging = Path(temporary)
    try:
        codec = "copy" if stream["codec_name"] in {"subrip", "srt"} else "srt"
        run([
            executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-copyts", "-i", str(source), "-map", f"0:{stream['index']}",
            "-c:s", codec, "-avoid_negative_ts", "disabled", "-f", "srt", str(staging),
        ], timeout=1800)
        metadata = inspect_srt(staging)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Source changed during extraction; not publishing output")
        # Same-filesystem atomic creation: link fails rather than overwriting.
        os.link(staging, target)
        return metadata
    finally:
        staging.unlink(missing_ok=True)


def save_report(path: Path, data: dict) -> None:
    if path.is_symlink():
        raise ValueError("Report must not be a symlink")
    fd, temporary = tempfile.mkstemp(prefix=".report-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Series directory (read only)")
    parser.add_argument("--output", required=True, type=Path, help="Local export directory")
    parser.add_argument("--season", type=int, action="append", default=[], help="Repeatable; default: all")
    parser.add_argument("--apply", action="store_true", help="Write SRT files; default only previews")
    args = parser.parse_args(argv)
    source = args.source.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    if not source.is_dir():
        parser.error("Source must be a directory")
    if output.is_relative_to(source) or source.is_relative_to(output):
        parser.error("Source and output must be separate directories")
    if any(season < 0 or season > 99 for season in args.season):
        parser.error("Season must be between 0 and 99")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        parser.error("Install ffmpeg and ffprobe on the machine running this script")
    started = time.monotonic()
    plan = targets(discover(source, set(args.season)), output)
    results = []
    if args.apply:
        output.mkdir(parents=True, exist_ok=True)
    for index, (video, target) in enumerate(plan, 1):
        entry = {"source": str(video), "output": str(target)}
        try:
            if target.exists():
                entry.update(status="existing", **inspect_srt(target))
            else:
                stream = choose_stream(probe(video, ffprobe))
                entry["stream"] = stream
                if args.apply:
                    entry.update(status="extracted", **extract(video, target, stream, ffmpeg))
                else:
                    entry["status"] = "planned"
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            entry.update(status="failed", error=str(error))
        results.append(entry)
        print(f"[{index}/{len(plan)}] {entry['status']}: {target.parent.name}/{target.name}", flush=True)
        if "error" in entry:
            print(f"  {entry['error']}", flush=True)
        if args.apply:
            save_report(output / "extraction-report.json", {"source": str(source), "results": results})
    counts = {status: sum(r["status"] == status for r in results)
              for status in ("planned", "extracted", "existing", "failed")}
    print(json.dumps({"summary": counts, "seconds": round(time.monotonic() - started, 2)}), flush=True)
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("Interrupted; completed SRT files were kept")
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(f"Error: {error}")
