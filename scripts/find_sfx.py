"""Search local, commercially cleared sound-effect libraries and copy picks into a project.

Usage:
  python scripts/find_sfx.py index  --lib DIR
  python scripts/find_sfx.py search --lib DIR "metal clang landing" [--n 10] [--category impacts]
  python scripts/find_sfx.py get    --lib DIR --project P sfx-kit:cinematic-metal-big sfx-kit:tone-ding-mid ...

DIR holds clones of the libraries (outside this repo; nothing here is redistributed):
  sfx-kit/   github.com/wyzowl/sfx-kit        CC0. 320 sounds with descriptions, use_for/avoid_for, and a measured
                                             sync point (where the sound should meet the action). Best for video.
  uisfx/     github.com/romainsimon/uisfx     audio CC0 (LICENSE-AUDIO), code MIT. UI sounds.
  soundcn/   github.com/kapishdima/soundcn    code MIT; sounds are Kenney CC0 packs in assets/kenney_*. The
                                             assets/wow pack (110 World of Warcraft sounds, (c) Blizzard, not
                                             free) is EXCLUDED and never indexed.
  ZzFX is a JavaScript generator with no sound files; it is not indexed.

index   writes DIR/INDEX.json (one row per cleared sound).
search  ranks rows by word overlap with the query over name, category, description, use_for and tags;
        prints JSON rows with id, file, duration_s, sync_s and what the sync point meets.
get     copies each id to P/sfx/<lib>_<name>.<ext>, appends P/sfx/catalog.json and P/licenses.json, and
        prints the EDL snippet: {"asset": "file:sfx/...", "sync_s": ...}. With sync_s in an sfx event the
        mixer lands that point of the file on at_f (render.py), instead of guessing from the waveform.
Nothing is sent over the network. Every command prints JSON and exits 1 with {"ok": false, "error"} on failure.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

AUDIO = (".wav", ".mp3", ".ogg", ".flac")


def _fail(msg: str) -> None:
    print(json.dumps({"ok": False, "error": msg}, indent=1))
    sys.exit(1)


def build_index(lib: Path) -> list[dict]:
    rows = []
    kit = lib / "sfx-kit" / "sounds.json"
    if kit.exists():
        d = json.loads(kit.read_text(encoding="utf-8"))
        for s in d["sounds"]:
            sync = s.get("sync") or {}
            rows.append({"id": f"sfx-kit:{s['id']}", "lib": "sfx-kit", "file": f"sfx-kit/{s['file']}", "name": s["name"],
                         "category": s.get("category", ""), "desc": s.get("description", ""),
                         "use_for": s.get("use_for", []), "avoid_for": s.get("avoid_for", []), "tags": s.get("tags", []),
                         "duration_s": s.get("duration"), "sync_s": sync.get("at"), "meets": sync.get("meets"),
                         "license": "CC0-1.0", "source": "https://github.com/wyzowl/sfx-kit", "author": "Wyzowl SFX Kit"})
    ui = lib / "uisfx" / "packages" / "uisfx" / "sounds"
    if ui.exists():
        for f in sorted(ui.rglob("*")):
            if f.suffix.lower() == ".mp3":        # each cue ships as mp3 and ogg; one is enough
                rows.append({"id": f"uisfx:{f.parent.name}/{f.stem}", "lib": "uisfx", "file": f.relative_to(lib).as_posix(),
                             "name": f.stem.replace("-", " "), "category": f.parent.name, "desc": "", "use_for": [], "avoid_for": [],
                             "tags": [f.parent.name], "duration_s": None, "sync_s": None, "meets": None,
                             "license": "CC0-1.0", "source": "https://github.com/romainsimon/uisfx", "author": "UI SFX (Yuki Capital)"})
    sc = lib / "soundcn" / "assets"
    if sc.exists():
        for f in sorted(sc.rglob("*")):
            if f.suffix.lower() not in AUDIO:
                continue
            pack = f.relative_to(sc).parts[0]
            if not pack.startswith("kenney_"):     # the 'wow' pack is (c) Blizzard: never index it
                continue
            rows.append({"id": f"soundcn:{pack}/{f.stem}", "lib": "soundcn", "file": f.relative_to(lib).as_posix(),
                         "name": re.sub(r"[_-]+", " ", f.stem), "category": pack[7:], "desc": "", "use_for": [], "avoid_for": [],
                         "tags": [pack[7:]], "duration_s": None, "sync_s": None, "meets": None,
                         "license": "CC0-1.0", "source": "https://kenney.nl (via github.com/kapishdima/soundcn)", "author": "Kenney"})
    return rows


def _load(lib: Path) -> list[dict]:
    p = lib / "INDEX.json"
    if not p.exists() or "sync_s" not in p.read_text(encoding="utf-8")[:4000]:
        rows = build_index(lib)
        p.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
        return rows
    return json.loads(p.read_text(encoding="utf-8"))


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 1}


def search(rows: list[dict], query: str, n: int = 10, category: str | None = None) -> list[dict]:
    q = _words(query)
    out = []
    for r in rows:
        if category and category.lower() not in r["category"].lower():
            continue
        name, meta = _words(r["name"] + " " + r["category"]), _words(" ".join([r["desc"], *r["use_for"], *r["tags"]]))
        avoid = _words(" ".join(r["avoid_for"]))
        score = 3 * len(q & name) + len(q & meta) - 0.5 * len(q & avoid) + (0.5 if r["lib"] == "sfx-kit" else 0)
        if score > 0.5:
            out.append((score, r))
    out.sort(key=lambda t: (-t[0], t[1]["id"]))
    return [{"score": round(s, 1), **{k: r[k] for k in ("id", "name", "category", "desc", "duration_s", "sync_s", "meets", "file")}}
            for s, r in out[:n]]


def get(lib: Path, rows: list[dict], project: Path, ids: list[str]) -> dict:
    by = {r["id"]: r for r in rows}
    missing = [i for i in ids if i not in by]
    if missing:
        _fail(f"unknown id(s): {missing}; run search first")
    (project / "sfx").mkdir(parents=True, exist_ok=True)
    cat_p, lic_p = project / "sfx" / "catalog.json", project / "licenses.json"
    cat = json.loads(cat_p.read_text(encoding="utf-8")) if cat_p.exists() else {"sounds": []}
    lic = json.loads(lic_p.read_text(encoding="utf-8")) if lic_p.exists() else {"assets": []}
    saved = []
    for i in ids:
        r = by[i]
        src = lib / r["file"]
        if not src.exists():
            _fail(f"{src} is missing; re-clone the library or rerun index")
        name = f"{r['lib']}_{re.sub(r'[^a-z0-9]+', '-', i.split(':', 1)[1].lower()).strip('-')}{src.suffix.lower()}"
        dst = project / "sfx" / name
        shutil.copy2(src, dst)
        rel = f"sfx/{name}"
        cat["sounds"] = [c for c in cat.get("sounds", []) if c.get("file") != rel] + [{
            "id": i, "role": r["category"], "file": rel, "name": r["name"], "description": r["desc"], "sync_s": r["sync_s"],
            "meets": r["meets"], "duration_s": r["duration_s"], "author": r["author"], "source": r["source"],
            "license": r["license"], "commercial": True, "attribution": None}]
        aid = f"file:{rel}"
        lic["assets"] = [a for a in lic.get("assets", []) if a.get("id") != aid] + [{
            "id": aid, "source": f"{r['name']} ({r['author']}, {r['file']})", "url": r["source"], "license": r["license"],
            "commercial": True, "attribution": None, "used_as": "sfx"}]
        saved.append({"id": i, "asset": aid, "sync_s": r["sync_s"], "meets": r["meets"]})
    cat_p.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    lic_p.write_text(json.dumps(lic, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "saved": saved,
            "edl": [{"asset": s["asset"], **({"sync_s": s["sync_s"]} if s["sync_s"] is not None else {"align": "peak"})} for s in saved]}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("index", "search", "get"):
        sp = sub.add_parser(c)
        sp.add_argument("--lib", required=True, type=Path, help="folder holding the cloned libraries")
        if c == "search":
            sp.add_argument("query")
            sp.add_argument("--n", type=int, default=10)
            sp.add_argument("--category")
        if c == "get":
            sp.add_argument("--project", required=True, type=Path)
            sp.add_argument("ids", nargs="+")
    a = ap.parse_args(argv)
    if not a.lib.is_dir():
        _fail(f"--lib {a.lib} is not a folder")
    if a.cmd == "index":
        rows = build_index(a.lib)
        if not rows:
            _fail("no supported library found in --lib (expected sfx-kit/, uisfx/ or soundcn/)")
        (a.lib / "INDEX.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
        libs: dict[str, int] = {}
        for r in rows:
            libs[r["lib"]] = libs.get(r["lib"], 0) + 1
        print(json.dumps({"ok": True, "indexed": len(rows), "by_library": libs, "excluded": "soundcn assets/wow ((c) Blizzard)"}, indent=1))
    elif a.cmd == "search":
        print(json.dumps({"ok": True, "query": a.query, "results": search(_load(a.lib), a.query, a.n, a.category)}, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(get(a.lib, _load(a.lib), a.project, a.ids), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
