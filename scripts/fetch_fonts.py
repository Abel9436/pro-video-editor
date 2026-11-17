#!/usr/bin/env python3
"""Fetch Google Fonts families into a project as .woff2 files, licence read first.

Usage:
  python scripts/fetch_fonts.py --project P "Caveat:700" "Instrument Serif:italic400" "Anton:400" "Amiri:400"

For each family the licence text is read from the google/fonts repository (ofl/<name>/OFL.txt,
then apache/ and ufl/); a family whose licence cannot be read is skipped. The woff2 files come
from the Google Fonts CSS2 API (all unicode ranges, so non-Latin scripts work). Writes
P/fonts/<slug>-<style><weight>-<n>.woff2, P/fonts/fonts.css (@font-face rules with relative
URLs), the licence texts, and one licenses.json entry per family. JSON summary on stdout.

Spec: "Family:STYLE" where STYLE is 400 / 700 / italic400 ... (default 400).
HyperFrames bundles only a few Latin families; anything else needs @font-face to a local file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
LIC_DIRS = [("ofl", "OFL.txt", "SIL Open Font License 1.1"), ("apache", "LICENSE.txt", "Apache-2.0"), ("ufl", "UFL.txt", "Ubuntu Font Licence 1.0")]


def get(url: str, binary: bool = False):
    r = subprocess.run(["curl", "-sfL", "--max-time", "60", "-A", UA, url], capture_output=True)
    if r.returncode != 0:
        raise OSError(f"curl exit {r.returncode} for {url}")
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def parse_spec(s: str) -> tuple[str, bool, int]:
    fam, _, st = s.partition(":")
    st = st or "400"
    ital = st.startswith("italic")
    w = int(st.replace("italic", "") or 400)
    return fam.strip(), ital, w


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, type=Path)
    ap.add_argument("specs", nargs="+")
    a = ap.parse_args()
    d = a.project / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    css_path = d / "fonts.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    res = {"ok": True, "saved": [], "failed": [], "css": str(css_path)}
    lp = a.project / "licenses.json"
    led = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else {"assets": []}
    for spec in a.specs:
        fam, ital, w = parse_spec(spec)
        slug = re.sub(r"[^a-z0-9]", "", fam.lower())
        tag = f"{'italic' if ital else 'normal'}{w}"
        try:
            lic_name = lic_text = None
            for sub, fn, name in LIC_DIRS:
                try:
                    lic_text = get(f"https://raw.githubusercontent.com/google/fonts/main/{sub}/{slug}/{fn}")
                    lic_name = name
                    break
                except OSError:
                    continue
            if not lic_text:
                raise ValueError("licence not readable in google/fonts; skipped")
            (d / f"LICENSE.{slug}.txt").write_text(lic_text, encoding="utf-8")
            q = fam.replace(" ", "+") + (f":ital,wght@1,{w}" if ital else f":wght@{w}")
            sheet = get(f"https://fonts.googleapis.com/css2?family={q}&display=block")
            faces = re.findall(r"@font-face\s*\{([^}]*)\}", sheet)
            if not faces:
                raise ValueError("no @font-face returned")
            if f"/* {fam} {tag} */" in css:
                res["saved"].append({"family": fam, "style": tag, "files": "cached"})
                continue
            css += f"/* {fam} {tag} */\n"
            files = []
            for i, body in enumerate(faces):
                url = re.search(r"url\((https://[^)]+\.woff2)\)", body)
                if not url:
                    continue
                fn = f"{slug}-{tag}-{i}.woff2"
                (d / fn).write_bytes(get(url.group(1), binary=True))
                files.append(fn)
                rng = re.search(r"unicode-range:\s*([^;]+);", body)
                css += (f"@font-face {{ font-family: '{fam}'; font-style: {'italic' if ital else 'normal'}; font-weight: {w}; font-display: block; "
                        f"src: url('{fn}') format('woff2');{f' unicode-range: {rng.group(1)};' if rng else ''} }}\n")
            res["saved"].append({"family": fam, "style": tag, "files": len(files), "license": lic_name})
            if not any(x.get("id") == f"font:{slug}" for x in led["assets"]):
                led["assets"].append({"id": f"font:{slug}", "what": f"{fam} (font)", "source": "https://fonts.google.com/specimen/" + fam.replace(" ", "+"),
                                      "license": f"{lic_name} (text in fonts/LICENSE.{slug}.txt)", "commercial": True, "attribution": None,
                                      "license_checked": dt.date.today().isoformat()})
        except (OSError, ValueError) as e:
            res["failed"].append({"family": fam, "error": str(e)})
    css_path.write_text(css, encoding="utf-8")
    lp.write_text(json.dumps(led, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=1))
    if not res["saved"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
