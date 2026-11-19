"""Spec-sheet explainer kit for HyperFrames (2026-11-19): a branded 3D studio world that replaces the
speaker's backdrop, and dark-glass graphics that read like a competition spec sheet. Written for an
Amharic bodybuilding explainer (what Open Bodybuilding demands), kept generic: any "here is what X
takes" talking head fits it.

Overlays (times in frames, relative to the overlay start; positions 0-1 of the frame):
  World      the studio set alone, full frame: deep brand-colour space, LED slat walls in perspective,
             a travelling floor grid, a soft top light and seeded dust. Use it `behind: true` so the
             speaker stands in the set instead of the original backdrop.
  Ring       a dial ring that draws on behind the speaker's head (a halo that is also a zero): ticks,
             a lit arc, optional text running round it on a path, a slow 3D turn.
  Stat       a big rolling number (slot digits land on the value) with a label beside it.
  FlipCard   a dark-glass card that enters standing up and flips in 3D at a cue from one statement to
             its answer (front {kicker, title}, back {kicker, title, sub}).
  NextUp     a next-episode card: kicker, title, a progress line, and a follow pill that is pressed.
Scenes (`under: true`, played while camera `card` folds the footage aside):
  Meters     the world plus a 3D glass panel of rows; each row's segmented bar sits at a normal level,
             then slams to MAX on its cue; a row can carry a value that counts down to a figure.
  Divisions  the world plus a column that runs three beats: a growth curve with one marked point; a
             card that is struck out and stamped; then a stack of cards dealt in one by one.
Captions: captions_plate, phrase by phrase; each word rises out of a mask on its spoken frame and a
brand-colour plate lands under the word being said (karaoke plate), emphasis words in the accent.

Motion rules (references/craft-motion-design.md, "Finish"): one lens (PERSP), moves never reverse,
nothing bounces, exits push through or cut. Every number marked STARTING DEFAULT was set by eye on the
first edit that used it and isn't a measurement.
"""
from __future__ import annotations

import math
import random

from .hf_ae import esc
from .hf_design import Ctx, scene_file
from .hf_explainer import PERSP
from .hf_objects import objvid

TITLE, BODY, ACCENT_FONT = "'Tsega Elto', 'Difres', sans-serif", "'Difres', sans-serif", "'Nael Tarik', serif"
META = "'Hanken Grotesk', 'Difres', sans-serif"
PLATE_IN_S = 0.14     # STARTING DEFAULT: the caption plate's scale-in under each spoken word
SEGMENTS = 14         # STARTING DEFAULT: segments in a meter bar


def _c(cx: Ctx) -> dict:
    b = cx.brand
    return {"title": b.get("font_title", TITLE), "body": b.get("font_body", BODY), "acc_font": b.get("font_script", ACCENT_FONT),
            "meta": b.get("font_meta", META), "brand": b.get("brand", "#0E7A43"), "mint": b.get("glow", "#8BF5B8"),
            "gold": b.get("accent", "#E8C268"), "deep": b.get("ink", "#03100A"), "alert": b.get("alert", "#FF6B5A")}


def _glass(C: dict, alpha: float = 0.62) -> str:
    return (f"background:linear-gradient(160deg, rgba(20,60,38,{alpha}) 0%, rgba(4,18,11,{alpha + 0.16:.2f}) 100%);"
            f"border:1.5px solid rgba(139,245,184,0.28);border-radius:30px;backdrop-filter:blur(18px);"
            f"box-shadow:inset 0 1.5px 0 rgba(255,255,255,0.16),0 40px 90px rgba(0,0,0,0.55),0 0 60px rgba(14,122,67,0.25)")


