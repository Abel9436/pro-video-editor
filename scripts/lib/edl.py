"""EDL: JSON Schema, loading helpers and checks shared by plan_edit, render, qc and export.

Conventions (references/edl-schema.md is the human-readable version of this file):
- Every time is an integer frame count at project.fps.
- Video events sit back to back on the timeline: at_f is the timeline frame where the event starts.
- Source frames (in_f/out_f) are on the source file's timeline-rate clock (proxies and
  analysis use the same clock, set at ingest). out_f is exclusive.
- transform[].at_f is relative to the event's own start on the timeline.
- `src` is a media id from media.json; `asset` is a catalog id (cat:..., kit:...).
"""
from __future__ import annotations

from fractions import Fraction

from .timebase import parse_rate

REASON = {"type": "string", "minLength": 3}
FRAME = {"type": "integer"}
NONNEG = {"type": "integer", "minimum": 0}
EASES = ["linear", "in_cubic", "out_cubic", "in_out_cubic", "out_back", "in_out_sine"]

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version", "project", "tracks"],
    "properties": {
        "version": {"const": 1},
        "project": {
            "type": "object",
            "required": ["fps", "width", "height"],
            "properties": {
                "fps": {"type": ["string", "integer"]}, "width": {"type": "integer", "minimum": 16},
                "height": {"type": "integer", "minimum": 16}, "platform": {"type": "string"},
                "type": {"type": "string"}, "style": {"type": ["string", "null"]},
                "profile": {"type": ["string", "null"]}, "target_duration_f": NONNEG,
                "commercial": {"type": "boolean"}, "kit": {"type": "object"},
            },
        },
        "tracks": {
            "type": "object",
            "required": ["video"],
            "properties": {
                "video": {"type": "array", "minItems": 1, "items": {
                    "type": "object", "required": ["id", "src", "in_f", "out_f", "at_f", "reason"],
                    "properties": {
                        "id": {"type": "string"}, "src": {"type": "string"},
                        "in_f": NONNEG, "out_f": NONNEG, "at_f": NONNEG,
                        "reframe": {"type": "object", "properties": {
                            "mode": {"enum": ["face_track", "center", "fixed"]},
                            "zoom": {"type": "number", "minimum": 1.0, "maximum": 4.0},
                            "x": {"type": "number"}, "y": {"type": "number"}}},
                        "transform": {"type": "array", "items": {
                            "type": "object", "required": ["at_f", "type"],
                            "properties": {"at_f": NONNEG, "type": {"enum": ["punch_in", "punch_out", "push_in", "pull_out", "shake"]},
                                           "scale": {"type": "number", "minimum": 0.5, "maximum": 4.0},
                                           "ease": {"enum": EASES}, "dur_f": NONNEG,
                                           "hold_f": NONNEG}}},
                        "speed": {"type": "number", "exclusiveMinimum": 0, "maximum": 8},
                        "freeze_f": NONNEG, "cutaway": {"type": "boolean"},
                        "transition_in": {"enum": ["cut", "dissolve", "fade", "whip", "zoom"]},
                        "transition_dur_f": NONNEG,
                        "reason": REASON,
                        "role": {"type": "string"},
                        "rule_of_six": {"type": "object", "properties": {
                            k: {"type": "number", "minimum": 0, "maximum": 10} for k in ("emotion", "story", "rhythm")}},
                    }}},
                "broll": {"type": "array", "items": {
                    "type": "object", "required": ["id", "at_f", "dur_f", "reason"],
                    "properties": {"id": {"type": "string"}, "asset": {"type": "string"}, "src": {"type": "string"},
                                   "in_f": NONNEG, "at_f": NONNEG, "dur_f": {"type": "integer", "minimum": 1},
                                   "over": {"type": "string"}, "reason": REASON,
                                   "push": {"type": "array", "items": {"type": "number", "minimum": 1}, "minItems": 2, "maxItems": 2},
                                   "speed": {"type": "number", "exclusiveMinimum": 0, "maximum": 4},
                                   "grade": {"type": "object", "properties": {"gain": {"type": "number", "minimum": 0, "maximum": 2},
                                             "sat": {"type": "number", "minimum": 0, "maximum": 2}, "vignette": {"type": "number", "minimum": 0, "maximum": 1}}},
                                   "x": {"type": "number", "minimum": 0, "maximum": 1}, "y": {"type": "number", "minimum": 0, "maximum": 1},
                                   "transition_in": {"enum": ["cut", "dissolve", "fade", "whip", "zoom"]}}}},
                "dialogue": {"type": "array", "items": {
                    "type": "object", "required": ["id", "src", "in_f", "out_f", "at_f"],
                    "properties": {"id": {"type": "string"}, "src": {"type": "string"}, "in_f": NONNEG,
                                   "out_f": NONNEG, "at_f": FRAME, "split_edit": {"enum": ["none", "j_cut", "l_cut"]},
                                   "chain": {"type": "string"}, "gain_db": {"type": "number"}, "speed": {"type": "number"}}}},
                "music": {"type": "array", "items": {
                    "type": "object", "required": ["asset", "at_f"],
                    "properties": {"asset": {"type": "string"}, "at_f": NONNEG, "in_f": NONNEG, "dur_f": NONNEG,
                                   "gain_db": {"type": "number"}, "align": {"type": "string"},
                                   "end": {"enum": ["bar", "hit", "fade", "natural"]},
                                   "reason": {"type": "string"},
                                   "duck": {"type": "object", "properties": {
                                       "under": {"type": "string"}, "depth_db": {"type": "number", "maximum": 0},
                                       "attack_ms": {"type": "number", "minimum": 1}, "release_ms": {"type": "number", "minimum": 1}}}}}},
                "sfx": {"type": "array", "items": {
                    "type": "object", "required": ["asset", "at_f", "reason"],
                    "properties": {"asset": {"type": "string"}, "at_f": FRAME, "gain_db": {"type": "number"},
                                   "in_s": {"type": "number", "minimum": 0}, "dur_f": {"type": "integer", "minimum": 1},
                                   "reason": REASON, "role": {"type": "string"},
                                   "align": {"enum": ["peak", "start", "end"]},
                                   "pitch": {"type": "number", "minimum": 0.5, "maximum": 2},
                                   "lp": {"type": "number", "minimum": 200}, "hp": {"type": "number", "minimum": 20},
                                   "pan": {"type": "number", "minimum": -1, "maximum": 1}}}},
                "captions": {"type": ["object", "null"], "properties": {
                    "template": {"type": "string"}, "source": {"enum": ["transcript", "text"]},
                    "highlight": {"enum": ["keyword", "none", "active_word"]}, "safe_zone": {"type": "string"},
                    "language": {"type": "string"}, "keywords": {"type": "array", "items": {"type": "string"}},
                    "position": {"type": "string"}, "words_per_card": {"type": "integer", "minimum": 1, "maximum": 12},
                    "fix": {"type": "object"}}},
                "graphics": {"type": "array", "items": {
                    "type": "object", "required": ["component", "at_f", "dur_f"],
                    "properties": {"component": {"type": "string"}, "at_f": NONNEG, "dur_f": {"type": "integer", "minimum": 1},
                                   "props": {"type": "object"}, "reason": {"type": "string"}}}},
            },
        },
        "color": {"type": "object", "properties": {
            "correction": {"enum": ["auto", "none"]}, "match_shots": {"type": "boolean"},
            "look": {"type": ["string", "object", "null"]}, "strength": {"type": "number", "minimum": 0, "maximum": 1},
            "halation": {"type": "number", "minimum": 0, "maximum": 1}}},
        "master": {"type": "object", "properties": {"lufs": {"type": "number"}, "true_peak_db": {"type": "number"}}},
        "privacy": {"type": "object", "properties": {
            "blur_faces": {"enum": ["none", "bystanders", "all"]},
            "regions": {"type": "array", "items": {"type": "object", "required": ["box"], "properties": {
                "t0_f": NONNEG, "t1_f": NONNEG, "box": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
                "what": {"type": "string"}}}}}},
        "design": {"type": "object", "description": "premium design pass (render.py design_pass, remotion Design)",
                   "properties": {"brand": {"type": "object"}, "face_y": {"type": "number", "minimum": 0, "maximum": 1},
                                  "layout": {"type": "array"}, "scenes": {"type": "array"}, "overlays": {"type": "array"},
                                  "fx": {"type": "array"}, "emphasis": {"type": "array", "items": {"type": "string"}},
                                  "caption_skip": {"type": "array", "items": {"type": ["string", "integer"]}},
                                  "caption_hide": {"type": "array"}, "caption_text": {"type": "object", "additionalProperties": {"type": "string"}}, "caption_y_at": {"type": "array"}, "engine": {"enum": ["hyperframes", "remotion"]}, "max_words": {"type": "integer", "minimum": 1},
                                  "caption_style": {"enum": ["phrase", "slam", "neon", "keyword", "tier", "box", "lockup", "ink", "cine", "pop", "whisper", "plate"]}, "caption_font": {"type": "string"}, "caption_font_emph": {"type": "string"}, "camera": {"type": "array"}, "finish": {"type": "object"}, "caption_framed": {"type": "array"},
                                  "caption_size": {"type": "number", "minimum": 10}, "raw_video": {"type": "string", "description": "project-relative, timeline-aligned ungraded footage for bg color raw (log vs graded wipes) and Scopes"},
                                  "caption_y": {"type": "number", "minimum": 0, "maximum": 1, "description": "caption centre in full layout (default 0.7): move it off a mic or prop"},
                                  "caption_palette": {"type": "array", "items": {"type": "string"}, "description": "keyword style: colours the key words cycle through"},
                                  "matte": {"type": "boolean", "description": "cut the speaker out so overlays with behind:true sit behind them"},
                                  "bg": {"type": "array", "items": {"type": "object", "required": ["s", "e", "color"]}}}},
        "notes": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
}


