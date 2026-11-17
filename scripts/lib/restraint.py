"""Restraint audit: the tells that make an edit read as machine-made rather than cut by an editor.

Reads only the EDL (design + tracks), so it runs before a render. Every finding is a warning, never a
fail: an editor can break any of these on purpose, and the reason belongs in the EDL notes.

Where a limit comes from (references/craft-human.md has the full sources):
- SFX, fx, punch-ins: practitioner advice that a whoosh/zoom on every cut "feels nervous"; the one
  number we found is "a punch-in no more than once every three or four cuts" (Evgeny Maximov, talking-
  head editing guide). The per-minute limits below are STARTING DEFAULTS, not measured.
- Emphasis: "only emphasise the punchlines" (editor review notes). Limit: STARTING DEFAULT.
- Concurrent layers: LottieFiles motion-design skill, "with 3+ elements, no more than 1/3 in active
  motion"; digicurator: "five things moving at once reads as noise". The count of 3 is a STARTING DEFAULT.
- Persistent decoration: "animate only what supports the idea, hold everything else still"
  (digicurator). The 50 % share is a STARTING DEFAULT.
"""
from __future__ import annotations

SFX_PER_MIN = 20.0           # STARTING DEFAULT: one placed sound every ~3 s on average (amh2 had 60/min, s25 46/min)
FX_PER_MIN = 4.0             # STARTING DEFAULT: flashes, zoom blurs, glitches
EMPH_PER_10S = 2.0           # STARTING DEFAULT: two emphasised caption words per 10 s
MAX_LAYERS = 3               # STARTING DEFAULT: graphics animating at once (captions count as one)
PERSIST_SHARE = 0.5          # STARTING DEFAULT: one overlay type on screen for more than half the video
MOVING_CAM_SHARE = 0.4       # STARTING DEFAULT: share of the runtime with an animated zoom or shake
SHAKES_PER_MIN = 2.0         # STARTING DEFAULT
PUNCH_EVERY_N_CUTS = 3       # sourced: "no more than once every three or four cuts" (Maximov)
MAX_REVEAL_MOVES = 2         # STARTING DEFAULT: a before/after wipe is spent once (in, and maybe out)
KARAOKE_STYLES = {"pop", "phrase", "slam", "neon", "keyword", "tier", "box", "lockup", "ink", "cine"}


def _total_f(edl: dict) -> int:
    v = edl["tracks"]["video"]
    return max((x["at_f"] + x["out_f"] - x["in_f"] for x in v), default=0)


def _w(cid: str, ok: bool, value, limit, detail: str, fix: str) -> dict:
    return {"id": f"restraint_{cid}", "status": "pass" if ok else "warn", "value": value, "limit": limit,
            "detail": detail, "fix": None if ok else fix}


