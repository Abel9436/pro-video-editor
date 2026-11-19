"""Design grammar memory across projects (2026-11-19).

The owner's rule: every new footage gets its own design, read from its story; an edit that reuses the
last edit's devices (the same 3D stage, the same card fold, the same caption style and title font)
reads as a template, which is the beginner tell. render.py records each delivered edit's grammar;
slop_check.py compares a new EDL against the last few other projects and warns when most of it is
reused.

Log: $PVE_DESIGN_LOG, default ~/.pve/design_log.jsonl (one JSON line per project, latest wins). It is
user data and never lives in the skill repo.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

REUSE_WARN = 0.5      # STARTING DEFAULT: share of this edit's devices already used by one recent project
RECENT = 3            # STARTING DEFAULT: how many other recent projects to compare against


def log_path() -> Path:
    return Path(os.environ.get("PVE_DESIGN_LOG") or Path.home() / ".pve" / "design_log.jsonl")


def _family(font: str | None) -> str:
    return (font or "").split(",")[0].strip().strip("'\"").lower()


def signature(edl: dict) -> list[str]:
    """The devices an edit is built from: graphic types, transitions, caption style, title font, card moves."""
    d = edl.get("design") or {}
    toks = {f"scene:{s['type']}" for s in d.get("scenes") or []}
    toks |= {f"overlay:{o['type']}" for o in d.get("overlays") or []}
    toks |= {f"fx:{x['type']}" for x in d.get("fx") or []}
    toks.add(f"caption:{d.get('caption_style', 'phrase')}")
    brand = d.get("brand") or {}
    if brand.get("font_title"):
        toks.add(f"font:{_family(brand['font_title'])}")
    if d.get("caption_font"):
        toks.add(f"capfont:{_family(d['caption_font'])}")
    if any(m.get("card") for m in d.get("camera") or []):
        toks.add("camera:card")
    return sorted(toks)


def _read() -> list[dict]:
    p = log_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def record(edl: dict, project: str) -> Path:
    """Replace this project's line with its current grammar (the latest render wins)."""
    rows = [r for r in _read() if r.get("project") != project]
    rows.append({"project": project, "t": int(time.time()), "tokens": signature(edl)})
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return p


def compare(edl: dict, project: str) -> dict:
    """Overlap with the most recent other projects. Returns {status, value, limit, detail, fix}."""
    mine = set(signature(edl))
    others = sorted((r for r in _read() if r.get("project") != project), key=lambda r: r.get("t", 0))[-RECENT:]
    worst, who, shared = 0.0, None, set()
    for r in others:
        s = mine & set(r.get("tokens") or [])
        share = len(s) / max(1, len(mine))
        if share > worst:
            worst, who, shared = share, r["project"], s
    same_voice = who is not None and {t for t in shared if t.startswith(("font:", "caption:"))} >= {t for t in mine if t.startswith(("font:", "caption:"))}
    bad = worst > REUSE_WARN or same_voice
    return {"status": "warn" if bad else "pass", "value": round(worst, 2), "limit": REUSE_WARN,
            "detail": (f"{worst:.0%} of this edit's devices were used by '{who}': {', '.join(sorted(shared))}" if who else
                       "no earlier project in the design log"),
            "fix": ("design from this footage's story: list what the subject is about, pick devices that only "
                    "make sense for it, a new title font and caption style (references/craft-motion-design.md, 'Fresh grammar')") if bad else None}