def fps_of(edl: dict) -> Fraction:
    return parse_rate(edl["project"]["fps"])


def event_len(ev: dict) -> int:
    """Timeline length of a video event (speed and freeze applied)."""
    n = ev["out_f"] - ev["in_f"]
    sp = ev.get("speed", 1.0) or 1.0
    return int(round(n / sp)) + int(ev.get("freeze_f", 0))


def timeline_len(edl: dict) -> int:
    return max((ev["at_f"] + event_len(ev) for ev in edl["tracks"]["video"]), default=0)


def schema_errors(edl: dict) -> list[str]:
    import jsonschema
    v = jsonschema.Draft202012Validator(SCHEMA)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
            for e in sorted(v.iter_errors(edl), key=lambda e: list(e.absolute_path))]


def words_by_src(analysis: dict) -> dict[str, list[dict]]:
    out = {}
    for fid, rec in analysis.get("files", {}).items():
        tr = rec.get("transcript") or {}
        if tr.get("ref"):
            ref = analysis["files"].get(tr["ref"], {}).get("transcript", {}).get("words", [])
            off = tr.get("offset_f", 0)
            out[fid] = [{**w, "s_f": w["s_f"] - off, "e_f": w["e_f"] - off} for w in ref]
        else:
            out[fid] = tr.get("words", [])
    return out


