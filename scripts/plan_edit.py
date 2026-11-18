#!/usr/bin/env python3
"""Stage 6 - Turn Claude's paper edit into a full EDL, and validate any EDL.

Usage:
  python scripts/plan_edit.py draft PAPER.json --project P --out P/edl/v1.json
  python scripts/plan_edit.py diff P/edl/v1.json P/edl/v2.json --project P
  python scripts/plan_edit.py check EDL.json --project P [--fix] [--report OUT.json]

draft: the paper edit is an ordered list of beats, each a word range from the transcript
(word indices from analysis/transcript_<id>.md) with a reason. The script turns word
ranges into frame-exact events: cuts land in the gaps between words with AIR_F frames of
air before the first word, hard fillers and flagged false starts inside a beat are cut out,
long pauses are tightened (except in beats marked keep_pauses), jump cuts alternate framing,
emphasis words get punch-ins, and every removal inside a sentence is written to notes.

check: schema, frame math, overlaps and gaps, missing media, cuts inside words, clipped
first consonants, missing reasons, duration against the target, explicit split edits.
With --fix it repairs what is mechanical (re-packs at_f, snaps cuts out of words) and
reports what needs a decision. Exit code 1 when errors remain.

Paper edit format: references/edl-schema.md, section "Paper edit".
"""
from __future__ import annotations

import argparse
import math
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.common import fail, log, read_json, write_json  # noqa: E402
from lib.edl import event_len, fps_of, schema_errors, timeline_len, word_at, words_by_src  # noqa: E402
from lib.timebase import parse_rate, timecode  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
AIR_F_S = Fraction(1, 10)      # STARTING DEFAULT: 0.1 s (3 frames at 30 fps) of air before a first word
TAIL_S = Fraction(2, 15)       # STARTING DEFAULT: 0.13 s after the last word so its release is not clipped
END_HOLD_S = Fraction(1, 3)    # hold after the final line: let the payoff land
MAX_PAUSE_S = {"short_form": Fraction(7, 20), "podcast_clip": Fraction(2, 5), "talking_head": Fraction(1, 2),
               "default": Fraction(3, 4)}   # STARTING DEFAULTS: longest kept pause inside a beat, by type
UPSCALE_LIMIT = 2.0        # same as qc.py UPSCALE_FAIL: beyond this, 8-bit sources visibly soften
PUNCH_SCALE = 1.12             # STARTING DEFAULT when the style has no measured punch_in_scale
PUNCH_DUR_S = Fraction(1, 6)   # punch-in ease duration
TARGET_SLACK = 0.10            # duration may exceed the target by 10 % before it is an error
PLATFORM_SIZE = {"shorts": (1080, 1920), "youtube_shorts": (1080, 1920), "tiktok": (1080, 1920),
                 "reels": (1080, 1920), "instagram_reels": (1080, 1920), "youtube": (1920, 1080),
                 "instagram_feed": (1080, 1350), "linkedin": (1080, 1080), "podcast": (1920, 1080)}


def style_value(style: dict, field: str, default):
    f = (style.get("fields") or {}).get(field) or {}
    v = f.get("med") if isinstance(f, dict) else None
    if v is None:
        v = style.get(field.split(".")[0]) if "." not in field else None
        if isinstance(v, dict):
            v = v.get("med")
    return default if v is None else v


