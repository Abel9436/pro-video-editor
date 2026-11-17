#!/usr/bin/env python3
"""Fetch 3D icon renders (3dicons by Vijay Verma, CC0) into a project for Stage3D, Podium3D,
Title3D and FloatIcons.

Usage:
  python scripts/fetch_3dicons.py list
  python scripts/fetch_3dicons.py get --project P gym trophy target thumb-down crown

Each icon's metadata lives in the repo realvjy/3dicons (content/3dicons-meta/<name>.md); its front
matter gives CDN URLs per style. The `color` style is used (`premium` renders near-black on dark
sets). Saved as P/icons3d/<name>_color.png, which is the path the design pass expects. Metadata is
read through the jsDelivr mirror of the repo (GitHub's own API allows 60 requests an hour without a
token), then GitHub's API, then the CDN's usual URL pattern.
licenses.json gets one entry. Only the icon names are sent.

Names that exist (2026-11-17) include: gym, trophy, medal, crown, target, thumb-up, thumb-down, tick,
fire, flash, star, rocket, bulb, lock, key, money, dollar, chart, clock, calender, heart, mic,
camera, video-camera, headphone, music, megaphone, notebook, puzzle, gift, map-pin, sheild.

Prints JSON; exits 1 when nothing could be fetched.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/realvjy/3dicons/contents/content/3dicons-meta"
MIRROR = "https://cdn.jsdelivr.net/gh/realvjy/3dicons@HEAD/content/3dicons-meta"        # no rate limit (default branch)
LISTING = "https://data.jsdelivr.com/v1/packages/gh/realvjy/3dicons@HEAD?structure=flat"
CDN = "https://3dicons.sgp1.cdn.digitaloceanspaces.com/v1"
UA = {"User-Agent": "pro-video-editor-skill/1.0"}


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def parse_meta(md: str) -> dict:
    """Front matter 'key: value' lines between the --- fences."""
    m = re.search(r"^---\s*\n(.*?)\n---", md, re.S | re.M)
    return dict(re.findall(r"^([\w-]+):\s*(.+?)\s*$", m.group(1), re.M)) if m else {}


def is_png(b: bytes) -> bool:
    return b[:8] == b"\x89PNG\r\n\x1a\n"


def url_for(name: str, style: str) -> list[str]:
    """Metadata first (some files differ from their name, e.g. crown -> crow-dynamic-color.png), from the
    jsDelivr mirror, then GitHub's API, then the CDN's usual URL pattern."""
    urls = []
    for src in ("mirror", "api"):
        try:
            if src == "mirror":
                md = fetch(f"{MIRROR}/{name}.md").decode("utf-8")
            else:
                md = base64.b64decode(json.loads(fetch(f"{API}/{name}.md").decode("utf-8"))["content"]).decode("utf-8")
            meta = parse_meta(md)
            if meta.get(style):
                urls.append(meta[style])
                break
        except (OSError, ValueError, KeyError):
            continue
    urls += [f"{CDN}/{angle}/{style}/{name}-{angle}-{style}.png" for angle in ("dynamic", "iso", "front")]
    return urls


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="print the icon names in the 3dicons repo")
    g = sub.add_parser("get")
    g.add_argument("--project", required=True, type=Path)
    g.add_argument("--style", default="color", choices=["color", "clay", "gradient", "premium"])
    g.add_argument("names", nargs="+")
    a = ap.parse_args()
    if a.cmd == "list":
        try:
            files = json.loads(fetch(LISTING).decode("utf-8"))["files"]
            names = sorted(Path(x["name"]).stem for x in files if x["name"].startswith("/content/3dicons-meta/") and x["name"].endswith(".md"))
        except (OSError, ValueError, KeyError) as e:
            print(json.dumps({"ok": False, "error": f"3dicons listing not readable: {e}"}))
            return 1
        print(json.dumps({"ok": True, "names": names}))
        return 0
    d = a.project / "icons3d"
    d.mkdir(parents=True, exist_ok=True)
    res = {"ok": True, "saved": [], "failed": []}
    for n in a.names:
        err = "no URL returned a PNG"
        for u in url_for(n, a.style):
            try:
                b = fetch(u)
            except (OSError, urllib.error.HTTPError) as e:
                err = str(e)
                continue
            if is_png(b):
                (d / f"{n}_color.png").write_bytes(b)       # design pass reads <name>_color.png whatever the style
                res["saved"].append(f"icons3d/{n}_color.png")
                break
            err = "download is not a PNG (unknown icon name?)"
        else:
            if "403" in err or "404" in err:
                err = "not found: unknown icon name (run `list` for the names)"
            res["failed"].append({"name": n, "error": err})
    if res["saved"]:
        lp = a.project / "licenses.json"
        led = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else {"assets": []}
        if not any(x.get("id") == "file:icons3d/" for x in led["assets"]):
            led["assets"].append({"id": "file:icons3d/", "what": f"3D icon renders, '{a.style}' style (icons3d/*.png)",
                                  "source": "3dicons.co by Vijay Verma (github.com/realvjy/3dicons)", "license": "CC0 1.0",
                                  "commercial": True, "attribution": None, "license_checked": dt.date.today().isoformat()})
            lp.write_text(json.dumps(led, indent=1, ensure_ascii=False), encoding="utf-8")
    res["ok"] = bool(res["saved"])
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
