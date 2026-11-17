"""Captions and simple graphics as an ASS subtitle file rendered by libass at the final encode.

Templates (references/craft-motion-type.md):
  pop_3word   short-form: 1-3 words per card, pop in with overshoot and settle, keyword in the accent colour
  bold_1word  one word per card, larger; for very fast styles
  clean_line  long-form: full readable lines, at most two lines, fade in/out

Graphics components drawn here when Remotion is not used: Title, Callout, LowerThird, ProgressBar.
Ethiopic text: cards are limited by syllables (each Ethiopic character is one syllable).
Also writes SRT/VTT from the same cards so burned-in and sidecar captions always agree.
"""
from __future__ import annotations

import re
from fractions import Fraction

PAUSE_BREAK_S = 0.3          # a pause this long starts a new card
CARD_TAIL_S = 0.2            # a card stays this long after its last word when a pause follows
MAX_CHARS = {"pop_3word": 16, "bold_1word": 12, "clean_line": 42}
MAX_WORDS = {"pop_3word": 3, "bold_1word": 1, "clean_line": 14}
ETHIOPIC_SYLLABLES = {"pop_3word": 8, "bold_1word": 5, "clean_line": 24}
SAFE = {  # fraction of height for the caption baseline area; bottom/right UI of short-form apps
    "shorts": 0.70, "youtube_shorts": 0.70, "tiktok": 0.68, "reels": 0.68, "instagram_reels": 0.68,
    "youtube": 0.88, "instagram_feed": 0.85, "linkedin": 0.85, "podcast": 0.88}
SIDE_MARGIN = 0.08           # left/right margin; short-form UI covers ~12 % on the right
ETHIOPIC = re.compile(r"[ሀ-᎟ⶀ-⷟꬀-꬯]")


def _ass_color(hex_rgb: str, alpha: int = 0) -> str:
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _t(frames: int, fps: Fraction) -> str:
    cs = int(round(Fraction(frames) / fps * 100))
    h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _srt_t(frames: int, fps: Fraction, sep: str = ",") -> str:
    ms = int(round(Fraction(frames) / fps * 1000))
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def clean_word(w: str) -> str:
    return w.strip()


def make_cards(words: list[dict], fps: Fraction, template: str, end_f: int) -> list[dict]:
    """Group timeline words ({w, t_s, t_e}) into caption cards."""
    mw, mc = MAX_WORDS.get(template, 3), MAX_CHARS.get(template, 16)
    cards, cur = [], []
    def flush():
        if cur:
            cards.append({"words": list(cur), "s_f": cur[0]["t_s"], "e_f": cur[-1]["t_e"]})
            cur.clear()
    for k, w in enumerate(words):
        txt = clean_word(w["w"])
        if not txt:
            continue
        if cur:
            gap = Fraction(w["t_s"] - cur[-1]["t_e"]) / fps
            text_len = sum(len(x["w"]) + 1 for x in cur) + len(txt)
            eth = ETHIOPIC.search(txt)
            syl = sum(len(ETHIOPIC.findall(x["w"])) for x in cur) + len(ETHIOPIC.findall(txt))
            limit_hit = (syl > ETHIOPIC_SYLLABLES.get(template, 8)) if eth else (len(cur) >= mw or text_len > mc)
            if gap >= PAUSE_BREAK_S or limit_hit or re.search(r"[.!?,;:]$", cur[-1]["w"]):
                flush()
        cur.append({**w, "w": txt})
    flush()
    tail = int(round(CARD_TAIL_S * fps))
    for a, b in zip(cards, cards[1:]):
        a["e_f"] = b["s_f"] if b["s_f"] - a["e_f"] < tail * 2 else a["e_f"] + tail
    if cards:
        cards[-1]["e_f"] = min(end_f, cards[-1]["e_f"] + tail)
    return cards


def _is_key(w: str, keywords: set[str]) -> bool:
    return re.sub(r"[^\w']", "", w.lower()) in keywords