def word_at(words: list[dict], f: int) -> dict | None:
    """The word whose body contains source frame f (strictly inside, edges allowed)."""
    lo, hi = 0, len(words)
    while lo < hi:
        mid = (lo + hi) // 2
        if words[mid]["e_f"] <= f:
            lo = mid + 1
        else:
            hi = mid
    if lo < len(words) and words[lo]["s_f"] < f < words[lo]["e_f"]:
        return words[lo]
    return None


def timeline_words(edl: dict, analysis: dict) -> list[dict]:
    """Words heard on the timeline: dialogue events mapped to timeline frames, in order."""
    wbs = words_by_src(analysis)
    out = []
    dia = edl["tracks"].get("dialogue") or []
    for d in dia:
        sp = d.get("speed", 1.0) or 1.0
        for w in wbs.get(d["src"], []):
            if w["s_f"] >= d["in_f"] and w["e_f"] <= d["out_f"]:
                out.append({**w, "src": d["src"], "t_s": d["at_f"] + int((w["s_f"] - d["in_f"]) / sp),
                            "t_e": d["at_f"] + int((w["e_f"] - d["in_f"]) / sp)})
    out.sort(key=lambda w: w["t_s"])
    return out


def edl_metrics(edl: dict) -> dict:
    """Edit-shape numbers used for change lists and learned preferences."""
    fps = float(fps_of(edl))
    vids = edl["tracks"]["video"]
    total = timeline_len(edl) / fps if vids else 0.0
    lens = sorted(event_len(v) / fps for v in vids)
    zooms = sum(1 for v in vids for t in v.get("transform", []) if t["type"] in ("punch_in", "punch_out", "push_in"))
    return {"duration_s": round(total, 2), "events": len(vids),
            "cuts_per_min": round(60 * max(0, len(vids) - 1) / total, 1) if total else 0.0,
            "shot_len_med_s": round(lens[len(lens) // 2], 2) if lens else 0.0,
            "zooms_per_min": round(60 * zooms / total, 1) if total else 0.0,
            "sfx": len(edl["tracks"].get("sfx") or []), "music": len(edl["tracks"].get("music") or []),
            "graphics": len(edl["tracks"].get("graphics") or []), "broll": len(edl["tracks"].get("broll") or []),
            "caption_template": (edl["tracks"].get("captions") or {}).get("template"),
            "look": (edl.get("color") or {}).get("look")}


def edl_diff(a: dict, b: dict) -> list[str]:
    """Readable change list from EDL a to EDL b (what an editor would say in a revision note)."""
    fps = fps_of(b)
    out = []
    ma, mb = edl_metrics(a), edl_metrics(b)
    for k, label in (("duration_s", "length"), ("events", "picture events"), ("cuts_per_min", "cuts per minute"),
                     ("shot_len_med_s", "median shot length"), ("zooms_per_min", "zooms per minute"),
                     ("sfx", "sound effects"), ("music", "music tracks"), ("graphics", "graphics"), ("broll", "B-roll inserts")):
        if ma[k] != mb[k]:
            out.append(f"{label}: {ma[k]} -> {mb[k]}")
    for k in ("caption_template", "look"):
        if ma[k] != mb[k]:
            out.append(f"{k.replace('_', ' ')}: {ma[k]} -> {mb[k]}")
    sa = {(v["src"], v["in_f"], v["out_f"]) for v in a["tracks"]["video"]}
    sb = {(v["src"], v["in_f"], v["out_f"]) for v in b["tracks"]["video"]}

    def tc(f):
        s = f / float(fps)
        return f"{int(s // 60)}:{s % 60:04.1f}"
    for v in b["tracks"]["video"]:
        if (v["src"], v["in_f"], v["out_f"]) not in sa:
            out.append(f"new/changed shot at {tc(v['at_f'])} ({v['src']} {v['in_f']}-{v['out_f']}): {v.get('reason', '')[:80]}")
    for v in a["tracks"]["video"]:
        if (v["src"], v["in_f"], v["out_f"]) not in sb:
            out.append(f"removed shot ({v['src']} {v['in_f']}-{v['out_f']}) that was at {tc(v['at_f'])}")
    ma_, mb_ = a.get("master") or {}, b.get("master") or {}
    if ma_ != mb_:
        out.append(f"master: {ma_} -> {mb_}")
    new_notes = [n for n in b.get("notes", []) if n not in a.get("notes", [])]
    out += [f"note: {n}" for n in new_notes]
    return out or ["no change"]
