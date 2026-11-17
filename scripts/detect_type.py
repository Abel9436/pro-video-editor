#!/usr/bin/env python3
"""Stage 4 - Classify the footage into a video type and choose a style fingerprint.

Usage:
  python scripts/detect_type.py --project PROJECT [--target short|long] [--platform P]
                                [--style styles/x/y.json] [--profile profiles/me.json]

Reads PROJECT/media.json and PROJECT/analysis.json. Writes PROJECT/type.json:
  {"type", "content_type", "confidence", "evidence": [...], "scores", "per_file": [...],
   "style": {"path", "why", "measured"}}

Types (references/video-types.md): short_form, talking_head, vlog, cinematic_travel,
podcast_long, podcast_clip, documentary, product_ad, gaming_reaction, explainer_3d.
`short_form` is a delivery target: when the brief asks for a short, `type` is short_form
(or podcast_clip for conversation footage) and `content_type` says what the footage is.

Style choice order: --style, then the profile's default for the target, then the best
fingerprint in styles/ for the type and platform (measured styles before starting defaults).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.common import fail, log, read_json, write_json  # noqa: E402
from lib.timebase import parse_rate  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
LONG_S = 600                  # sources longer than 10 min count as long-form recordings
SHORT_TARGET_S = 90           # platform short-form limit used to infer a short target


def file_signals(fid: str, rec: dict, item: dict, fps: float) -> dict:
    shots = rec.get("shots", [])
    total = sum(s["e_f"] - s["s_f"] for s in shots) or item.get("duration_f", 1)
    face_f = sum(s["e_f"] - s["s_f"] for s in shots if (s.get("faces") or {}).get("count", 0) > 0)
    big_face_f = sum(s["e_f"] - s["s_f"] for s in shots if ((s.get("faces") or {}).get("main") or {}).get("size", 0) >= 0.15)
    moving = sum(s["e_f"] - s["s_f"] for s in shots
                 if (s.get("camera") or {}).get("type", "static") not in ("static", "unknown", "too_short"))
    handheld = sum(s["e_f"] - s["s_f"] for s in shots if "handheld" in (s.get("camera") or {}).get("type", ""))
    static_noface = sum(s["e_f"] - s["s_f"] for s in shots if (s.get("camera") or {}).get("type") == "static"
                        and not (s.get("faces") or {}).get("count"))
    sp = rec.get("speakers") or {}
    n_spk = sp.get("speakers") or len({t["speaker"] for t in sp.get("turns", [])}) or 0
    speech = rec.get("speech") or {}
    dur_s = item.get("duration_f", total) / fps
    return {"file": fid, "duration_s": round(dur_s, 1), "kind": item.get("kind"),
            "speech_ratio": speech.get("speech_ratio", 0.0), "speakers": n_spk,
            "speaker_method": sp.get("method"), "face_time": round(face_f / total, 2),
            "big_face_time": round(big_face_f / total, 2), "scenery_ratio": round(1 - face_f / total, 2),
            "camera_moving": round(moving / total, 2), "handheld": round(handheld / total, 2),
            "static_no_face": round(static_noface / total, 2),
            "shots_per_min": round(len(shots) / max(dur_s / 60, 1e-6), 1),
            "music": bool(rec.get("music")), "synced": bool(item.get("sync"))}


def score_types(s: dict, n_files: int, multicam: bool) -> dict[str, tuple[float, list[str]]]:
    """Rule scores in 0..1 with the evidence that produced them."""
    out = {}
    def put(t, sc, why):
        out[t] = (round(max(0.0, min(1.0, sc)), 2), why)
    sr, ft = s["speech_ratio"], s["face_time"]
    put("talking_head", 0.5 * (sr > 0.5) + 0.3 * (ft > 0.6) + 0.2 * (s["speakers"] <= 1) - 0.3 * (s["handheld"] > 0.6 and n_files > 3),
        [f"speech {sr:.0%}", f"face on screen {ft:.0%}", f"{s['speakers']} speaker(s) ({s['speaker_method']})"])
    put("podcast_long", 0.4 * (s["speakers"] >= 2 or multicam) + 0.3 * (sr > 0.6) + 0.3 * (s["duration_s"] > LONG_S),
        [f"{s['speakers']} speakers", f"multicam {multicam}", f"{s['duration_s']:.0f} s long"])
    put("vlog", 0.35 * (s["handheld"] > 0.4) + 0.25 * (0.15 < sr < 0.75) + 0.2 * (n_files >= 4) + 0.2 * (0.2 < ft < 0.8),
        [f"handheld {s['handheld']:.0%}", f"speech {sr:.0%}", f"{n_files} files"])
    put("cinematic_travel", 0.45 * (sr < 0.15) + 0.3 * (s["camera_moving"] > 0.5) + 0.25 * (ft < 0.3),
        [f"speech {sr:.0%}", f"moving camera {s['camera_moving']:.0%}", f"faces {ft:.0%}"])
    put("documentary", 0.35 * (sr > 0.4) + 0.35 * (0.3 < s["scenery_ratio"] < 0.8) + 0.3 * (s["duration_s"] > 300),
        [f"non-face shots {s['scenery_ratio']:.0%}", f"{s['duration_s']:.0f} s"])
    put("gaming_reaction", 0.6 * (s["static_no_face"] > 0.5 and sr > 0.3) + 0.2 * (s["shots_per_min"] < 4),
        [f"static no-face (screen-like) {s['static_no_face']:.0%}"])
    put("explainer_3d", 0.5 * (sr > 0.6 and ft < 0.1) + 0.3 * (s["camera_moving"] < 0.3),
        [f"speech {sr:.0%} with faces {ft:.0%} (voice-over)"])
    put("product_ad", 0.4 * (sr < 0.4 and ft < 0.4) + 0.3 * (s["static_no_face"] > 0.4) + 0.3 * (s["duration_s"] < 120),
        [f"faces {ft:.0%}", f"static no-face {s['static_no_face']:.0%}"])
    return out


def choose_style(typ: str, content: str, platform: str | None, explicit: str | None, profile: str | None,
                 target: str) -> dict:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            fail(f"style {p} does not exist")
        return {"path": p.as_posix(), "why": "requested by the user", "measured": read_json(p).get("measured", False)}
    if profile:
        prof = read_json(profile)
        d = (prof.get("default_style") or {}).get(target)
        if d and (SKILL / d).exists():
            return {"path": d, "why": f"creator profile default for {target}", "measured": read_json(SKILL / d).get("measured", False)}
    best = None
    for p in sorted((SKILL / "styles").glob("*/*.json")):
        st = read_json(p)
        score = (2 if st.get("type") == typ else 1 if st.get("type") == content else 0)
        if not score:
            continue
        score += 0.5 * (platform is not None and st.get("platform") in (platform, None))
        score += 1.0 * bool(st.get("measured")) + 0.01 * (st.get("sources") or 0)
        if best is None or score > best[0]:
            best = (score, p, st)
    if best is None:
        return {"path": None, "why": f"no style for {typ}/{content}; references/video-types.md defaults apply",
                "measured": False}
    rel = best[1].relative_to(SKILL).as_posix()
    return {"path": rel, "why": f"best match for type {best[2].get('type')} ({best[2].get('sources', 0)} measured sources)"
            if best[2].get("measured") else "starting default (no measured style for this type yet)",
            "measured": bool(best[2].get("measured"))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--target", choices=["short", "long", "auto"], default="auto",
                    help="delivery target from the brief; auto infers from platform")
    ap.add_argument("--platform", help="platform from the brief (default: media.json platform)")
    ap.add_argument("--style"); ap.add_argument("--profile")
    ap.add_argument("--out", help="default PROJECT/type.json")
    a = ap.parse_args()
    project = Path(a.project)
    try:
        media = read_json(project / "media.json")
        ana = read_json(project / "analysis.json")
    except FileNotFoundError as e:
        fail(f"{e}; run ingest.py and analyze.py first")
    fps = float(parse_rate(media["fps"]))
    platform = a.platform or media.get("platform")
    target = a.target
    if target == "auto":
        target = "short" if (platform or "") in ("shorts", "youtube_shorts", "tiktok", "reels", "instagram_reels") else "long"
    items = {it["id"]: it for it in media["items"]}
    multicam = any(len(g["members"]) > 1 for g in media.get("sync_groups", []))
    per_file, agg = [], {}
    total_w = 0.0
    for fid, rec in ana["files"].items():
        it = items.get(fid, {})
        if it.get("kind") == "audio" or not rec.get("shots"):
            continue
        s = file_signals(fid, rec, it, fps)
        sc = score_types(s, len(ana["files"]), multicam)
        best = max(sc, key=lambda k: sc[k][0])
        per_file.append({"file": fid, "type": best, "score": sc[best][0], "signals": s})
        w = s["duration_s"]
        total_w += w
        for k, (v, why) in sc.items():
            agg.setdefault(k, [0.0, why])[0] += v * w
    if not per_file:
        fail("no video files with shots in analysis.json")
    scores = {k: round(v[0] / total_w, 2) for k, v in agg.items()}
    ranked = sorted(scores, key=scores.get, reverse=True)
    content = ranked[0]
    margin = scores[ranked[0]] - (scores[ranked[1]] if len(ranked) > 1 else 0)
    conf = round(min(1.0, scores[content] * 0.7 + margin), 2)
    typ = content
    if target == "short":
        typ = "podcast_clip" if content == "podcast_long" else "short_form"
    evidence = agg[content][1] + [f"target {target} on {platform or 'unspecified platform'}"]
    if len({p["type"] for p in per_file}) > 1:
        evidence.append("mixed footage: see per_file for the sequence of types")
    style = choose_style(typ, content, platform, a.style, a.profile, target)
    out = {"type": typ, "content_type": content, "confidence": conf, "target": target, "platform": platform,
           "evidence": evidence, "scores": scores, "per_file": per_file, "style": style,
           "statement": f"Type: {typ} ({content} footage), confidence {conf}. Style: {style['path'] or 'defaults'} - {style['why']}."}
    dst = Path(a.out) if a.out else project / "type.json"
    write_json(dst, out)
    log(out["statement"])
    log(f"wrote {dst}")


if __name__ == "__main__":
    main()
