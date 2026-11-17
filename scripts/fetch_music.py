#!/usr/bin/env python3
"""Fetch a licensed music bed from Mixkit into a project (no API key).

Usage:
  python scripts/fetch_music.py search --query workout [--min-s 40]
  python scripts/fetch_music.py get --project P --query workout --pick 0 [--as bed.mp3] [--min-s 40]

Why Mixkit: the open search (fetch_assets.py, Openverse) returns little commercial-safe music, mostly
CC BY-SA. Every Mixkit music item is under the Mixkit Stock Music Free License: commercial social
videos, YouTube, podcasts and online ads, no attribution; NOT CDs/DVDs, TV or radio broadcast, video
games, remixes or music-only tracks, and never register it with Content ID. Each run checks that the
listing page links that licence and that the licence page still says "Stock Music Free License";
if either check fails nothing is downloaded.

The query is tried as a Mixkit tag, mood, genre and instrument page (workout, energetic, hip-hop,
drums...). `get` saves P/music/<as> and adds one entry to P/licenses.json with the restrictions.
Only the query words are sent. Prints JSON; exits 1 when nothing was found or saved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://mixkit.co"
LICENSE_URL = f"{BASE}/license/modal/musicFree/"
LICENSE_NAME = "Mixkit Stock Music Free License"
UA = {"User-Agent": "pro-video-editor-skill/1.0"}
RESTRICTIONS = "no CDs/DVDs, TV or radio broadcast, video games, remixes or music-only use; never register with Content ID"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def slug(q: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")


def to_s(mmss: str) -> int:
    m = re.match(r"\s*(\d+):(\d\d)", mmss or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 0


def parse_listing(page: str) -> list[dict]:
    """One dict per track block on a Mixkit music listing page."""
    out = []
    for b in page.split('data-controller="audio-player"')[1:]:
        mid = re.search(r'data-audio-player-item-id-value="(\d+)"', b)
        url = re.search(r'data-audio-player-preview-url-value="(https://assets\.mixkit\.co/music/\d+/\d+\.mp3)"', b)
        if not (mid and url):
            continue
        title = re.search(r'item-grid-card__title">\s*(.*?)\s*</h2>', b, re.S)
        author = re.search(r'music-preview__author">\s*by\s*(.*?)\s*</p>', b, re.S)
        dur = re.search(r'data-test-id="duration">\s*([\d:]+)', b)
        tags = re.findall(r'meta-links__link"[^>]*href="/free-stock-music/[^"]*">([^<]+)</a>', b)
        out.append({"id": mid.group(1), "title": html.unescape(title.group(1)) if title else None,
                    "author": html.unescape(author.group(1)) if author else None,
                    "duration_s": to_s(dur.group(1)) if dur else 0, "tags": tags, "url": url.group(1)})
    return out


def license_ok() -> bool:
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fetch(LICENSE_URL).decode("utf-8", "replace")))
    return "Stock Music Free License" in t and "Social Media" in t


def search(query: str, min_s: float) -> dict:
    s = slug(query)
    tried = []
    for path in (f"tag/{s}", f"mood/{s}", s, f"instrument/{s}"):
        u = f"{BASE}/free-stock-music/{path}/"
        try:
            page = fetch(u).decode("utf-8", "replace")
        except (OSError, urllib.error.HTTPError) as e:
            tried.append(f"{path}: {e}")
            continue
        if "#musicFree" not in page:
            tried.append(f"{path}: page does not link the music free licence; skipped")
            continue
        items = [x for x in parse_listing(page) if x["duration_s"] >= min_s]
        if items:
            return {"ok": True, "page": u, "results": items, "tried": tried}
        tried.append(f"{path}: no tracks of {min_s:.0f} s or longer")
    return {"ok": False, "error": "no Mixkit music page for that word; try a genre or mood (hip-hop, energetic, drums, cinematic)",
            "tried": tried}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("search", "get"):
        p = sub.add_parser(name)
        p.add_argument("--query", required=True)
        p.add_argument("--min-s", type=float, default=30, help="shortest track to list (s)")
        if name == "get":
            p.add_argument("--project", required=True, type=Path)
            p.add_argument("--pick", type=int, default=0)
            p.add_argument("--as", dest="as_", default="bed.mp3")
    a = ap.parse_args()
    res = search(a.query, a.min_s)
    if a.cmd == "search" or not res["ok"]:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res["ok"] else 1
    try:
        if not license_ok():
            print(json.dumps({"ok": False, "error": f"{LICENSE_URL} no longer reads as the free music licence; check it by hand"}))
            return 1
        it = res["results"][a.pick]
        b = fetch(it["url"])
    except IndexError:
        print(json.dumps({"ok": False, "error": f"--pick {a.pick} out of range ({len(res['results'])} results)"}))
        return 1
    except (OSError, urllib.error.HTTPError) as e:
        print(json.dumps({"ok": False, "error": f"download failed: {e}"}))
        return 1
    if not (b[:3] == b"ID3" or b[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        print(json.dumps({"ok": False, "error": "download is not an MP3"}))
        return 1
    d = a.project / "music"
    d.mkdir(parents=True, exist_ok=True)
    (d / a.as_).write_bytes(b)
    lp = a.project / "licenses.json"
    led = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else {"assets": []}
    lid = f"file:music/{a.as_}"
    led["assets"] = [x for x in led["assets"] if x.get("id") != lid] + [{
        "id": lid, "what": f"'{it['title']}' by {it['author']} (Mixkit music {it['id']})", "source": it["url"],
        "license": LICENSE_NAME, "license_url": LICENSE_URL, "commercial": True, "attribution": None,
        "restrictions": RESTRICTIONS, "license_checked": dt.date.today().isoformat()}]
    lp.write_text(json.dumps(led, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "saved": f"music/{a.as_}", "track": it, "license": LICENSE_NAME,
                      "restrictions": RESTRICTIONS}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
