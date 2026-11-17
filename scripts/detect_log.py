#!/usr/bin/env python3
"""Detect camera log footage and, optionally, write the .cube that converts it to Rec.709.

Usage:
  python scripts/detect_log.py --media CLIP [--log auto|none|PROFILE] [--cube-dir DIR]
  python scripts/detect_log.py --list

ingest.py runs the same detection and conversion on every clip automatically; this script is
for checking one clip, or for taking the conversion LUT into another editor.

Detection order (lib/logcam.py): --log, then the camera's own metadata (Sony XML, maker
markers), then maker + flat picture. A flat picture from an unknown maker is reported, not
guessed. Prints JSON: {"ok", "profile", "name", "source", "evidence", "stats", "cube"}.
Exits 1 with {"ok": false, "error"} on failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--media", help="video file")
    ap.add_argument("--log", default="auto", help="auto, none or a profile id (see --list)")
    ap.add_argument("--cube-dir", help="write the log-to-Rec.709 .cube here when a log profile is found")
    ap.add_argument("--list", action="store_true", help="list the known profiles and exit")
    a = ap.parse_args()
    try:
        from lib import logcam
        if a.list:
            print(json.dumps({"ok": True, "profiles": {k: {"name": v["name"], "needs_maker_lut": bool(v.get("lut"))}
                                                       for k, v in logcam.PROFILES.items()}}, indent=2))
            return 0
        if not a.media:
            raise ValueError("--media is required (or --list)")
        path = Path(a.media)
        if not path.is_file():
            raise FileNotFoundError(f"no such file: {path}")
        from lib.common import ffprobe_json
        pr = ffprobe_json(path)
        vs = next((s for s in pr.get("streams", []) if s.get("codec_type") == "video"), None)
        if vs is None:
            raise ValueError(f"no video stream in {path}")
        video = {"color": {"primaries": vs.get("color_primaries"), "matrix": vs.get("color_space"),
                           "range": vs.get("color_range"), "transfer": vs.get("color_transfer")},
                 "hdr": {"smpte2084": "pq", "arib-std-b67": "hlg"}.get(vs.get("color_transfer") or "")}
        tags = " ".join(f"{k}={v}" for sec in [pr.get("format", {})] + pr.get("streams", [])
                        for k, v in (sec.get("tags") or {}).items())
        det = logcam.detect(path, video, tags, a.log, float(pr.get("format", {}).get("duration") or 0))
        out = {"ok": True, **det, "name": logcam.PROFILES[det["profile"]]["name"] if det.get("profile") else None,
               "cube": None}
        if det.get("profile") and a.cube_dir:
            full = video["color"]["range"] == "pc"
            spec = logcam.PROFILES[det["profile"]]
            if spec.get("lut"):
                stats = det.get("stats") or logcam.pixel_stats(path, float(pr["format"].get("duration") or 0))
                out["cube"] = str(logcam.approx_cube(stats, Path(a.cube_dir)))
                out["note"] = "approximate: this profile has no published formula; use the maker's LUT for exact colour"
            else:
                out["cube"] = str(logcam.conversion_cube(det["profile"], full, Path(a.cube_dir)))
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:  # noqa: BLE001 - one clear JSON error for any failure
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
