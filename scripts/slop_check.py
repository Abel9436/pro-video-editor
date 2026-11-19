"""slop_check.py - audit an EDL for the tells that make an edit look machine-made.

Runs on the EDL alone (no render needed): SFX and effect density, emphasis count, karaoke captions,
decorations that never leave, too many graphics at once, a camera that never holds still, punch-ins
on every shot, a before/after reveal spent more than once, and (fresh_grammar) an edit that reuses
most of a recent project's devices, title font and caption style. Every finding is a warning with a fix.
Limits and their sources: lib/restraint.py and references/craft-human.md.

Usage:
  python scripts/slop_check.py --edl project/edl/v3.json [--project NAME]
NAME defaults to the folder above project/ (the name render.py logs it under).
Prints JSON {"ok": true, "summary": {...}, "items": [...]}; exit 0 even with warnings, 1 on error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.restraint import audit, summary  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", required=True, help="EDL JSON file to audit")
    ap.add_argument("--project", help="project name in the design log (default: the folder above project/)")
    a = ap.parse_args()
    try:
        edl = json.loads(Path(a.edl).read_text(encoding="utf-8"))
        items = audit(edl)
        if edl.get("design"):
            from lib import grammar
            ep = Path(a.edl).resolve()
            name = a.project or (ep.parents[2].name if ep.parents[1].name == "project" else ep.parents[1].name)
            items.append({"id": "fresh_grammar", **grammar.compare(edl, name)})
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)
    print(json.dumps({"ok": True, "summary": summary(items), "items": items}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
