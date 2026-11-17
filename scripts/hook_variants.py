#!/usr/bin/env python3
"""Propose 5-10 alternative openings from the selects, score them, optionally export A/B versions.

Usage:
  python scripts/hook_variants.py --paper P/edl/paper_v1.json --project P [--n 8] [--out P/hooks.json]
                                  [--export 2]

A candidate is a complete sentence from the material in the paper edit, 1.5-7 s long. Each
gets: first shot (source, frames), first line, an on-screen text suggestion (the line's key
words, at most 5), a first sound (kit role chosen by hook type) and a score with reasons:
  + contrarian / curiosity / stakes / number / question / direct address words
  + emphasis peaks inside the line, a face on screen, camera or subject motion
  + self-contained (does not open on "and/but/so")
  - too long to land in 2 s, or already the opening
The score ranks; Claude chooses, and the hook must be true to the content (viral-hooks.md).
--export N writes paper edits and preview renders for the top N (hook moved to the front,
removed from where it was), for A/B testing.
"""
from __future__ import annotations

import argparse
import copy
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.common import fail, log, read_json, write_json  # noqa: E402
from lib.edl import words_by_src  # noqa: E402
from lib.speech import STOPWORDS, sentences  # noqa: E402
from lib.timebase import parse_rate  # noqa: E402
from lib.viral import hook_features  # noqa: E402

MIN_S, MAX_S, IDEAL_S = 1.5, 7.0, 3.5
SOUND_FOR = {"contrarian": "kit:hit_low", "stakes": "kit:hit_low", "curiosity": "kit:riser", "question": "kit:riser",
             "number": "kit:pop_soft", "address": "kit:pop_soft"}


def candidates(paper: dict, analysis: dict, fps) -> list[dict]:
    wbs = words_by_src(analysis)
    out = []
    srcs = {b["src"] for b in paper["beats"]}
    for src in srcs:
        words = wbs.get(src, [])
        if not words:
            continue
        rec = analysis["files"][src]
        emph = {e["i"] for e in (rec.get("speech") or {}).get("emphasis", [])}
        shots = rec.get("shots", [])
        lo = min(b["words"][0] for b in paper["beats"] if b["src"] == src)
        hi = max(b["words"][1] for b in paper["beats"] if b["src"] == src)
        for s in sentences(words):
            if s["i_from"] < lo or s["i_to"] > hi:
                continue
            dur = (s["e_f"] - s["s_f"]) / float(fps)
            if not MIN_S <= dur <= MAX_S:
                continue
            f = hook_features(s["text"])
            sc, why = 50.0, []
            for k, pts in (("contrarian", 14), ("curiosity", 10), ("stakes", 10), ("address", 4)):
                if f[k]:
                    sc += pts; why.append(f"{k}: {', '.join(f[k][:3])}")
            if f["number"]:
                sc += 8; why.append("number")
            if f["question"]:
                sc += 8; why.append("question")
            if f["weak_opener"]:
                sc -= 12; why.append("opens on a connective (not self-contained)")
            n_emph = sum(1 for i in range(s["i_from"], s["i_to"] + 1) if i in emph)
            if n_emph:
                sc += min(10, 4 * n_emph); why.append(f"{n_emph} emphasis peak(s)")
            sc -= abs(dur - IDEAL_S) * 3
            sh = next((x for x in shots if x["s_f"] <= s["s_f"] < x["e_f"]), {})
            if (sh.get("faces") or {}).get("count"):
                sc += 4; why.append("face on screen")
            if (sh.get("camera") or {}).get("type", "static") not in ("static", "unknown"):
                sc += 2; why.append("motion in the first frame")
            first_beat = paper["beats"][0]
            if first_beat["src"] == src and first_beat["words"][0] <= s["i_from"] <= first_beat["words"][1]:
                why.append("inside the current opening")
            kws = [w["w"].strip(".,!?").upper() for w in words[s["i_from"]:s["i_to"] + 1]
                   if w["w"].lower().strip(".,!?") not in STOPWORDS and len(w["w"]) > 2][:5]
            kind = next((k for k in ("contrarian", "stakes", "curiosity", "question", "number", "address")
                         if f.get(k)), None)
            out.append({"src": src, "words": [s["i_from"], s["i_to"]], "line": s["text"], "dur_s": round(dur, 2),
                        "first_shot": {"src": src, "in_f": s["s_f"], "camera": (sh.get("camera") or {}).get("type")},
                        "on_screen_text": " ".join(kws), "first_sound": SOUND_FOR.get(kind, "kit:pop_soft"),
                        "type": kind or "statement", "score": round(sc, 1), "why": why})
    out.sort(key=lambda c: -c["score"])
    return out