# ----------------------------------------------------------------------------- draft
def draft(paper: dict, project: Path) -> dict:
    media = read_json(project / "media.json")
    ana = read_json(project / "analysis.json")
    fps = parse_rate(media["fps"])
    wbs = words_by_src(ana)
    prof = read_json(SKILL / paper["profile"]) if paper.get("profile") and (SKILL / paper["profile"]).exists() else {}
    if not paper.get("style") and prof.get("default_styles", {}).get(paper.get("platform") or media.get("platform")):
        paper = {**paper, "style": prof["default_styles"][paper.get("platform") or media.get("platform")]}
    style = {}
    if paper.get("style") and (SKILL / paper["style"]).exists():
        style = read_json(SKILL / paper["style"])
    typ = paper.get("type") or style.get("type") or "short_form"
    platform = paper.get("platform") or media.get("platform") or "shorts"
    W, H = paper.get("width"), paper.get("height")
    if not (W and H):
        W, H = PLATFORM_SIZE.get(platform, (1080, 1920))
    air = max(1, round(AIR_F_S * fps)); tail = max(1, round(TAIL_S * fps))
    max_pause = round(MAX_PAUSE_S.get(typ, MAX_PAUSE_S["default"]) * fps)
    punch_scale = float(style_value(style, "punch_in_scale", PUNCH_SCALE) or PUNCH_SCALE)
    punch_dur = max(2, round(PUNCH_DUR_S * fps))

    video, dialogue, notes = [], [], list(paper.get("notes", []))
    t = 0
    zoom_state = False
    beats = paper.get("beats") or []
    if not beats:
        raise ValueError("paper edit has no beats")
    for bi, beat in enumerate(beats):
        src = beat["src"]
        words = wbs.get(src)
        if words is None:
            raise ValueError(f"beat {bi}: unknown src '{src}' (media ids: {', '.join(wbs)})")
        a, b = beat["words"]
        if not (0 <= a <= b < len(words)):
            raise ValueError(f"beat {bi}: word range {a}-{b} outside 0-{len(words) - 1}")
        drop = set()
        for r in beat.get("drop", []):
            drop.update(range(r[0], r[1] + 1))
        rec = ana["files"][src]
        sp = rec.get("speech") or {}
        if beat.get("drop_fillers", True):
            for f in sp.get("fillers", []):
                if f.get("kind") == "hard" and a < f["i"] < b:
                    drop.update(i for i in range(f["i"], b) if words[i]["s_f"] < f["e_f"])
        if beat.get("drop_false_starts", True):
            for fs in sp.get("false_starts", []):
                lo, hi = fs.get("i_from", -1), fs.get("i_to", -2)
                if a <= lo and hi < b:
                    drop.update(range(lo, hi + 1))
        keep = [i for i in range(a, b + 1) if i not in drop]
        gone = sorted(drop & set(range(a, b + 1)))
        runs_d = []
        for i in gone:                      # one note per removed span, not per word
            if runs_d and i == runs_d[-1][-1] + 1:
                runs_d[-1].append(i)
            else:
                runs_d.append([i])
        for r in runs_d:
            text = " ".join(words[i]["w"] for i in r)
            span = f"word {r[0]}" if len(r) == 1 else f"words {r[0]}-{r[-1]}"
            notes.append(f"Removed '{text}' ({span}, {timecode(words[r[0]]['s_f'], fps)} in {src}) inside beat {bi}")
        runs, cur = [], [keep[0]]
        for i in keep[1:]:
            gap = words[i]["s_f"] - words[cur[-1]]["e_f"]
            contiguous = i == cur[-1] + 1
            if contiguous and (beat.get("keep_pauses") or gap <= max_pause):
                cur.append(i)
            else:
                if contiguous:
                    notes.append(f"Tightened a {float(gap / fps):.2f} s pause before word {i} in {src}")
                runs.append(cur); cur = [i]
        runs.append(cur)
        last_beat = bi == len(beats) - 1
        for ri, run in enumerate(runs):
            w0, w1 = words[run[0]], words[run[-1]]
            prev_e = words[run[0] - 1]["e_f"] if run[0] > 0 else 0
            next_s = words[run[-1] + 1]["s_f"] if run[-1] + 1 < len(words) else rec_len(media, src)
            in_f = max(w0["s_f"] - air, prev_e, 0)
            if in_f == prev_e and prev_e > 0 and w0["s_f"] - prev_e >= 2:
                in_f = (prev_e + w0["s_f"] + 1) // 2      # tight gap: cut in its middle
            hold = round(END_HOLD_S * fps) if (last_beat and ri == len(runs) - 1) else tail
            hold = beat.get("hold_f", hold) if ri == len(runs) - 1 else hold
            out_f = min(w1["e_f"] + hold, next_s if run[-1] + 1 < len(words) else w1["e_f"] + hold)
            out_f = max(out_f, w1["e_f"])     # Whisper word spans can touch or overlap by a frame
            ev = {"id": f"v{len(video) + 1}", "src": src, "in_f": int(in_f), "out_f": int(out_f), "at_f": t,
                  "reason": beat["reason"] if ri == 0 else f"jump cut inside beat {bi}: removes a pause or filler",
                  "role": beat.get("role", "body"), "transition_in": beat.get("transition_in", "cut") if ri == 0 else "cut"}
            if ri == 0 and beat.get("rule_of_six"):
                ev["rule_of_six"] = beat["rule_of_six"]
            zoom = float(beat.get("zoom", 1.0))
            if ri > 0 and beat.get("alternate_framing", True):
                zoom_state = not zoom_state
                ev["reason"] += "; framing alternates so the jump reads as intentional"
            elif ri == 0:
                zoom_state = zoom > 1.0
            ev["reframe"] = {"mode": beat.get("reframe", "face_track"),
                             "zoom": round(zoom if not zoom_state or zoom > 1.0 else punch_scale, 3)}
            if ri > 0 and beat.get("alternate_framing", True):
                ev["reframe"]["zoom"] = round(punch_scale if zoom_state else max(1.0, zoom), 3)
            tr = []
            for wi in beat.get("punch", []):
                if wi in run:
                    tr.append({"at_f": max(0, words[wi]["s_f"] - in_f - 1), "type": "punch_in", "scale": punch_scale,
                               "ease": "out_cubic", "dur_f": punch_dur})
            if beat.get("push_in"):
                tr.append({"at_f": 0, "type": "push_in", "scale": float(beat["push_in"]), "ease": "in_out_sine",
                           "dur_f": int(out_f - in_f)})
            if tr:
                ev["transform"] = tr
            if beat.get("transition_dur_f") and ri == 0:
                ev["transition_dur_f"] = int(beat["transition_dur_f"])
            video.append(ev)
            dialogue.append({"id": f"d{len(dialogue) + 1}", "src": src, "in_f": int(in_f), "out_f": int(out_f),
                             "at_f": t, "split_edit": "none", "chain": "voice_default"})
            t += int(out_f - in_f)
        if beat.get("split") and bi > 0:
            apply_split(video, dialogue, beat["split"], int(beat.get("split_f", round(fps / 3))), len(runs))
    edl = {"version": 1,
           "project": {"fps": media["fps"], "width": int(W), "height": int(H), "platform": platform, "type": typ,
                       "style": paper.get("style"), "profile": paper.get("profile"),
                       "target_duration_f": int(round(float(paper.get("target_duration_s", 0)) * fps)) or None,
                       "commercial": bool(paper.get("commercial", True)),
                       "kit": paper.get("kit", {"sound": "pve_synth_v2", "type": "default", "icons": None})},
           "tracks": {"video": video, "dialogue": dialogue, "broll": [], "music": [], "sfx": [],
                      "captions": None, "graphics": []},
           "color": paper.get("color", {"correction": "auto", "match_shots": True, "look": None, "strength": 0.0}),
           "master": paper.get("master", {"lufs": -14, "true_peak_db": -1}),
           "notes": notes, "assumptions": paper.get("assumptions", [])}
    if edl["project"]["target_duration_f"] is None:
        del edl["project"]["target_duration_f"]
    # captions
    if paper.get("captions") is not False:
        cap = {"template": "pop_3word" if H > W else "clean_line", "source": "transcript", "highlight": "keyword",
               "safe_zone": platform, "language": (ana["files"][beats[0]["src"]].get("transcript") or {}).get("language") or "en"}
        if prof.get("caption_template"):
            cap["template"] = prof["caption_template"]
        cap.update(paper.get("captions") or {})
        edl["tracks"]["captions"] = cap
    # word -> timeline frame for graphics, sfx, broll anchored on words
    def word_t(src, wi):
        for d in dialogue:
            w = wbs[src][wi]
            if d["src"] == src and d["in_f"] <= w["s_f"] < d["out_f"]:
                return d["at_f"] + w["s_f"] - d["in_f"]
        raise ValueError(f"word {wi} of {src} is not in the cut")
    for g in paper.get("graphics", []):
        g = dict(g)
        if "at_word" in g:
            g["at_f"] = int(word_t(g.pop("src", beats[0]["src"]), g.pop("at_word")))
        if "dur_s" in g:
            g["dur_f"] = int(round(float(g.pop("dur_s")) * fps))
        edl["tracks"]["graphics"].append(g)
    for b in paper.get("broll", []):
        b = dict(b)
        if "at_word" in b:
            b["at_f"] = int(word_t(b.pop("src_word", beats[0]["src"]), b.pop("at_word")))
        if "dur_s" in b:
            b["dur_f"] = int(round(float(b.pop("dur_s")) * fps))
        b.setdefault("id", f"b{len(edl['tracks']['broll']) + 1}")
        edl["tracks"]["broll"].append(b)
    for m in paper.get("music", []) if isinstance(paper.get("music"), list) else ([paper["music"]] if paper.get("music") else []):
        m = {"at_f": 0, "duck": {"under": "dialogue", "depth_db": -20, "attack_ms": 80, "release_ms": 400},
             "end": "bar", **m}
        edl["tracks"]["music"].append(m)
    for s in paper.get("sfx", []) if isinstance(paper.get("sfx"), list) else []:
        s = dict(s)
        if "at_word" in s:
            s["at_f"] = int(word_t(s.pop("src", beats[0]["src"]), s.pop("at_word")))
        edl["tracks"]["sfx"].append(s)
    for phrase in prof.get("never_cut", []):          # segments the creator never wants cut
        toks = phrase.lower().split()
        for src, ws in wbs.items():
            low = [w["w"].lower().strip(".,!?") for w in ws]
            for i in range(len(low) - len(toks) + 1):
                if low[i:i + len(toks)] == toks:
                    kept = [any(d["src"] == src and d["in_f"] <= ws[k]["s_f"] < d["out_f"] for d in dialogue)
                            for k in range(i, i + len(toks))]
                    if any(kept) and not all(kept):
                        notes.append(f"WARNING: never-cut phrase '{phrase}' is partly removed in {src} (word {i})")
    if paper.get("pattern_interrupts") == "auto":
        add_interrupts(edl, ana, wbs, style, fps, notes)
    fit_zoom_budget(edl, media, notes)
    if paper.get("sfx") == "auto":
        edl["tracks"]["sfx"] = auto_sfx(edl, style, fps)
    return edl


