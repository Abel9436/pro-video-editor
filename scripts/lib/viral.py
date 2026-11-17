"""Shared measures for retention_sim.py, virality_score.py and hook_variants.py.

All of this estimates risk; none of it predicts views. Thresholds come from the style
fingerprint when it has them, otherwise from the STARTING DEFAULTS below
(references/viral-retention.md).
"""
from __future__ import annotations

import difflib
import re
from fractions import Fraction

from .edl import event_len, fps_of, timeline_len, timeline_words

DEFAULT_MAX_STATIC_S = {"short": 4.0, "long": 10.0}      # STARTING DEFAULT: longest stretch without a visible change
DEFAULT_REHOOK_S = {"short": (5, 10), "long": (30, 60)}   # STARTING DEFAULT re-hook interval
DEAD_AIR_S = 0.6                                          # a gap in speech this long with nothing else happening
PAYOFF_MAX_S = {"short": 8.0, "long": 60.0}               # STARTING DEFAULT: first payoff must arrive by then
REPEAT_SIM = 0.6
HOOK_WORDS = {
    "contrarian": {"not", "never", "stop", "wrong", "myth", "lie", "bs", "nobody", "don't", "dont", "isn't", "won't", "can't"},
    "curiosity": {"secret", "why", "how", "what", "truth", "actually", "nobody", "hidden", "real"},
    "stakes": {"lose", "lost", "fail", "money", "million", "millionaire", "broke", "risk", "mistake", "guarantee", "guarantees"},
    "address": {"you", "your", "you're"},
}
WEAK_OPENERS = {"and", "but", "so", "that", "which", "because", "also", "then", "um", "uh"}


def target_kind(edl: dict) -> str:
    return "short" if edl["project"]["height"] > edl["project"]["width"] else "long"


def style_field(style: dict, name: str, default):
    v = ((style or {}).get("fields") or {}).get(name, {}).get("med")
    return default if v is None else v


def visual_changes(edl: dict, analysis: dict | None = None) -> list[tuple[int, str]]:
    """Timeline frames where the picture visibly changes, with what changed.
    Cuts that already exist inside the source footage (pre-edited material) count too."""
    ch = []
    for ev in edl["tracks"]["video"]:
        ch.append((ev["at_f"], f"cut to {ev['id']}"))
        for sh in ((analysis or {}).get("files", {}).get(ev["src"]) or {}).get("shots", []):
            if ev["in_f"] < sh["s_f"] < ev["out_f"]:
                ch.append((ev["at_f"] + int((sh["s_f"] - ev["in_f"]) / (ev.get("speed") or 1.0)),
                           f"source cut in {ev['id']}"))
        for t in ev.get("transform", []):
            ch.append((ev["at_f"] + t["at_f"], f"{t['type']} in {ev['id']}"))
    for b in edl["tracks"].get("broll") or []:
        ch += [(b["at_f"], f"B-roll {b['id']}"), (b["at_f"] + b["dur_f"], f"back from {b['id']}")]
    for g in edl["tracks"].get("graphics") or []:
        ch.append((g["at_f"], f"{g['component']} graphic"))
    return sorted(set(ch))


def static_gaps(edl: dict, analysis: dict | None = None) -> list[tuple[int, int]]:
    total = timeline_len(edl)
    pts = sorted({f for f, _ in visual_changes(edl, analysis)} | {0, total})
    return [(a, b) for a, b in zip(pts, pts[1:])]


def speech_gaps(edl: dict, analysis: dict) -> list[tuple[int, int]]:
    tw = timeline_words(edl, analysis)
    gaps = []
    if tw and tw[0]["t_s"] > 0:
        gaps.append((0, tw[0]["t_s"]))
    for a, b in zip(tw, tw[1:]):
        if b["t_s"] > a["t_e"]:
            gaps.append((a["t_e"], b["t_s"]))
    return gaps


def repeated_points(edl: dict, analysis: dict) -> list[tuple[int, int, str]]:
    from .speech import sentences
    tw = timeline_words(edl, analysis)
    if not tw:
        return []
    ws = [{**w, "i": k} for k, w in enumerate(tw)]
    sents = sentences(ws)
    out = []
    for i, a in enumerate(sents):
        for b in sents[i + 1:]:
            ta, tb = a["text"].lower().split(), b["text"].lower().split()
            if len(ta) >= 5 and len(tb) >= 5 and difflib.SequenceMatcher(None, ta, tb).ratio() >= REPEAT_SIM:
                out.append((tw[a["i_from"]]["t_s"], tw[b["i_from"]]["t_s"], b["text"][:60]))
    return out


def hook_features(text: str) -> dict:
    toks = [re.sub(r"[^\w']", "", t.lower()) for t in text.split()]
    feats = {k: sorted(set(toks) & v) for k, v in HOOK_WORDS.items()}
    feats["number"] = bool(re.search(r"\b\d+|\b(one|two|three|five|ten|hundred|thousand|million)\b", text.lower()))
    feats["question"] = text.strip().endswith("?")
    feats["weak_opener"] = bool(toks) and toks[0] in WEAK_OPENERS
    return feats


def sec(f: int, fps: Fraction) -> float:
    return round(float(Fraction(f) / fps), 2)
