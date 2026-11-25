"""Talking-head reel grammar (2026-11-25), from a 30 fps frame study of the owner's second reference (work/gvqo/ref2:
a Pinterest editor showcase; the edit is the "Final video" card, read at full resolution frame by frame).

What the reference does (frame counts at 30 fps; every number below is a STARTING DEFAULT read off those frames):
  - captions in two tiers: one or two small white lead words (bold sans, ~0.045 H) left of centre, then the key word
    big in a lime gradient with a soft glow (~0.085 H), overlapping the lead's baseline; a small white tail word under
    it, right-aligned. Lead words blur in one by one (3 frames); the key word shows dim for 1-2 frames and then slams
    to full (scale 1.25 -> 1, blur 12 -> 0, 3 frames). The group clears on the next phrase;
  - sometimes the key word is huge at the top and sits BEHIND the head (the matte in front of it);
  - a red hand-drawn strike is drawn through a key word (6 frames);
  - transition: vertical blinds, thin white stripes that rise over 2 frames to near white and fall over 3;
  - a punch-in close-up with a thin glowing ring round the head;
  - a REC viewfinder frame (corner brackets, a blinking red dot, a crosshair);
  - a small pill bubble beside the head that types its text;
  - dark-red glass banners with a warning triangle or a cross, typing word by word, stacking down;
  - a row of 3D glass tiles (Blender) popping in one by one with a flash, three then two;
  - a glass comment bar with a round avatar, typing letter by letter.

Overlays (times are frames from the overlay's start):
  Cap2     {lead: [[t, at]], hero: [t, at], tail: [[t, at]], y, x, size, lead_size, strike_at, align, top}
  Blinds   {peak}
  RingHead {cx, cy, r, at}
  RecFrame {at}
  Pill     {t, x, y, at, cps, tone red|green}
  Alerts   {rows: [{icon warn|x|ok, t, at}], y, tone}
  Comment  {t, at, y, avatar, cps}
  TileRow  {tiles: [{obj, still, at}], y, size}       at < 0: already there (shown as the still)
  Obj      {obj, x, y, size, at, media_start}
"""
from __future__ import annotations

from .hf_ae import esc
from .hf_design import Ctx, scene_file

LIME = "linear-gradient(180deg, #EEFF7A 0%, #CFF53E 42%, #9BDB2A 100%)"
GLOW = "drop-shadow(0 0 14px rgba(196,255,64,0.45)) drop-shadow(0 6px 18px rgba(0,0,0,0.55))"
F_HERO = "'Ketefa', 'Anton', sans-serif"
F_LEAD = "'Noto Sans Ethiopic', 'Poppins', sans-serif"


def _fonts(cx: Ctx):
    global F_HERO, F_LEAD
    b = cx.brand or {}
    F_HERO = b.get("font_hero", F_HERO)
    F_LEAD = b.get("font_lead", F_LEAD)


def _obj(name: str) -> str:
    return name if name.startswith("assets/") else f"assets/objects/{name}.webm"


def _vid(vid: str, src: str, start: float, dur: float, style: str, media_start: float = 0.0) -> str:
    ms = f' data-media-start="{media_start:.3f}"' if media_start else ""
    return (f'<video id="{vid}" class="clip" data-start="{start:.3f}" data-duration="{max(0.05, dur):.3f}"{ms} data-track-index="1" '
            f'src="{src}" muted playsinline style="{style}"></video>')