def peak_zoom(ev: dict) -> float:
    from render import zoom_at
    marks = {0, event_len(ev) - 1} | {t["at_f"] + t.get("dur_f", 6) for t in ev.get("transform", [])}
    return max(zoom_at(ev, k) for k in marks if 0 <= k < event_len(ev)) if event_len(ev) else 1.0


def fit_zoom_budget(edl: dict, media: dict, notes: list) -> None:
    """Scale each event's framing (reframe zoom and every transform, keeping their ratios) so the
    total upscale from the source never passes UPSCALE_LIMIT. A 720p source in a 1080p frame is
    already 1.5x before any punch-in, so it gets a smaller zoom budget than 4K footage."""
    W, H = edl["project"]["width"], edl["project"]["height"]
    items = {it["id"]: it for it in media["items"]}
    fitted = []
    for ev in edl["tracks"]["video"]:
        v = (items.get(ev["src"]) or {}).get("video") or {}
        sw, sh = v.get("display_width"), v.get("display_height")
        if not sw:
            continue
        bw = sh * W / H if sw / sh > W / H else sw          # widest crop of the target aspect
        budget = 0.99 * UPSCALE_LIMIT * bw / W                 # max zoom on top of the base fit (1% under the QC limit: scales are rounded)
        peak = peak_zoom(ev)
        if peak <= budget:
            continue
        if budget <= 1.0:
            k = 0.0
        else:
            k = math.log(budget) / math.log(peak)
        rf = ev.setdefault("reframe", {})
        rf["zoom"] = round(max(1.0, float(rf.get("zoom", 1.0)) ** k), 3)
        for t in ev.get("transform", []):
            t["scale"] = round(max(1.0, float(t.get("scale", 1.15)) ** k), 3)
        fitted.append(ev["id"])
    if fitted:
        notes.append(f"Framing scaled down in {len(fitted)} event(s) ({', '.join(fitted)}) to keep upscaling "
                     f"within {UPSCALE_LIMIT}x of the source resolution")