def audit(edl: dict) -> list[dict]:
    fps = float(edl["project"].get("fps", 30))
    if isinstance(edl["project"].get("fps"), str) and "/" in edl["project"]["fps"]:
        a, b = edl["project"]["fps"].split("/")
        fps = float(a) / float(b)
    total = _total_f(edl)
    if total <= 0:
        return []
    mins = total / fps / 60.0
    d = edl.get("design") or {}
    T = edl["tracks"]
    out = []

    n = len(T.get("sfx") or [])
    out.append(_w("sfx", n / mins <= SFX_PER_MIN, round(n / mins, 1), SFX_PER_MIN,
                  f"{n} placed sound(s) in {total / fps:.1f} s ({n / mins:.1f}/min)",
                  "keep sounds for actions the viewer sees land (the reveal, a hit); drop whooshes under captions and panels"))

    fx = d.get("fx") or []
    out.append(_w("fx", len(fx) / mins <= FX_PER_MIN, round(len(fx) / mins, 1), FX_PER_MIN,
                  f"{len(fx)} flash/blur/glitch effect(s)", "cut straight; keep one effect for the moment that earns it"))

    emph = d.get("emphasis") or []
    lim = max(1, int(EMPH_PER_10S * total / fps / 10))
    out.append(_w("emphasis", len(emph) <= lim, len(emph), lim,
                  f"{len(emph)} emphasised word(s); {lim} allowed in {total / fps:.0f} s",
                  "emphasise the punchline only; when every line has a highlight nothing stands out"))

    style = d.get("caption_style", "phrase")
    has_caps = bool(d) and not d.get("no_captions")
    # word-by-word captions are the creator norm on shorts; the tell is when every word ALSO blurs, glows
    # and rises. Informational only.
    out.append({"id": "restraint_caption_style", "status": "pass", "value": style, "limit": None,
                "detail": f"caption style '{style}'" + (" (per-word reveal)" if style in KARAOKE_STYLES else ""), "fix": None})

    # one overlay type on screen for most of the runtime is decoration, not information
    share: dict[str, int] = {}
    for o in d.get("overlays") or []:
        share[o["type"]] = share.get(o["type"], 0) + max(0, o["e"] - o["s"])
    worst = max(share.items(), key=lambda kv: kv[1], default=(None, 0))
    sh = worst[1] / total
    out.append(_w("persistent_overlay", sh <= PERSIST_SHARE, round(sh, 2), PERSIST_SHARE,
                  f"{worst[0] or 'no overlay'} on screen {sh:.0%} of the video",
                  "show a graphic while it explains something, then take it off"))

    # graphics animating at the same frame
    spans = [(o["s"], o["e"]) for o in d.get("overlays") or []] + [(s["s"], s["e"]) for s in d.get("scenes") or []]
    spans += [(b["s"], b["e"]) for b in d.get("bg") or [] if b.get("color") == "raw" and b.get("labels")]
    peak, at = 0, 0
    for f in range(0, total, 3):
        k = sum(1 for s, e in spans if s <= f < e) + (1 if has_caps else 0)
        if k > peak:
            peak, at = k, f
    out.append(_w("concurrent_layers", peak <= MAX_LAYERS, peak, MAX_LAYERS,
                  f"up to {peak} graphic layers at once (at {at / fps:.1f} s, captions included)",
                  "one hero per moment: hide the captions or the panel, or move one of them to another beat"))

    cam = d.get("camera") or []
    moving = sum(c["e"] - c["s"] for c in cam if abs(c.get("z1", 1) - c.get("z0", 1)) > 0.005 or c.get("shake"))
    out.append(_w("moving_camera", moving / total <= MOVING_CAM_SHARE, round(moving / total, 2), MOVING_CAM_SHARE,
                  f"an animated zoom or shake runs {moving / total:.0%} of the time",
                  "hold most shots still; a slow push only where the shot is long and nothing else changes"))
    shakes = sum(1 for c in cam if c.get("shake"))
    out.append(_w("shake", shakes / mins <= SHAKES_PER_MIN, shakes, round(SHAKES_PER_MIN * mins, 1),
                  f"{shakes} camera shake(s)", "keep shake for a physical impact, not a word"))

    cuts = len(T["video"])
    big = sum(1 for c in cam if max(c.get("z0", 1), c.get("z1", 1)) >= 1.12)
    lim_p = max(1, cuts // PUNCH_EVERY_N_CUTS)
    out.append(_w("punch_ins", big <= lim_p, big, lim_p,
                  f"{big} punch-in(s) (>= 1.12x) across {cuts} shot(s)",
                  "alternate plain and punched framing; punch on the key line, not every shot"))

    moves = sum(len(b.get("wipe") or []) for b in d.get("bg") or [] if b.get("color") == "raw")
    out.append(_w("reveal_spent_once", moves <= MAX_REVEAL_MOVES, moves, MAX_REVEAL_MOVES,
                  f"the before/after line moves {moves} time(s)",
                  "save the before/after for the payoff: one sweep, then let it land"))
    return out


def summary(items: list[dict]) -> dict:
    w = [i for i in items if i["status"] == "warn"]
    return {"checks": len(items), "warnings": len(w), "ids": [i["id"] for i in w]}
