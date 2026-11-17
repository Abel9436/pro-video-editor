#!/usr/bin/env python3
"""Score an EDL for retention-style platforms and list specific fixes.

Usage:
  python scripts/virality_score.py --edl P/edl/v1.json --project P [--style S.json]
                                   [--judged P/judged.json] [--out P/virality.json]

Measured in code: hook layers in the first second (motion, text, sound), first payoff time,
dead air, longest stretch without a visual change, re-hook gaps, caption coverage, loop
similarity between the last and first frame.
Judged by Claude (passed in --judged, each with a one-line reason): dominant emotion and
arousal, STEPPS 0-10, promise_kept. Missing judged fields are reported as not scored.

Virality is a probability an edit can raise, never a guarantee; the output says so.
Score weights (STARTING DEFAULTS): hook 25, retention 25, payoff 15, captions 10, loop 10, judged 15.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from lib.common import fail, log, read_json, write_json  # noqa: E402
from lib.edl import fps_of, timeline_len, timeline_words  # noqa: E402
from lib.viral import (DEAD_AIR_S, DEFAULT_MAX_STATIC_S, PAYOFF_MAX_S, sec, speech_gaps,  # noqa: E402
                       static_gaps, style_field, target_kind)

SKILL = Path(__file__).resolve().parent.parent
PASS_SCORE = 70
LOOP_TARGET = 0.6


def loop_similarity(edl: dict, project: Path) -> float | None:
    import cv2
    from render import decode, dims, in_matrix, src_path
    media = {it["id"]: it for it in read_json(project / "media.json")["items"]}
    fps = fps_of(edl)
    v0, v1 = edl["tracks"]["video"][0], edl["tracks"]["video"][-1]
    try:
        a = next(decode(src_path(media[v0["src"]], True, project), v0["in_f"], 1, fps, in_matrix(media[v0["src"]])))
        b = next(decode(src_path(media[v1["src"]], True, project), v1["out_f"] - 1, 1, fps, in_matrix(media[v1["src"]])))
    except (StopIteration, KeyError):
        return None
    g = [cv2.resize(cv2.cvtColor(x, cv2.COLOR_BGR2GRAY), (36, 64)).astype(float).ravel() for x in (a, b)]
    return round(float(np.corrcoef(g[0], g[1])[0, 1]), 3) if g[0].std() and g[1].std() else 0.0


def score(edl: dict, analysis: dict, project: Path, style: dict, judged: dict) -> dict:
    fps = fps_of(edl)
    kind = target_kind(edl)
    total = timeline_len(edl)
    first_s = int(fps)
    vids = edl["tracks"]["video"]
    shots = (analysis["files"].get(vids[0]["src"]) or {}).get("shots", [])
    sh0 = next((s for s in shots if s["s_f"] <= vids[0]["in_f"] < s["e_f"]), {})
    motion = (sh0.get("motion_pct_per_f") or 0) > 0.05 or bool(vids[0].get("transform")) or \
        (sh0.get("camera") or {}).get("type", "static") != "static"
    tw = timeline_words(edl, analysis)
    text_first = any(g["at_f"] < first_s for g in edl["tracks"].get("graphics") or []) or \
        (bool(edl["tracks"].get("captions")) and bool(tw) and tw[0]["t_s"] < first_s)
    sound_first = (bool(tw) and tw[0]["t_s"] < first_s) or any(s["at_f"] < first_s for s in edl["tracks"].get("sfx") or []) \
        or any(m["at_f"] < first_s for m in edl["tracks"].get("music") or [])
    hook_pts = 4 * motion + 3 * text_first + 3 * sound_first
    payoff = next((ev["at_f"] for ev in vids if ev.get("role") in ("payoff", "reveal", "answer")), None)
    dead = sum(b - a for a, b in speech_gaps(edl, analysis) if (b - a) / float(fps) >= DEAD_AIR_S and b < total - 2)
    gaps = [b - a for a, b in static_gaps(edl, analysis)]
    max_gap = max(gaps) if gaps else total
    max_static = float(style_field(style, "structure.max_no_change_s", DEFAULT_MAX_STATIC_S[kind]))
    rehooks = [round(float(g / fps), 2) for g in gaps]
    cov = 0.0
    if edl["tracks"].get("captions") and tw:
        cov = 100.0
    loop = loop_similarity(edl, project) if kind == "short" else None
    risks, fixes = [], []
    if not motion:
        risks.append("first frame is static"); fixes.append("open on a punch-in or a moving shot")
    if not text_first:
        risks.append("no on-screen text in the first second (many watch muted)"); fixes.append("add a title or start captions at 0:00")
    if not sound_first:
        risks.append("no sound in the first second"); fixes.append("start on the first word or add a hit/riser at 0:00")
    if payoff is None or payoff / float(fps) > PAYOFF_MAX_S[kind]:
        risks.append("payoff arrives late" if payoff else "no payoff marked")
        fixes.append(f"move a payoff before {PAYOFF_MAX_S[kind]:.0f} s or tease it in the hook")
    if max_gap / float(fps) > max_static:
        a = next(a for a, b in static_gaps(edl, analysis) if b - a == max_gap)
        risks.append(f"no visual change from {sec(a, fps)} s to {sec(a + max_gap, fps)} s")
        fixes.append(f"add a punch-in, B-roll or graphic near {sec(a + max_gap // 2, fps)} s")
    if dead / float(fps) > 0.5:
        risks.append(f"{sec(dead, fps)} s of dead air"); fixes.append("tighten pauses that are not emotional beats")
    if loop is not None and loop < LOOP_TARGET:
        fixes.append("end on a frame that matches the opening (same framing) so the short loops")
    hook_score = hook_pts * 2.5
    ret = 25 * max(0.0, 1 - max(0.0, max_gap / float(fps) - max_static) / max_static) * max(0.0, 1 - dead / float(fps) / 3)
    pay = 15 if payoff is not None and payoff / float(fps) <= PAYOFF_MAX_S[kind] else 5 if payoff is not None else 0
    capt = 10 * cov / 100
    lp = 10 * max(0.0, min(1.0, (loop or 0) / LOOP_TARGET)) if loop is not None else 10
    st = judged.get("stepps") or {}
    jd = 15 * (np.mean([v for v in st.values() if isinstance(v, (int, float))]) / 10) if st else None
    total_score = round(hook_score + ret + pay + capt + lp + (jd if jd is not None else 7.5))
    return {
        "hook": {"motion_in_first_frame": motion, "text_in_first_s": text_first, "sound_in_first_s": sound_first,
                 "score": hook_pts},
        "first_payoff_s": None if payoff is None else sec(payoff, fps),
        "dead_air_s": sec(dead, fps), "max_gap_without_visual_change_s": sec(max_gap, fps),
        "rehook_gaps_s": rehooks, "caption_coverage_pct": cov, "loop_similarity": loop,
        "emotion": judged.get("emotion"), "stepps": st or None, "promise_kept": judged.get("promise_kept"),
        "judged_reasons": judged.get("reasons"),
        "score": total_score, "passed": total_score >= PASS_SCORE and not (payoff is None),
        "parts": {"hook": hook_score, "retention": round(ret, 1), "payoff": pay, "captions": capt, "loop": round(lp, 1),
                  "judged": None if jd is None else round(jd, 1)},
        "risks": risks, "fixes": fixes,
        "disclaimer": "Virality is a probability an edit can raise, never a guarantee.",
        "note": None if st else "judged fields (emotion, STEPPS, promise_kept) not provided: pass --judged; scored as neutral",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", required=True); ap.add_argument("--project", required=True)
    ap.add_argument("--style"); ap.add_argument("--judged"); ap.add_argument("--out")
    a = ap.parse_args()
    project = Path(a.project)
    try:
        edl = read_json(a.edl); analysis = read_json(project / "analysis.json")
        judged = read_json(a.judged) if a.judged else {}
    except FileNotFoundError as e:
        fail(str(e))
    sp = a.style or edl["project"].get("style")
    style = read_json(SKILL / sp) if sp and (SKILL / sp).exists() else {}
    res = score(edl, analysis, project, style, judged)
    out = Path(a.out) if a.out else project / "virality.json"
    write_json(out, res)
    log(f"virality score {res['score']}/100 ({'pass' if res['passed'] else 'below the bar'}); wrote {out}")
    for r in res["risks"]:
        log(f"  risk: {r}")
    for f in res["fixes"]:
        log(f"  fix: {f}")


if __name__ == "__main__":
    main()