def add_interrupts(edl: dict, ana: dict, wbs: dict, style: dict, fps: Fraction, notes: list) -> None:
    """Keep every stretch without a visible change under the style's limit, with punch-ins that land
    on a word start. Scale changes toggle (in, out, in) so framing never creeps tighter and tighter."""
    from lib.viral import DEFAULT_MAX_STATIC_S, static_gaps
    W, H = edl["project"]["width"], edl["project"]["height"]
    limit = float(style_value(style, "structure.max_no_change_s", DEFAULT_MAX_STATIC_S["short" if H > W else "long"]))
    limit_f = int(limit * fps)
    scale = min(float(style_value(style, "punch_in_scale", PUNCH_SCALE) or PUNCH_SCALE), PUNCH_SCALE)
    added = 0
    for _ in range(50):
        gaps = [(a, b) for a, b in static_gaps(edl, ana) if b - a > limit_f]
        if not gaps:
            break
        a, b = gaps[0]
        mid = (a + b) // 2
        ev = next(e for e in edl["tracks"]["video"] if e["at_f"] <= mid < e["at_f"] + event_len(e))
        mid_src = ev["in_f"] + mid - ev["at_f"]
        lo_src, hi_src = ev["in_f"] + (a - ev["at_f"]) + 3, ev["in_f"] + (b - ev["at_f"]) - 3
        starts = [w["s_f"] for w in wbs.get(ev["src"], []) if max(ev["in_f"] + 3, lo_src) < w["s_f"] < min(ev["out_f"] - 3, hi_src)]
        if not starts:
            notes.append(f"No word start to hang a framing change on between {a} and {b}; stretch left as is")
            break
        s = min(starts, key=lambda x: abs(x - mid_src))
        rel = s - ev["in_f"] - 1
        tr = ev.setdefault("transform", [])
        depth = sum(1 for t in tr if t["at_f"] < rel and t["type"] == "punch_in") - \
            sum(1 for t in tr if t["at_f"] < rel and t["type"] == "punch_out")
        tr.append({"at_f": rel, "type": "punch_out" if depth > 0 else "punch_in", "scale": scale,
                   "ease": "out_cubic", "dur_f": max(2, round(PUNCH_DUR_S * fps)), "auto": True})
        tr.sort(key=lambda t: t["at_f"])
        depth = 0                      # re-toggle in timeline order: an earlier insert must not stack
        for t in tr:
            if t.get("auto"):
                t["type"] = "punch_out" if depth > 0 else "punch_in"
            depth += 1 if t["type"] == "punch_in" else -1 if t["type"] == "punch_out" else 0
        added += 1
    if added:
        notes.append(f"Added {added} pattern-interrupt framing change(s): no stretch longer than {limit:.1f} s "
                     "without a visible change")


