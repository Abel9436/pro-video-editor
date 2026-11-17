#!/usr/bin/env python3
"""Fetch Amharic (Ge'ez) fonts from font.et into a project, SIL OFL fonts only.

Usage:
  python scripts/fetch_fontet.py list [--query bold]
  python scripts/fetch_fontet.py get --project P Menbere Zemach "Bela Bereka"

font.et renders its pages with JavaScript; the catalogue behind them is the static file
https://font.et/data/fonts.json (name, designers, licence, styles, file URLs). `list` prints the
fonts whose licence there is "SIL Open Font License". `get` refuses any other licence, downloads
the font files into P/fonts/, appends @font-face rules to P/fonts/fonts.css (the design pass
inlines that file), writes P/fonts/LICENSE.<slug>.txt and adds one entry per font to
P/licenses.json. Nothing about the user or project is sent; only the catalogue and font URLs.

Good display/caption choices tried on real edits (2026-11-17): Menbere (variable 100-700, captions),
Zemach (titles), Bela Bereka (blocky, emphasis words), Difres (variable 300-700).

Prints JSON; exits 1 when nothing could be fetched.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://font.et"
OFL = "SIL Open Font License"
UA = {"User-Agent": "pro-video-editor-skill/1.0"}
WEIGHT_WORDS = [("thin", 100), ("extralight", 200), ("light", 300), ("medium", 500), ("semibold", 600),
                ("extrabold", 800), ("black", 900), ("heavy", 900), ("bold", 700), ("regular", 400)]


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
        return r.read()


def catalogue() -> list[dict]:
    return json.loads(fetch(f"{BASE}/data/fonts.json").decode("utf-8"))["data"]


def is_ofl(f: dict) -> bool:
    return any((x.get("name") or "").strip() == OFL for x in f.get("licenses") or [])


def find(cat: list[dict], name: str) -> dict | None:
    k = name.strip().lower()
    return next((f for f in cat if k in ((f.get("name") or "").lower(), (f.get("slug") or "").lower())), None)


def files_of(f: dict) -> list[str]:
    urls = [(f.get("file") or {}).get("url")] + [s.get("url") for s in f.get("staticFiles") or [] if isinstance(s, dict)]
    out = []
    for u in urls:
        if u and u not in out:
            out.append(u)
    return out


def is_font(b: bytes) -> bool:
    return b[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"wOFF", b"wOF2")


def weight_of(filename: str, variable_range: tuple[int, int] | None) -> str:
    if variable_range:
        return f"{variable_range[0]} {variable_range[1]}"
    n = re.sub(r"[^a-z]", "", filename.lower())
    return str(next((w for word, w in WEIGHT_WORDS if word in n), 400))


def variable_range(path: Path) -> tuple[int, int] | None:
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(str(path), lazy=True)
        if "fvar" in f:
            ax = next((a for a in f["fvar"].axes if a.axisTag == "wght"), None)
            return (int(ax.minValue), int(ax.maxValue)) if ax else None
    except Exception:  # noqa: BLE001  fontTools missing or file unreadable: treat as static
        return None
    return None


def face_css(family: str, rel: str, weight: str, italic: bool) -> str:
    fmt = "opentype" if rel.lower().endswith(".otf") else "truetype"
    return (f"@font-face {{ font-family: '{family}'; font-style: {'italic' if italic else 'normal'}; font-weight: {weight}; "
            f"font-display: block; src: url('{rel}') format('{fmt}'); }}")


def get_fonts(project: Path, names: list[str], cat: list[dict]) -> dict:
    fd = project / "fonts"
    fd.mkdir(parents=True, exist_ok=True)
    css_p = fd / "fonts.css"
    css = css_p.read_text(encoding="utf-8") if css_p.exists() else ""
    res = {"ok": True, "saved": [], "failed": []}
    led_p = project / "licenses.json"
    led = json.loads(led_p.read_text(encoding="utf-8")) if led_p.exists() else {"assets": []}
    for name in names:
        f = find(cat, name)
        if not f:
            res["failed"].append({"name": name, "error": "not in the font.et catalogue (try `list`)"})
            continue
        if not is_ofl(f):
            lic = ", ".join(x.get("name", "?") for x in f.get("licenses") or []) or "no licence listed"
            res["failed"].append({"name": f["name"], "error": f"licence is '{lic}', not SIL OFL: not downloaded"})
            continue
        slug, family = f.get("slug") or re.sub(r"\W+", "-", f["name"].lower()), f["name"]
        faces = []
        urls = files_of(f)
        for i, u in enumerate(urls):
            try:
                b = fetch(BASE + u if u.startswith("/") else u)
                if not is_font(b):
                    raise ValueError("download is not a font file")
                ext = Path(u).suffix.lower() or ".ttf"
                rel = f"fontet-{slug}-{i}{ext}"
                (fd / rel).write_bytes(b)
                vr = variable_range(fd / rel) if f.get("isVariableFont") or "variable" in u.lower() else None
                # a family shipped as one static file covers every weight, so the browser never fakes a bold
                w = weight_of(Path(u).stem, vr) if vr or len(urls) > 1 else "100 900"
                faces.append(face_css(family, rel, w, "italic" in u.lower()))
                res["saved"].append(f"fonts/{rel}")
            except (OSError, ValueError) as e:
                res["failed"].append({"name": family, "file": u, "error": str(e)})
        if not faces:
            continue
        marker = f"/* font.et: {family} */"
        if marker not in css:
            css += f"\n{marker}\n" + "\n".join(faces) + "\n"
        who = ", ".join(d["name"] for d in f.get("designers") or []) or "designer not listed"
        pub = ", ".join(p["name"] for p in f.get("publishers") or [])
        (fd / f"LICENSE.{slug}.txt").write_text(
            f"{family} by {who}{f' ({pub})' if pub else ''}\nSource: {BASE} (catalogue licence: {OFL})\n"
            f"License: SIL Open Font License 1.1 - https://openfontlicense.org\nChecked: {dt.date.today().isoformat()}\n", encoding="utf-8")
        lid = f"font:fontet:{slug}"
        led["assets"] = [x for x in led["assets"] if x.get("id") != lid] + [{
            "id": lid, "what": f"font '{family}' by {who} (fonts/fontet-{slug}-*)", "source": f"{BASE}/data/fonts.json",
            "license": "SIL Open Font License 1.1", "commercial": True, "attribution": None,
            "license_checked": dt.date.today().isoformat()}]
    css_p.write_text(css, encoding="utf-8")
    led_p.write_text(json.dumps(led, indent=1, ensure_ascii=False), encoding="utf-8")
    res["ok"] = bool(res["saved"])
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="print the SIL OFL fonts on font.et")
    ls.add_argument("--query", default="")
    g = sub.add_parser("get", help="download fonts into a project")
    g.add_argument("--project", required=True, type=Path)
    g.add_argument("names", nargs="+")
    a = ap.parse_args()
    try:
        cat = catalogue()
    except (OSError, ValueError, KeyError) as e:
        print(json.dumps({"ok": False, "error": f"font.et catalogue not readable: {e}"}))
        return 1
    if a.cmd == "list":
        q = a.query.lower()
        rows = [{"name": f["name"], "slug": f.get("slug"), "weights": sorted({s.get("weight") for s in f.get("styles") or []}),
                 "variable": bool(f.get("isVariableFont"))} for f in cat if is_ofl(f) and q in f["name"].lower()]
        print(json.dumps({"ok": True, "ofl_fonts": rows}, ensure_ascii=False, indent=1))
        return 0
    res = get_fonts(a.project, a.names, cat)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
