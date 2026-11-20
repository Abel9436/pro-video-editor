"""Pull CC0 sound effects without an API key, verifying the licence on each sound's own page.

Usage:
  python scripts/fetch_sfx.py --project P --query "cinematic whoosh" [--role whoosh] [--n 3] [--max-dur 4]
  python scripts/fetch_sfx.py --project P --plan plan.json     ({"role": "query", ...})
  python scripts/fetch_sfx.py --project P --source ves --query "riser"   (VideoEditingSFX)

Sources (both CC0, both checked per sound on the day of download):
  freesound (default)  Freesound search filtered to CC0. With an API key (env FREESOUND_API_KEY, or the file
                       ~/.pve/freesound_key; never put it in the repo) it uses the APIv2 text search sorted by
                       rating with a duration filter and reads the licence from each sound's API record;
                       without one it scrapes the search page and reads the licence from the sound page.
                       --min-dur/--max-dur make it a music search too (e.g. --min-dur 40 --max-dur 240).
  ves                  videoeditingsfx.com, ~100 sounds made for edits (whooshes, risers, impacts,
                       reverse hits, camera shutters, UI pops). Each page carries schema.org
                       metadata with "license": "https://creativecommons.org/publicdomain/zero/1.0/";
                       a sound without it is skipped. The query is matched against the sound's slug.

Each kept sound is saved to P/sfx/<role>_<id>.mp3 (Freesound HQ preview, 128 kbps) and listed in
P/sfx/catalog.json with id, author, name, URL, duration and the licence string read from the
sound's own page on the day it was fetched. Sounds whose page does not say "Creative Commons 0"
are skipped, even if the search filter returned them. Writes a JSON summary to stdout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) pro-video-editor"}
SEARCH = "https://freesound.org/search/?q={q}&f=license%3A%22Creative+Commons+0%22&s=Downloads+%28most+first%29"


def get(url: str) -> bytes:
    # curl uses the OS certificate store; some Python installs ship an expired one.
    import shutil
    import subprocess
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-sfL", "--max-time", "60", "-A", UA["User-Agent"], url], capture_output=True)
        if r.returncode != 0:
            raise OSError(f"curl exit {r.returncode} for {url}")
        return r.stdout
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def search(q: str) -> list[dict]:
    page = get(SEARCH.format(q=urllib.parse.quote_plus(q))).decode("utf-8", "replace")
    out, seen = [], set()
    for m in re.finditer(r'href="/people/([^/"]+)/sounds/(\d+)/"', page):
        user, sid = m.group(1), m.group(2)
        if sid in seen:
            continue
        seen.add(sid)
        out.append({"id": int(sid), "user": user, "page": f"https://freesound.org/people/{user}/sounds/{sid}/"})
    return out


def api_key() -> str | None:
    k = os.environ.get("FREESOUND_API_KEY")
    f = Path.home() / ".pve" / "freesound_key"
    return (k or (f.read_text(encoding="utf-8").strip() if f.exists() else "")) or None


API = "https://freesound.org/apiv2/search/text/"


def api_search(q: str, key: str, min_dur: float, max_dur: float, n: int) -> list[dict]:
    """APIv2 search (CC0 only, rated first); each hit carries its licence and preview URL, so no page scrape."""
    flt = f'license:"Creative Commons 0" duration:[{min_dur} TO {max_dur}]'
    url = API + "?" + urllib.parse.urlencode({"query": q, "filter": flt, "sort": "rating_desc", "page_size": max(n * 3, 10),
                                              "fields": "id,name,username,license,url,previews,duration,avg_rating,num_ratings", "token": key})
    d = json.loads(get(url).decode("utf-8"))
    if "results" not in d:
        raise OSError(d.get("detail", "Freesound API error"))
    hits = sorted(d["results"], key=lambda r: (-(r.get("num_ratings", 0) >= 3), -r.get("avg_rating", 0), -r.get("num_ratings", 0)))
    return [{"id": r["id"], "user": r["username"], "page": r["url"], "name": r["name"], "url": r["previews"]["preview-hq-mp3"],
             "duration_s": round(r["duration"], 3), "license_url": r["license"], "rating": r.get("avg_rating")}
            for r in hits if "publicdomain/zero" in r["license"]]


def details(s: dict) -> dict | None:
    page = get(s["page"]).decode("utf-8", "replace")
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    if "Creative Commons 0" not in text and "publicdomain/zero" not in page:
        return None
    mp3 = re.search(r'https://cdn\.freesound\.org/previews/\d+/\d+_\d+-hq\.mp3', page) or \
        re.search(r'https://cdn\.freesound\.org/previews/\d+/\d+_\d+-lq\.mp3', page)
    if not mp3:
        return None
    title = re.search(r"<title>(.*?)</title>", page, re.S)
    dur = re.search(r'data-duration="([\d.]+)"', page) or re.search(r'Duration</dt>\s*<dd[^>]*>\s*([\d:.]+)', page)
    d = None
    if dur:
        v = dur.group(1)
        d = float(v) if ":" not in v else sum(float(x) * 60 ** i for i, x in enumerate(reversed(v.split(":"))))
    return {**s, "name": html.unescape(title.group(1)).split(" by ")[0].replace("Freesound - ", "").strip() if title else "",
            "url": mp3.group(0).replace("-lq.mp3", "-hq.mp3"), "duration_s": d}


VES_INDEX = "https://videoeditingsfx.com/sfx/"


def ves_search(q: str) -> list[dict]:
    page = get(VES_INDEX).decode("utf-8", "replace")
    slugs = sorted({m.group(1) for m in re.finditer(r'href="/sfx/([a-z0-9-]+)"', page)})
    toks = [t for t in re.split(r"\W+", q.lower()) if t]
    scored = [(sum(any(w in (t, t + "s", t + "es") for w in sl.split("-")) for t in toks), sl) for sl in slugs]
    return [{"id": f"ves-{sl}", "user": "VideoEditingSFX", "page": f"https://videoeditingsfx.com/sfx/{sl}"} for n, sl in sorted(scored, key=lambda x: -x[0]) if n > 0]


def ves_details(s: dict) -> dict | None:
    page = get(s["page"]).decode("utf-8", "replace")
    if '"license": "https://creativecommons.org/publicdomain/zero/1.0/"' not in page and "publicdomain/zero/1.0" not in page:
        return None
    mp3 = re.search(r'"contentUrl":\s*"([^"]+\.mp3)"', page) or re.search(r'src="(/sounds/[^"]+\.mp3)"', page)
    if not mp3:
        return None
    url = mp3.group(1)
    if url.startswith("/"):
        url = "https://videoeditingsfx.com" + url
    title = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    return {**s, "name": html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else s["id"], "url": url, "duration_s": None}


def probe_dur(f: Path) -> float | None:
    import subprocess
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True, timeout=30)
        return round(float(r.stdout.strip()), 3)
    except Exception:  # noqa: BLE001
        return None


def measure(f: Path) -> dict:
    """Peak and onset of a sound (s from file start), so the SFX can be placed peak-on-cut:
    start = cut_frame - round(peak_s * fps). Onset = first 10 ms window within 30 dB of the peak."""
    import subprocess
    try:
        import numpy as np
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, timeout=60)
        x = np.frombuffer(r.stdout, np.float32)
        if x.size < 320:
            return {}
        w = 160
        rms = np.sqrt((x[: x.size // w * w].reshape(-1, w) ** 2).mean(1)) + 1e-9
        db = 20 * np.log10(rms)
        pk = int(db.argmax())
        on = int(np.argmax(db > db[pk] - 30))
        return {"peak_s": round(pk * w / 16000, 3), "onset_s": round(on * w / 16000, 3), "peak_dbfs": round(float(db[pk]), 1)}
    except Exception:  # noqa: BLE001
        return {}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--query"); ap.add_argument("--role")
    ap.add_argument("--plan", help='JSON file {"role": "query", ...}')
    ap.add_argument("--n", type=int, default=3, help="sounds kept per query")
    ap.add_argument("--max-dur", type=float, default=6.0, help="skip sounds longer than this (s)")
    ap.add_argument("--min-dur", type=float, default=0.0, help="skip sounds shorter than this (s); with --max-dur 240 finds music")
    ap.add_argument("--source", choices=["freesound", "ves"], default="freesound")
    ap.add_argument("--measure-only", action="store_true", help="add peak_s/onset_s to every catalogue entry that lacks them, then exit")
    a = ap.parse_args()
    if a.measure_only:
        cp = Path(a.project) / "sfx" / "catalog.json"
        cat = json.loads(cp.read_text(encoding="utf-8"))
        n = 0
        for e in cat["sounds"]:
            if "peak_s" not in e and (Path(a.project) / e["file"]).exists():
                e.update(measure(Path(a.project) / e["file"])); n += 1
        cp.write_text(json.dumps(cat, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "measured": n})); return
    if not a.plan and not a.query:
        print(json.dumps({"ok": False, "error": "give --query or --plan"})); sys.exit(2)
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8")) if a.plan else {a.role or re.sub(r"\W+", "_", a.query): a.query}
    out_dir = Path(a.project) / "sfx"
    out_dir.mkdir(parents=True, exist_ok=True)
    cat_path = out_dir / "catalog.json"
    cat = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else {"sounds": []}
    have = {s["id"] for s in cat["sounds"]}
    today = dt.date.today().isoformat()
    summary = {}
    for role, q in plan.items():
        kept = []
        try:
            key = api_key() if a.source == "freesound" else None
            hits = ves_search(q) if a.source == "ves" else (api_search(q, key, a.min_dur, a.max_dur, a.n) if key else search(q))
        except Exception as e:  # noqa: BLE001 - network errors of many kinds; report and continue
            summary[role] = {"error": f"search failed: {e}"}; continue
        for s in hits:
            if len(kept) >= a.n:
                break
            try:
                d = s if "license_url" in s else (ves_details(s) if a.source == "ves" else details(s))
                time.sleep(0.4)
            except Exception:  # noqa: BLE001
                continue
            if not d or (d["duration_s"] and not a.min_dur <= d["duration_s"] <= a.max_dur):
                continue
            f = out_dir / f"{role}_{d['id']}.mp3"
            if not f.exists():
                try:
                    f.write_bytes(get(d["url"]))
                except OSError:
                    continue
            if d["duration_s"] is None:
                d["duration_s"] = probe_dur(f)
                if d["duration_s"] and d["duration_s"] > a.max_dur:
                    f.unlink(); continue
            entry = {**measure(f), "id": d["id"], "role": role, "query": q, "file": f"sfx/{f.name}", "name": d["name"], "author": d["user"],
                     "source": d["page"], "license": "CC0 1.0 (Creative Commons 0)", "license_checked": today,
                     "license_source": "Freesound API record" if "license_url" in d else "sound page",
                     "duration_s": d["duration_s"], "commercial": True, "attribution": None}
            if d["id"] not in have:
                cat["sounds"].append(entry); have.add(d["id"])
            kept.append(entry["file"])
            cat_path.write_text(json.dumps(cat, indent=2), encoding="utf-8")
        summary[role] = {"query": q, "kept": kept}
    cat_path.write_text(json.dumps(cat, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "catalog": cat_path.as_posix(), "roles": summary}, indent=1))


if __name__ == "__main__":
    main()