def rec_len(media: dict, src: str) -> int:
    return next((it["duration_f"] for it in media["items"] if it["id"] == src), 10**9)


def apply_split(video, dialogue, kind, n, runs_in_beat):
    """J-cut: picture of the new beat arrives n frames after its sound. L-cut: n frames before."""
    k = len(video) - runs_in_beat
    prev, cur = video[k - 1], video[k]
    sign = 1 if kind == "j_cut" else -1
    if cur["out_f"] - cur["in_f"] - sign * n < 2 or prev["out_f"] - prev["in_f"] + sign * n < 2:
        return
    prev["out_f"] += sign * n
    cur["in_f"] += sign * n
    cur["at_f"] += sign * n
    for d in dialogue[k:k + 1]:
        d["split_edit"] = kind


def auto_sfx(edl: dict, style: dict, fps: Fraction) -> list[dict]:
    """Sound on transitions and graphic entrances, thinned to the style's SFX density."""
    per_min = style_value(style, "audio.sfx_per_min", None)
    dur_min = timeline_len(edl) / float(fps) / 60
    budget = None if per_min is None else max(1, int(round(per_min * dur_min)))
    out = []
    for ev in edl["tracks"]["video"]:
        tr = ev.get("transition_in", "cut")
        if tr in ("whip", "zoom"):
            out.append({"asset": "kit:whoosh_short", "at_f": ev["at_f"], "gain_db": -16, "align": "peak",
                        "role": "transition_whoosh", "reason": f"{tr} transition into {ev['id']}"})
        for x in ev.get("transform", []):
            if x["type"] == "punch_in":
                out.append({"asset": "kit:click_soft", "at_f": ev["at_f"] + x["at_f"], "gain_db": -24, "align": "peak",
                            "role": "click", "reason": f"accent on the punch-in in {ev['id']}"})
    for g in edl["tracks"].get("graphics", []):
        out.append({"asset": "kit:pop_soft", "at_f": g["at_f"], "gain_db": -18, "align": "peak", "role": "text_pop",
                    "reason": f"{g['component']} entrance"})
    for b in edl["tracks"].get("broll", []):
        out.append({"asset": "kit:whoosh_short", "at_f": b["at_f"], "gain_db": -18, "align": "peak",
                    "role": "transition_whoosh", "reason": f"B-roll {b['id']} entry"})
    out.sort(key=lambda s: s["at_f"])
    if budget is not None and len(out) > budget:
        step = len(out) / budget
        out = [out[int(k * step)] for k in range(budget)]
    return out