def variant_paper(paper: dict, cand: dict) -> dict:
    p = copy.deepcopy(paper)
    a, b = cand["words"]
    beats = []
    for bt in p["beats"]:
        if bt["src"] != cand["src"] or bt["words"][1] < a or bt["words"][0] > b:
            beats.append(bt); continue
        if bt["words"][0] < a:
            beats.append({**bt, "words": [bt["words"][0], a - 1]})
        if bt["words"][1] > b:
            beats.append({**bt, "words": [b + 1, bt["words"][1]], "role": bt.get("role", "body"),
                          "reason": bt["reason"] + " (remainder after the hook moved)"})
    for bt in beats:
        if bt.get("role") == "hook":
            bt["role"] = "setup"
    hook = {"src": cand["src"], "words": cand["words"], "role": "hook",
            "reason": f"Hook variant ({cand['type']}): {'; '.join(cand['why'][:3])}"}
    p["beats"] = [hook] + [bt for bt in beats if bt["words"][1] >= bt["words"][0]]
    for g in p.get("graphics", []):
        if g.get("at_f") == 0 and g.get("component") == "Title":
            g["props"] = {**g.get("props", {}), "text": cand["on_screen_text"].title()}
    p["sfx"] = [s for s in p.get("sfx", []) if s.get("at_f") != 0] + [
        {"asset": cand["first_sound"], "at_f": 0, "gain_db": -20, "reason": "first-second sound layer of the hook"}]
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paper", required=True); ap.add_argument("--project", required=True)
    ap.add_argument("--n", type=int, default=8); ap.add_argument("--export", type=int, default=0)
    ap.add_argument("--out")
    a = ap.parse_args()
    project = Path(a.project)
    try:
        paper = read_json(a.paper); analysis = read_json(project / "analysis.json")
        fps = parse_rate(read_json(project / "media.json")["fps"])
    except FileNotFoundError as e:
        fail(str(e))
    cands = candidates(paper, analysis, fps)[: max(5, min(10, a.n))]
    if len(cands) < 5:
        log(f"only {len(cands)} usable opening(s) in this material (sentences of {MIN_S}-{MAX_S} s)")
    out = Path(a.out) if a.out else project / "hooks.json"
    res = {"candidates": cands, "rule": "the hook must be true to the content and its promise must be paid off"}
    if a.export:
        here = Path(__file__).parent
        res["exports"] = []
        for k, c in enumerate(cands[: a.export]):
            vp = variant_paper(paper, c)
            pp = project / "edl" / f"paper_hook{k + 1}.json"
            write_json(pp, vp)
            edl_p = project / "edl" / f"hook{k + 1}.json"
            r = subprocess.run([sys.executable, str(here / "plan_edit.py"), "draft", str(pp), "--project", str(project),
                                "--out", str(edl_p)], capture_output=True, text=True)
            if r.returncode:
                log(f"  variant {k + 1}: plan failed: {r.stderr[-200:]}"); continue
            r = subprocess.run([sys.executable, str(here / "render.py"), "--edl", str(edl_p), "--project", str(project),
                                "--preview"], capture_output=True, text=True)
            res["exports"].append({"variant": k + 1, "line": c["line"], "edl": edl_p.as_posix(),
                                   "video": (project / "exports" / f"hook{k + 1}_preview.mp4").as_posix(),
                                   "ok": r.returncode == 0})
    write_json(out, res)
    log(f"{len(cands)} hook candidate(s); wrote {out}")
    for k, c in enumerate(cands):
        log(f"  [{k}] {c['score']:>5} {c['type']:<10} {c['line'][:80]}")


if __name__ == "__main__":
    main()
