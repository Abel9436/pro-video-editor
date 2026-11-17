"""Detect external tools and pick graceful fallbacks.

Each capability reports: available (bool), detail, and the fallback the skill
uses when it is missing. Results are cached for the process.
"""
from __future__ import annotations

import importlib.util
import os
import re
import tempfile
from functools import lru_cache
from pathlib import Path

from .common import ToolError, run, which

# Encoders tried in order of preference. A listed encoder is not proof the
# hardware exists, so each one is test-encoded before it is trusted.
GPU_H264_ENCODERS = ("h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox")

REQUIRED_FILTERS = ("zscale", "tonemap", "ebur128", "astats", "lut3d", "sidechaincompress",
                    "loudnorm", "blackdetect", "freezedetect")

PY_PACKAGES = {
    "numpy": "required",
    "cv2": "required (opencv-python)",
    "soundfile": "required",
    "pyloudnorm": "required",
    "librosa": "music beats and audio features",
    "scenedetect": "shot detection (fallback: OpenCV histogram detector)",
    "faster_whisper": "transcription (fallback: none, transcript skipped with warning)",
    "jsonschema": "EDL validation",
    "pyannote.audio": "speaker diarization (fallback: MFCC clustering, low confidence)",
    "opentimelineio": "timeline export (milestone 8)",
}


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


@lru_cache(maxsize=1)
def ffmpeg_filters() -> set[str]:
    out = run(["ffmpeg", "-hide_banner", "-filters"]).stdout.decode("utf-8", "replace")
    names = set()
    for line in out.splitlines():
        m = re.match(r"^\s*[TSC.|]{2,4}\s+(\S+)\s", line)
        if m:
            names.add(m.group(1))
    return names


@lru_cache(maxsize=1)
def ffmpeg_encoders() -> set[str]:
    out = run(["ffmpeg", "-hide_banner", "-encoders"]).stdout.decode("utf-8", "replace")
    return {m.group(1) for m in re.finditer(r"^\s*[VAS][F.][S.][X.][B.][D.]\s+(\S+)", out, re.M)}


def _encoder_works(encoder: str) -> bool:
    """Encode 10 frames to a temp file; True only if the hardware accepts it."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "probe.mp4"
        try:
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                 "testsrc2=size=256x256:rate=30:duration=0.34", "-c:v", encoder, "-y", str(out)],
                timeout=30)
            return out.exists() and out.stat().st_size > 0
        except ToolError:
            return False


@lru_cache(maxsize=1)
def best_h264_encoder() -> str:
    if os.environ.get("PVE_FORCE_CPU"):
        return "libx264"
    listed = ffmpeg_encoders()
    for enc in GPU_H264_ENCODERS:
        if enc in listed and _encoder_works(enc):
            return enc
    return "libx264"


def blender_path() -> str | None:
    found = which("blender")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), "/Applications"):
        root = Path(base) / "Blender Foundation"
        if root.exists():
            hits = sorted(root.glob("Blender*/blender.exe"))
            if hits:
                return str(hits[-1])
        mac = Path(base) / "Blender.app/Contents/MacOS/Blender"
        if mac.exists():
            return str(mac)
    return None


def check_all(test_gpu: bool = True) -> dict:
    report: dict = {"tools": {}, "python": {}, "fallbacks": [], "fatal": []}
    for tool in ("ffmpeg", "ffprobe"):
        p = which(tool)
        report["tools"][tool] = {"available": bool(p), "path": p}
        if not p:
            report["fatal"].append(f"{tool} is required: install FFmpeg 6+ and put it on PATH")
    if report["fatal"]:
        return report

    ver = run(["ffmpeg", "-hide_banner", "-version"]).stdout.decode("utf-8", "replace").splitlines()[0]
    report["tools"]["ffmpeg"]["version"] = ver
    filters = ffmpeg_filters()
    missing = [f for f in REQUIRED_FILTERS if f not in filters]
    report["tools"]["ffmpeg"]["missing_filters"] = missing
    if "zscale" in missing:
        report["fallbacks"].append("No zscale filter: HDR sources cannot be tone-mapped; ingest will flag them instead")

    enc = best_h264_encoder() if test_gpu else "libx264"
    report["tools"]["gpu_encoder"] = {"available": enc != "libx264", "encoder": enc}
    if enc == "libx264":
        report["fallbacks"].append("No working GPU encoder: CPU encoding with libx264")

    node = which("node")
    node_ver = run(["node", "--version"]).stdout.decode().strip() if node else None
    node_ok = bool(node_ver) and int(node_ver.lstrip("v").split(".")[0]) >= 20
    report["tools"]["node"] = {"available": node_ok, "path": node, "version": node_ver}
    if not node_ok:
        report["fallbacks"].append("Node 20+ missing: no Remotion; captions fall back to FFmpeg ASS burn-in")

    blender = blender_path()
    report["tools"]["blender"] = {"available": bool(blender), "path": blender}
    if not blender:
        report["fallbacks"].append("Blender not found: 3D titles render with Three.js inside Remotion")

    for mod, role in PY_PACKAGES.items():
        ok = _has_module(mod)
        report["python"][mod] = {"available": ok, "role": role}
        if not ok:
            if role.startswith("required"):
                report["fatal"].append(f"Python package '{mod}' is required: pip install -r requirements.txt")
            else:
                report["fallbacks"].append(f"{mod} missing: {role}")
    return report
