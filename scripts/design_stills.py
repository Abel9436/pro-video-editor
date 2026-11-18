#!/usr/bin/env python3
"""Review sheet of every design transition: stills just before, on, just after and settled.

Usage:
  python scripts/design_stills.py --video P/exports/v4.mp4 --edl P/edl/v4.json [--out P/qc/design_sheet.jpg]
  python scripts/design_stills.py --video P/exports/v4.mp4 --at 1.7,3.4,10.2

Holds look fine; mistakes hide in transitions (shapes passing through each other, a frame of nothing,
left and right swapped, a card leaving the frame). For each design event in the EDL (scene and overlay
starts and ends, camera moves in and out, fx) the sheet shows the frame 0.10 s before, on the event,
0.15 s after and 0.40 s after, labelled with the time and the event. Stills are not playback: watch the
video too. Prints JSON; exits 1 if the video can't be read.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

OFFSETS = (-0.10, 0.0, 0.15, 0.40)
TW, TH = 216, 384          # 9:16 tiles; 4 per event, 2 events per row


def events_of(edl: dict) -> list[tuple[float, str]]:
    """(seconds, label) for every design event, sorted and de-duplicated within 2 frames."""
    fps = float(Fraction(str(edl.get("fps", 30))))      # 30, "30" or "30000/1001"
    d = edl.get("design") or {}
    out = []
    for k in ("scenes", "overlays"):
        for x in d.get(k) or []:
            out += [(x["s"] / fps, f"{x['type']} in"), (x["e"] / fps, f"{x['type']} out")]
    for x in d.get("camera") or []:
        tag = "card" if "card" in x else "camera"
        out += [(x["s"] / fps, f"{tag} in"), (x["e"] / fps, f"{tag} out")]
    for x in d.get("fx") or []:
        out.append((x["at"] / fps, x["type"]))
    out.sort()
    keep: list[tuple[float, str]] = []
    for t, lab in out:
        if keep and t - keep[-1][0] < 2 / fps:
            keep[-1] = (keep[-1][0], keep[-1][1] + " + " + lab)
        else:
            keep.append((t, lab))
    return keep


def duration(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def grab(video: Path, t: float, dst: Path) -> bool:
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={TW}:{TH}", str(dst)], capture_output=True)
    return r.returncode == 0 and dst.exists()


def sheet(rows: list[tuple[float, str, list[Path]]], out: Path) -> None:
    from PIL import Image, ImageDraw
    per = 2
    lines = -(-len(rows) // per)
    im = Image.new("RGB", (TW * 4 * per + 12 * (per - 1), lines * (TH + 30)), "#111111")
    dr = ImageDraw.Draw(im)
    for i, (t, lab, paths) in enumerate(rows):
        x0, y0 = (i % per) * (TW * 4 + 12), (i // per) * (TH + 30)
        dr.text((x0 + 6, y0 + 8), f"{t:6.2f}s  {lab}"[:60], fill="#ffffff")
        for j, p in enumerate(paths):
            if p.exists():
                im.paste(Image.open(p).convert("RGB"), (x0 + j * TW, y0 + 30))
            dr.text((x0 + j * TW + 4, y0 + 34), f"{OFFSETS[j]:+.2f}", fill="#ffd400")
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=85)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--edl", type=Path, help="take the events from this EDL's design block")
    ap.add_argument("--at", default="", help="comma-separated seconds instead of (or as well as) --edl")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    try:
        dur = duration(a.video)
    except (OSError, ValueError):
        print(json.dumps({"ok": False, "error": f"cannot read {a.video}"}))
        return 1
    ev = events_of(json.loads(a.edl.read_text(encoding="utf-8"))) if a.edl else []
    ev += [(float(t), "at") for t in a.at.split(",") if t.strip()]
    if not ev:
        print(json.dumps({"ok": False, "error": "no events: pass --edl with a design block, or --at"}))
        return 1
    out = a.out or a.video.with_name(a.video.stem + "_design_sheet.jpg")
    rows = []
    with tempfile.TemporaryDirectory() as td:
        for i, (t, lab) in enumerate(sorted(ev)):
            paths = []
            for j, o in enumerate(OFFSETS):
                p = Path(td) / f"{i:03d}_{j}.png"
                grab(a.video, min(dur - 0.12, t + o), p)   # a seek at the very last frame returns nothing
                paths.append(p)
            rows.append((t, lab, paths))
        sheet(rows, out)
    print(json.dumps({"ok": True, "sheet": str(out), "events": [{"t": round(t, 3), "what": lab} for t, lab in sorted(ev)],
                      "note": "stills are not playback: watch the video as well"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