# ------------------------------------------------------------------------------------------ the world
def world(cx: Ctx, cid: str, dur: float, seed: int = 5) -> tuple[str, str, list[str]]:
    """(css, body, js) of the studio set. Static CSS transforms sit on wrappers GSAP never touches; the
    motion is background travel, light breathing and dust drift, all one-way and deterministic."""
    C = _c(cx)
    W, H = cx.W, cx.H
    rnd = random.Random(seed)
    slat = (f"repeating-linear-gradient(90deg, rgba(139,245,184,0) 0px, rgba(139,245,184,0) 150px, rgba(139,245,184,0.20) 150px, "
            f"rgba(139,245,184,0.06) 162px, rgba(139,245,184,0) 176px, rgba(139,245,184,0) 260px)")
    css = f"""#{cid}-w {{ position:absolute; inset:0; overflow:hidden; background:radial-gradient(ellipse 80% 55% at 50% 30%, {C['brand']}cc 0%, #06301b 38%, {C['deep']} 78%), {C['deep']}; }}
#{cid}-wl, #{cid}-wr {{ position:absolute; top:-10%; width:{W}px; height:120%; perspective:{PERSP}px; }}
#{cid}-wl {{ left:-{W * 0.5:.0f}px; }} #{cid}-wr {{ right:-{W * 0.5:.0f}px; }}
#{cid}-wl > div, #{cid}-wr > div {{ position:absolute; inset:0; background:{slat}; -webkit-mask-image:linear-gradient(180deg, transparent 0%, #000 25%, #000 70%, transparent 100%); mask-image:linear-gradient(180deg, transparent 0%, #000 25%, #000 70%, transparent 100%); }}
#{cid}-wl > div {{ transform:rotateY(64deg); transform-origin:100% 50%; }}
#{cid}-wr > div {{ transform:rotateY(-64deg); transform-origin:0% 50%; }}
#{cid}-fl {{ position:absolute; left:-50%; width:200%; top:{H * 0.6:.0f}px; height:{H * 0.7:.0f}px; perspective:900px; }}
#{cid}-fl > div {{ position:absolute; inset:0; transform:rotateX(74deg); transform-origin:50% 0%;
  background-image:linear-gradient(rgba(139,245,184,0.22) 2px, transparent 2px), linear-gradient(90deg, rgba(139,245,184,0.22) 2px, transparent 2px);
  background-size:120px 120px; -webkit-mask-image:linear-gradient(180deg, transparent, #000 30%, #000 60%, transparent); mask-image:linear-gradient(180deg, transparent, #000 30%, #000 60%, transparent); }}
#{cid}-beam {{ position:absolute; left:{W * 0.5 - 520:.0f}px; top:-200px; width:1040px; height:{H * 0.9:.0f}px;
  background:radial-gradient(ellipse 50% 60% at 50% 0%, rgba(214,255,230,0.30) 0%, rgba(139,245,184,0.08) 45%, transparent 75%); filter:blur(20px); }}
#{cid}-vig {{ position:absolute; inset:0; background:radial-gradient(ellipse 75% 70% at 50% 42%, transparent 50%, rgba(0,0,0,0.6) 100%); }}
.{cid}-d {{ position:absolute; border-radius:50%; background:#d9ffe9; }}"""
    dots = []
    for i in range(34):
        x, y, r = rnd.random() * W, rnd.random() * H, 1.2 + rnd.random() * 3.4
        blur = "filter:blur(2px);" if r > 3.6 else ""
        dots.append(f'<div class="{cid}-d" id="{cid}-d{i}" style="left:{x:.0f}px;top:{y:.0f}px;width:{r:.1f}px;height:{r:.1f}px;opacity:{0.15 + rnd.random() * 0.45:.2f};{blur}"></div>')
    body = (f'<div id="{cid}-w"><div id="{cid}-beam"></div><div id="{cid}-wl"><div id="{cid}-wls"></div></div><div id="{cid}-wr"><div id="{cid}-wrs"></div></div>'
            f'<div id="{cid}-fl"><div id="{cid}-flg"></div></div>{"".join(dots)}<div id="{cid}-vig"></div></div>')
    js = [f'tl.fromTo("#{cid}-flg", {{ backgroundPosition: "0px 0px" }}, {{ backgroundPosition: "0px {120 * max(1, round(dur * 0.6))}px", duration: {dur:.3f}, ease: "none" }}, 0);',
          f'tl.fromTo("#{cid}-wls", {{ backgroundPosition: "0px 0px" }}, {{ backgroundPosition: "{-40 * dur:.0f}px 0px", duration: {dur:.3f}, ease: "none" }}, 0);',
          f'tl.fromTo("#{cid}-wrs", {{ backgroundPosition: "0px 0px" }}, {{ backgroundPosition: "{40 * dur:.0f}px 0px", duration: {dur:.3f}, ease: "none" }}, 0);',
          f'tl.fromTo("#{cid}-beam", {{ opacity: 0.75 }}, {{ opacity: 1, duration: {max(0.5, dur / 2):.3f}, ease: "sine.inOut", yoyo: true, repeat: 1 }}, 0);']
    for i in range(34):
        js.append(f'tl.fromTo("#{cid}-d{i}", {{ y: 0 }}, {{ y: {-(20 + (i * 37) % 70) * dur / 4:.0f}, duration: {dur:.3f}, ease: "none" }}, 0);')
    return css, body, js


