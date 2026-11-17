#!/usr/bin/env python3
"""Fetch line icons (Lucide, ISC licence) into a project as stroke paths the design pass draws on
like a neon tube (Remotion `LineIcon`, trim-path animation).

Usage:
  python scripts/fetch_lineicons.py --project P monitor search rocket radio-tower heart ...

Each icon is downloaded from the pinned npm package lucide-static (unpkg CDN), its rect / line /
circle / ellipse / polyline / polygon elements are converted to SVG path data, and it is saved as
P/lineicons/<name>.json ({"paths": [...], "viewBox": "0 0 24 24"}). The ISC licence text is read
from the package and stored in P/lineicons/LICENSE.lucide.txt; licenses.json gets one entry.
Icon names: https://lucide.dev/icons (use the kebab-case name).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

PKG = "lucide-static@0.469.0"
BASE = f"https://unpkg.com/{PKG}"


def get(url: str) -> str:
    r = subprocess.run(["curl", "-sfL", "--max-time", "60", url], capture_output=True)
    if r.returncode != 0:
        raise OSError(f"curl exit {r.returncode} for {url}")
    return r.stdout.decode("utf-8", "replace")


def attrs(tag: str) -> dict:
    return {k: v for k, v in re.findall(r'([a-zA-Z][a-zA-Z0-9:-]*)="([^"]*)"', tag)}


def to_paths(svg: str) -> list[str]:
    out = []
    for m in re.finditer(r"<(path|rect|line|circle|ellipse|polyline|polygon)\b([^>]*)/?>", svg):
        kind, a = m.group(1), attrs(m.group(2))
        f = lambda k, d=0.0: float(a.get(k, d))  # noqa: E731
        if kind == "path":
            out.append(a["d"])
        elif kind == "line":
            out.append(f"M{f('x1')} {f('y1')}L{f('x2')} {f('y2')}")
        elif kind in ("circle", "ellipse"):
            cx, cy = f("cx"), f("cy")
            rx = f("r") if kind == "circle" else f("rx"); ry = f("r") if kind == "circle" else f("ry")
            out.append(f"M{cx - rx} {cy}a{rx} {ry} 0 1 0 {2 * rx} 0a{rx} {ry} 0 1 0 {-2 * rx} 0")
        elif kind == "rect":
            x, y, w, h = f("x"), f("y"), f("width"), f("height")
            r = min(f("rx", a.get("ry", 0)), w / 2, h / 2)
            if r:
                out.append(f"M{x + r} {y}H{x + w - r}a{r} {r} 0 0 1 {r} {r}V{y + h - r}a{r} {r} 0 0 1 {-r} {r}H{x + r}a{r} {r} 0 0 1 {-r} {-r}V{y + r}a{r} {r} 0 0 1 {r} {-r}Z")
            else:
                out.append(f"M{x} {y}H{x + w}V{y + h}H{x}Z")
        elif kind in ("polyline", "polygon"):
            # points may be "x,y x,y" or "x y x y": pair the numbers either way
            nums = re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", a.get("points", ""))
            pts = [f"{nums[i]} {nums[i + 1]}" for i in range(0, len(nums) - 1, 2)]
            d = "M" + "L".join(pts)
            out.append(d + ("Z" if kind == "polygon" else ""))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, type=Path)
    ap.add_argument("names", nargs="+")
    a = ap.parse_args()
    d = a.project / "lineicons"
    d.mkdir(parents=True, exist_ok=True)
    res = {"ok": True, "saved": [], "failed": []}
    try:
        lic = get(f"{BASE}/LICENSE")
    except OSError as e:
        print(json.dumps({"ok": False, "error": f"licence not readable: {e}"})); sys.exit(1)
    if "ISC License" not in lic:
        print(json.dumps({"ok": False, "error": "unexpected licence text; not downloading"})); sys.exit(1)
    (d / "LICENSE.lucide.txt").write_text(lic, encoding="utf-8")
    for n in a.names:
        try:
            svg = get(f"{BASE}/icons/{n}.svg")
            paths = to_paths(svg)
            if not paths:
                raise ValueError("no drawable elements")
            (d / f"{n}.json").write_text(json.dumps({"name": n, "paths": paths, "viewBox": "0 0 24 24", "source": f"{BASE}/icons/{n}.svg"}), encoding="utf-8")
            res["saved"].append(f"lineicons/{n}.json")
        except (OSError, ValueError) as e:
            res["failed"].append({"name": n, "error": str(e)})
    lp = a.project / "licenses.json"
    led = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else {"assets": []}
    if not any(x.get("id") == "file:lineicons/" for x in led["assets"]):
        led["assets"].append({"id": "file:lineicons/", "what": "Lucide line icons (stroke paths)", "source": f"https://unpkg.com/{PKG}",
                              "license": "ISC (keep LICENSE.lucide.txt with the files)", "commercial": True, "attribution": None,
                              "license_checked": dt.date.today().isoformat()})
        lp.write_text(json.dumps(led, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=1))
    if not res["saved"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
