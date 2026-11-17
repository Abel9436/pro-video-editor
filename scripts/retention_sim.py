#!/usr/bin/env python3
"""Walk an EDL second by second and flag likely drop-off points.

Usage:
  python scripts/retention_sim.py --edl P/edl/v1.json --project P [--style STYLE.json] [--out P/retention.json]

Risks (each adds to that second's score, 0..1):
  no_visual_change   picture unchanged longer than the style's max_no_change_s (default 4 s short / 10 s long)
  dead_air           a gap in speech >= 0.6 s with no planned hold, music or graphic
  slow_start         no speech or motion in the first second; hook role missing
  late_payoff        first payoff later than 8 s (short) / 60 s (long)
  repeated_point     a sentence repeating an earlier one (similarity >= 0.6)
  talking_only       speech over the same talking-head picture for 2x the change limit with no B-roll/graphic
The curve is a predicted risk, not a retention prediction: compare it with real analytics
in the creator profile (profile.py analytics) to calibrate it for a channel.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.common import fail, log, read_json, write_json  # noqa: E402
from lib.edl import fps_of, timeline_len  # noqa: E402
from lib.viral import (DEAD_AIR_S, DEFAULT_MAX_STATIC_S, PAYOFF_MAX_S, repeated_points, sec, speech_gaps,  # noqa: E402
                       static_gaps, style_field, target_kind)

SKILL = Path(__file__).resolve().parent.parent
WEIGHTS = {"no_visual_change": 0.35, "dead_air": 0.4, "slow_start": 0.5, "late_payoff": 0.3, "repeated_point": 0.3,
           "talking_only": 0.2}


def simulate(edl: dict, analysis: dict, style: dict) -> dict:
    fps = fps_of(edl)
    kind = target_kind(edl)
    total = timeline_len(edl)
    n_s = int(total / float(fps)) + 1
    curve = [{"t": s, "risk": 0.0, "reasons": []} for s in range(n_s)]

    def flag(a_f, b_f, key, why):
        for s in range(int(a_f / float(fps)), min(n_s, int(b_f / float(fps)) + 1)):
            c = curve[s]
            if key not in [r.split(":")[0] for r in c["reasons"]]:
                c["risk"] = min(1.0, c["risk"] + WEIGHTS[key])
                c["reasons"].append(f"{key}: {why}")

    max_static = float(style_field(style, "structure.max_no_change_s", DEFAULT_MAX_STATIC_S[kind]))
    limit_f = int(max_static * float(fps))
    for a, b in static_gaps(edl, analysis):
        if b - a > limit_f:
            flag(a + limit_f, b, "no_visual_change", f"{sec(b - a, fps)} s without a visible change (limit {max_static:.1f} s)")
    holds = {ev["at_f"] + (ev["out_f"] - ev["in_f"]) for ev in edl["tracks"]["video"] if ev.get("role") == "ending"}
    has_music = bool(edl["tracks"].get("music"))
    for a, b in speech_gaps(edl, analysis):
        if (b - a) / float(fps) >= DEAD_AIR_S and not has_music and b not in holds and b < total - 2:
            flag(a, b, "dead_air", f"{sec(b - a, fps)} s with no speech at {sec(a, fps)} s")
    vids = edl["tracks"]["video"]
    if not vids or vids[0].get("role") != "hook":
        flag(0, int(fps), "slow_start", "the first event is not marked as the hook")
    from lib.edl import timeline_words
    tw = timeline_words(edl, analysis)
    if tw and tw[0]["t_s"] > int(fps * 0.5) and not edl["tracks"].get("music") and not edl["tracks"].get("sfx"):
        flag(0, tw[0]["t_s"], "slow_start", f"first word at {sec(tw[0]['t_s'], fps)} s with no sound before it")
    payoff = next((ev["at_f"] for ev in vids if ev.get("role") in ("payoff", "reveal", "answer")), None)
    if payoff is None or payoff / float(fps) > PAYOFF_MAX_S[kind]:
        where = payoff if payoff is not None else total
        flag(int(PAYOFF_MAX_S[kind] * float(fps)), where, "late_payoff",
             "no payoff planned" if payoff is None else f"first payoff at {sec(payoff, fps)} s")
    for a, b, text in repeated_points(edl, analysis):
        flag(b, b + int(3 * fps), "repeated_point", f"'{text}' repeats the point at {sec(a, fps)} s")
    support = [(b["at_f"], b["at_f"] + b["dur_f"]) for b in edl["tracks"].get("broll") or []] + \
              [(g["at_f"], g["at_f"] + g["dur_f"]) for g in edl["tracks"].get("graphics") or []]
    run_start = 0
    for s in range(n_s):
        f = int(s * float(fps))
        if any(a <= f < b for a, b in support):
            run_start = s + 1
        elif s - run_start >= 2 * max_static and s % int(max_static) == 0:
            flag(f, f + int(fps), "talking_only", f"{s - run_start} s of talking head with no B-roll or graphic")
    dips = [c for c in curve if c["risk"] >= 0.35]
    return {"duration_s": sec(total, fps), "max_static_s": max_static, "curve": curve,
            "dips": [{"t": c["t"], "risk": round(c["risk"], 2), "why": c["reasons"]} for c in dips],
            "mean_risk": round(sum(c["risk"] for c in curve) / max(1, n_s), 3),
            "note": "predicted risk from edit structure; calibrate against real retention in the creator profile"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", required=True); ap.add_argument("--project", required=True)
    ap.add_argument("--style"); ap.add_argument("--out")
    a = ap.parse_args()
    project = Path(a.project)
    try:
        edl = read_json(a.edl); analysis = read_json(project / "analysis.json")
    except FileNotFoundError as e:
        fail(str(e))
    sp = a.style or edl["project"].get("style")
    style = read_json(SKILL / sp) if sp and (SKILL / sp).exists() else {}
    res = simulate(edl, analysis, style)
    out = Path(a.out) if a.out else project / "retention.json"
    write_json(out, res)
    log(f"retention: mean risk {res['mean_risk']}, {len(res['dips'])} risky second(s); wrote {out}")
    for d in res["dips"][:12]:
        log(f"  {d['t']:>4} s  risk {d['risk']}: {'; '.join(d['why'])}")


if __name__ == "__main__":
    main()