# ---------------------------------------------------------------------------------------------- captions
def ov_cap2(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    size = p.get("size", 0.085 * H)
    ls = p.get("lead_size", min(size * 0.5, 0.036 * H))
    y = p.get("y", 0.56) * H
    x = p.get("x", 0.5) * W
    lead = " ".join(f'<span id="{cid}-l{i}" style="display:inline-block;margin-right:0.22em">{esc(t)}</span>' for i, (t, _) in enumerate(p.get("lead", [])))
    tail = " ".join(f'<span id="{cid}-t{i}" style="display:inline-block;margin-left:0.22em">{esc(t)}</span>' for i, (t, _) in enumerate(p.get("tail", [])))
    ht, ha = p["hero"]
    strike = ""
    if p.get("strike_at") is not None:
        strike = (f'<svg id="{cid}-sk" viewBox="0 0 300 40" preserveAspectRatio="none" style="position:absolute;left:-4%;top:38%;width:108%;height:0.36em;overflow:visible">'
                  f'<path d="M 4 30 C 70 22, 160 18, 296 8" fill="none" stroke="#FF2B2B" stroke-width="7" stroke-linecap="butt" pathLength="1" '
                  f'stroke-dasharray="1" stroke-dashoffset="1" style="filter:drop-shadow(0 0 6px rgba(255,40,40,0.6))"/></svg>')
    sh = "text-shadow:0 3px 14px rgba(0,0,0,0.65);"
    G = GLOW
    if p.get("style") == "green":       # white key word on a dark green glass slab (the owner's brand colour)
        G = "drop-shadow(0 10px 22px rgba(0,0,0,0.5))"
        hero_css = (f"color:#FFFFFF;filter:{G};padding:0.06em 0.30em 0.02em;border-radius:0.16em;"
                    "background:linear-gradient(180deg, rgba(14,96,54,0.94) 0%, rgba(1,50,32,0.96) 60%, rgba(0,34,20,0.97) 100%);"
                    "box-shadow:inset 0 1px 0 rgba(160,255,200,0.35), inset 0 -2px 0 rgba(0,0,0,0.35);border:1px solid rgba(120,230,170,0.28)")
    else:
        hero_css = f"background:{LIME};-webkit-background-clip:text;background-clip:text;color:transparent;filter:{G};padding:0 0.04em"
    body = (f'<div style="position:absolute;left:{x:.0f}px;top:{y:.0f}px;transform:translate(-50%,-50%)"><div id="{cid}-g" style="text-align:center;white-space:nowrap">'
            f'<div style="font-family:{F_LEAD};font-weight:700;font-size:{ls:.0f}px;line-height:1;color:#fff;{sh}text-align:{p.get("lead_align", "left")};'
            f'margin-bottom:-{ls * 0.18:.0f}px;padding-left:0.3em">{lead}</div>'
            f'<div style="position:relative;display:inline-block"><div id="{cid}-h" style="opacity:0;font-family:{F_HERO};font-size:{size:.0f}px;line-height:1.08;'
            f'{hero_css}">{esc(ht)}</div>{strike}</div>'
            f'<div style="font-family:{F_LEAD};font-weight:600;font-size:{ls * 0.9:.0f}px;line-height:1;color:#F2F2F2;{sh}text-align:right;margin-top:-{ls * 0.12:.0f}px;'
            f'padding-right:0.3em">{tail}</div></div></div>')
    js = []
    for i, (_, at) in enumerate(p.get("lead", [])):
        js.append(f'tl.fromTo("#{cid}-l{i}", {{ opacity: 0, y: 10, filter: "blur(8px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: {3 * fr:.3f}, ease: "power3.out" }}, {cx.s(at):.3f});')
    for i, (_, at) in enumerate(p.get("tail", [])):
        js.append(f'tl.fromTo("#{cid}-t{i}", {{ opacity: 0, y: -8, filter: "blur(8px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: {3 * fr:.3f}, ease: "power3.out" }}, {cx.s(at):.3f});')
    a = cx.s(ha)
    if a >= 2 * fr:                         # the key word shows dim for 2 frames before it slams in
        js.append(f'tl.fromTo("#{cid}-h", {{ opacity: 0.32, filter: "blur(2px) {G}" }}, {{ opacity: 0.32, duration: {2 * fr - 0.002:.3f}, immediateRender: false }}, {a - 2 * fr:.3f});')
    js += [
           f'tl.fromTo("#{cid}-h", {{ opacity: 0.32, scale: 1.25, filter: "blur(12px) {G}" }}, {{ opacity: 1, scale: 1, filter: "blur(0px) {G}", duration: {3 * fr:.3f}, ease: "power3.out", immediateRender: false }}, {a:.3f});',
           f'tl.to("#{cid}-g", {{ scale: 1.03, duration: {max(0.2, dur):.3f}, ease: "none" }}, 0);']
    if p.get("strike_at") is not None:
        js.append(f'draw("#{cid}-sk path", {cx.s(p["strike_at"]):.3f}, {6 * fr:.3f});')
    js.append(f'tl.to("#{cid}-g", {{ opacity: 0, filter: "blur(10px)", duration: {2 * fr:.3f}, ease: "power2.in" }}, {max(0, dur - 2 * fr):.3f});')
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- blinds
def ov_blinds(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Vertical-blinds white transition peaking at frame `peak` (reference frames 132-140 and 615-622)."""
    fr = 1 / cx.fps
    pk = cx.s(p.get("peak", 3))
    body = (f'<div id="{cid}-w" style="position:absolute;inset:0;opacity:0;background:rgba(255,255,255,0.0)"></div>'
            f'<div id="{cid}-s" style="position:absolute;inset:0;opacity:0;background:repeating-linear-gradient(90deg, rgba(255,255,255,0.95) 0px, rgba(255,255,255,0.95) 3px, '
            f'rgba(255,255,255,0.0) 3px, rgba(255,255,255,0.0) 8px)"></div>')
    js = [f'tl.to("#{cid}-s", {{ opacity: 1, duration: {2 * fr:.3f}, ease: "power2.in" }}, {max(0, pk - 2 * fr):.3f});',
          f'tl.to("#{cid}-w", {{ opacity: 1, backgroundColor: "rgba(255,255,255,0.75)", duration: {1 * fr:.3f} }}, {max(0, pk - fr):.3f});',
          f'tl.to("#{cid}-w", {{ opacity: 0, duration: {2 * fr:.3f} }}, {pk + fr:.3f});',
          f'tl.to("#{cid}-s", {{ opacity: 0, duration: {3 * fr:.3f}, ease: "power2.out" }}, {pk + fr:.3f});']
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- ring
def ov_ringhead(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A thin glowing ring round the head on a punch-in (reference 186-248): it draws on in 5 frames and breathes."""
    fr = 1 / cx.fps
    r = p.get("r", 360)
    cxp, cyp = p.get("cx", 0.5) * cx.W, p.get("cy", 0.36) * cx.H
    body = (f'<svg id="{cid}-r" viewBox="0 0 {2 * r + 80} {2 * r + 80}" style="position:absolute;left:{cxp - r - 40:.0f}px;top:{cyp - r - 40:.0f}px;'
            f'width:{2 * r + 80}px;height:{2 * r + 80}px;overflow:visible">'
            f'<circle cx="{r + 40}" cy="{r + 40}" r="{r}" fill="none" stroke="#FFF6E0" stroke-width="4" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" '
            f'transform="rotate(-90 {r + 40} {r + 40})" style="filter:drop-shadow(0 0 8px rgba(255,236,190,0.9)) drop-shadow(0 0 26px rgba(255,214,140,0.55))"/></svg>')
    a = cx.s(p.get("at", 0))
    js = [f'draw("#{cid}-r circle", {a:.3f}, {5 * fr:.3f});',
          f'tl.fromTo("#{cid}-r", {{ scale: 1.12, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: {5 * fr:.3f}, ease: "expo.out" }}, {a:.3f});',
          f'tl.to("#{cid}-r", {{ scale: 0.97, duration: {max(0.2, dur - a - 5 * fr):.3f}, ease: "sine.inOut" }}, {a + 5 * fr + 0.002:.3f});',
          f'tl.to("#{cid}-r", {{ opacity: 0, duration: {2 * fr:.3f} }}, {max(0, dur - 2 * fr):.3f});']
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- REC frame
def ov_recframe(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    m, arm, t = 56, 74, 4
    c = "rgba(255,255,255,0.85)"
    br = "".join(
        f'<i style="position:absolute;{v}:{m}px;{h}:{m}px;width:{arm}px;height:{arm}px;border-{v}:{t}px solid {c};border-{h}:{t}px solid {c}"></i>'
        for v, h in (("top", "left"), ("top", "right"), ("bottom", "left"), ("bottom", "right")))
    body = (f'<div id="{cid}-f" style="position:absolute;inset:0">{br}'
            f'<div style="position:absolute;left:{m + 30}px;top:{m + 26}px;display:flex;align-items:center;gap:12px;font:700 30px/1 Poppins, sans-serif;color:#fff;letter-spacing:0.06em">'
            f'<b id="{cid}-d" style="width:18px;height:18px;border-radius:50%;background:#FF2E2E;box-shadow:0 0 12px #FF2E2E"></b>REC</div>'
            f'<div style="position:absolute;right:{m + 18}px;bottom:{m + 18}px;width:44px;height:44px">'
            f'<i style="position:absolute;left:21px;top:0;width:3px;height:44px;background:{c}"></i><i style="position:absolute;top:21px;left:0;height:3px;width:44px;background:{c}"></i></div></div>')
    a = cx.s(p.get("at", 0))
    js = [f'tl.fromTo("#{cid}-f", {{ opacity: 0, scale: 1.06 }}, {{ opacity: 1, scale: 1, duration: {5 * fr:.3f}, ease: "expo.out" }}, {a:.3f});']
    t_ = a + 0.5
    while t_ < dur - 0.3:                     # the dot blinks once a second
        js.append(f'tl.set("#{cid}-d", {{ opacity: 0.15 }}, {t_:.3f});')
        js.append(f'tl.set("#{cid}-d", {{ opacity: 1 }}, {t_ + 0.5:.3f});')
        t_ += 1.0
    js.append(f'tl.to("#{cid}-f", {{ opacity: 0, duration: {3 * fr:.3f} }}, {max(0, dur - 3 * fr):.3f});')
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- typing helpers
def _typed(cid: str, key: str, text: str, at: float, cps: float, fr: float) -> tuple[str, list]:
    """Letters as spans that appear one by one (grapheme-safe for Ethiopic: one code point per syllable)."""
    spans = "".join(f'<span class="{cid}-{key}" style="opacity:0">{esc(ch) if ch != " " else "&nbsp;"}</span>' for ch in text)
    js = [f'tl.to(".{cid}-{key}", {{ opacity: 1, duration: 0.001, stagger: {1 / cps:.3f} }}, {at:.3f});']
    return spans, js


def ov_pill(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A small pill bubble beside the head that pops and types (reference 210-240)."""
    fr = 1 / cx.fps
    tone = {"red": "linear-gradient(90deg,#B8463A,#E07A63)", "green": "linear-gradient(90deg,#0C5A33,#2FA060)"}.get(p.get("tone", "red"))
    a = cx.s(p.get("at", 0))
    spans, js = _typed(cid, "c", p["t"], a + 4 * fr, p.get("cps", 18), fr)
    body = (f'<div id="{cid}-p" style="position:absolute;left:{p.get("x", 0.62) * cx.W:.0f}px;top:{p.get("y", 0.30) * cx.H:.0f}px;padding:14px 26px;border-radius:40px;'
            f'background:{tone};box-shadow:0 10px 30px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.35);font:600 {p.get("size", 34)}px/1.1 {F_LEAD};color:#fff;'
            f'white-space:nowrap;transform-origin:0% 50%">{spans}</div>')
    js = [f'tl.fromTo("#{cid}-p", {{ scale: 0.2, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: {5 * fr:.3f}, ease: "back.out(2.2)" }}, {a:.3f});'] + js
    js.append(f'tl.to("#{cid}-p", {{ opacity: 0, scale: 0.9, duration: {3 * fr:.3f} }}, {max(0, dur - 3 * fr):.3f});')
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


_ICON = {
    "warn": '<svg viewBox="0 0 24 24" width="38" height="38"><path d="M12 2 L23 21 H1 Z" fill="#FF3B3B"/><rect x="11" y="8" width="2.2" height="7" fill="#fff"/><rect x="11" y="16.6" width="2.2" height="2.2" fill="#fff"/></svg>',
    "x": '<svg viewBox="0 0 24 24" width="34" height="34"><path d="M4 4 L20 20 M20 4 L4 20" stroke="#fff" stroke-width="4" stroke-linecap="round"/></svg>',
    "ok": '<svg viewBox="0 0 24 24" width="34" height="34"><path d="M3 13 L9 19 L21 5" stroke="#CFF53E" stroke-width="4" fill="none" stroke-linecap="round"/></svg>',
}


def ov_alerts(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Dark glass banners with an icon, typing word by word, stacking down (reference 306-445)."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    bg = {"red": "linear-gradient(90deg, rgba(70,6,8,0.92) 0%, rgba(150,14,18,0.78) 45%, rgba(90,8,10,0.35) 100%)",
          "green": "linear-gradient(90deg, rgba(2,30,16,0.92) 0%, rgba(8,90,45,0.78) 45%, rgba(4,50,26,0.35) 100%)"}[p.get("tone", "red")]
    body, js = [], []
    y0 = p.get("y", 0.60) * H
    for i, row in enumerate(p["rows"]):
        a = cx.s(row["at"])
        words = row["t"].split(" ")
        ws = "".join(f'<span id="{cid}-r{i}w{k}" style="display:inline-block;margin-right:0.28em;opacity:0">{esc(w)}</span>' for k, w in enumerate(words))
        body.append(f'<div id="{cid}-r{i}" style="position:absolute;left:{W * 0.09:.0f}px;width:{W * 0.82:.0f}px;top:{y0 + i * 112:.0f}px;height:92px;border-radius:18px;'
                    f'background:{bg};border:1px solid rgba(255,120,120,0.22);box-shadow:0 16px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.12);'
                    f'display:flex;align-items:center;gap:22px;padding-left:30px;font:600 38px/1 {F_LEAD};color:#fff">{_ICON[row.get("icon", "warn")]}<div>{ws}</div></div>')
        js.append(f'tl.fromTo("#{cid}-r{i}", {{ opacity: 0, x: -60, filter: "blur(10px)" }}, {{ opacity: 1, x: 0, filter: "blur(0px)", duration: {5 * fr:.3f}, ease: "expo.out" }}, {a:.3f});')
        span = max(0.1, cx.s(row.get("type_f", 14)))
        for k in range(len(words)):
            js.append(f'tl.fromTo("#{cid}-r{i}w{k}", {{ opacity: 0, y: 8 }}, {{ opacity: 1, y: 0, duration: {2 * fr:.3f} }}, {a + 3 * fr + span * k / max(1, len(words)):.3f});')
        if row.get("strike_at") is not None:
            body[-1] = body[-1][:-6] + f'<i id="{cid}-x{i}" style="position:absolute;left:90px;right:40px;top:46px;height:4px;background:#FF4A4A;transform-origin:0 50%"></i></div>'
            js.append(f'tl.fromTo("#{cid}-x{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {5 * fr:.3f}, ease: "power2.out" }}, {cx.s(row["strike_at"]):.3f});')
            js.append(f'tl.to("#{cid}-r{i}", {{ opacity: 0.45, duration: {6 * fr:.3f} }}, {cx.s(row["strike_at"]) + 5 * fr:.3f});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, y: 20, duration: {3 * fr:.3f} }}, {max(0, dur - 3 * fr):.3f});')
    return scene_file(cx, cid, cx.H, "", f'<div id="{cid}-all" style="position:absolute;inset:0">{"".join(body)}</div>', "\n".join(js), transparent=True)


def ov_comment(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A glass comment bar with a round avatar that types its text (reference 624-690)."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    a = cx.s(p.get("at", 0))
    spans, js = _typed(cid, "c", p["t"], a + 5 * fr, p.get("cps", 14), fr)
    av = p.get("avatar")
    avh = (f'<div id="{cid}-a" style="width:96px;height:96px;border-radius:50%;overflow:hidden;flex:none;box-shadow:0 0 0 3px rgba(255,255,255,0.25)">'
           f'<img src="{av}" alt="" style="width:100%;height:100%;object-fit:cover"></div>') if av else ""
    body = (f'<div id="{cid}-c" style="position:absolute;left:{W * 0.06:.0f}px;top:{p.get("y", 0.62) * H:.0f}px;display:flex;align-items:center;gap:20px">{avh}'
            f'<div id="{cid}-b" style="width:{W * 0.70:.0f}px;height:96px;border-radius:20px;display:flex;align-items:center;padding-left:34px;'
            f'background:linear-gradient(90deg, rgba(1,50,32,0.95) 0%, rgba(10,92,52,0.88) 55%, rgba(1,40,24,0.45) 100%);border:1px solid rgba(120,230,170,0.25);'
            f'box-shadow:0 18px 44px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.15);font:600 44px/1 {F_LEAD};color:#F6FFE9;white-space:nowrap;overflow:hidden">{spans}'
            f'<b id="{cid}-k" style="display:inline-block;width:3px;height:44px;background:#E9FFD0;margin-left:4px"></b></div></div>')
    js = [f'tl.fromTo("#{cid}-c", {{ opacity: 0, y: 30, filter: "blur(10px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: {6 * fr:.3f}, ease: "expo.out" }}, {a:.3f});'] + js
    t_ = a
    while t_ < dur - 0.2:
        js.append(f'tl.set("#{cid}-k", {{ opacity: 0 }}, {t_ + 0.27:.3f});')
        js.append(f'tl.set("#{cid}-k", {{ opacity: 1 }}, {t_ + 0.54:.3f});')
        t_ += 0.54
    js.append(f'tl.to("#{cid}-c", {{ opacity: 0, duration: {3 * fr:.3f} }}, {max(0, dur - 3 * fr):.3f});')
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- 3D (Blender)
def ov_tilerow(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A row of Blender glass tiles under the speaker. A tile with `at` >= 0 plays its pop-in render from then; one
    with `at` < 0 was introduced earlier and stands as its settled still."""
    W, H = cx.W, cx.H
    tiles = p["tiles"]
    sz = p.get("size", 320)
    th = sz * 600 / 560
    gap = -18
    total = len(tiles) * sz + (len(tiles) - 1) * gap
    x0 = (W - total) / 2
    y = p.get("y", 0.80) * H - th / 2
    body = []
    for i, t in enumerate(tiles):
        x = x0 + i * (sz + gap)
        st = f"position:absolute;left:{x:.0f}px;top:{y:.0f}px;width:{sz}px;height:{th:.0f}px"
        if t.get("at", 0) < 0:
            body.append(f'<img src="assets/images/{t["still"]}" alt="" style="{st}">')
        else:
            a = cx.s(t["at"])
            body.append(_vid(f"{cid}-v{i}", _obj(t["obj"]), a, dur - a, st))
    js = [f'tl.fromTo("#{cid}-all", {{ opacity: 1 }}, {{ opacity: 0, y: 30, duration: {3 / cx.fps:.3f} }}, {max(0, dur - 3 / cx.fps):.3f});']
    return scene_file(cx, cid, cx.H, "", f'<div id="{cid}-all" style="position:absolute;inset:0">{"".join(body)}</div>', "\n".join(js), transparent=True)


def ov_obj(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """One Blender object (alpha webm) at a place on the frame."""
    sz = p.get("size", 400)
    x, y = p.get("x", 0.5) * cx.W - sz / 2, p.get("y", 0.5) * cx.H - sz / 2
    a = cx.s(p.get("at", 0))
    body = _vid(f"{cid}-v", _obj(p["obj"]), a, dur - a, f"position:absolute;left:{x:.0f}px;top:{y:.0f}px;width:{sz}px;height:{sz}px", p.get("media_start", 0.0))
    js = [f'tl.to("#{cid}-w", {{ opacity: 0, duration: {3 / cx.fps:.3f} }}, {max(0, dur - 3 / cx.fps):.3f});']
    return scene_file(cx, cid, cx.H, "", f'<div id="{cid}-w" style="position:absolute;inset:0">{body}</div>', "\n".join(js), transparent=True)


def ov_film(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A full-screen opaque 3D shot (Blender render as mp4). It arrives through a short zoom-blur (scale 1.10 -> 1, blur
    16 -> 0 over 6 frames) and leaves through a zoom-through (scale 1 -> 1.35, blur 0 -> 22, brightness 1 -> 1.6 over the
    last `out_f` frames, 5 by default, expo.in), so the next shot can land pushed in and carry the motion on.
    `out_f: 0` gives a hard cut."""
    fr = 1 / cx.fps
    src = p["src"] if p["src"].startswith("assets/") else f"assets/objects/{p['src']}"
    body = (f'<div id="{cid}-w" style="position:absolute;inset:0;background:#00140A;opacity:0">'
            + _vid(f"{cid}-v", src, 0, dur, "position:absolute;inset:0;width:100%;height:100%;object-fit:cover", p.get("media_start", 0.0)) + '</div>')
    n = p.get("in_f", 6)
    js = [f'tl.fromTo("#{cid}-w", {{ opacity: 0, scale: 1.10, filter: "blur(16px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: {n * fr:.3f}, ease: "expo.out" }}, 0);']
    m = p.get("out_f", 5)
    if m:
        js.append(f'tl.fromTo("#{cid}-w", {{ scale: 1, filter: "blur(0px) brightness(1)" }}, {{ scale: 1.35, filter: "blur(22px) brightness(1.6)", '
                  f'duration: {m * fr:.3f}, ease: "expo.in", immediateRender: false }}, {max(n * fr, dur - m * fr):.3f});')
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


def _fonted(fn):
    def run(cx, cid, dur, p):
        _fonts(cx)
        return fn(cx, cid, dur, p)
    run.__name__, run.__doc__ = fn.__name__, fn.__doc__
    return run


OVERLAYS = {k: _fonted(v) for k, v in {
    "Cap2": ov_cap2, "Blinds": ov_blinds, "RingHead": ov_ringhead, "RecFrame": ov_recframe, "Pill": ov_pill, "Alerts": ov_alerts,
    "Comment": ov_comment, "TileRow": ov_tilerow, "Obj": ov_obj, "Film": ov_film}.items()}