def ass_document(cards: list[dict], fps: Fraction, W: int, H: int, template: str, platform: str,
                 keywords: list[str], fonts: dict, colors: dict, highlight: str = "keyword",
                 graphics: list[dict] | None = None, avoid_boxes: list[tuple[int, int, list[float]]] | None = None,
                 position: str | None = None, card_y: dict | None = None) -> str:
    """avoid_boxes: (s_f, e_f, [x, y, w, h] normalised face box) - captions move off faces."""
    keys = {k.lower() for k in keywords}
    cap_font = fonts.get("caption", "Poppins ExtraBold")
    head_font = fonts.get("heading", "Anton")
    if any(ETHIOPIC.search(c["words"][0]["w"]) for c in cards if c["words"]):
        cap_font = fonts.get("ethiopic", "Noto Sans Ethiopic")
    text_c = _ass_color(colors.get("text", "#FFFFFF"))
    stroke_c = _ass_color(colors.get("stroke", "#000000"))
    accent = _ass_color(colors.get("primary", "#FFD400"))
    size = {"pop_3word": 0.058, "bold_1word": 0.07, "clean_line": 0.034}.get(template, 0.05) * H
    if W > H:
        size *= W / H * 0.75
    outline = max(2, round(size * 0.11))
    base_y = SAFE.get(platform, 0.8) if position in (None, "center_low", "safe") else \
        {"center": 0.5, "bottom": 0.82, "top": 0.2}.get(position, 0.7)
    margin_lr = int(W * SIDE_MARGIN)
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{cap_font},{size:.0f},{text_c},{accent},{stroke_c},&H64000000,-1,0,0,0,100,100,0,0,1,{outline},{max(1, outline // 2)},5,{margin_lr},{margin_lr},0,1",
        f"Style: Head,{head_font},{size * 1.35:.0f},{text_c},{accent},{stroke_c},&H64000000,0,0,0,0,100,100,1,0,1,{outline + 1},2,5,{margin_lr},{margin_lr},0,1",
        f"Style: Box,{cap_font},{size * 0.8:.0f},{_ass_color(colors.get('box_text', '#111111'))},{accent},{accent},&H00000000,-1,0,0,0,100,100,0,0,3,{round(size * 0.35)},0,5,{margin_lr},{margin_lr},0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    ev = []
    for c in cards:
        y = float((card_y or {}).get(str(c["s_f"]), base_y))
        for s, e, box in ((avoid_boxes or []) if str(c["s_f"]) not in (card_y or {}) else []):
            if s < c["e_f"] and c["s_f"] < e and box:
                face_bottom = box[1] + box[3]
                if box[1] - 0.04 < y < face_bottom + 0.04:
                    y = min(SAFE.get(platform, 0.8), face_bottom + 0.08)
        x, yy = W // 2, int(y * H)
        parts = []
        for w in c["words"]:
            t = w["w"].replace("{", "(").replace("}", ")")
            if template != "clean_line":
                t = t.upper()
            if highlight == "keyword" and _is_key(w["w"], keys):
                parts.append(r"{\c" + accent + "}" + t + r"{\c" + text_c + "}")
            else:
                parts.append(t)
        if highlight == "active_word" and template != "clean_line":
            # one event per word, the spoken word in the accent colour
            for i, w in enumerate(c["words"]):
                s = w["t_s"]; e = c["words"][i + 1]["t_s"] if i + 1 < len(c["words"]) else c["e_f"]
                txt = " ".join((r"{\c" + accent + "}" + p + r"{\c" + text_c + "}") if j == i else p
                               for j, p in enumerate([x_["w"].upper() for x_ in c["words"]]))
                anim = r"{\an5\pos(%d,%d)}" % (x, yy) if i else r"{\an5\pos(%d,%d)\fscx80\fscy80\t(0,90,\fscx106\fscy106)\t(90,150,\fscx100\fscy100)}" % (x, yy)
                ev.append(f"Dialogue: 1,{_t(s, fps)},{_t(e, fps)},Cap,,0,0,0,,{anim}{txt}")
            continue
        text = " ".join(parts)
        if template == "clean_line":
            anim = r"{\an2\pos(%d,%d)\fad(80,80)}" % (x, yy)
        else:
            # pop: anticipation (small), overshoot (106 %), settle (100 %) - never linear
            anim = r"{\an5\pos(%d,%d)\fscx78\fscy78\t(0,90,\fscx106\fscy106)\t(90,150,\fscx100\fscy100)}" % (x, yy)
        ev.append(f"Dialogue: 1,{_t(c['s_f'], fps)},{_t(c['e_f'], fps)},Cap,,0,0,0,,{anim}{text}")
    for g in graphics or []:
        ev += graphic_events(g, fps, W, H, size, accent, text_c)
    return "\n".join(head + ev) + "\n"


def graphic_events(g: dict, fps: Fraction, W: int, H: int, size: float, accent: str, text_c: str) -> list[str]:
    comp, p = g["component"], g.get("props", {})
    s, e = g["at_f"], g["at_f"] + g["dur_f"]
    txt = str(p.get("text", "")).replace("{", "(").replace("}", ")")
    if comp == "Title":
        y = int(H * p.get("y", 0.16))
        return [f"Dialogue: 2,{_t(s, fps)},{_t(e, fps)},Head,,0,0,0,,"
                r"{\an5\pos(%d,%d)\fscx70\fscy70\alpha&HFF&\t(0,120,\alpha&H00&\fscx104\fscy104)\t(120,200,\fscx100\fscy100)\fad(0,120)}%s"
                % (W // 2, y, txt.upper())]
    if comp == "Callout":
        x, y = int(W * p.get("x", 0.5)), int(H * p.get("y", 0.3))
        return [f"Dialogue: 2,{_t(s, fps)},{_t(e, fps)},Box,,0,0,0,,"
                r"{\an5\pos(%d,%d)\fscx60\fscy60\t(0,100,\fscx108\fscy108)\t(100,170,\fscx100\fscy100)\fad(0,100)}%s" % (x, y, txt)]
    if comp == "LowerThird":
        y = int(H * p.get("y", 0.62)); x1 = int(W * 0.08)
        sub = str(p.get("subtitle", ""))
        line = r"{\an4\move(%d,%d,%d,%d,0,220)\fad(0,150)}%s" % (x1 - 60, y, x1, y, txt)
        out = [f"Dialogue: 2,{_t(s, fps)},{_t(e, fps)},Box,,0,0,0,,{line}"]
        if sub:
            out.append(f"Dialogue: 2,{_t(s + 3, fps)},{_t(e, fps)},Cap,,0,0,0,,"
                       r"{\an4\fs%d\move(%d,%d,%d,%d,0,240)\fad(0,150)}%s" % (int(size * 0.55), x1 - 60, y + int(size * 1.1), x1, y + int(size * 1.1), sub))
        return out
    if comp == "ProgressBar":
        y = int(H * p.get("y", 0.985)); h = max(4, int(H * 0.006))
        dur_ms = int(Fraction(g["dur_f"]) / fps * 1000)
        shape = r"m 0 0 l %d 0 l %d %d l 0 %d" % (W, W, h, h)
        return [f"Dialogue: 0,{_t(s, fps)},{_t(e, fps)},Cap,,0,0,0,,"
                r"{\an7\pos(0,%d)\bord0\shad0\1c%s\clip(0,0,0,%d)\t(0,%d,\clip(0,0,%d,%d))\p1}%s"
                % (y, accent, H, dur_ms, W, H, shape)]
    return []


def srt_vtt(cards: list[dict], fps: Fraction) -> tuple[str, str]:
    srt, vtt = [], ["WEBVTT", ""]
    for k, c in enumerate(cards, 1):
        text = " ".join(w["w"] for w in c["words"])
        srt += [str(k), f"{_srt_t(c['s_f'], fps)} --> {_srt_t(c['e_f'], fps)}", text, ""]
        vtt += [f"{_srt_t(c['s_f'], fps, '.')} --> {_srt_t(c['e_f'], fps, '.')}", text, ""]
    return "\n".join(srt), "\n".join(vtt)


def line_cards(words: list[dict], fps: Fraction, end_f: int) -> list[dict]:
    """Readable sidecar captions (two lines max) regardless of the burned-in template."""
    return make_cards(words, fps, "clean_line", end_f)


# ----------------------------------------------------------------------------- phrase captions (design pass)
PHRASE_MAX_WORDS = 3        # measured: median 3-4 words per caption card in the premium references (2026-11-15)
PHRASE_GAP_S = 0.35         # STARTING DEFAULT: a pause longer than this starts a new phrase
PHRASE_TAIL_F = 10          # STARTING DEFAULT: frames a phrase stays after its last word when nothing follows


def phrase_groups(tw: list[dict], fps, emphasis=(), skip=(), hide=(), max_words: int = PHRASE_MAX_WORDS,
                  end_f: int | None = None) -> list[dict]:
    """Timeline words -> phrase caption groups for the Remotion Design pass.

    Each group: {"s", "e", "words": [{"w", "s", "emph"}]}. A phrase breaks at max_words, at
    sentence punctuation, or at a pause. Words in `skip` (normalised) are dropped (e.g. a known
    mis-transcription; a number drops the word starting on that frame); groups starting inside a `hide` span [s, e) are dropped because the scene
    on screen already carries the line."""
    norm = lambda w: re.sub(r"[^\w']", "", w.lower())
    emph = {norm(x) for x in emphasis}
    sk = {norm(x) for x in skip if isinstance(x, str)}
    sk_at = {int(x) for x in skip if not isinstance(x, str)}      # a number = the word starting on that timeline frame
    gap = int(round(PHRASE_GAP_S * float(fps)))
    words = [w for w in tw if norm(w["w"]) not in sk and w["t_s"] not in sk_at]
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        brk = (len(cur) >= max_words or re.search(r"[.!?,።፣፤]$", w["w"]) or nxt is None or nxt["t_s"] - w["t_e"] > gap)
        if brk:
            groups.append(cur); cur = []
    out = []
    for gi, g in enumerate(groups):
        s = max(0, g[0]["t_s"] - 1)
        if any(a <= s < b for a, b in hide):
            continue
        nxt_s = groups[gi + 1][0]["t_s"] - 1 if gi + 1 < len(groups) else None
        e = g[-1]["t_e"] + PHRASE_TAIL_F
        if nxt_s is not None:
            e = min(e, nxt_s) if nxt_s - g[-1]["t_e"] <= gap else min(e, nxt_s)
        if end_f is not None:
            e = min(e, end_f)
        e = max(e, g[-1]["t_s"] + 4)
        out.append({"s": s, "e": e, "words": [{"w": x["w"], "s": x["t_s"], "emph": norm(x["w"]) in emph} for x in g]})
    return out