# ----------------------------------------------------------------------------- check
def check(edl: dict, project: Path, fix: bool) -> tuple[dict, dict]:
    errors, warnings, fixed = [], [], []
    errors += schema_errors(edl)
    if errors:
        return edl, {"ok": False, "errors": errors, "warnings": warnings, "fixed": fixed}
    media = read_json(project / "media.json")
    ana = read_json(project / "analysis.json") if (project / "analysis.json").exists() else {"files": {}}
    fps = fps_of(edl)
    if parse_rate(media["fps"]) != fps:
        errors.append(f"EDL fps {edl['project']['fps']} differs from the project timeline rate {media['fps']}")
    items = {it["id"]: it for it in media["items"]}
    wbs = words_by_src(ana)
    vids = edl["tracks"]["video"]
    vids.sort(key=lambda e: e["at_f"])
    # media + frame math
    for ev in vids + (edl["tracks"].get("dialogue") or []):
        it = items.get(ev["src"])
        if it is None:
            errors.append(f"{ev['id']}: src '{ev['src']}' is not in media.json")
            continue
        src_path = project / it.get("render_src", it["path"]) if not Path(it.get("render_src", it["path"])).is_absolute() \
            else Path(it.get("render_src", it["path"]))
        if not src_path.exists():
            errors.append(f"{ev['id']}: media file missing: {src_path}")
        if ev["out_f"] <= ev["in_f"]:
            errors.append(f"{ev['id']}: out_f {ev['out_f']} <= in_f {ev['in_f']}")
        if ev["out_f"] > it["duration_f"]:
            if fix:
                ev["out_f"] = it["duration_f"]; fixed.append(f"{ev['id']}: out_f clamped to source end")
            else:
                errors.append(f"{ev['id']}: out_f {ev['out_f']} past the end of {ev['src']} ({it['duration_f']})")
    # cuts inside words
    # a cutaway (video event with cutaway: true) is picture only - the dialogue track carries the sound,
    # so its in/out points cannot cut a word
    for ev in [v for v in vids if not v.get("cutaway")] + (edl["tracks"].get("dialogue") or []):
        words = wbs.get(ev["src"]) or []
        for key in ("in_f", "out_f"):
            w = word_at(words, ev[key])
            if w is None:
                continue
            if fix:
                new = w["s_f"] if key == "in_f" else w["e_f"]
                if key == "in_f" and ev[key] - w["s_f"] > w["e_f"] - ev[key]:
                    new = w["e_f"]
                if key == "out_f" and w["e_f"] - ev[key] > ev[key] - w["s_f"]:
                    new = w["s_f"]
                fixed.append(f"{ev['id']}: {key} {ev[key]} was inside '{w['w']}'; moved to {new}")
                ev[key] = new
            else:
                errors.append(f"{ev['id']}: {key} {ev[key]} cuts inside the word '{w['w']}' ({w['s_f']}-{w['e_f']})")
        # clipped first consonant: fewer than 2 frames of air before the first word when the gap allows it
        first = next((w for w in words if w["s_f"] >= ev["in_f"]), None)
        if first and first["s_f"] < ev["out_f"] and first["s_f"] - ev["in_f"] < 2:
            prev = [w for w in words if w["e_f"] <= ev["in_f"]]
            if not prev or first["s_f"] - prev[-1]["e_f"] >= 4:
                warnings.append(f"{ev['id']}: only {first['s_f'] - ev['in_f']} frame(s) before '{first['w']}': first consonant may clip")
    # timeline packing
    t = 0
    for ev in vids:
        if ev["at_f"] != t:
            if fix:
                fixed.append(f"{ev['id']}: at_f {ev['at_f']} -> {t} (gap/overlap removed)")
                ev["at_f"] = t
            else:
                errors.append(f"{ev['id']}: starts at {ev['at_f']} but the previous event ends at {t} "
                              f"({'gap shows black' if ev['at_f'] > t else 'overlap'})")
        t = ev["at_f"] + event_len(ev)
    if fix and edl["tracks"].get("dialogue"):
        # keep dialogue locked to its picture unless it is an explicit split edit
        for v, d in zip(vids, edl["tracks"]["dialogue"]):
            if d.get("split_edit", "none") == "none" and d["src"] == v["src"] and d["in_f"] == v["in_f"]:
                d["at_f"] = v["at_f"]
    # reasons
    for name in ("video", "broll", "sfx"):
        for ev in edl["tracks"].get(name) or []:
            if not str(ev.get("reason", "")).strip():
                errors.append(f"{name} {ev.get('id', ev.get('asset'))}: no reason")
    for g in edl["tracks"].get("graphics") or []:
        if not g.get("reason"):
            warnings.append(f"graphic {g['component']} at {g['at_f']}: no reason")
    # split edits explicit
    for v, d in zip([v for v in vids if not v.get("cutaway")] if any(v.get("cutaway") for v in vids) else vids,
                    [] if any(v.get("cutaway") for v in vids) else edl["tracks"].get("dialogue") or []):
        if d["at_f"] != v["at_f"] and d.get("split_edit", "none") == "none":
            warnings.append(f"{d['id']}: dialogue offset from picture {v['id']} without split_edit set")
    # B-roll inside timeline
    total = timeline_len(edl)
    for b in edl["tracks"].get("broll") or []:
        if b["at_f"] + b["dur_f"] > total:
            errors.append(f"B-roll {b['id']} ends at {b['at_f'] + b['dur_f']}, after the timeline ({total})")
        if not (b.get("asset") or b.get("src")):
            errors.append(f"B-roll {b['id']}: no asset or src")
    tgt = edl["project"].get("target_duration_f")
    if tgt:
        if total > tgt * (1 + TARGET_SLACK):
            errors.append(f"duration {total / float(fps):.1f} s exceeds the target {tgt / float(fps):.1f} s")
        elif total < tgt * 0.5:
            warnings.append(f"duration {total / float(fps):.1f} s is under half the target {tgt / float(fps):.1f} s")
    lens = [event_len(v) for v in vids]
    stats = {"duration_f": total, "duration_s": round(total / float(fps), 2), "video_events": len(vids),
             "avg_shot_s": round(sum(lens) / len(lens) / float(fps), 2) if lens else 0,
             "min_shot_f": min(lens) if lens else 0}
    for v in vids:
        if event_len(v) < 3:
            warnings.append(f"{v['id']}: {event_len(v)}-frame event reads as a flash frame")
    return edl, {"ok": not errors, "errors": errors, "warnings": warnings, "fixed": fixed, "stats": stats}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft", help="paper edit -> EDL")
    d.add_argument("paper"); d.add_argument("--project", required=True); d.add_argument("--out", required=True)
    c = sub.add_parser("check", help="validate (and with --fix, repair) an EDL")
    c.add_argument("edl"); c.add_argument("--project", required=True); c.add_argument("--fix", action="store_true")
    c.add_argument("--out", help="write the normalised EDL here (default: in place with --fix)")
    c.add_argument("--report", help="check report JSON (default: next to the EDL)")
    df = sub.add_parser("diff", help="readable change list between two EDL versions (written to <b>.changes.md)")
    df.add_argument("a"); df.add_argument("b"); df.add_argument("--project", required=True)
    a = ap.parse_args()
    if a.cmd == "diff":
        from lib.edl import edl_diff
        try:
            ch = edl_diff(read_json(a.a), read_json(a.b))
        except FileNotFoundError as e:
            fail(str(e))
        out = Path(a.b).with_suffix(".changes.md")
        body = "\n".join(f"- {c}" for c in ch)
        out.write_text(f"# {Path(a.a).stem} -> {Path(a.b).stem}\n\n{body}\n", encoding="utf-8")
        for c in ch:
            log(f"  {c}")
        log(f"wrote {out}")
        return
    project = Path(a.project)
    if not (project / "media.json").exists():
        fail(f"{project / 'media.json'} not found; run ingest.py first")
    try:
        if a.cmd == "draft":
            edl = draft(read_json(a.paper), project)
            edl, rep = check(edl, project, fix=True)
            write_json(a.out, edl)
            write_json(Path(a.out).with_suffix(".check.json"), rep)
            log(f"wrote {a.out}: {rep['stats'].get('duration_s')} s, {rep['stats'].get('video_events')} events")
        else:
            edl = read_json(a.edl)
            edl, rep = check(edl, project, fix=a.fix)
            if a.fix or a.out:
                write_json(a.out or a.edl, edl)
            write_json(a.report or Path(a.edl).with_suffix(".check.json"), rep)
        for e in rep["errors"]:
            log(f"  [error] {e}")
        for w in rep["warnings"]:
            log(f"  [warn] {w}")
        for f in rep["fixed"]:
            log(f"  [fixed] {f}")
        if not rep["ok"]:
            fail(f"{len(rep['errors'])} error(s) in the EDL")
        log("EDL ok")
    except (ValueError, KeyError, FileNotFoundError) as e:
        fail(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
