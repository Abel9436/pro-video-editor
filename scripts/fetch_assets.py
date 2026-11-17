#!/usr/bin/env python3
"""Stage 7 - Find and fetch assets with their licenses, local library first.

Usage:
  python scripts/fetch_assets.py search --kind music --query "calm piano" [--commercial] [--min-s 30]
                                        [--limit 10] --out P/assets_search.json
  python scripts/fetch_assets.py get --from P/assets_search.json --pick 0 [--project P]

Lookup order (references/assets-sources.md): the user's paid library (assets/local), the
editor kit, bulk free packs (assets/library) - all through assets/catalog.json built by
tag_assets.py - then online sources: Openverse (audio, images; no key), Pexels and Pixabay
(video, photos; keys in PEXELS_API_KEY / PIXABAY_API_KEY), Poly Haven (HDRIs, models; no key),
Iconify (icons; no key), Freesound (FREESOUND_API_KEY; excluded for commercial projects).

License filter: CC0, public domain and CC BY are accepted (BY adds an attribution line).
ND is rejected for music and video (an edit is a derivative), SA is rejected for commercial
projects (it would bind the whole video), NC is rejected for commercial projects. Results
below the quality bar are dropped: an empty slot beats a cheap-looking asset.

`get` downloads into assets/cache/<source>/, adds a catalog entry (id cat:<source>:<id>)
and a ledger line in P/licenses.json. Nothing about the user or project is sent to any API;
only the search words.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.common import fail, log, read_json, write_json  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
UA = "pro-video-editor/1.0 (asset search)"
TIMEOUT = 30
LICENSE_CHECKED = {   # date each provider's own terms page was read; see references/assets-sources.md
    "openverse": "2026-11-15 (API terms page not published; per-item license fields used)",
    "pexels": "2026-11-15", "pixabay": "2026-11-15 (summary page)", "polyhaven": "2026-11-15",
    "iconify": "not verified: license page returned 404 on 2026-11-15; per-set license fields used",
    "freesound": "2026-11-15 (API commercial use negotiated case by case)",
}
MIN_IMAGE_SHORT_SIDE = 1080
MIN_VIDEO_HEIGHT = 1080


def _get(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def license_ok(lic: str, kind: str, commercial: bool) -> tuple[bool, str]:
    lic = (lic or "").lower()
    if lic in ("cc0", "pdm", "pd", "pexels", "pixabay", "cc0-1.0"):
        return True, ""
    if "nd" in lic.split("-") and kind in ("music", "video", "sfx"):
        return False, "no-derivatives license: the edit would be a derivative"
    if "nc" in lic.split("-") and commercial:
        return False, "non-commercial license on a commercial project"
    if "sa" in lic.split("-") and commercial:
        return False, "share-alike would bind the whole video to the same license"
    if lic.startswith("by"):
        return True, ""
    return False, f"unknown license '{lic}'"


def attribution(title: str, creator: str | None, lic: str, ver: str | None, url: str | None) -> str | None:
    lic = (lic or "").lower()
    if lic in ("cc0", "pdm", "pexels", "pixabay"):
        return None
    return f"\"{title}\" by {creator or 'unknown'}, licensed CC {lic.upper()} {ver or ''}".strip() + (f" ({url})" if url else "")


# ----------------------------------------------------------------------------- sources
def search_catalog(kind: str, query: str) -> list[dict]:
    cat = SKILL / "assets" / "catalog.json"
    if not cat.exists():
        return []
    words = set(query.lower().split())
    out = []
    for e in read_json(cat).get("assets", []):
        if e.get("kind") != kind:
            continue
        tags = set(" ".join([*(e.get("tags") or []), e.get("role") or "", Path(e.get("path", "")).stem]).lower()
                   .replace("_", " ").split())
        score = len(words & tags)
        if score:
            out.append({**e, "score": score, "origin": "local"})
    return sorted(out, key=lambda e: (e.get("tier", 9), -e["score"]))


def search_openverse(kind: str, query: str, limit: int, commercial: bool) -> list[dict]:
    ep = "audio" if kind in ("music", "sfx") else "images"
    q = {"q": query, "page_size": min(20, limit * 3),  # anonymous requests above 20 get HTTP 401 (2026-11-17)
          "license_type": "commercial" if commercial else "all"}
    if kind in ("music", "sfx"):
        q["category"] = "music" if kind == "music" else "sound_effect"
    d = _get(f"https://api.openverse.org/v1/{ep}/?{urllib.parse.urlencode(q)}")
    out = []
    for r in d.get("results", []):
        ok, why = license_ok(f"{r['license']}", kind, commercial)
        item = {"origin": "openverse", "source_id": r["id"], "title": r.get("title"), "creator": r.get("creator"),
                "license": r["license"], "license_version": r.get("license_version"), "license_url": r.get("license_url"),
                "url": r["url"], "page": r.get("foreign_landing_url"), "provider": r.get("provider"),
                "duration_s": (r.get("duration") or 0) / 1000 if kind in ("music", "sfx") else None,
                "width": r.get("width"), "height": r.get("height"), "filetype": r.get("filetype"),
                "accepted": ok, "rejected_because": why or None}
        item["attribution"] = attribution(item["title"], item["creator"], r["license"], r.get("license_version"), item["page"])
        out.append(item)
    return out


def search_pexels(kind: str, query: str, limit: int) -> list[dict]:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    if kind == "video":
        d = _get(f"https://api.pexels.com/videos/search?{urllib.parse.urlencode({'query': query, 'per_page': limit})}",
                 {"Authorization": key})
        out = []
        for v in d.get("videos", []):
            files = sorted((f for f in v["video_files"] if (f.get("height") or 0) >= MIN_VIDEO_HEIGHT),
                           key=lambda f: f.get("height") or 0)
            if not files:
                continue
            out.append({"origin": "pexels", "source_id": str(v["id"]), "title": v.get("url"), "creator": v["user"]["name"],
                        "license": "pexels", "url": files[0]["link"], "page": v["url"], "duration_s": v.get("duration"),
                        "width": files[0].get("width"), "height": files[0].get("height"), "accepted": True,
                        "attribution": None, "courtesy": f"Video by {v['user']['name']} on Pexels"})
        return out
    d = _get(f"https://api.pexels.com/v1/search?{urllib.parse.urlencode({'query': query, 'per_page': limit})}",
             {"Authorization": key})
    return [{"origin": "pexels", "source_id": str(p["id"]), "title": p.get("alt"), "creator": p["photographer"],
             "license": "pexels", "url": p["src"]["original"], "page": p["url"], "width": p["width"], "height": p["height"],
             "accepted": min(p["width"], p["height"]) >= MIN_IMAGE_SHORT_SIDE, "attribution": None,
             "courtesy": f"Photo by {p['photographer']} on Pexels"} for p in d.get("photos", [])]


def search_pixabay(kind: str, query: str, limit: int) -> list[dict]:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    ep = "videos/" if kind == "video" else ""
    d = _get(f"https://pixabay.com/api/{ep}?{urllib.parse.urlencode({'key': key, 'q': query, 'per_page': max(3, limit)})}")
    out = []
    for h in d.get("hits", []):
        if kind == "video":
            v = h["videos"].get("large") or h["videos"].get("medium")
            out.append({"origin": "pixabay", "source_id": str(h["id"]), "title": h.get("tags"), "creator": h.get("user"),
                        "license": "pixabay", "url": v["url"], "page": h["pageURL"], "width": v.get("width"),
                        "height": v.get("height"), "duration_s": h.get("duration"),
                        "accepted": (v.get("height") or 0) >= MIN_VIDEO_HEIGHT, "attribution": None})
        else:
            out.append({"origin": "pixabay", "source_id": str(h["id"]), "title": h.get("tags"), "creator": h.get("user"),
                        "license": "pixabay", "url": h.get("largeImageURL"), "page": h["pageURL"],
                        "width": h.get("imageWidth"), "height": h.get("imageHeight"),
                        "accepted": min(h.get("imageWidth", 0), h.get("imageHeight", 0)) >= MIN_IMAGE_SHORT_SIDE,
                        "attribution": None})
    return out


def search_polyhaven(kind: str, query: str, limit: int) -> list[dict]:
    t = {"hdri": "hdris", "model": "models", "texture": "textures"}[kind]
    d = _get(f"https://api.polyhaven.com/assets?t={t}")
    words = query.lower().split()
    out = []
    for aid, a in d.items():
        hay = " ".join([aid, a.get("name", ""), *a.get("tags", []), *a.get("categories", [])]).lower()
        if all(w in hay for w in words):
            out.append({"origin": "polyhaven", "source_id": aid, "title": a.get("name"), "creator": ", ".join(a.get("authors", {})),
                        "license": "cc0", "page": f"https://polyhaven.com/a/{aid}", "url": None, "accepted": True,
                        "attribution": None, "download_api": f"https://api.polyhaven.com/files/{aid}"})
    return out[:limit]


def search_iconify(query: str, limit: int, prefix: str | None) -> list[dict]:
    q = {"query": query, "limit": max(32, limit)}
    if prefix:
        q["prefix"] = prefix
    d = _get(f"https://api.iconify.design/search?{urllib.parse.urlencode(q)}")
    out = []
    for icon in d.get("icons", [])[:limit]:
        pre, name = icon.split(":", 1)
        info = (d.get("collections") or {}).get(pre, {})
        lic = (info.get("license") or {}).get("spdx", "unknown")
        ok = lic.lower() in ("mit", "apache-2.0", "cc0-1.0", "isc", "cc-by-4.0", "ofl-1.1")
        out.append({"origin": "iconify", "source_id": icon, "title": name, "creator": (info.get("author") or {}).get("name"),
                    "license": lic, "url": f"https://api.iconify.design/{pre}/{name}.svg", "page": f"https://icon-sets.iconify.design/{pre}/",
                    "icon_set": pre, "accepted": ok, "attribution": None if lic.lower() != "cc-by-4.0" else
                    f"{name} icon from {info.get('name', pre)} (CC BY 4.0)"})
    return out


def search(kind: str, query: str, limit: int, commercial: bool, min_s: float | None, prefix: str | None) -> dict:
    results, tried = [], []
    local = search_catalog(kind, query)
    results += local; tried.append(f"local catalog ({len(local)})")
    def safe(name, fn):
        try:
            r = fn(); tried.append(f"{name} ({len(r)})"); return r
        except Exception as e:  # an API being down falls through to the next source
            tried.append(f"{name} (failed: {e})"); return []
    if kind in ("music", "sfx"):
        results += safe("openverse", lambda: search_openverse(kind, query, limit, commercial))
    elif kind in ("image",):
        results += safe("pexels", lambda: search_pexels("image", query, limit))
        results += safe("pixabay", lambda: search_pixabay("image", query, limit))
        results += safe("openverse", lambda: search_openverse("image", query, limit, commercial))
    elif kind == "video":
        results += safe("pexels", lambda: search_pexels("video", query, limit))
        results += safe("pixabay", lambda: search_pixabay("video", query, limit))
    elif kind in ("hdri", "model", "texture"):
        results += safe("polyhaven", lambda: search_polyhaven(kind, query, limit))
    elif kind == "icon":
        results += safe("iconify", lambda: search_iconify(query, limit, prefix))
    if min_s:
        for r in results:
            if r.get("duration_s") is not None and r["duration_s"] < min_s:
                r["accepted"] = False; r["rejected_because"] = f"shorter than {min_s} s"
    accepted = [r for r in results if r.get("accepted", True)]
    return {"kind": kind, "query": query, "commercial": commercial, "searched": tried,
            "results": accepted[:limit], "rejected": [r for r in results if not r.get("accepted", True)][:limit],
            "date": str(_dt.date.today())}


# ----------------------------------------------------------------------------- download
def download(item: dict, kind: str) -> Path:
    origin = item["origin"]
    d = SKILL / "assets" / "cache" / origin
    d.mkdir(parents=True, exist_ok=True)
    url = item.get("url")
    if origin == "polyhaven":
        files = _get(item["download_api"])
        if kind == "hdri":
            url = files["hdri"]["2k"]["hdr"]["url"]
        else:
            url = next(iter(files.get("gltf", {}).get("2k", {}).get("gltf", {}).get("url", "") for _ in [0]), None)
    ext = Path(urllib.parse.urlparse(url).path).suffix or {"music": ".mp3", "sfx": ".mp3", "image": ".jpg",
                                                            "video": ".mp4", "icon": ".svg"}.get(kind, ".bin")
    if item.get("filetype") and len(item["filetype"]) <= 5:
        ext = "." + item["filetype"].replace("mp32", "mp3")
    dst = d / f"{str(item['source_id']).replace(':', '_').replace('/', '_')}{ext}"
    if not dst.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
            f.write(r.read())
    return dst


def add_to_catalog(item: dict, kind: str, path: Path) -> dict:
    cat_path = SKILL / "assets" / "catalog.json"
    cat = read_json(cat_path) if cat_path.exists() else {"version": 1, "assets": []}
    aid = f"cat:{item['origin']}:{item['source_id']}"
    entry = {"id": aid, "kind": kind, "path": path.relative_to(SKILL).as_posix(), "title": item.get("title"),
             "creator": item.get("creator"), "source": item["origin"] + (f" / {item['provider']}" if item.get("provider") else ""),
             "license": f"{item.get('license')} {item.get('license_version') or ''}".strip(), "license_url": item.get("license_url"),
             "url": item.get("page"), "commercial": True, "attribution": item.get("attribution"),
             "courtesy": item.get("courtesy"), "license_checked": LICENSE_CHECKED.get(item["origin"], str(_dt.date.today())),
             "tags": [w for w in str(item.get("title") or "").lower().split() if len(w) > 2],
             "duration_s": item.get("duration_s"), "tier": 4,
             "restrictions": ["Content ID claims possible on CC music; keep this entry as proof"] if kind == "music" else []}
    cat["assets"] = [e for e in cat["assets"] if e["id"] != aid] + [entry]
    write_json(cat_path, cat)
    return entry


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--kind", required=True, choices=["music", "sfx", "image", "video", "icon", "hdri", "model", "texture"])
    s.add_argument("--query", required=True); s.add_argument("--limit", type=int, default=10)
    s.add_argument("--commercial", action="store_true", help="exclude NC, SA and Freesound results")
    s.add_argument("--min-s", type=float, help="minimum duration in seconds (music, video)")
    s.add_argument("--icon-set", help="Iconify prefix, keeps one icon family per video")
    s.add_argument("--out", required=True)
    g = sub.add_parser("get")
    g.add_argument("--from", dest="src", required=True); g.add_argument("--pick", type=int, required=True)
    g.add_argument("--project", help="add a ledger line to PROJECT/licenses.json")
    a = ap.parse_args()
    try:
        if a.cmd == "search":
            res = search(a.kind, a.query, a.limit, a.commercial, a.min_s, a.icon_set)
            write_json(a.out, res)
            log(f"{len(res['results'])} usable result(s) from {', '.join(res['searched'])}; wrote {a.out}")
            for k, r in enumerate(res["results"]):
                log(f"  [{k}] {r.get('title')!s:.50} | {r.get('license')} {r.get('license_version') or ''} | "
                    f"{r.get('duration_s') or ''} | {r.get('origin')}")
            if not res["results"]:
                log("  nothing passed the license and quality filters: leave the slot empty or try other words"
                    + ("; for music beds use scripts/fetch_music.py (Mixkit)" if a.kind == "music" else ""))
        else:
            res = read_json(a.src)
            if not (0 <= a.pick < len(res["results"])):
                fail(f"--pick must be 0..{len(res['results']) - 1}")
            item = res["results"][a.pick]
            if item.get("origin") == "local":
                print(json.dumps({"id": item["id"], "path": item["path"]}))
                return
            path = download(item, res["kind"])
            entry = add_to_catalog(item, res["kind"], path)
            if a.project:
                lp = Path(a.project) / "licenses.json"
                led = read_json(lp) if lp.exists() else {"assets": []}
                led["assets"] = [e for e in led["assets"] if e["id"] != entry["id"]] + [
                    {k: entry[k] for k in ("id", "source", "license", "url", "commercial", "attribution", "license_checked",
                                           "restrictions")}]
                write_json(lp, led)
            print(json.dumps({"id": entry["id"], "path": entry["path"], "attribution": entry["attribution"]}))
    except (urllib.error.URLError, TimeoutError) as e:
        fail(f"network error: {e}; local library results are still available")
    except (KeyError, ValueError, FileNotFoundError) as e:
        fail(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
