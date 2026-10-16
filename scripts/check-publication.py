#!/usr/bin/env python3
"""Local publication preflight. No server access, staging, commits or network.

Uses disposable Git metadata to honor the repository's own .gitignore files,
without depending on a contributor's global excludes or initializing this tree.
Checks working files and, if present, index blobs. Does NOT scan Git history,
OCR images, interpret PDFs or guarantee the absence of every secret.
"""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LAB_GUIDE = "media-server/docs/qbittorrent.md"
TABLE = re.compile(r"^\|\s*(Password|Contraseña|API Key|Token)\s*\|\s*`([^`]+)`\s*\|", re.M | re.I)
ASSIGNMENT = re.compile(r"(?:^|[,{])[ \t]*[\"']?(password|passwd|api[_-]?key|access[_-]?token|client[_-]?secret)[\"']?[ \t]*[:=][ \t]*[\"']?([^\"'\s,}#]+)", re.M | re.I)
CONFIG_SUFFIXES = {".json", ".yaml", ".yml", ".ini", ".conf", ".env", ".txt", ".example"}
DETECTORS = {
    "private-key": re.compile("-----BEGIN " + r"(?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "url-password": re.compile(r"[a-z]+://[^\s/:@]+:[^\s/@]+@", re.I),
}


def git_environment():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return env


def git(args, cwd, data=None):
    return subprocess.run(["git", *args], cwd=cwd, input=data, capture_output=True,
                          check=True, env=git_environment()).stdout


@contextmanager
def portable_view(root):
    with tempfile.TemporaryDirectory(prefix="homelab-publication-") as temp:
        git(["init", "--quiet", "--template=", temp], root)
        yield ["-c", "core.excludesFile=" + os.devnull, "--git-dir", str(Path(temp) / ".git"),
               "--work-tree", str(root)]


def candidate_paths(root, view):
    output = git([*view, "ls-files", "--others", "--exclude-standard", "--exclude=.git", "-z"], root)
    return [os.fsdecode(p) for p in output.split(b"\0") if p]


def ignored_paths(root, view, paths):
    if not paths:
        return set()
    data = b"\0".join(os.fsencode(p) for p in paths) + b"\0"
    result = subprocess.run(["git", *view, "check-ignore", "--no-index", "-z", "--stdin"],
                            cwd=root, input=data, capture_output=True, env=git_environment())
    if result.returncode not in (0, 1):
        raise RuntimeError("Git ignore check failed")
    return {os.fsdecode(p) for p in result.stdout.split(b"\0") if p}


def placeholder(value):
    return (not value or value.startswith(("<", "${", "{{")) or
            value.upper() in {"NULL", "NONE", "FALSE", "TRUE", "REDACTED", "CHANGE_ME", "REPLACE_ME", "SECRET", "YOUR_PASSWORD"})


def lab_password_slot(text):
    marker = "## Laboratory Login Example\n"
    if marker not in text:
        return None
    start = text.index(marker)
    end = text.find("\n## ", start + len(marker))
    end = len(text) if end < 0 else end
    matches = [m for m in TABLE.finditer(text) if start <= m.start() < end and m[1].lower() == "password"]
    return matches[0] if len(matches) == 1 and not placeholder(matches[0][2]) else None


def scan_text(path, text, acknowledge=False, known_lab_value=None):
    findings = []
    def add(kind, position):
        findings.append({"path": path, "line": text.count("\n", 0, position) + 1, "kind": kind})
    for kind, regex in DETECTORS.items():
        for match in regex.finditer(text):
            add(kind, match.start())
    if Path(path).suffix in CONFIG_SUFFIXES or Path(path).name.startswith(".env"):
        for match in ASSIGNMENT.finditer(text):
            if not placeholder(match[2]):
                add("literal-config-credential", match.start())
    allowed = lab_password_slot(text) if path == LAB_GUIDE else None
    for match in TABLE.finditer(text):
        if placeholder(match[2]):
            continue
        if allowed is not None and match.start() == allowed.start() and acknowledge:
            continue
        add("public-lab-password-needs-acknowledgement" if allowed is not None and match.start() == allowed.start()
            else "literal-markdown-credential", match.start())
    if known_lab_value and len(known_lab_value) >= 6 and path != LAB_GUIDE and known_lab_value in text:
        add("duplicated-lab-credential-outside-canonical-guide", text.index(known_lab_value))
    return findings


def decode_text(blob):
    if len(blob) > 2_000_000 or b"\0" in blob:
        return None
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        return None


def audit(root, acknowledge=False):
    root = Path(root).resolve()
    findings, binaries = [], []
    canonical = root / LAB_GUIDE
    text = canonical.read_text() if canonical.is_file() else ""
    slot = lab_password_slot(text)
    known = slot[2] if slot is not None else None
    with portable_view(root) as view:
        paths = candidate_paths(root, view)
        tracked = []
        if (root / ".git").exists():
            tracked = [os.fsdecode(p) for p in git(["-C", str(root), "ls-files", "--cached", "-z"], root).split(b"\0") if p]
        ignored = ignored_paths(root, view, tracked)
        for path in sorted(ignored):
            findings.append({"path": path, "line": 0, "kind": "already-tracked-despite-ignore"})
        for path in sorted(set(paths) | (set(tracked) - ignored)):
            item = root / path
            if item.is_symlink():
                findings.append({"path": path, "line": 0, "kind": "symlink-needs-review"})
                continue
            if item.is_file():
                content = decode_text(item.read_bytes())
                if content is None:
                    binaries.append(path)
                else:
                    findings.extend(scan_text(path, content, acknowledge, known))
            if path in tracked and path not in ignored:
                # Working-tree content alone cannot detect a secret left staged.
                try:
                    staged = decode_text(git(["-C", str(root), "show", ":" + path], root))
                except subprocess.CalledProcessError:
                    findings.append({"path": path, "line": 0, "kind": "index-blob-unavailable"})
                else:
                    if staged is not None:
                        for finding in scan_text(path, staged, acknowledge, known):
                            finding["kind"] = "index:" + finding["kind"]
                            findings.append(finding)
    return {"candidates": len(set(paths) | set(tracked)), "tracked": len(tracked),
            "git_initialized": (root / ".git").exists(), "findings": findings,
            "binary_files": binaries, "public_lab_password_present": known is not None,
            "public_lab_password_acknowledged": acknowledge and known is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acknowledge-public-lab-password", action="store_true",
                        help="Explicitly acknowledge the owner-selected real qBit login in its canonical guide")
    args = parser.parse_args()
    result = audit(ROOT, args.acknowledge_public_lab_password)
    print(f"Publication candidates: {result['candidates']}; tracked files: {result['tracked']}")
    for finding in result["findings"]:
        print(f"BLOCK {finding['path']}:{finding['line']}: {finding['kind']}")
    if result["public_lab_password_acknowledged"]:
        print("KNOWN PUBLIC EXCEPTION: owner-selected qBit credential in " + LAB_GUIDE + " (value withheld here)")
    print(f"Manual binary review required: {len(result['binary_files'])} image/PDF/other binary files; no OCR performed by this script.")
    print("Git history is NOT scanned; this heuristic check is not a guarantee of no secrets.")
    print("No staging, commit, push, server access or repository initialization performed.")
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
