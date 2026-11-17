"""Shared helpers for every pro-video-editor script.

Rules enforced here so individual scripts cannot drift:
- JSON output is written atomically (temp file + rename) with UTF-8.
- Failures exit non-zero with one clear message (`fail`).
- External commands run through `run`, which raises a readable error with stderr.
- File identity is a content hash (`file_hash`), used as the cache key everywhere.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

# Hash 4 MiB from the start, middle and end plus the byte size. Media files are
# multi-GB; a full SHA-256 costs seconds per file, while three windows plus size
# make an accidental collision between two real recordings practically impossible.
HASH_WINDOW_BYTES = 4 * 1024 * 1024

# Bump when the meaning of cached results changes so stale cache entries are ignored.
CACHE_SCHEMA = 1

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mxf", ".webm", ".mts", ".m2ts", ".3gp"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aif", ".aiff"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic"}


class ToolError(RuntimeError):
    """An external tool failed; message is safe to show the user."""


def fail(message: str, code: int = 1) -> None:
    """Print a clear error to stderr and exit non-zero."""
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


def log(message: str) -> None:
    """Progress output goes to stderr so stdout stays clean for JSON piping."""
    print(message, file=sys.stderr, flush=True)


def write_json(path: str | Path, obj: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=_json_default)
        f.write("\n")
    os.replace(tmp, path)
    return path


def read_json(path: str | Path) -> Any:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _json_default(o: Any) -> Any:
    try:
        import numpy as np  # local import: numpy is optional for some scripts
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.bool_):
            return bool(o)
    except ImportError:
        pass
    if isinstance(o, Path):
        return o.as_posix()
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


def file_hash(path: str | Path) -> str:
    """Content identity: sha256 over size + three 4 MiB windows."""
    path = Path(path)
    size = path.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode())
    with open(path, "rb") as f:
        offsets = sorted({0, max(0, size // 2 - HASH_WINDOW_BYTES // 2), max(0, size - HASH_WINDOW_BYTES)})
        for off in offsets:
            f.seek(off)
            h.update(f.read(HASH_WINDOW_BYTES))
    return h.hexdigest()[:24]


def params_key(params: dict) -> str:
    blob = json.dumps(params, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


class Cache:
    """JSON result cache keyed by (file hash, stage, params).

    Never analyse the same file twice: callers ask `get` before computing and
    `put` after. Entries live under <cache_dir>/<stage>/<hash>_<params>.json.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, digest: str, stage: str, params: dict) -> Path:
        key = params_key({**params, "_schema": CACHE_SCHEMA})
        return self.root / stage / f"{digest}_{key}.json"

    def get(self, digest: str, stage: str, params: dict) -> Any | None:
        p = self._path(digest, stage, params)
        if p.exists():
            try:
                return read_json(p)
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def put(self, digest: str, stage: str, params: dict, value: Any) -> Any:
        write_json(self._path(digest, stage, params), value)
        return value


def which(name: str) -> str | None:
    return shutil.which(name)


def run(cmd: Iterable[str], *, capture: bool = True, check: bool = True, timeout: float | None = None,
        input_bytes: bytes | None = None, cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    """Run an external command; raise ToolError with the tail of stderr on failure."""
    cmd = [str(c) for c in cmd]
    try:
        proc = subprocess.run(cmd, capture_output=capture, timeout=timeout, input=input_bytes, cwd=cwd)
    except FileNotFoundError:
        raise ToolError(f"'{cmd[0]}' is not installed or not on PATH")
    except subprocess.TimeoutExpired:
        raise ToolError(f"'{cmd[0]}' timed out after {timeout}s")
    if check and proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        tail = "\n".join(err[-12:])
        raise ToolError(f"{Path(cmd[0]).name} exited {proc.returncode}: {tail}")
    return proc


def ffprobe_json(path: str | Path, extra: list[str] | None = None) -> dict:
    args = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams"]
    args += extra or []
    args.append(str(path))
    out = run(args).stdout.decode("utf-8", "replace")
    return json.loads(out or "{}")


def media_kind(path: str | Path) -> str | None:
    ext = Path(path).suffix.lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in IMAGE_EXT:
        return "image"
    return None


def rel(path: str | Path, base: str | Path) -> str:
    """Forward-slash path relative to base when possible (portable JSON)."""
    try:
        return Path(path).resolve().relative_to(Path(base).resolve()).as_posix()
    except ValueError:
        return Path(path).resolve().as_posix()