def ov_world(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    css, body, js = world(cx, cid, dur, p.get("seed", 5))
    return scene_file(cx, cid, cx.H, css, body, "\n".join(js))


# ------------------------------------------------------------------------------------------- Ring
def ov_ring(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{x, y (centre 0-1), r (px), at (draw-on), lockAt (the arc lights up), text (runs round the ring),
    ticks (default 72), turn (deg of slow 3D turn)}. Sits behind the speaker so the head is inside it."""
    C = _c(cx)
    x, y, r = p.get("x", 0.5) * cx.W, p.get("y", 0.22) * cx.H, p.get("r", 380)
    at, lock = cx.s(p.get("at", 0)), cx.s(p.get("lockAt", p.get("at", 0) + 30))
    S = r * 2 + 220
    c = S / 2
    ticks = []
    n = p.get("ticks", 72)
    for i in range(n):
        a = i / n * 2 * math.pi
        L = 26 if i % 6 == 0 else 12
        x1, y1 = c + (r + 34) * math.cos(a), c + (r + 34) * math.sin(a)
        x2, y2 = c + (r + 34 + L) * math.cos(a), c + (r + 34 + L) * math.sin(a)
        ticks.append(f'<line class="{cid}-t" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="rgba(214,255,230,{0.75 if L > 12 else 0.4})" stroke-width="{4 if L > 12 else 2.5}" stroke-linecap="round"/>')
    tp = ""
    if p.get("text"):
        rt = r - 58
        tp = (f'<path id="{cid}-tp" d="M {c - rt:.1f},{c:.1f} a {rt:.1f},{rt:.1f} 0 1,1 {2 * rt:.1f},0 a {rt:.1f},{rt:.1f} 0 1,1 {-2 * rt:.1f},0" fill="none"/>'
              f'<text id="{cid}-tx" font-family="{C["body"]}" font-weight="600" font-size="34" letter-spacing="6" fill="rgba(214,255,230,0.7)">'
              f'<textPath href="#{cid}-tp">{esc(p["text"])}</textPath></text>')
    svg = (f'<svg width="{S:.0f}" height="{S:.0f}" viewBox="0 0 {S:.0f} {S:.0f}" style="overflow:visible">'
           f'<defs><linearGradient id="{cid}-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C["gold"]}"/><stop offset="0.5" stop-color="#fff4d6"/><stop offset="1" stop-color="{C["mint"]}"/></linearGradient></defs>'
           f'<circle cx="{c}" cy="{c}" r="{r + 12}" fill="none" stroke="rgba(214,255,230,0.18)" stroke-width="2"/>'
           f'<circle id="{cid}-arc" cx="{c}" cy="{c}" r="{r}" fill="none" stroke="url(#{cid}-g)" stroke-width="16" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" transform="rotate(-90 {c} {c})"/>'
           f'<g id="{cid}-ticks">{"".join(ticks)}</g><g id="{cid}-rot">{tp}</g></svg>')
    body = (f'<div id="{cid}-all" style="position:absolute;left:{x - S / 2:.0f}px;top:{y - S / 2:.0f}px;width:{S:.0f}px;height:{S:.0f}px">'
            f'<div id="{cid}-glow" style="position:absolute;inset:60px;border-radius:50%;box-shadow:0 0 120px 20px {C["gold"]}55, inset 0 0 80px {C["mint"]}33;opacity:0"></div>{svg}</div>')
    js = [f'tl.fromTo("#{cid}-all", {{ rotationY: -28, rotationX: 10, scale: 0.86, opacity: 0, transformPerspective: {PERSP} }}, '
          f'{{ rotationY: 0, rotationX: 4, scale: 1, opacity: 1, duration: 0.8, ease: "expo.out" }}, {at:.3f});',
          f'tl.to("#{cid}-all", {{ rotationY: {p.get("turn", 14)}, duration: {max(0.2, dur - at - 0.8):.3f}, ease: "none" }}, {at + 0.8:.3f});',
          f'tl.fromTo("#{cid}-arc", {{ attr: {{ "stroke-dashoffset": 1 }} }}, {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {max(0.3, lock - at):.3f}, ease: "power2.inOut" }}, {at:.3f});',
          f'tl.fromTo(".{cid}-t", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.05, stagger: {min(0.012, max(0.002, (lock - at) / n)):.4f} }}, {at:.3f});',
          f'tl.fromTo("#{cid}-glow", {{ opacity: 0, scale: 0.9 }}, {{ opacity: 1, scale: 1, duration: 0.35, ease: "expo.out" }}, {lock:.3f});',
          f'tl.fromTo("#{cid}-arc", {{ attr: {{ "stroke-width": 16 }} }}, {{ attr: {{ "stroke-width": 24 }}, duration: 0.3, ease: "expo.out" }}, {lock:.3f});']
    if tp:
        js.append(f'tl.fromTo("#{cid}-rot", {{ rotation: 0, svgOrigin: "{c} {c}" }}, {{ rotation: 40, svgOrigin: "{c} {c}", duration: {dur:.3f}, ease: "none" }}, 0);')
        js.append(f'tl.fromTo("#{cid}-tx", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, {at + 0.3:.3f});')
    js.append(f'tl.to("#{cid}-all", {{ scale: 1.25, opacity: 0, filter: "blur(14px)", duration: 0.3, ease: "power2.in" }}, {max(0, dur - 0.3):.3f});')
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ------------------------------------------------------------------------------------------- Stat
def ov_stat(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{value (digits), roll (digits the slot passes through first, e.g. "987654321"), label, sub, x, y,
    at, land (frames), size}. The number sits in a slot window and lands on the value with one hard stop."""
    C = _c(cx)
    size = p.get("size", 260)
    x, y, at = p.get("x", 0.5) * cx.W, p.get("y", 0.55) * cx.H, cx.s(p.get("at", 0))
    land = cx.s(p.get("land", p.get("at", 0) + 18))
    seq = list(p.get("roll", "987654321")) + [str(p["value"])]
    col = "".join(f'<div style="height:{size * 1.05:.0f}px;line-height:{size * 1.05:.0f}px">{esc(d)}</div>' for d in seq)
    k = len(seq) - 1
    body = (f'<div id="{cid}-all" style="position:absolute;left:{x - 600:.0f}px;width:1200px;top:{y - size * 0.55:.0f}px;display:flex;align-items:center;justify-content:center;gap:34px">'
            f'<div style="height:{size * 1.05:.0f}px;overflow:hidden;font:700 {size}px/1 {C["title"]};color:{C["gold"]};text-shadow:0 0 50px {C["gold"]}66,0 20px 50px rgba(0,0,0,0.5)">'
            f'<div id="{cid}-col">{col}</div></div>'
            f'<div id="{cid}-lab" style="text-align:left"><div style="font:700 {size * 0.26:.0f}px/1.15 {C["title"]};color:#fff;text-shadow:0 8px 30px rgba(0,0,0,0.6)">{esc(p.get("label", ""))}</div>'
            f'<div style="margin-top:12px;font:500 {size * 0.11:.0f}px/1 {C["meta"]};letter-spacing:0.3em;color:{C["mint"]}">{esc(p.get("sub", ""))}</div></div></div>')
    js = [f'tl.fromTo("#{cid}-all", {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "expo.out" }}, {at:.3f});',
          f'tl.fromTo("#{cid}-col", {{ y: 0 }}, {{ y: {-k * size * 1.05:.0f}, duration: {max(0.2, land - at):.3f}, ease: "power4.inOut" }}, {at:.3f});',
          f'tl.fromTo("#{cid}-lab", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.5, ease: "expo.out" }}, {land:.3f});',
          f'tl.to("#{cid}-all", {{ y: -30, opacity: 0, filter: "blur(10px)", duration: 0.26, ease: "power2.in" }}, {max(0, dur - 0.26):.3f});']
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# --------------------------------------------------------------------------------------- FlipCard
def ov_flipcard(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{front {kicker, title}, back {kicker, title, sub}, x, y, w, h, at, flipAt}. The card stands up from
    a lay-flat tilt, then turns 180 degrees on its vertical axis to the answer."""
    C = _c(cx)
    w, h = p.get("w", 820), p.get("h", 340)
    x, y, at, fa = p.get("x", 0.5) * cx.W, p.get("y", 0.55) * cx.H, cx.s(p.get("at", 0)), cx.s(p["flipAt"])

    def face(f, back):
        tcol = C["gold"] if back else "#ffffff"
        sub = f'<div style="margin-top:16px;font:500 26px/1 {C["meta"]};letter-spacing:0.34em;color:{C["mint"]}">{esc(f.get("sub", ""))}</div>' if f.get("sub") else ""
        return (f'<div style="position:absolute;inset:0;{_glass(C)};backface-visibility:hidden;-webkit-backface-visibility:hidden;'
                f'{"transform:rotateY(180deg);" if back else ""}display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center">'
                f'<div style="font:500 34px/1 {C["body"]};color:rgba(214,255,230,0.75);letter-spacing:0.04em">{esc(f.get("kicker", ""))}</div>'
                f'<div style="margin-top:18px;font:700 {f.get("size", 112)}px/1.05 {C["title"]};color:{tcol};text-shadow:0 0 40px {tcol}44">{esc(f["title"])}</div>{sub}</div>')
    body = (f'<div id="{cid}-all" style="position:absolute;left:{x - w / 2:.0f}px;top:{y - h / 2:.0f}px;width:{w}px;height:{h}px;perspective:{PERSP}px">'
            f'<div id="{cid}-card" data-layout-allow-overlap style="position:absolute;inset:0;transform-style:preserve-3d">{face(p["front"], False)}{face(p["back"], True)}</div></div>')
    js = [f'tl.fromTo("#{cid}-card", {{ rotationX: -75, y: 120, opacity: 0 }}, {{ rotationX: 0, y: 0, opacity: 1, duration: 0.7, ease: "expo.out" }}, {at:.3f});',
          f'tl.fromTo("#{cid}-card", {{ rotationY: 0 }}, {{ rotationY: 180, duration: 0.62, ease: "expo.inOut", immediateRender: false }}, {fa - 0.2:.3f});',
          f'tl.fromTo("#{cid}-all", {{ scale: 1 }}, {{ scale: 1.05, duration: {max(0.2, dur - at):.3f}, ease: "none" }}, {at:.3f});',
          f'tl.to("#{cid}-all", {{ y: -60, opacity: 0, filter: "blur(12px)", duration: 0.28, ease: "power2.in" }}, {max(0, dur - 0.28):.3f});']
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ----------------------------------------------------------------------------------------- NextUp
def ov_nextup(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{kicker, title, sub, button, x, y, w, at, pressAt}. A next-episode card; the progress line fills
    while it holds and the follow pill is pressed once (a one-way dip and a ring that opens out)."""
    C = _c(cx)
    w = p.get("w", 820)
    x, y, at, pa = p.get("x", 0.5) * cx.W, p.get("y", 0.55) * cx.H, cx.s(p.get("at", 0)), cx.s(p.get("pressAt", p.get("at", 0) + 40))
    body = (f'<div id="{cid}-all" style="position:absolute;left:{x - w / 2:.0f}px;top:{y - 190:.0f}px;width:{w}px">'
            f'<div id="{cid}-card" style="position:relative;padding:40px 46px 44px;{_glass(C, 0.7)}">'
            f'<div style="display:flex;align-items:center;gap:16px;font:500 26px/1 {C["meta"]};letter-spacing:0.32em;color:{C["mint"]}">'
            f'<span style="width:14px;height:14px;border-radius:50%;background:{C["alert"]};box-shadow:0 0 16px {C["alert"]}"></span>{esc(p.get("sub", "NEXT EPISODE"))}</div>'
            f'<div style="margin-top:22px;font:500 40px/1 {C["body"]};color:rgba(255,255,255,0.75)">{esc(p.get("kicker", ""))}</div>'
            f'<div style="margin-top:14px;font:700 96px/1.05 {C["title"]};color:#fff">{esc(p["title"])}</div>'
            f'<div style="margin-top:30px;height:8px;border-radius:4px;background:rgba(255,255,255,0.12);overflow:hidden">'
            f'<div id="{cid}-bar" style="height:8px;width:100%;background:linear-gradient(90deg,{C["brand"]},{C["mint"]})"></div></div>'
            f'<div style="position:relative;margin-top:34px;display:flex;justify-content:flex-end">'
            + (objvid(f"{cid}-bell", p["bell"], max(0.0, pa - 0.2), dur - max(0.0, pa - 0.2),
               "position:absolute;left:-40px;top:-80px;width:240px;height:240px;filter:drop-shadow(0 18px 24px rgba(0,0,0,0.5))") if p.get("bell") else "") +
            f'<div id="{cid}-ring" style="position:absolute;right:0;top:0;width:330px;height:92px;border-radius:46px;border:3px solid {C["mint"]};opacity:0"></div>'
            f'<div id="{cid}-btn" style="width:330px;height:92px;border-radius:46px;background:linear-gradient(180deg,#19a35c,{C["brand"]});'
            f'display:flex;align-items:center;justify-content:center;font:700 46px/1 {C["title"]};color:#fff;box-shadow:0 14px 34px rgba(14,122,67,0.55),inset 0 1.5px 0 rgba(255,255,255,0.3)">{esc(p.get("button", ""))}</div>'
            f'</div></div></div>')
    js = [f'tl.fromTo("#{cid}-card", {{ rotationX: 60, y: 160, opacity: 0, transformPerspective: {PERSP} }}, {{ rotationX: 0, y: 0, opacity: 1, duration: 0.75, ease: "expo.out" }}, {at:.3f});',
          f'tl.set("#{cid}-bar", {{ scaleX: 0, transformOrigin: "0% 50%" }}, 0);',
          f'tl.to("#{cid}-bar", {{ scaleX: 1, duration: {max(0.3, pa - at - 0.2):.3f}, ease: "none" }}, {at + 0.2:.3f});',
          f'tl.fromTo("#{cid}-btn", {{ scale: 1 }}, {{ scale: 0.92, duration: 0.09, ease: "power2.in" }}, {pa:.3f});',
          f'tl.to("#{cid}-btn", {{ scale: 1, duration: 0.3, ease: "expo.out" }}, {pa + 0.09:.3f});',
          f'tl.fromTo("#{cid}-ring", {{ opacity: 0.9, scale: 1 }}, {{ opacity: 0, scale: 1.35, duration: 0.55, ease: "expo.out" }}, {pa + 0.05:.3f});',
          f'tl.fromTo("#{cid}-all", {{ y: 0 }}, {{ y: -24, duration: {max(0.2, dur - at):.3f}, ease: "sine.out" }}, {at:.3f});']
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ----------------------------------------------------------------------------------- shared column
def _column_box(cx: Ctx, p: dict) -> tuple[float, float, float]:
    """Left edge, width and top of the content column beside the folded footage card."""
    return p.get("x", 0.53) * cx.W, p.get("w", 0.43) * cx.W, p.get("top", 0.2) * cx.H


def sc_meters(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    """p: under, x/w/top (column), kicker, sub, rows [{label, sub, at, maxAt, base (segments, default 5),
    value {from, to, at, dur, final, unit}}]. Frames are relative to the scene start."""
    C = _c(cx)
    wcss, wbody, js = world(cx, cid, dur, p.get("seed", 9))
    x0, cw, top = _column_box(cx, p)
    rows = []
    for i, r in enumerate(p["rows"]):
        segs = "".join(f'<div class="{cid}-s{i}" style="flex:1;height:34px;border-radius:6px;background-color:rgba(255,255,255,0.08)"></div>' for _ in range(SEGMENTS))
        val = ""
        if r.get("value"):
            v = r["value"]
            val = (f'<div style="display:flex;align-items:baseline;gap:10px;margin-top:16px"><span id="{cid}-v{i}" style="font:700 84px/1 {C["title"]};color:{C["gold"]}">{v["from"]}</span>'
                   f'<span style="font:700 40px/1 {C["title"]};color:{C["gold"]}">{esc(v.get("unit", "%"))}</span>'
                   f'<span style="font:500 30px/1 {C["body"]};color:rgba(255,255,255,0.7);margin-left:8px">{esc(v.get("label", ""))}</span></div>')
        ico = ""
        if r.get("icon"):
            ico = objvid(f"{cid}-ic{i}", r["icon"], cx.s(r["at"]), dur - cx.s(r["at"]), "position:absolute;right:-30px;top:-62px;width:180px;height:180px;filter:drop-shadow(0 18px 22px rgba(0,0,0,0.5))")
        rows.append(f'<div id="{cid}-r{i}" style="position:relative;padding:24px 28px 26px;margin-top:{0 if i == 0 else 18}px;{_glass(C, 0.55)}">{ico}'
                    f'<div style="font:700 62px/1 {C["title"]};color:#fff;white-space:nowrap;padding-right:{130 if ico else 0}px">{esc(r["label"])}</div>'
                    f'<div style="display:flex;align-items:center;justify-content:space-between;margin-top:12px">'
                    f'<div style="font:500 22px/1 {C["meta"]};letter-spacing:0.3em;color:{C["mint"]}">{esc(r.get("sub", ""))}</div>'
                    f'<div id="{cid}-m{i}" style="font:700 24px/1 {C["meta"]};letter-spacing:0.24em;color:{C["deep"]};background:{C["gold"]};padding:8px 14px;border-radius:9px;opacity:0">MAX</div></div>'
                    f'<div style="display:flex;gap:6px;margin-top:22px">{segs}</div>{val}</div>')
    hero = ""
    if p.get("hero"):
        hp = p["hero"]
        hs = hp.get("size", 380)
        hero = (f'<div id="{cid}-hero" style="position:relative;height:{hs * 0.78:.0f}px;margin-bottom:10px">'
                + objvid(f"{cid}-hv", hp["obj"], cx.s(hp.get("at", 0)), dur - cx.s(hp.get("at", 0)),
                         f"position:absolute;left:50%;top:{-hs * 0.12:.0f}px;width:{hs}px;height:{hs}px;margin-left:{-hs / 2:.0f}px;filter:drop-shadow(0 30px 40px rgba(0,0,0,0.55))")
                + '</div>')
    head = hero + (f'<div id="{cid}-hd" style="margin-bottom:26px"><div style="font:500 24px/1 {C["meta"]};letter-spacing:0.36em;color:{C["mint"]}">{esc(p.get("sub", ""))}</div>'
            f'<div style="margin-top:14px;font:700 {p.get("kicker_size", 76)}px/1.05 {C["title"]};color:{C["gold"]};white-space:nowrap;text-shadow:0 0 40px {C["gold"]}55">{esc(p.get("kicker", ""))}</div></div>')
    body = (wbody + f'<div id="{cid}-col" style="position:absolute;left:{x0:.0f}px;top:{top:.0f}px;width:{cw:.0f}px;perspective:{PERSP}px">'
            f'<div id="{cid}-pan" style="transform-style:preserve-3d">{head}{"".join(rows)}</div></div>')
    js.append(f'tl.fromTo("#{cid}-pan", {{ rotationY: -48, x: 320, opacity: 0 }}, {{ rotationY: -12, x: 0, opacity: 1, duration: 0.8, ease: "expo.out" }}, 0.15);')
    js.append(f'tl.to("#{cid}-pan", {{ rotationY: -6, duration: {max(0.2, dur - 0.95):.3f}, ease: "none" }}, 0.95);')
    js.append(f'tl.fromTo("#{cid}-hd", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "expo.out" }}, 0.35);')
    for i, r in enumerate(p["rows"]):
        a, m = cx.s(r["at"]), cx.s(r["maxAt"])
        base = r.get("base", 5)
        js.append(f'tl.fromTo("#{cid}-r{i}", {{ opacity: 0, x: 80 }}, {{ opacity: 1, x: 0, duration: 0.5, ease: "expo.out" }}, {a:.3f});')
        js.append(f'tl.to(gsap.utils.toArray(".{cid}-s{i}").slice(0, {base}), {{ backgroundColor: "rgba(139,245,184,0.55)", duration: 0.08, stagger: 0.05 }}, {a + 0.2:.3f});')
        js.append(f'tl.to(".{cid}-s{i}", {{ backgroundColor: "{C["gold"]}", boxShadow: "0 0 18px {C["gold"]}99", duration: 0.05, stagger: 0.018 }}, {m:.3f});')
        js.append(f'tl.fromTo("#{cid}-m{i}", {{ opacity: 0, scale: 1.6 }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: "expo.out" }}, {m + 0.22:.3f});')
        js.append(f'tl.fromTo("#{cid}-r{i}", {{ borderColor: "rgba(139,245,184,0.28)" }}, {{ borderColor: "{C["gold"]}", duration: 0.2 }}, {m:.3f});')
        if r.get("value"):
            v = r["value"]
            js.append(f'count("#{cid}-v{i}", {v["from"]}, {v["to"]}, {cx.s(v["at"]):.3f}, {v.get("dur", 1.0)});')
            if v.get("final"):
                js.append(f'tl.set("#{cid}-v{i}", {{ textContent: "{v["final"]}" }}, {cx.s(v["at"]) + v.get("dur", 1.0) + 0.02:.3f});')
    js.append(f'tl.to("#{cid}-stage", {{ scale: 1.12, opacity: 0, filter: "blur(14px)", duration: 0.3, ease: "power2.in" }}, {max(0, dur - 0.3):.3f});')
    return scene_file(cx, cid, h, wcss, body, "\n".join(js))


def sc_divisions(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    """p: under, x/w/top, curve {title, sub, at, point (0-1 along the curve), label, out},
    struck {t, sub, at, strikeAt, stamp, chipAt}, cards [{n, t, sub, at}], spreadAt. Frames relative."""
    C = _c(cx)
    wcss, wbody, js = world(cx, cid, dur, p.get("seed", 13))
    x0, cw, top = _column_box(cx, p)
    parts = []
    cv = p.get("curve")
    if cv:
        gw, gh = cw - 60, 420
        pts = [(gw * t, gh - gh * (1 / (1 + math.exp(-9 * (t - 0.62))))) for t in [i / 40 for i in range(41)]]
        d = "M " + " L ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
        k = int(cv.get("point", 0.22) * 40)
        px, py = pts[k]
        grid = "".join(f'<line x1="0" y1="{gh * j / 4:.0f}" x2="{gw:.0f}" y2="{gh * j / 4:.0f}" stroke="rgba(255,255,255,0.08)" stroke-width="2"/>' for j in range(5))
        parts.append(f'<div id="{cid}-cv" style="position:absolute;left:0;top:0;width:{cw:.0f}px;padding:34px 30px;{_glass(C)}">'
                     f'<div style="font:500 22px/1 {C["meta"]};letter-spacing:0.34em;color:{C["mint"]}">{esc(cv.get("sub", ""))}</div>'
                     f'<div style="margin-top:14px;font:700 62px/1.05 {C["title"]};color:#fff">{esc(cv["title"])}</div>'
                     f'<svg width="{gw:.0f}" height="{gh + 40}" style="margin-top:30px;overflow:visible">{grid}'
                     f'<path id="{cid}-cp" d="{d}" fill="none" stroke="url(#{cid}-cg)" stroke-width="8" stroke-linecap="round" pathLength="1" stroke-dasharray="1.1" stroke-dashoffset="1.1"/>'
                     f'<defs><linearGradient id="{cid}-cg" x1="0" x2="1"><stop offset="0" stop-color="{C["mint"]}"/><stop offset="1" stop-color="{C["gold"]}"/></linearGradient></defs>'
                     f'<circle id="{cid}-pt" cx="{px:.1f}" cy="{py:.1f}" r="16" fill="{C["gold"]}" stroke="#fff" stroke-width="5" opacity="0"/>'
                     f'<circle id="{cid}-pr" cx="{px:.1f}" cy="{py:.1f}" r="16" fill="none" stroke="{C["gold"]}" stroke-width="3" opacity="0"/></svg>'
                     f'<div id="{cid}-pl" style="position:absolute;left:{30 + px - 20:.0f}px;top:{150 + py - 120:.0f}px;font:700 46px/1 {C["title"]};color:{C["gold"]};'
                     f'padding:12px 20px;border-radius:14px;background:rgba(0,0,0,0.35);border:1.5px solid {C["gold"]}88;opacity:0;white-space:nowrap">{esc(cv.get("label", ""))}</div></div>')
        a = cx.s(cv.get("at", 0))
        js += [f'tl.fromTo("#{cid}-cv", {{ rotationY: -40, x: 300, opacity: 0, transformPerspective: {PERSP} }}, {{ rotationY: -10, x: 0, opacity: 1, duration: 0.8, ease: "expo.out" }}, {a:.3f});',
               f'tl.to("#{cid}-cp", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 1.6, ease: "power2.inOut" }}, {a + 0.4:.3f});',
               f'tl.fromTo("#{cid}-pt", {{ opacity: 0, scale: 0, svgOrigin: "{px:.1f} {py:.1f}" }}, {{ opacity: 1, scale: 1, duration: 0.35, ease: "expo.out" }}, {cx.s(cv.get("pointAt", cv.get("at", 0) + 40)):.3f});',
               f'tl.fromTo("#{cid}-pr", {{ opacity: 0.9, scale: 1, svgOrigin: "{px:.1f} {py:.1f}" }}, {{ opacity: 0, scale: 3, duration: 0.9, ease: "expo.out" }}, {cx.s(cv.get("pointAt", cv.get("at", 0) + 40)):.3f});',
               f'tl.fromTo("#{cid}-pl", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "expo.out" }}, {cx.s(cv.get("pointAt", cv.get("at", 0) + 40)) + 0.1:.3f});',
               f'tl.to("#{cid}-cv", {{ y: -140, opacity: 0, filter: "blur(12px)", duration: 0.35, ease: "power2.in" }}, {cx.s(cv["out"]):.3f});']
    st = p.get("struck")
    if st:
        parts.append(f'<div id="{cid}-sk" data-layout-allow-overlap style="position:absolute;left:0;top:0;width:{cw:.0f}px;height:260px;{_glass(C)};display:flex;flex-direction:column;justify-content:center;padding:0 36px;overflow:hidden">'
                     f'<div style="font:500 22px/1 {C["meta"]};letter-spacing:0.34em;color:{C["mint"]}">{esc(st.get("sub", ""))}</div>'
                     f'<div id="{cid}-skt" style="margin-top:16px;font:700 74px/1.05 {C["title"]};color:#fff">{esc(st["t"])}</div>'
                     f'<svg width="{cw:.0f}" height="260" style="position:absolute;left:0;top:0"><line id="{cid}-sl" x1="24" y1="210" x2="{cw - 24:.0f}" y2="50" stroke="{C["alert"]}" stroke-width="12" stroke-linecap="round" pathLength="1" stroke-dasharray="1.1" stroke-dashoffset="1.1"/></svg>'
                     f'<div id="{cid}-ss" style="position:absolute;right:30px;bottom:26px;font:700 44px/1 {C["title"]};color:{C["alert"]};border:5px solid {C["alert"]};border-radius:14px;padding:10px 20px;opacity:0;background:rgba(10,5,5,0.4)">{esc(st.get("stamp", ""))}</div></div>')
        a = cx.s(st["at"])
        js += [f'tl.fromTo("#{cid}-sk", {{ rotationX: -70, y: 120, opacity: 0, transformPerspective: {PERSP} }}, {{ rotationX: 0, y: 0, opacity: 1, duration: 0.7, ease: "expo.out" }}, {a:.3f});',
               f'tl.to("#{cid}-sl", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 0.3, ease: "power3.out" }}, {cx.s(st["strikeAt"]):.3f});',
               f'tl.to("#{cid}-skt", {{ opacity: 0.4, duration: 0.3 }}, {cx.s(st["strikeAt"]):.3f});',
               f'tl.fromTo("#{cid}-ss", {{ opacity: 0, scale: 1.8, rotation: -14 }}, {{ opacity: 1, scale: 1, rotation: -6, duration: 0.22, ease: "power4.in" }}, {cx.s(st["strikeAt"]) + 0.2:.3f});']
        if st.get("chipAt") is not None:
            js.append(f'tl.to("#{cid}-sk", {{ scale: 0.62, y: -40, opacity: 0.55, transformOrigin: "0% 0%", duration: 0.55, ease: "expo.inOut" }}, {cx.s(st["chipAt"]):.3f});')
    cards = p.get("cards") or []
    for i, c in enumerate(cards):
        parts.append(f'<div id="{cid}-k{i}" style="position:absolute;left:0;top:{200 + i * 176}px;width:{cw:.0f}px;height:156px;{_glass(C, 0.6)};display:flex;align-items:center;gap:26px;padding:0 30px">'
                     + (objvid(f"{cid}-ki{i}", c["icon"], cx.s(c["at"]), dur - cx.s(c["at"]),
                        "width:150px;height:150px;margin:0 -20px 0 -30px;flex:none;filter:drop-shadow(0 12px 18px rgba(0,0,0,0.5))", c.get("media_start", 0.0))
                        if c.get("icon") else f'<div style="font:700 64px/1 {C["title"]};color:{C["gold"]};width:84px">{esc(c.get("n", f"0{i + 1}"))}</div>') +
                     f'<div><div style="font:700 {c.get("size", 46)}px/1.05 {C["title"]};color:#fff;white-space:nowrap">{esc(c["t"])}</div>'
                     f'<div style="margin-top:12px;font:500 22px/1 {C["meta"]};letter-spacing:0.3em;color:{C["mint"]}">{esc(c.get("sub", ""))}</div></div></div>')
        js.append(f'tl.fromTo("#{cid}-k{i}", {{ rotationY: -70, x: 260, opacity: 0, transformPerspective: {PERSP}, transformOrigin: "100% 50%" }}, '
                  f'{{ rotationY: 0, x: 0, opacity: 1, duration: 0.6, ease: "expo.out" }}, {cx.s(c["at"]):.3f});')
    if p.get("spreadAt") is not None and cards:
        for i in range(len(cards)):
            js.append(f'tl.to("#{cid}-k{i}", {{ y: {i * 26}, borderColor: "{C["gold"]}", duration: 0.5, ease: "expo.inOut" }}, {cx.s(p["spreadAt"]) + i * 0.06:.3f});')
    body = wbody + f'<div id="{cid}-col" style="position:absolute;left:{x0:.0f}px;top:{top:.0f}px;width:{cw:.0f}px;height:{h - top:.0f}px">{"".join(parts)}</div>'
    js.append(f'tl.to("#{cid}-stage", {{ scale: 1.12, opacity: 0, filter: "blur(14px)", duration: 0.3, ease: "power2.in" }}, {max(0, dur - 0.3):.3f});')
    return scene_file(cx, cid, h, wcss, body, "\n".join(js))


# ----------------------------------------------------------------------------------------- captions
def captions_plate(cx: Ctx, caps: list[dict], ys: list[float], size: float, font: str | None = None, font_emph: str | None = None) -> str:
    """Phrase captions: each word rises out of a mask on its spoken frame, and a brand-colour plate lands
    under the word being said, handing over to the next word. Emphasis words take the accent colour."""
    C = _c(cx)
    f1 = font or C["body"]
    groups, js = [], []
    for gi, (g, y) in enumerate(zip(caps, ys)):
        s_, e_ = cx.s(g["s"]), cx.s(g["e"])
        if gi + 1 < len(caps):
            e_ = min(e_, cx.s(caps[gi + 1]["s"]))
        spans = "".join(f'<span class="cp{" e" if w["emph"] else ""}"><i id="cp{gi}p{wi}"></i><span class="m"><b id="cp{gi}w{wi}">{esc(w["w"])}</b></span></span> '
                        for wi, w in enumerate(g["words"]))
        groups.append(f'<div id="cp{gi}" class="cg" style="top:{y * cx.H:.0f}px">{spans}</div>')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "visible" }}, {s_:.3f});')
        ws = g["words"]
        for wi, w in enumerate(ws):
            t0 = max(s_, cx.s(w["s"]) - 1 / cx.fps)
            js.append(f'tl.fromTo("#cp{gi}w{wi}", {{ yPercent: 105 }}, {{ yPercent: 0, duration: 0.3, ease: "expo.out" }}, {t0:.3f});')
            js.append(f'tl.fromTo("#cp{gi}p{wi}", {{ scaleX: 0, opacity: 1 }}, {{ scaleX: 1, duration: {PLATE_IN_S}, ease: "expo.out" }}, {t0:.3f});')
            if wi + 1 < len(ws):
                js.append(f'tl.to("#cp{gi}p{wi}", {{ opacity: 0, duration: 0.1 }}, {max(t0 + PLATE_IN_S, cx.s(ws[wi + 1]["s"]) - 1 / cx.fps):.3f});')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "hidden" }}, {e_:.3f});')
    css = f"""#capp {{ position: absolute; inset: 0; }}
#capp .cg {{ position: absolute; left: 70px; right: 70px; transform: translateY(-50%); text-align: center; visibility: hidden; line-height: 1.45; text-wrap: balance; }}
#capp .cp {{ position: relative; display: inline-block; margin: 0 0.2em; }}
#capp .cp i {{ position: absolute; left: -0.2em; right: -0.2em; top: 0.08em; bottom: 0.02em; border-radius: 0.22em; background: linear-gradient(180deg, #18a85f, {C['brand']});
  box-shadow: 0 10px 26px rgba(0,0,0,0.35), inset 0 1.5px 0 rgba(255,255,255,0.28); transform-origin: 0% 50%; opacity: 0; }}
#capp .m {{ position: relative; display: inline-block; overflow: hidden; padding: 0.04em 0 0.1em; vertical-align: bottom; }}
#capp b {{ display: inline-block; font-family: {f1}; font-weight: 700; font-size: {size}px; color: #fff; font-synthesis: none;
  text-shadow: 0 3px 6px rgba(0,0,0,0.4), 0 8px 30px rgba(0,0,0,0.45); }}
#capp .e b {{ color: {C['gold']}; }}"""
    return scene_file(cx, "captions", cx.H, css, f'<div id="capp">{"".join(groups)}</div>', "\n".join(js), transparent=True)


OVERLAYS = {"World": ov_world, "Ring": ov_ring, "Stat": ov_stat, "FlipCard": ov_flipcard, "NextUp": ov_nextup}
SCENES = {"Meters": sc_meters, "Divisions": sc_divisions}
