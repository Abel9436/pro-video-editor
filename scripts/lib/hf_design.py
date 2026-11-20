"""HyperFrames design engine: the EDL `design` block -> an editable HyperFrames project.

The clean speaker cut (picture pass) plays full-frame; layouts (full / split / hidden), explainer
scenes, overlays, phrase captions and transitions are written as HTML + GSAP, one sub-composition
per scene and overlay, so the result opens in the HyperFrames desktop app / Studio and every
element stays editable. render.py calls `build()` then renders the project to design.mp4.

Grades and blurs on footage are files (ffmpeg), never CSS filters: base.mp4 (keyframe every
second, so seeking never freezes), base_bw.mp4 (background B&W spans) and base_soft.mp4 (blurred,
darkened copy behind split layouts and frosted scenes).

Supported: the types in SCENES / OVERLAYS / FX below and caption_style "phrase". Anything else
makes `unsupported()` non-empty and render.py falls back to the Remotion engine.
"""
from __future__ import annotations

import html
import json
import math
import random
import re
import shutil
from pathlib import Path

SCENES = {"RingsDash", "BalanceScale", "Equation", "PageScan", "AppReveal", "EndCard", "CalendarBlocks", "ChoiceCards", "PileUp", "TypeWall", "CounterHero", "Formula"}
OVERLAYS = {"FloatChips", "Halo", "SelectionBox", "Counter", "BigWord", "FloatIcons", "Stamp", "Kinetic"}
FX = {"overexpose", "flash", "zoomblur", "whip", "leakdip", "leak", "wash", "smoke", "bands", "flip3d"}
CAPTION_STYLES = {"phrase", "box", "lockup", "ink"}

SPLIT_FACE_AT = 0.62   # same STARTING DEFAULTS as the Remotion engine (Design.tsx)
SPLIT_SCALE = 0.62
GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"

esc = html.escape


def unsupported(d: dict) -> list[str]:
    out = [f"scene {s['type']}" for s in d.get("scenes", []) if s["type"] not in SCENES]
    out += [f"overlay {o['type']}" for o in d.get("overlays", []) if o["type"] not in OVERLAYS]
    out += [f"fx {x['type']}" for x in d.get("fx", []) if x["type"] not in FX]
    if d.get("caption_style", "phrase") not in CAPTION_STYLES:
        out.append(f"caption_style {d.get('caption_style')}")
    return out


class Ctx:
    def __init__(self, fps: float, W: int, H: int, brand: dict, fonts_css: str):
        self.fps, self.W, self.H, self.brand, self.fonts_css = fps, W, H, brand, fonts_css

    def s(self, f: float) -> float:
        return round(f / self.fps, 4)


def n(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


# ============================================================================== shared pieces
def scene_file(cx: Ctx, cid: str, h: int, css: str, body: str, js: str, transparent: bool = False) -> str:
    return f"""<template>
<style>
{cx.fonts_css}
#root {{ position: absolute; inset: 0; overflow: hidden; {'' if transparent else ''} }}
#{cid}-stage {{ position: absolute; left: 0; top: 0; width: {cx.W}px; height: {h}px; overflow: hidden; }}
{css}
</style>
<div id="root" data-composition-id="{cid}" data-width="{cx.W}" data-height="{cx.H}">
<div id="{cid}-stage">
{body}
</div>
</div>
<script>
(function () {{
const tl = gsap.timeline({{ paused: true }});
const fmt = (v) => Math.round(v).toLocaleString("en-US");
const count = (sel, from, to, at, dur, ease) => {{ const o = {{ v: from }}; const el = document.querySelector(sel);
  tl.fromTo(o, {{ v: from }}, {{ v: to, duration: dur, ease: ease || "power4.out", onUpdate: () => {{ el.textContent = fmt(o.v); }} }}, at); }};
const draw = (sel, at, dur, stagger) => tl.fromTo(sel, {{ attr: {{ "stroke-dashoffset": 1.1 }} }}, {{ attr: {{ "stroke-dashoffset": 0 }}, duration: dur, ease: "power2.inOut", stagger: stagger || 0 }}, at);
{js}
window.__timelines["{cid}"] = tl;
}})();
</script>
</template>
"""


def night(cx: Ctx, cid: str, h: int, glow_at: str = "50% 35%", stars: int = 60, seed: int = 1) -> tuple[str, str, str]:
    """Deep navy stage with a brand-colour glow and a star field that drifts up (the world moves,
    the type stays still)."""
    rnd = random.Random(seed)
    dots = []
    for i in range(stars):
        x, y, r = rnd.random() * cx.W, rnd.random() * (h + 80), 0.8 + rnd.random() * 2.2
        a = 0.25 + rnd.random() * 0.6
        glow = "box-shadow:0 0 8px #fff;" if r > 2.3 else ""
        dots.append(f'<i style="left:{x:.0f}px;top:{y:.0f}px;width:{2*r:.1f}px;height:{2*r:.1f}px;opacity:{a:.2f};{glow}"></i>')
    g = cx.brand.get("glow", "#6C4CF1")
    css = f"""#{cid}-bg {{ position: absolute; inset: 0; background: radial-gradient(ellipse 85% 60% at {glow_at}, {g}40 0%, #0d0b22 50%, #05040c 100%), #05040c; }}
#{cid}-stars {{ position: absolute; left: 0; top: 0; width: 100%; height: {h + 80}px; }}
#{cid}-stars i {{ position: absolute; border-radius: 50%; background: #fff; }}"""
    body = f'<div id="{cid}-bg"></div><div id="{cid}-stars">{"".join(dots)}</div>'
    return css, body, ""


def stroke_svg(paths: list[str] | None, size: float, color: str, cls: str, glow: bool = True, width: float = 1.8) -> str:
    if not paths:
        return ""
    f = f"filter:drop-shadow(0 0 6px {color});" if glow else ""
    ps = "".join(f'<path class="{cls}" d="{esc(d)}" pathLength="1" stroke-dasharray="1 1.2" stroke-dashoffset="1.1"/>' for d in paths)
    return (f'<svg viewBox="0 0 24 24" width="{size:.0f}" height="{size:.0f}" style="overflow:visible;flex:none;{f}" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">{ps}</svg>')


GLASS = "background:rgba(22,20,40,0.62);border:1.5px solid rgba(255,255,255,0.16);box-shadow:0 24px 60px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.12);"


# ============================================================================== scenes
def sc_ringsdash(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    ncss, nbody, _ = night(cx, cid, h, stars=40, seed=11)
    items = p["items"]
    cxp, cy, R0, sw = cx.W / 2, h * 0.32, h * 0.19, h * 0.032
    rings, tiles, js = [], [], []
    for i, it in enumerate(items):
        r = R0 - i * sw * 1.25
        c = it["color"]
        rings.append(f'<circle cx="{cxp}" cy="{cy:.1f}" r="{r:.1f}" stroke="{c}" stroke-opacity="0.16" stroke-width="{sw:.1f}" fill="none"/>'
                     f'<circle id="{cid}-r{i}" cx="{cxp}" cy="{cy:.1f}" r="{r:.1f}" stroke="{c}" stroke-width="{sw:.1f}" fill="none" stroke-linecap="round" '
                     f'pathLength="1" stroke-dasharray="1 1.2" stroke-dashoffset="1.1" transform="rotate(-90 {cxp} {cy:.1f})" style="filter:drop-shadow(0 0 12px {c})"/>')
        at = cx.s(it["at"])
        unit = f'<span class="u" style="color:{c}">{esc(it.get("unit", ""))}</span>' if it.get("unit") else ""
        tiles.append(f'<div id="{cid}-t{i}" class="tile"><div class="ic">{stroke_svg(it.get("paths"), h * 0.055, c, f"{cid}-ip{i}")}</div>'
                     f'<div class="v"><span id="{cid}-n{i}">0</span>{unit}</div><div class="l">{esc(it["label"])}</div></div>')
        js.append(f'tl.fromTo("#{cid}-t{i}", {{ opacity: 0, y: 60, scale: 0.85 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.5, ease: "back.out(1.5)" }}, {at});')
        js.append(f'tl.fromTo("#{cid}-r{i}", {{ attr: {{ "stroke-dashoffset": 1.1 }} }}, {{ attr: {{ "stroke-dashoffset": 0.28 }}, duration: 0.8, ease: "expo.out" }}, {at});')
        js.append(f'count("#{cid}-n{i}", 0, {it["value"]}, {at + 0.08}, 0.75);')
        if it.get("paths"):
            js.append(f'draw(".{cid}-ip{i}", {at}, 0.4, 0.08);')
    close = cx.s(p.get("closeAt", dur * cx.fps - 20))
    sel = ", ".join(f"#{cid}-r{i}" for i in range(len(items)))
    js.append(f'tl.to("{sel}", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 0.5, ease: "power2.inOut" }}, {close});')
    js.append(f'tl.fromTo("#{cid}-done", {{ opacity: 0, scale: 0.7 }}, {{ opacity: 1, scale: 1, duration: 0.45, ease: "back.out(2)" }}, {close + 0.05});')
    js.append(f'tl.fromTo("#{cid}-rings", {{ rotationX: 16 }}, {{ rotationX: 4, duration: {dur}, ease: "power1.inOut" }}, 0);')
    js.append(f'tl.fromTo("#{cid}-stars", {{ y: 0 }}, {{ y: -60, duration: {dur}, ease: "none" }}, 0);')
    css = ncss + f"""
#{cid}-persp {{ position: absolute; inset: 0; perspective: 1800px; }}
#{cid}-rings {{ position: absolute; inset: 0; transform-origin: 50% 32%; }}
#{cid}-done {{ position: absolute; left: 0; right: 0; top: {cy - h * 0.045:.0f}px; text-align: center; font-family: 'Caveat'; font-weight: 700; font-size: {h * 0.06:.0f}px; color: #fff; }}
#{cid}-row {{ position: absolute; left: 54px; right: 54px; top: {h * 0.6:.0f}px; display: flex; gap: 27px; justify-content: center; }}
#{cid}-row .tile {{ flex: 1; {GLASS} border-radius: 30px; padding: {h * 0.022:.0f}px 20px; text-align: center; }}
#{cid}-row .ic {{ display: flex; justify-content: center; height: {h * 0.055:.0f}px; }}
#{cid}-row .v {{ font-family: 'Inter'; font-weight: 900; font-size: {h * 0.06:.0f}px; color: #fff; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; margin-top: 6px; }}
#{cid}-row .u {{ font-size: {max(30, h * 0.028):.0f}px; font-weight: 700; margin-left: 6px; }}
#{cid}-row .l {{ font-family: 'Inter'; font-weight: 700; font-size: {max(30, h * 0.024):.0f}px; color: rgba(255,255,255,0.65); letter-spacing: 0.12em; text-transform: uppercase; }}"""
    body = nbody + f"""<div id="{cid}-persp"><div id="{cid}-rings"><svg width="{cx.W}" height="{h}" style="position:absolute;left:0;top:0;overflow:visible">{''.join(rings)}</svg>
<div id="{cid}-done">{esc(p.get("done", "all tracked"))}</div></div></div>
<div id="{cid}-row">{''.join(tiles)}</div>"""
    return scene_file(cx, cid, h, css, body, "\n".join(js))


def sc_balancescale(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    ncss, nbody, _ = night(cx, cid, h, glow_at="50% 25%", seed=12)
    gold = cx.brand.get("accent", "#F4C76B")
    S = min(cx.W * 0.9, h * 0.95) / 600
    ox, oy = cx.W / 2 - 300 * S, h * 0.48 - 260 * S
    d0 = cx.s(p.get("drawAt", 0))
    tip, deg = cx.s(p["tipAt"]), p.get("tipDeg", 9)

    def pan(k: int, x: float, lit: bool) -> str:
        fill = f'fill="{gold}" fill-opacity="0"' if lit else 'fill="none"'
        lab = p.get("right" if lit else "left")
        txt = ""
        if lab:
            if lit:
                txt = (f'<text id="{cid}-lab{k}" x="{x}" y="400" text-anchor="middle" font-family="Instrument Serif" font-style="italic" font-size="{h * 0.075 / S:.0f}" '
                       f'fill="{gold}" opacity="0" style="filter:drop-shadow(0 0 18px {gold})">{esc(lab["t"])}</text>')
            else:
                txt = (f'<text id="{cid}-lab{k}" x="{x}" y="385" text-anchor="middle" font-family="Inter" font-weight="700" font-size="{h * 0.036 / S:.0f}" '
                       f'letter-spacing="3" fill="rgba(255,255,255,0.6)" opacity="0">{esc(lab["t"].upper())}</text>')
        return (f'<g id="{cid}-pan{k}">'
                f'<path class="{cid}-d2" d="M{x} 120 L{x - 70} 270 M{x} 120 L{x + 70} 270" stroke="{gold}" stroke-width="3" fill="none" pathLength="1" stroke-dasharray="1 1.2" stroke-dashoffset="1.1"/>'
                f'<path id="{cid}-bowl{k}" class="{cid}-d3" d="M{x - 92} 270 Q {x} 345 {x + 92} 270 Z" stroke="{gold}" stroke-width="4" {fill} pathLength="1" stroke-dasharray="1 1.2" stroke-dashoffset="1.1"/>'
                f'{txt}</g>')
    svg = (f'<svg width="{cx.W}" height="{h}" style="position:absolute;left:0;top:0;overflow:visible">'
           f'<g transform="translate({ox:.1f} {oy:.1f}) scale({S:.4f})" style="filter:drop-shadow(0 0 8px {gold}aa)" stroke-linecap="round">'
           f'<path class="{cid}-d0" d="M300 120 L300 470 M220 470 L380 470 M250 470 Q300 430 350 470" stroke="{gold}" stroke-width="5" fill="none" pathLength="1" stroke-dasharray="1 1.2" stroke-dashoffset="1.1"/>'
           f'<circle class="{cid}-d0" cx="300" cy="100" r="14" stroke="{gold}" stroke-width="4" fill="none" pathLength="1" stroke-dasharray="1 1.2" stroke-dashoffset="1.1"/>'
           f'<g id="{cid}-beam"><line class="{cid}-d1" x1="100" y1="120" x2="500" y2="120" stroke="{gold}" stroke-width="6" pathLength="1" stroke-dasharray="1 1.2" stroke-dashoffset="1.1"/>'
           f'{pan(0, 100, False)}{pan(1, 500, True)}</g></g></svg>')
    js = [f'draw(".{cid}-d0", {d0}, 0.55, 0.08);', f'draw(".{cid}-d1", {d0 + 0.3}, 0.45);', f'draw(".{cid}-d2", {d0 + 0.55}, 0.5, 0.05);',
          f'draw(".{cid}-d3", {d0 + 0.85}, 0.55, 0.05);',
          # the beam swings down on the right and settles; each pan counter-rotates so it keeps hanging
          f'tl.fromTo("#{cid}-beam", {{ rotation: 0 }}, {{ rotation: {deg}, svgOrigin: "300 120", duration: 1.6, ease: "elastic.out(1, 0.42)" }}, {tip});',
          f'tl.fromTo("#{cid}-pan0", {{ rotation: 0 }}, {{ rotation: {-deg}, svgOrigin: "100 120", duration: 1.6, ease: "elastic.out(1, 0.42)" }}, {tip});',
          f'tl.fromTo("#{cid}-pan1", {{ rotation: 0 }}, {{ rotation: {-deg}, svgOrigin: "500 120", duration: 1.6, ease: "elastic.out(1, 0.42)" }}, {tip});',
          f'tl.fromTo("#{cid}-bowl1", {{ attr: {{ "fill-opacity": 0 }} }}, {{ attr: {{ "fill-opacity": 0.28 }}, duration: 0.5, ease: "power2.out" }}, {tip});',
          f'tl.fromTo("#{cid}-stars", {{ y: 0 }}, {{ y: -50, duration: {dur}, ease: "none" }}, 0);']
    for k, key in ((0, "left"), (1, "right")):
        if p.get(key):
            js.append(f'tl.fromTo("#{cid}-lab{k}", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "expo.out" }}, {cx.s(p[key]["at"])});')
    kick = ""
    if p.get("kicker"):
        kick = f'<div id="{cid}-kick">{esc(p["kicker"])}</div>'
        js.append(f'tl.fromTo("#{cid}-kick", {{ opacity: 0, filter: "blur(8px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.3, ease: "power3.out" }}, {cx.s(p.get("kickerAt", 0))});')
    css = ncss + f"\n#{cid}-kick {{ position: absolute; top: {h * 0.06:.0f}px; left: 0; right: 0; text-align: center; font-family: 'Caveat'; font-weight: 700; font-size: {h * 0.05:.0f}px; color: rgba(255,255,255,0.88); }}"
    return scene_file(cx, cid, h, css, nbody + kick + svg, "\n".join(js))


def sc_equation(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    gold = cx.brand.get("accent", "#F4C76B")
    size = float(p.get("size") or h * 0.12)
    y = p.get("y", 0.4) * h
    terms, js = [], []
    for i, t in enumerate(p["terms"]):
        k = t["kind"]
        if k == "glyph":
            inner = f'<div class="glyph">{esc(t["t"])}</div>'
        else:
            inner = f'<div class="k-{k}">{esc(t["t"])}</div>'
        sub = f'<div id="{cid}-s{i}" class="sub">{esc(t["sub"])}</div>' if t.get("sub") else ""
        terms.append(f'<div id="{cid}-t{i}" class="term">{inner}{sub}</div>')
        at = cx.s(t["at"])
        ease = "back.out(1.2)" if k == "op" else "back.out(1.8)"
        js.append(f'tl.fromTo("#{cid}-t{i}", {{ opacity: 0, y: 40, scale: 0.6, filter: "blur(14px)" }}, {{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)", duration: 0.42, ease: "{ease}" }}, {at});')
        if t.get("sub"):
            js.append(f'tl.fromTo("#{cid}-s{i}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.25, ease: "power2.out" }}, {at + 0.16});')
    res = ""
    if p.get("result"):
        r = p["result"]
        at, cd = cx.s(r["at"]), (r.get("countDur", 14)) / cx.fps
        lab = f'<div id="{cid}-rl" class="rl">{esc(r["label"])}</div>' if r.get("label") else ""
        res = f'<div id="{cid}-res"><div class="rv">{esc(r.get("prefix", "= "))}<span id="{cid}-rn">{r.get("from", 0)}</span></div>{lab}</div>'
        js.append(f'tl.fromTo("#{cid}-res", {{ opacity: 0, scale: 0.7 }}, {{ opacity: 1, scale: 1, duration: 0.45, ease: "back.out(1.9)" }}, {at});')
        js.append(f'count("#{cid}-rn", {r.get("from", 0)}, {r["to"]}, {at}, {cd:.3f});')
        js.append(f'tl.fromTo("#{cid}-res .rv", {{ textShadow: "0 0 8px #fff, 0 0 70px {gold}, 0 0 120px {gold}" }}, {{ textShadow: "0 0 8px #fff, 0 0 30px {gold}, 0 0 90px {gold}88", duration: 0.6, ease: "power2.out" }}, {at + cd:.3f});')
        if r.get("label"):
            js.append(f'tl.fromTo("#{cid}-rl", {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.35, ease: "expo.out" }}, {at + cd:.3f});')
    glass = bool(p.get("glass"))
    if glass:
        ncss, nbody = f"#{cid}-tint {{ position: absolute; inset: 0; background: rgba(8,6,20,0.45); }}", f'<div id="{cid}-tint"></div>'
        js.append(f'tl.fromTo("#{cid}-tint", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.24, ease: "power2.out" }}, 0);')
    else:
        ncss, nbody, _ = night(cx, cid, h, seed=13)
        js.append(f'tl.fromTo("#{cid}-stars", {{ y: 0 }}, {{ y: -50, duration: {dur}, ease: "none" }}, 0);')
    css = ncss + f"""
#{cid}-row {{ position: absolute; left: 0; right: 0; top: {y - size * 0.62:.0f}px; display: flex; justify-content: center; align-items: flex-start; gap: {size * 0.22:.0f}px; }}
#{cid}-row .term {{ text-align: center; }}
#{cid}-row .glyph {{ width: {size * 1.25:.0f}px; height: {size * 1.25:.0f}px; border-radius: {size * 0.28:.0f}px; border: 3px solid {gold}; display: flex; align-items: center; justify-content: center;
  background: radial-gradient(circle at 50% 40%, {gold}33, rgba(10,8,24,0.75)); box-shadow: 0 0 40px {gold}66, inset 0 0 30px {gold}33;
  font-family: 'Amiri'; font-weight: 700; font-size: {size * 0.95:.0f}px; color: #fff; line-height: 1; padding-bottom: {size * 0.1:.0f}px; }}
#{cid}-row .k-num {{ font-family: 'Anton'; font-size: {size:.0f}px; line-height: 1.25; color: #fff; text-shadow: 0 0 26px {gold}88; }}
#{cid}-row .k-op {{ font-family: 'Inter'; font-weight: 400; font-size: {size * 0.75:.0f}px; line-height: 1.25; color: rgba(255,255,255,0.72); padding-top: {size * 0.12:.0f}px; }}
#{cid}-row .k-word {{ font-family: 'Instrument Serif'; font-style: italic; font-size: {size:.0f}px; line-height: 1.25; color: #fff; }}
#{cid}-row .sub {{ font-family: 'Caveat'; font-weight: 700; font-size: {max(36, size * 0.3):.0f}px; color: {gold}; margin-top: {size * 0.06:.0f}px; white-space: nowrap; }}
#{cid}-res {{ position: absolute; left: 0; right: 0; top: {y + size * 1.15:.0f}px; text-align: center; }}
#{cid}-res .rv {{ font-family: 'Anton'; font-size: {size * 1.7:.0f}px; line-height: 1; color: #fff; font-variant-numeric: tabular-nums; text-shadow: 0 0 8px #fff, 0 0 30px {gold}, 0 0 90px {gold}88; }}
#{cid}-res .rl {{ font-family: 'Instrument Serif'; font-style: italic; font-size: {min(size * 0.55, 80):.0f}px; white-space: nowrap; color: {gold}; margin-top: {size * 0.05:.0f}px; }}"""
    body = nbody + f'<div id="{cid}-row">{"".join(terms)}</div>{res}'
    return scene_file(cx, cid, h, css, body, "\n".join(js), transparent=glass)


def sc_pagescan(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    ncss, nbody, _ = night(cx, cid, h, glow_at="50% 45%", stars=45, seed=14)
    gold = cx.brand.get("accent", "#F4C76B")
    N = 11
    pw, ph = cx.W * 0.72, h * 0.40
    px, py = (cx.W - pw) / 2, h * 0.1
    rnd = random.Random(7)
    lines, js = [], []
    scan_at, scan_dur = cx.s(p["scanAt"]), p["scanDur"] / cx.fps
    for i in range(N):
        w = 0.82 - rnd.random() * 0.18 - (0.35 if i == N - 1 else 0)
        top = 70 + i * ((ph - 140) / N)
        lines.append(f'<div class="ln" style="top:{top:.0f}px;width:{(pw - 120) * w:.0f}px"><div id="{cid}-f{i}" class="fill"></div></div>')
        js.append(f'tl.fromTo("#{cid}-f{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {scan_dur / N:.3f}, ease: "none" }}, {scan_at + i * scan_dur / N:.3f});')
    js.append(f'count("#{cid}-cn", 0, {p["letters"]}, {scan_at}, {scan_dur:.3f}, "none");')
    js.append(f'tl.fromTo("#{cid}-chip", {{ opacity: 0, y: -20 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "expo.out" }}, {max(0, scan_at - 0.2):.3f});')
    js.append(f'tl.fromTo("#{cid}-mul", {{ opacity: 0, scale: 0.3 }}, {{ opacity: 1, scale: 1, duration: 0.4, ease: "back.out(2.2)" }}, {cx.s(p["multAt"])});')
    ra = cx.s(p["resultAt"])
    js.append(f'tl.fromTo("#{cid}-res", {{ opacity: 0, y: 80 }}, {{ opacity: 1, y: 0, duration: 0.55, ease: "expo.out" }}, {ra});')
    js.append(f'count("#{cid}-rn", 0, {p["letters"] * p["mult"]}, {ra}, 0.56);')
    js.append(f'tl.fromTo("#{cid}-page", {{ rotationX: 18, rotationZ: -3, y: 40 }}, {{ rotationX: 6, rotationZ: -1.5, y: 0, duration: {dur}, ease: "power1.out" }}, 0);')
    js.append(f'tl.fromTo("#{cid}-stars", {{ y: 0 }}, {{ y: -60, duration: {dur}, ease: "none" }}, 0);')
    css = ncss + f"""
#{cid}-persp {{ position: absolute; inset: 0; perspective: 2000px; }}
#{cid}-page {{ position: absolute; left: {px:.0f}px; top: {py:.0f}px; width: {pw:.0f}px; height: {ph:.0f}px; border-radius: 26px; overflow: hidden;
  background: linear-gradient(170deg,#fbf7ec,#efe6d2); box-shadow: 0 60px 120px rgba(0,0,0,0.6), 0 0 80px {gold}22; transform-origin: 50% 60%; }}
#{cid}-page .frame {{ position: absolute; inset: 22px; border: 3px double {gold}; border-radius: 14px; }}
#{cid}-page .ln {{ position: absolute; right: 60px; height: 16px; border-radius: 8px; background: #d3c8b1; overflow: hidden; }}
#{cid}-page .fill {{ position: absolute; inset: 0; transform-origin: 100% 50%; background: linear-gradient(270deg, {gold} 0%, #f6d58a 92%, #fff 100%); }}
#{cid}-chip {{ position: absolute; left: 0; right: 0; top: {max(h * 0.025, 176 if h > 1000 else 0):.0f}px; display: flex; justify-content: center; }}
#{cid}-chip .in {{ {GLASS} border-radius: 60px; padding: 16px 40px; display: flex; gap: 20px; align-items: baseline; white-space: nowrap; }}
#{cid}-chip .lb {{ font-family: 'Inter'; font-weight: 700; font-size: {h * 0.026:.0f}px; color: rgba(255,255,255,0.72); letter-spacing: 0.14em; }}
#{cid}-chip .nm {{ font-family: 'Anton'; font-size: {h * 0.05:.0f}px; color: #fff; font-variant-numeric: tabular-nums; min-width: {h * 0.06:.0f}px; text-align: right; }}
#{cid}-mul {{ font-family: 'Anton'; font-size: {h * 0.05:.0f}px; color: {gold}; display: inline-block; }}
#{cid}-res {{ position: absolute; left: 0; right: 0; top: {py + ph + h * 0.02:.0f}px; text-align: center; white-space: nowrap; }}
#{cid}-res .rv {{ font-family: 'Anton'; font-size: {h * 0.1:.0f}px; color: #fff; text-shadow: 0 0 10px #fff, 0 0 40px {gold}, 0 0 90px {gold}99; }}
#{cid}-res .rl {{ font-family: 'Instrument Serif'; font-style: italic; font-size: {h * 0.06:.0f}px; color: {gold}; margin-left: 18px; }}"""
    body = nbody + f"""<div id="{cid}-persp"><div id="{cid}-page"><div class="frame"></div>{''.join(lines)}</div></div>
<div id="{cid}-chip"><div class="in"><span class="lb">{esc(p.get("counterLabel", "LETTERS"))}</span><span id="{cid}-cn" class="nm">0</span><span id="{cid}-mul">× {p["mult"]}</span></div></div>
<div id="{cid}-res"><span class="rv">= <span id="{cid}-rn">0</span></span><span class="rl">{esc(p.get("resultLabel", ""))}</span></div>"""
    return scene_file(cx, cid, h, css, body, "\n".join(js))


def sc_appreveal(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    ncss, nbody, _ = night(cx, cid, h, glow_at="50% 40%", seed=15)
    g, gold = cx.brand.get("glow", "#6C4CF1"), cx.brand.get("accent", "#F4C76B")
    at = cx.s(p.get("at", 2))
    T = h * 0.17
    letters = "".join(f'<span class="{cid}-ch">{esc(c)}</span>' for c in p["name"])
    js = [f'tl.fromTo("#{cid}-rays", {{ opacity: 0, rotation: 0 }}, {{ opacity: 1, rotation: 24, duration: {dur}, ease: "none" }}, 0);',
          f'tl.fromTo("#{cid}-tile", {{ opacity: 0, scale: 0.2, rotation: -25 }}, {{ opacity: 1, scale: 1, rotation: 0, duration: 0.6, ease: "back.out(1.6)" }}, {at});',
          f'draw(".{cid}-ip", {at + 0.16}, 0.5, 0.1);',
          f'tl.fromTo(".{cid}-ch", {{ opacity: 0.0, y: 50, filter: "blur(10px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.32, ease: "expo.out", stagger: 0.06 }}, {at + 0.24});',
          f'tl.fromTo("#{cid}-name", {{ backgroundPosition: "130% 0" }}, {{ backgroundPosition: "-30% 0", duration: 0.9, ease: "power2.inOut" }}, {at + 0.6});',
          f'tl.fromTo("#{cid}-sub", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "expo.out" }}, {at + 0.5});',
          f'tl.fromTo("#{cid}-stars", {{ y: 0 }}, {{ y: -40, duration: {dur}, ease: "none" }}, 0);']
    css = ncss + f"""
#{cid}-rays {{ position: absolute; left: -50%; top: -50%; width: 200%; height: 200%; transform-origin: 50% {50 + 0:.0f}%;
  background: conic-gradient(from 0deg at 50% 50%, transparent 0deg, {g}26 30deg, transparent 60deg, transparent 180deg, {gold}1c 210deg, transparent 240deg); }}
#{cid}-tile {{ position: absolute; left: {cx.W / 2 - T / 2:.0f}px; top: {h * 0.3 - T / 2:.0f}px; width: {T:.0f}px; height: {T:.0f}px; border-radius: {T * 0.27:.0f}px;
  background: linear-gradient(145deg, {p.get("tileFrom", g)}, {p.get("tileTo", "#2b1b6e")}); display: flex; align-items: center; justify-content: center;
  box-shadow: 0 30px 80px rgba(0,0,0,0.5), 0 0 60px {g}aa, inset 0 2px 0 rgba(255,255,255,0.35); }}
#{cid}-name {{ position: absolute; left: 0; right: 0; top: {h * 0.41:.0f}px; text-align: center; font-family: 'Inter'; font-weight: 900; font-size: {h * 0.11:.0f}px; letter-spacing: -0.045em;
  background-image: linear-gradient(100deg, #fff 40%, {gold} 50%, #fff 60%); background-size: 250% 100%; -webkit-background-clip: text; background-clip: text; color: transparent; }}
#{cid}-name span {{ display: inline-block; }}
#{cid}-sub {{ position: absolute; left: 0; right: 0; top: {h * 0.535:.0f}px; text-align: center; font-family: 'Instrument Serif'; font-style: italic; font-size: {h * 0.045:.0f}px; color: {gold}; }}"""
    body = nbody + f"""<div id="{cid}-rays"></div>
<div id="{cid}-tile">{stroke_svg(p.get("paths"), T * 0.58, "#fff", f"{cid}-ip", width=1.6)}</div>
<div id="{cid}-name">{letters}</div>{f'<div id="{cid}-sub">{esc(p["sub"])}</div>' if p.get("sub") else ""}"""
    return scene_file(cx, cid, h, css, body, "\n".join(js))


def sc_endcard(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    ncss, nbody, _ = night(cx, cid, h, glow_at="50% 30%", seed=16)
    gold, g = cx.brand.get("accent", "#F4C76B"), cx.brand.get("glow", "#6C4CF1")
    pills, js = [], [f'tl.fromTo("#{cid}-head", {{ opacity: 0, scale: 0.8, filter: "blur(10px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, 0.05);',
                     f'tl.fromTo("#{cid}-stars", {{ y: 0 }}, {{ y: -90, duration: {dur}, ease: "none" }}, 0);',
                     f'tl.fromTo("#{cid}-glow", {{ scale: 0.9, opacity: 0.6 }}, {{ scale: 1.25, opacity: 1, duration: {dur}, ease: "power1.inOut" }}, 0);']
    for i, pl in enumerate(p.get("pills", [])):
        light = i == 0
        ink = "#120f24" if light else "#fff"
        bg = "rgba(255,255,255,0.95)" if light else "rgba(22,20,40,0.62)"
        pills.append(f'<div id="{cid}-p{i}" class="pill" style="background:{bg}">{stroke_svg(pl.get("paths"), h * 0.04, ink, f"{cid}-pp{i}", glow=not light)}'
                     f'<span style="color:{ink}">{esc(pl["t"])}</span></div>')
        at = cx.s(pl["at"])
        js.append(f'tl.fromTo("#{cid}-p{i}", {{ opacity: 0, x: {-140 if i % 2 == 0 else 140} }}, {{ opacity: 1, x: 0, duration: 0.5, ease: "expo.out" }}, {at});')
        if pl.get("paths"):
            js.append(f'draw(".{cid}-pp{i}", {at + 0.1}, 0.35, 0.06);')
    bio = ""
    if p.get("bioAt") is not None:
        ba = cx.s(p["bioAt"])
        bio = (f'<div id="{cid}-bio"><div id="{cid}-bt">{esc(p.get("bio", "link in bio"))}</div>'
               f'<svg width="120" height="140" viewBox="0 0 120 140" style="overflow:visible;margin-top:6px"><path id="{cid}-arrow" d="M60 6 C 40 50, 80 80, 60 128 M36 104 L60 130 L84 104" '
               f'fill="none" stroke="{gold}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1 1.2" stroke-dashoffset="1.1" style="filter:drop-shadow(0 0 10px {gold})"/></svg></div>')
        js.append(f'tl.fromTo("#{cid}-bt", {{ opacity: 0, scale: 0.4, rotation: -4 }}, {{ opacity: 1, scale: 1, rotation: -4, duration: 0.45, ease: "back.out(2.4)" }}, {ba});')
        js.append(f'draw("#{cid}-arrow", {ba + 0.12}, 0.45);')
    css = ncss + f"""
#{cid}-glow {{ position: absolute; left: 140px; top: {h * 0.12:.0f}px; width: 800px; height: 800px; border-radius: 50%; background: radial-gradient(circle, {g}55 0%, transparent 65%); }}
#{cid}-head {{ position: absolute; left: 0; right: 0; top: {h * 0.13:.0f}px; text-align: center; }}
#{cid}-head .k {{ font-family: 'Caveat'; font-weight: 700; font-size: {h * 0.04:.0f}px; color: rgba(255,255,255,0.85); }}
#{cid}-head .n {{ font-family: 'Inter'; font-weight: 900; font-size: {h * 0.095:.0f}px; letter-spacing: -0.045em; color: #fff; text-shadow: 0 0 50px {g}; }}
#{cid}-head .s {{ font-family: 'Instrument Serif'; font-style: italic; font-size: {h * 0.04:.0f}px; color: {gold}; }}
#{cid}-pills {{ position: absolute; left: 0; right: 0; top: {h * 0.36:.0f}px; display: flex; flex-direction: column; align-items: center; gap: {h * 0.022:.0f}px; }}
#{cid}-pills .pill {{ {GLASS} display: flex; align-items: center; justify-content: center; gap: 26px; border-radius: 80px; padding: {h * 0.016:.0f}px {h * 0.035:.0f}px; min-width: {cx.W * 0.56:.0f}px; }}
#{cid}-pills .pill span {{ font-family: 'Inter'; font-weight: 800; font-size: {h * 0.036:.0f}px; letter-spacing: -0.01em; }}
#{cid}-bio {{ position: absolute; left: 0; right: 0; top: {h * 0.53:.0f}px; text-align: center; }}
#{cid}-bt {{ font-family: 'Caveat'; font-weight: 700; font-size: {h * 0.05:.0f}px; color: {gold}; display: inline-block; }}"""
    kick = '<div class="k">' + esc(p["kicker"]) + "</div>" if p.get("kicker") else ""
    sub = '<div class="s">' + esc(p["sub"]) + "</div>" if p.get("sub") else ""
    head = f'<div id="{cid}-head">{kick}<div class="n">{esc(p["name"])}</div>{sub}</div>'
    body = nbody + f'<div id="{cid}-glow"></div>{head}<div id="{cid}-pills">{"".join(pills)}</div>{bio}'
    return scene_file(cx, cid, h, css, body, "\n".join(js))



# ============================================================================== motion-graphics scenes (UI cards + 3D icons)
INK = "#0B0B12"
CARD = "background:#fff;border-radius:44px;box-shadow:0 40px 90px rgba(0,0,0,0.55), 0 2px 0 rgba(255,255,255,0.9) inset;"
FONT_UI = "'Montserrat', 'Noto Sans Ethiopic'"      # Ethiopic glyphs fall through to Noto, Latin stays Montserrat
FONT_HERO = "'Instrument Serif', 'Noto Serif Ethiopic'"
ETH = re.compile("[ሀ-᎟ⶀ-⷟꬀-꬯]")


def text_w(t: str, size: float, latin: float = 0.43, eth: float = 0.82) -> float:
    """Rough rendered width: an Ethiopic syllable is about twice as wide as a Latin serif letter."""
    return sum((eth if ETH.match(c) else latin) * size for c in t)


def studio(cx: Ctx, cid: str, h: int) -> tuple[str, str, str]:
    """Black stage with a brand-colour bloom rising from the bottom edge and a soft top light; the
    bloom breathes. UI cards and 3D icons sit on it. No grid, no stars, no particles."""
    g = cx.brand.get("glow", "#6C4CF1")
    css = f"""#{cid}-bg {{ position: absolute; inset: 0; background: #050409; }}
#{cid}-bloom {{ position: absolute; left: -20%; width: 140%; top: {h * 0.52:.0f}px; height: {h * 0.7:.0f}px; background: radial-gradient(ellipse 50% 50% at 50% 62%, {g} 0%, {g}aa 26%, {g}33 56%, {g}00 74%); }}
#{cid}-top {{ position: absolute; left: 0; width: 100%; top: 0; height: {h * 0.5:.0f}px; background: radial-gradient(ellipse 70% 60% at 50% 0%, {g}44 0%, {g}00 70%); }}"""
    body = f'<div id="{cid}-bg"></div><div id="{cid}-bloom"></div><div id="{cid}-top"></div>'
    js = (f'tl.fromTo("#{cid}-bloom", {{ scale: 0.9, opacity: 0.7, y: 80 }}, {{ scale: 1.12, opacity: 1, y: -40, duration: DUR, ease: "sine.inOut" }}, 0);\n'
          f'tl.fromTo("#{cid}-all", {{ rotationY: -7, transformPerspective: 1500 }}, {{ rotationY: 7, duration: DUR, ease: "sine.inOut" }}, 0);')
    return css, body, js


def icon3d(name: str) -> str:
    return f"assets/icons3d/{name}_color.png"


def kicker_html(cid: str, text: str | None, accent: str, top: int) -> tuple[str, str, str]:
    if not text:
        return "", "", ""
    css = (f"#{cid}-k {{ position: absolute; left: 0; width: 100%; top: {top}px; text-align: center; }}\n"
           f"#{cid}-k span {{ display: inline-block; font-family: {FONT_UI}; font-weight: 800; font-size: 34px; letter-spacing: 0.16em; text-transform: uppercase; "
           f"color: {INK}; background: {accent}; padding: 12px 28px 11px; border-radius: 999px; }}")
    js = f'tl.fromTo("#{cid}-k span", {{ opacity: 0, y: -30, scale: 0.8 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.4, ease: "back.out(1.8)" }}, 0.12);'
    return css, f'<div id="{cid}-k"><span>{esc(text)}</span></div>', js


def sc_calendarblocks(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    """A week planner card fills with time blocks until nothing is left, then gets stamped.
    p: kicker, title, meta, blocks [{day 0-4, top 0-1, len 0-1, t, c}], fillFrom/fillTo (frames: blocks
    arrive across this span), stampAt (frames), stamp text, icons (two 3dicons names)."""
    a = cx.brand.get("accent", "#FFD21F")
    scss, sbody, sjs = studio(cx, cid, h)
    kcss, kbody, kjs = kicker_html(cid, p.get("kicker"), a, 176)
    X, Y, Wc, Hc = 80, int(h * 0.14), cx.W - 160, int(h * 0.385)
    gx, gy, gw, gh = 44, 190, Wc - 88, Hc - 190 - 44
    colw = gw / 5
    days = "".join(f'<b style="left:{gx + i * colw:.0f}px;width:{colw:.0f}px">{d}</b>' for i, d in enumerate(["MON", "TUE", "WED", "THU", "FRI"]))
    lines = "".join(f'<u style="top:{gy + gh * k / 4:.0f}px"></u>' for k in range(5))
    blocks, js = [], [sjs.replace("DUR", f"{dur:.3f}"), kjs]
    f0, f1 = cx.s(p.get("fillFrom", 8)), cx.s(p.get("fillTo", 60))
    nb = len(p["blocks"])
    for i, b in enumerate(p["blocks"]):
        fg = INK if b.get("c", a).upper() in (a.upper(), "#FFFFFF") else "#fff"
        blocks.append(f'<div class="blk" id="{cid}-b{i}" style="left:{gx + b["day"] * colw + 7:.0f}px;top:{gy + b["top"] * gh + 5:.0f}px;width:{colw - 14:.0f}px;'
                      f'height:{b["len"] * gh - 10:.0f}px;background:{b.get("c", a)};color:{fg}">{esc(b.get("t", ""))}</div>')
        at = f0 + (f1 - f0) * (i / max(1, nb - 1)) ** 0.8
        js.append(f'tl.fromTo("#{cid}-b{i}", {{ opacity: 0, scale: 0.5, y: 20 }}, {{ opacity: 1, scale: 1, y: 0, duration: 0.32, ease: "back.out(2)" }}, {at:.3f});')
    ic = p.get("icons", ["calender", "clock"])
    st = cx.s(p.get("stampAt", 70))
    css = f"""{scss}
{kcss}
#{cid}-card {{ position: absolute; left: {X}px; top: {Y}px; width: {Wc}px; height: {Hc}px; {CARD} }}
#{cid}-card h3 {{ position: absolute; left: 190px; top: 40px; margin: 0; font-family: {FONT_UI}; font-weight: 800; font-size: 54px; letter-spacing: -0.03em; color: {INK}; }}
#{cid}-card em {{ position: absolute; right: 48px; top: 54px; font-family: {FONT_UI}; font-style: normal; font-weight: 700; font-size: 30px; color: #6b6b78; }}
#{cid}-card b {{ position: absolute; top: 138px; text-align: center; font-family: {FONT_UI}; font-weight: 700; font-size: 28px; letter-spacing: 0.08em; color: #9a9aa6; }}
#{cid}-card u {{ position: absolute; left: {gx}px; width: {gw}px; height: 2px; background: #ececf1; }}
#{cid}-card .blk {{ position: absolute; border-radius: 20px; font-family: {FONT_UI}; font-weight: 800; font-size: 28px; letter-spacing: -0.02em; display: flex; align-items: flex-start; padding: 12px 14px; box-sizing: border-box; overflow: hidden; box-shadow: 0 6px 14px rgba(0,0,0,0.14); }}
#{cid}-i0 {{ position: absolute; left: {X - 62}px; top: {Y - 96}px; width: 240px; height: 240px; filter: drop-shadow(0 24px 30px rgba(0,0,0,0.5)); }}
#{cid}-i1 {{ position: absolute; left: {X + Wc - 200}px; top: {Y + Hc - 150}px; width: 280px; height: 280px; filter: drop-shadow(0 24px 30px rgba(0,0,0,0.5)); }}
#{cid}-st {{ position: absolute; left: 0; width: 100%; top: {Y + Hc * 0.47:.0f}px; text-align: center; }}
#{cid}-st span {{ display: inline-block; font-family: 'Anton'; font-size: 120px; line-height: 1; letter-spacing: 0.02em; color: #E5352B; border: 10px solid #E5352B; border-radius: 24px; padding: 14px 34px 8px; background: rgba(255,255,255,0.9); }}"""
    body = (f'{sbody}{kbody}<div id="{cid}-all"><div id="{cid}-card"><h3>{esc(p.get("title", "This week"))}</h3><em>{esc(p.get("meta", ""))}</em>{days}{lines}{"".join(blocks)}</div>'
            f'<img id="{cid}-i0" src="{icon3d(ic[0])}" alt=""><img id="{cid}-i1" src="{icon3d(ic[1])}" alt="">'
            f'<div id="{cid}-st"><span>{esc(p.get("stamp", "FULLY BOOKED"))}</span></div></div>')
    js += [f'tl.fromTo("#{cid}-card", {{ opacity: 0, y: 160, rotationX: 28, transformPerspective: 1400 }}, {{ opacity: 1, y: 0, rotationX: 0, duration: 0.6, ease: "expo.out" }}, 0);',
           f'tl.fromTo("#{cid}-all", {{ scale: 1 }}, {{ scale: 1.045, duration: {dur:.3f}, ease: "none", transformOrigin: "50% 35%" }}, 0);',
           f'tl.fromTo("#{cid}-i0", {{ opacity: 0, scale: 0.3, rotation: -40 }}, {{ opacity: 1, scale: 1, rotation: -12, duration: 0.55, ease: "back.out(1.9)" }}, 0.22);',
           f'tl.fromTo("#{cid}-i1", {{ opacity: 0, scale: 0.3, rotation: 50 }}, {{ opacity: 1, scale: 1, rotation: 10, duration: 0.55, ease: "back.out(1.9)" }}, {max(0.3, st - 0.5):.3f});',
           f'tl.fromTo("#{cid}-st span", {{ opacity: 0, scale: 2.4, rotation: -22 }}, {{ opacity: 1, scale: 1, rotation: -8, duration: 0.24, ease: "power4.in" }}, {st:.3f});',
           f'tl.fromTo("#{cid}-card", {{ x: 0 }}, {{ x: 10, duration: 0.05, ease: "none", yoyo: true, repeat: 5 }}, {st + 0.24:.3f});']
    return scene_file(cx, cid, h, css, body, "\n".join(js))


def sc_choicecards(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    """Cards with 3D icons fan in; on pickAt one is lifted and ticked, the rest fall back.
    p: kicker, cards [{t, icon}], pick (index), pickAt (frames)."""
    a = cx.brand.get("accent", "#FFD21F")
    scss, sbody, sjs = studio(cx, cid, h)
    kcss, kbody, kjs = kicker_html(cid, p.get("kicker"), a, 176)
    n_, cw, ch = len(p["cards"]), 330, 470
    gap = (cx.W - 2 * 60 - cw) / max(1, n_ - 1)
    cy = h * 0.35
    cards, js = [], [sjs.replace("DUR", f"{dur:.3f}"), kjs]
    pk, pa = int(p.get("pick", 1)), cx.s(p.get("pickAt", 40))
    for i, c in enumerate(p["cards"]):
        rot = (i - (n_ - 1) / 2) * 7
        cards.append(f'<div class="cc" id="{cid}-c{i}" style="left:{60 + i * gap:.0f}px;top:{cy - ch / 2 + abs(rot) * 5:.0f}px"><img src="{icon3d(c["icon"])}" alt=""><span>{esc(c["t"])}</span></div>')
        js.append(f'tl.fromTo("#{cid}-c{i}", {{ opacity: 0, y: 520, rotation: {rot * 3:.1f} }}, {{ opacity: 1, y: 0, rotation: {rot:.1f}, duration: 0.6, ease: "expo.out" }}, {0.1 + i * 0.09:.3f});')
        if i == pk:
            js.append(f'tl.to("#{cid}-c{i}", {{ scale: 1.2, y: -40, rotation: 0, boxShadow: "0 0 0 10px {a}, 0 50px 110px rgba(0,0,0,0.6)", duration: 0.45, ease: "back.out(2)" }}, {pa:.3f});')
        else:
            js.append(f'tl.to("#{cid}-c{i}", {{ scale: 0.86, y: 60, opacity: 0.32, filter: "blur(4px)", duration: 0.4, ease: "power3.out" }}, {pa:.3f});')
    tx = 60 + pk * gap + cw - 70
    css = f"""{scss}
{kcss}
#{cid}-all .cc {{ position: absolute; width: {cw}px; height: {ch}px; {CARD} display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; z-index: 1; }}
#{cid}-all #{cid}-c{pk} {{ z-index: 3; }}
#{cid}-all .cc img {{ width: 250px; height: 250px; filter: drop-shadow(0 18px 20px rgba(0,0,0,0.28)); }}
#{cid}-all .cc span {{ font-family: {FONT_UI}; font-weight: 800; font-size: 50px; letter-spacing: -0.03em; color: {INK}; }}
#{cid}-tick {{ position: absolute; left: {tx:.0f}px; top: {cy - ch / 2 - 130:.0f}px; width: 200px; height: 200px; z-index: 5; filter: drop-shadow(0 16px 22px rgba(0,0,0,0.5)); }}"""
    body = f'{sbody}{kbody}<div id="{cid}-all">{"".join(cards)}<img id="{cid}-tick" src="{icon3d("tick")}" alt=""></div>'
    js.append(f'tl.fromTo("#{cid}-tick", {{ opacity: 0, scale: 0.2, rotation: -60 }}, {{ opacity: 1, scale: 1, rotation: 8, duration: 0.5, ease: "back.out(2.2)" }}, {pa + 0.12:.3f});')
    return scene_file(cx, cid, h, css, body, "\n".join(js))


def sc_pileup(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    """Notification cards land faster and faster, each pushing the pile down, every one badged the
    same; at winAt one is kept, enlarged and crowned. Motion after the registry's notification-pileup.
    p: kicker, items [{t, body, icon, at (frames, optional)}], badge, win (index), winAt (frames), winBadge, crown (icon)."""
    a = cx.brand.get("accent", "#FFD21F")
    scss, sbody, sjs = studio(cx, cid, h)
    kcss, kbody, kjs = kicker_html(cid, p.get("kicker"), a, 176)
    items = p["items"]
    n_, step, top0 = len(items), 176, int(h * 0.15)
    wa, wi = cx.s(p.get("winAt", 80)), int(p.get("win", 0))
    ats, t, gap = [], 0.15, min(0.7, max(0.3, (wa - 0.5) / max(1, n_) * 1.5))
    for it in items:
        ats.append(cx.s(it["at"]) if "at" in it else t)
        t += gap
        gap = max(0.14, gap * 0.74)
    rows, js = [], [sjs.replace("DUR", f"{dur:.3f}"), kjs]
    for i, it in enumerate(items):
        win_badge = f'<em class="b1" id="{cid}-w">{esc(p.get("winBadge", "THE ONE"))}</em>' if i == wi else ""
        rows.append(f'<div class="nc" id="{cid}-n{i}"><i><img src="{icon3d(it["icon"])}" alt=""></i><div><b>{esc(it["t"])}</b><span>{esc(it.get("body", ""))}</span></div>'
                    f'<em class="b0" id="{cid}-r{i}">{esc(p.get("badge", "#1"))}</em>{win_badge}</div>')
        js.append(f'tl.fromTo("#{cid}-n{i}", {{ opacity: 0, y: -220, scale: 0.92 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.38, ease: "back.out(1.5)" }}, {ats[i]:.3f});')
        js.append(f'tl.fromTo("#{cid}-r{i}", {{ scale: 0 }}, {{ scale: 1, duration: 0.25, ease: "back.out(3)" }}, {ats[i] + 0.16:.3f});')
        for k in range(i + 1, n_):          # every later arrival pushes this card one slot down
            js.append(f'tl.to("#{cid}-n{i}", {{ y: {(k - i) * step}, duration: 0.24, ease: "power3.out" }}, {ats[k]:.3f});')
        if i == wi:
            js.append(f'tl.to("#{cid}-n{i}", {{ y: {int(h * 0.33) - top0 - 70}, scale: 1.14, boxShadow: "0 0 0 8px {a}, 0 50px 110px rgba(0,0,0,0.6)", duration: 0.5, ease: "expo.out" }}, {wa:.3f});')
            js.append(f'tl.to("#{cid}-r{i}", {{ opacity: 0, scale: 0.4, duration: 0.15 }}, {wa:.3f});')
            js.append(f'tl.fromTo("#{cid}-w", {{ opacity: 0, scale: 0.4 }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2.5)" }}, {wa + 0.12:.3f});')
        else:
            js.append(f'tl.to("#{cid}-n{i}", {{ x: {-900 if i % 2 else 900}, rotation: {-14 if i % 2 else 14}, opacity: 0, filter: "blur(8px)", duration: 0.42, ease: "power3.in" }}, {max(0.0, wa - 0.06 + 0.03 * i):.3f});')
    css = f"""{scss}
{kcss}
#{cid}-all .nc {{ position: absolute; left: 90px; top: {top0}px; width: {cx.W - 180}px; height: 150px; background: #fff; border-radius: 40px; box-shadow: 0 26px 60px rgba(0,0,0,0.5); display: flex; align-items: center; gap: 24px; padding: 0 30px; box-sizing: border-box; }}
#{cid}-all .nc i {{ flex: none; width: 104px; height: 104px; border-radius: 28px; background: #f0eefb; display: flex; align-items: center; justify-content: center; }}
#{cid}-all .nc i img {{ width: 96px; height: 96px; }}
#{cid}-all .nc div {{ flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }}
#{cid}-all .nc b {{ font-family: {FONT_UI}; font-weight: 800; font-size: 40px; letter-spacing: -0.03em; color: {INK}; white-space: nowrap; }}
#{cid}-all .nc span {{ font-family: {FONT_UI}; font-weight: 600; font-size: 28px; color: #77778a; white-space: nowrap; }}
#{cid}-all .nc em {{ flex: none; font-family: {FONT_UI}; font-style: normal; font-weight: 800; font-size: 34px; border-radius: 999px; padding: 10px 22px; }}
#{cid}-all .nc .b0 {{ background: #E5352B; color: #fff; }}
#{cid}-all .nc .b1 {{ position: absolute; right: 30px; background: {a}; color: {INK}; }}
#{cid}-crown {{ position: absolute; left: -6px; top: {int(h * 0.33) - 330}px; width: 250px; height: 250px; z-index: 6; filter: drop-shadow(0 20px 24px rgba(0,0,0,0.55)); }}"""
    body = f'{sbody}{kbody}<div id="{cid}-all">{"".join(rows)}<img id="{cid}-crown" src="{icon3d(p.get("crown", "crown"))}" alt=""></div>'
    js.append(f'tl.fromTo("#{cid}-crown", {{ opacity: 0, y: -260, rotation: 30, scale: 0.6 }}, {{ opacity: 1, y: 0, rotation: -16, scale: 1, duration: 0.55, ease: "back.out(1.9)" }}, {wa + 0.2:.3f});')
    return scene_file(cx, cid, h, css, body, "\n".join(js))


def sc_counterhero(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    """A 3D icon, a huge glowing number that counts up, a label, then a result pill.
    p: kicker, icon, to, suffix, countAt / countDur (frames), label, labelAt, pill {t, icon, at}."""
    a = cx.brand.get("accent", "#FFD21F")
    scss, sbody, sjs = studio(cx, cid, h)
    kcss, kbody, kjs = kicker_html(cid, p.get("kicker"), a, 176)
    ca, cd = cx.s(p.get("countAt", 6)), cx.s(p.get("countDur", 30))
    la = cx.s(p.get("labelAt", p.get("countAt", 6) + 12))
    pill = p.get("pill")
    css = f"""{scss}
{kcss}
#{cid}-ic {{ position: absolute; left: {cx.W / 2 - 150:.0f}px; top: {h * 0.125:.0f}px; width: 300px; height: 300px; filter: drop-shadow(0 26px 30px rgba(0,0,0,0.55)); }}
#{cid}-num {{ position: absolute; left: 0; width: 100%; top: {h * 0.275:.0f}px; text-align: center; font-family: {FONT_HERO}; font-style: italic; font-size: 400px; line-height: 1; color: #fffbe6; white-space: nowrap;
  text-shadow: 0 0 14px {a}, 0 0 44px {a}, 0 0 120px {a}cc; }}
#{cid}-lab {{ position: absolute; left: 0; width: 100%; top: {h * 0.47:.0f}px; text-align: center; font-family: {FONT_UI}; font-weight: 800; font-size: 78px; letter-spacing: -0.02em; color: #fff; text-shadow: 0 6px 24px rgba(0,0,0,0.7); }}
#{cid}-pill {{ position: absolute; left: 0; width: 100%; top: {h * 0.535:.0f}px; text-align: center; }}
#{cid}-pill span {{ display: inline-flex; align-items: center; gap: 16px; background: #fff; color: {INK}; border-radius: 999px; padding: 12px 34px 12px 14px; font-family: {FONT_UI}; font-weight: 800; font-size: 44px; box-shadow: 0 24px 50px rgba(0,0,0,0.5); }}
#{cid}-pill img {{ width: 84px; height: 84px; }}"""
    pill_html = (f'<div id="{cid}-pill"><span><img src="{icon3d(pill.get("icon", "tick"))}" alt="">{esc(pill["t"])}</span></div>' if pill else "")
    body = (f'{sbody}{kbody}<div id="{cid}-all"><img id="{cid}-ic" src="{icon3d(p.get("icon", "medal"))}" alt="">'
            f'<div id="{cid}-num"><span id="{cid}-v">0</span>{esc(p.get("suffix", ""))}</div><div id="{cid}-lab">{esc(p.get("label", ""))}</div>{pill_html}</div>')
    js = [sjs.replace("DUR", f"{dur:.3f}"), kjs,
          f'tl.fromTo("#{cid}-ic", {{ opacity: 0, scale: 0.3, rotation: -40 }}, {{ opacity: 1, scale: 1, rotation: -8, duration: 0.5, ease: "back.out(1.9)" }}, 0.08);',
          f'tl.fromTo("#{cid}-num", {{ opacity: 0, scale: 0.6, filter: "blur(16px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.3, ease: "expo.out" }}, {ca:.3f});',
          f'count("#{cid}-v", 0, {p["to"]}, {ca:.3f}, {cd:.3f}, "power3.out");',
          f'tl.fromTo("#{cid}-lab", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "power3.out" }}, {la:.3f});']
    if pill:
        js.append(f'tl.fromTo("#{cid}-pill span", {{ opacity: 0, scale: 0.6, y: 40 }}, {{ opacity: 1, scale: 1, y: 0, duration: 0.4, ease: "back.out(2)" }}, {cx.s(pill["at"]):.3f});')
    return scene_file(cx, cid, h, css, body, "\n".join(js))


def sc_typewall(cx: Ctx, cid: str, h: int, dur: float, p: dict) -> str:
    """Full-screen kinetic type on solid colour: one spoken word at a time, huge, each replacing the
    last. p: bg, fg, y (0-1), words [{t, at (frames), size, strikeAt, hold}], flipAt (frames) with
    flipBg / flipFg: the whole screen changes colour on that word."""
    bg, fg = p.get("bg", "#4B2BFF"), p.get("fg", "#ffffff")
    rows, js = [], []
    ws = p["words"]
    for i, w in enumerate(ws):
        size = w.get("size", 230)
        k = min(1.0, 980 / max(1.0, text_w(w["t"], size, 0.6, 0.9)))
        strike = f'<i id="{cid}-s{i}"></i>' if "strikeAt" in w else ""
        rows.append(f'<div class="tw" id="{cid}-w{i}" style="font-size:{size * k:.0f}px;opacity:0"><span>{esc(w["t"])}{strike}</span></div>')
        at = cx.s(w["at"])
        end = cx.s(ws[i + 1]["at"]) if i + 1 < len(ws) else dur
        life = max(0.08, end - at)
        tin = min(0.2, life * 0.45)          # a short word must finish arriving before it leaves, or the entrance overrides the exit
        js.append(f'tl.fromTo("#{cid}-w{i}", {{ opacity: 0, scale: 1.5, filter: "blur(18px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: {tin:.3f}, ease: "expo.out" }}, {at});')
        js.append(f'tl.fromTo("#{cid}-w{i} span", {{ scale: 1 }}, {{ scale: 1.08, duration: {max(0.1, end - at):.3f}, ease: "none" }}, {at});')
        if "strikeAt" in w:
            js.append(f'tl.fromTo("#{cid}-s{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.18, ease: "power4.out" }}, {cx.s(w["strikeAt"])});')
        if i + 1 < len(ws):
            tout = min(0.08, life * 0.3)
            js.append(f'tl.fromTo("#{cid}-w{i}", {{ opacity: 1, scale: 1, filter: "blur(0px)" }}, {{ opacity: 0, scale: 0.8, filter: "blur(14px)", duration: {tout:.3f}, ease: "power2.in", immediateRender: false }}, {end - tout:.3f});')
            js.append(f'tl.set("#{cid}-w{i}", {{ opacity: 0 }}, {end:.3f});')
    css = f"""#{cid}-bg {{ position: absolute; inset: 0; background: {bg}; }}
#{cid}-bg2 {{ position: absolute; inset: 0; background: {p.get("flipBg", bg)}; opacity: 0; }}
#{cid}-all .tw {{ position: absolute; left: 0; width: {cx.W}px; top: {p.get("y", 0.43) * h:.0f}px; height: 0; display: flex; align-items: center; justify-content: center; white-space: nowrap;
  font-family: {FONT_UI}; font-weight: 800; letter-spacing: -0.055em; color: {fg}; }}
#{cid}-all .tw span {{ position: relative; display: inline-block; }}
#{cid}-all .tw i {{ position: absolute; left: -3%; top: 50%; width: 106%; height: 0.09em; margin-top: -0.045em; background: {p.get("strike", "#0B0B12")}; transform-origin: 0 50%; }}"""
    if "flipAt" in p:
        fa = cx.s(p["flipAt"])
        js.append(f'tl.set("#{cid}-bg2", {{ opacity: 1 }}, {fa});')
        js.append(f'tl.set("#{cid}-all .tw", {{ color: "{p.get("flipFg", "#0B0B12")}" }}, {fa});')
    body = f'<div id="{cid}-bg"></div><div id="{cid}-bg2"></div><div id="{cid}-all">{"".join(rows)}</div>'
    return scene_file(cx, cid, h, css, body, "\n".join(js))


SCENE_FN = {"RingsDash": sc_ringsdash, "BalanceScale": sc_balancescale, "Equation": sc_equation, "PageScan": sc_pagescan,
            "AppReveal": sc_appreveal, "EndCard": sc_endcard,
            "CalendarBlocks": sc_calendarblocks, "ChoiceCards": sc_choicecards, "PileUp": sc_pileup, "TypeWall": sc_typewall, "CounterHero": sc_counterhero}


# ============================================================================== overlays
def ov_floatchips(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    gold = cx.brand.get("accent", "#F4C76B")
    chips, js = [], []
    for i, it in enumerate(p["items"]):
        c, sz = it.get("color", gold), it.get("size", 46)
        chips.append(f'<div class="chipw" style="left:0;top:{it["y"] * cx.H:.0f}px;width:100%;"><div id="{cid}-c{i}" class="chip" style="margin-left:{it["x"] * cx.W:.0f}px;'
                     f'border-radius:{sz}px;padding:{sz * 0.32:.0f}px {sz * 0.55:.0f}px;gap:{sz * 0.35:.0f}px">'
                     f'{stroke_svg(it.get("paths"), sz * 1.05, c, f"{cid}-ip{i}")}<span style="font-size:{sz}px">{esc(it["t"])}</span></div></div>')
        at = cx.s(it["at"])
        js.append(f'tl.fromTo("#{cid}-c{i}", {{ opacity: 0, scale: 0.6, filter: "blur(8px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.45, ease: "back.out(1.7)" }}, {at});')
        js.append(f'tl.fromTo("#{cid}-c{i}", {{ y: 0 }}, {{ y: {-18 if i % 2 else -10}, duration: {max(0.1, dur - at):.3f}, ease: "none" }}, {at});')
        if it.get("paths"):
            js.append(f'draw(".{cid}-ip{i}", {at + 0.1}, 0.4, 0.06);')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, filter: "blur(10px)", duration: 0.22, ease: "power2.in" }}, {max(0, dur - 0.22):.3f});')
    css = f"""#{cid}-all {{ position: absolute; inset: 0; }}
#{cid}-all .chipw {{ position: absolute; height: 0; }}
#{cid}-all .chip {{ position: absolute; transform: translate(-50%, -50%); display: inline-flex; align-items: center; white-space: nowrap; {GLASS} }}
#{cid}-all .chip span {{ font-family: 'Inter'; font-weight: 800; color: #fff; letter-spacing: -0.02em; }}"""
    # the chip carries a CSS translate for centring, so GSAP moves an inner wrapper instead: use xPercent/yPercent
    css = css.replace("transform: translate(-50%, -50%);", "")
    js.insert(0, f'gsap.set("#{cid}-all .chip", {{ xPercent: -50, yPercent: -50 }});')
    return scene_file(cx, cid, cx.H, css, f'<div id="{cid}-all">{"".join(chips)}</div>', "\n".join(js), transparent=True)


def ov_halo(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    gold = cx.brand.get("accent", "#F4C76B")
    R = p["r"] * cx.W
    css = f"""#{cid}-h {{ position: absolute; left: {p["x"] * cx.W - R:.0f}px; top: {p["y"] * cx.H - R:.0f}px; width: {2 * R:.0f}px; height: {2 * R:.0f}px; border-radius: 50%;
  border: {R * 0.05:.0f}px solid {gold}; box-shadow: 0 0 {R * 0.25:.0f}px {gold}, inset 0 0 {R * 0.25:.0f}px {gold}; background: radial-gradient(circle, {gold}55 0%, {gold}00 70%); }}"""
    js = [f'tl.fromTo("#{cid}-h", {{ opacity: 0, scale: 0.6 }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: "expo.out" }}, 0);',
          f'tl.to("#{cid}-h", {{ opacity: 0, scale: 1.08, duration: 0.3, ease: "power2.in" }}, {max(0.3, dur - 0.3):.3f});']
    return scene_file(cx, cid, cx.H, css, f'<div id="{cid}-h"></div>', "\n".join(js), transparent=True)


def ov_selectionbox(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    c = cx.brand.get("accent", "#F4C76B")
    L, T, Wd, Hd = (p["x"] - p["w"] / 2) * cx.W, (p["y"] - p["h"] / 2) * cx.H, p["w"] * cx.W, p["h"] * cx.H
    handles = [(0, 0), (0.5, 0), (1, 0), (0, 0.5), (1, 0.5), (0, 1), (0.5, 1), (1, 1)]
    hs = "".join(f'<circle class="{cid}-hd" cx="{hx * Wd:.1f}" cy="{hy * Hd:.1f}" r="9" fill="#fff" stroke="{c}" stroke-width="3"/>' for hx, hy in handles)
    guides = ""
    js = []
    if p.get("guides", True):
        guides = (f'<div id="{cid}-g0" class="gh" style="top:{T:.0f}px;left:0"></div><div id="{cid}-g1" class="gh" style="top:{T + Hd:.0f}px;left:0"></div>'
                  f'<div id="{cid}-g2" class="gv" style="left:{L:.0f}px;top:0"></div><div id="{cid}-g3" class="gv" style="left:{L + Wd:.0f}px;top:0"></div>')
        js += [f'tl.fromTo("#{cid}-g0, #{cid}-g1", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.25, ease: "expo.out" }}, 0);',
               f'tl.fromTo("#{cid}-g2, #{cid}-g3", {{ scaleY: 0 }}, {{ scaleY: 1, duration: 0.25, ease: "expo.out" }}, 0);']
    js += [f'draw("#{cid}-rect", 0, 0.4);',
           f'tl.fromTo(".{cid}-hd", {{ scale: 0, transformOrigin: "50% 50%" }}, {{ scale: 1, duration: 0.2, ease: "back.out(3)", stagger: 0.04 }}, 0.24);',
           f'tl.to("#{cid}-all", {{ opacity: 0, duration: 0.2, ease: "power2.in" }}, {max(0.4, dur - 0.2):.3f});']
    css = f"""#{cid}-all {{ position: absolute; inset: 0; }}
#{cid}-all .gh {{ position: absolute; width: {cx.W}px; height: 1.5px; background: {c}aa; transform-origin: 0 50%; }}
#{cid}-all .gv {{ position: absolute; height: {cx.H}px; width: 1.5px; background: {c}aa; transform-origin: 50% 0; }}"""
    body = (f'<div id="{cid}-all">{guides}<svg style="position:absolute;left:{L:.0f}px;top:{T:.0f}px;overflow:visible" width="{Wd:.0f}" height="{Hd:.0f}">'
            f'<rect id="{cid}-rect" x="0" y="0" width="{Wd:.0f}" height="{Hd:.0f}" fill="none" stroke="{c}" stroke-width="3" pathLength="1" stroke-dasharray="1 1.2" stroke-dashoffset="1.1"/>{hs}</svg></div>')
    return scene_file(cx, cid, cx.H, css, body, "\n".join(js), transparent=True)


def ov_counter(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    gold = cx.brand.get("accent", "#F4C76B")
    size = p.get("size", 150)
    cd = p.get("countDur", 40) / cx.fps
    css = f"""#{cid}-w {{ position: absolute; left: 0; top: {p["y"] * cx.H - size * 0.6:.0f}px; width: {2 * p.get("x", 0.5) * cx.W:.0f}px; text-align: center; }}
#{cid}-n {{ font-family: 'Instrument Serif'; font-style: italic; font-size: {size}px; line-height: 1; color: #f7ffef; white-space: nowrap;
  text-shadow: 0 0 6px #fff, 0 0 24px {gold}, 0 0 60px {gold}99; }}
#{cid}-l {{ font-family: 'Inter'; font-weight: 700; font-size: {max(32, size * 0.24):.0f}px; color: #fff; }}"""
    lab = f'<div id="{cid}-l">{esc(p["label"])}</div>' if p.get("label") else ""
    body = f'<div id="{cid}-w"><div id="{cid}-n">{esc(p.get("prefix", ""))}<span id="{cid}-v">{p.get("from", 0)}</span>{esc(p.get("suffix", ""))}</div>{lab}</div>'
    js = [f'tl.fromTo("#{cid}-w", {{ opacity: 0, scale: 0.7 }}, {{ opacity: 1, scale: 1, duration: 0.45, ease: "back.out(1.8)" }}, 0);',
          f'count("#{cid}-v", {p.get("from", 0)}, {p["to"]}, 0.16, {cd:.3f});',
          f'tl.to("#{cid}-w", {{ opacity: 0, filter: "blur(10px)", duration: 0.2, ease: "power2.in" }}, {max(0.4, dur - 0.2):.3f});']
    if p.get("label"):
        js.append(f'tl.fromTo("#{cid}-l", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, {0.16 + cd:.3f});')
    return scene_file(cx, cid, cx.H, css, body, "\n".join(js), transparent=True)


def ov_bigword(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Large display words, usually `behind: true` the speaker (the matte puts the head in front).
    items: {t, at (frames, overlay-relative), y (0-1 centre), size px, font 'Anton' | 'Instrument Serif',
    color, strikeAt (frames: a bar draws through the word, the word dims), out (frames: leaves early)}.
    Each word arrives with a horizontal squeeze (a transform, so it never snaps to whole pixels) and a rise; nothing bounces."""
    gold = cx.brand.get("accent", "#F4C76B")
    rows, js = [], []
    css = [f"#{cid}-all {{ position: absolute; inset: 0; }}",
           f"#{cid}-all .bw {{ position: absolute; left: 0; width: {cx.W}px; text-align: center; white-space: nowrap; line-height: 0.86; }}",
           f"#{cid}-all .bw span {{ position: relative; display: inline-block; }}",
           f"#{cid}-all .bw i {{ position: absolute; left: -4%; top: 50%; width: 108%; height: 0.075em; margin-top: -0.0375em; background: {gold}; transform-origin: 0 50%; }}"]
    for i, it in enumerate(p["items"]):
        size, font = it.get("size", 300), it.get("font", "Anton")
        italic = "font-style: italic;" if font == "Instrument Serif" else ""
        col = it.get("color", "#ffffff")
        rows.append(f'<div class="bw" id="{cid}-w{i}" style="top:{it["y"] * cx.H - size * 0.45:.0f}px;font-family:\'{font}\',\'Noto Sans Ethiopic\';font-weight:{it.get("weight", 400)};font-synthesis:none;{italic}font-size:{size}px;color:{col};'
                    f'text-shadow:0 10px 40px rgba(0,0,0,0.45);opacity:0"><span>{esc(it["t"])}{"<i id=" + chr(34) + f"{cid}-s{i}" + chr(34) + "></i>" if "strikeAt" in it else ""}</span></div>')
        at = cx.s(it["at"])
        js.append(f'tl.fromTo("#{cid}-w{i}", {{ opacity: 0, y: 40, scaleX: 1.18, filter: "blur(12px)" }}, '
                  f'{{ opacity: {it.get("alpha", 1)}, y: 0, scaleX: 1, filter: "blur(0px)", duration: 0.5, ease: "expo.out" }}, {at});')
        js.append(f'tl.fromTo("#{cid}-w{i} span", {{ scale: 1 }}, {{ scale: 1.06, duration: {max(0.2, dur - at):.3f}, ease: "none" }}, {at});')
        if "strikeAt" in it:
            sa = cx.s(it["strikeAt"])
            js.append(f'tl.fromTo("#{cid}-s{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.28, ease: "power3.inOut" }}, {sa});')
            js.append(f'tl.to("#{cid}-w{i}", {{ opacity: 0.38, duration: 0.3 }}, {sa + 0.2:.3f});')
        if "out" in it:
            js.append(f'tl.to("#{cid}-w{i}", {{ opacity: 0, filter: "blur(10px)", duration: 0.2, ease: "power2.in" }}, {cx.s(it["out"])});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, filter: "blur(10px)", duration: 0.2, ease: "power2.in" }}, {max(0, dur - 0.2):.3f});')
    return scene_file(cx, cid, cx.H, "\n".join(css), f'<div id="{cid}-all">{"".join(rows)}</div>', "\n".join(js), transparent=True)


def ov_floaticons(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """3D icons (3dicons renders) floating beside the speaker: pop in with a turn, drift, optional
    red slash (`slashAt`), optional early exit (`out`). items: {icon, x, y, size, at, rot, slashAt, out}."""
    rows, js, css = [], [], [f"#{cid}-all {{ position: absolute; inset: 0; }}",
                             f"#{cid}-all .fi {{ position: absolute; }}",
                             f"#{cid}-all .fi img {{ width: 100%; height: 100%; filter: drop-shadow(0 22px 26px rgba(0,0,0,0.55)); }}",
                             f"#{cid}-all .fi u {{ position: absolute; left: -8%; top: 46%; width: 116%; height: 9%; border-radius: 99px; background: #E5352B; box-shadow: 0 6px 16px rgba(0,0,0,0.4); transform-origin: 0 50%; }}"]
    for i, it in enumerate(p["items"]):
        sz, rot, at = it.get("size", 240), it.get("rot", 0), cx.s(it["at"])
        slash = f'<u id="{cid}-s{i}"></u>' if "slashAt" in it else ""
        rows.append(f'<div class="fi" id="{cid}-f{i}" style="left:{it["x"] * cx.W - sz / 2:.0f}px;top:{it["y"] * cx.H - sz / 2:.0f}px;width:{sz}px;height:{sz}px;opacity:0">'
                    f'<img src="{icon3d(it["icon"])}" alt="">{slash}</div>')
        js.append(f'tl.fromTo("#{cid}-f{i}", {{ opacity: 0, scale: 0.25, rotation: {rot - 45} }}, {{ opacity: 1, scale: 1, rotation: {rot}, duration: 0.5, ease: "back.out(2)" }}, {at});')
        js.append(f'tl.fromTo("#{cid}-f{i} img", {{ y: 0 }}, {{ y: {-20 if i % 2 else -14}, duration: {max(0.2, dur - at):.3f}, ease: "sine.inOut" }}, {at});')
        if "slashAt" in it:
            sa = cx.s(it["slashAt"])
            js.append(f'gsap.set("#{cid}-s{i}", {{ rotation: -28 }});')
            js.append(f'tl.fromTo("#{cid}-s{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.2, ease: "power4.out" }}, {sa});')
            js.append(f'tl.to("#{cid}-f{i} img", {{ opacity: 0.55, duration: 0.2 }}, {sa});')
        if "out" in it:
            js.append(f'tl.to("#{cid}-f{i}", {{ opacity: 0, scale: 0.6, filter: "blur(8px)", duration: 0.2, ease: "power2.in" }}, {cx.s(it["out"])});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, filter: "blur(10px)", duration: 0.2, ease: "power2.in" }}, {max(0, dur - 0.2):.3f});')
    return scene_file(cx, cid, cx.H, "\n".join(css), f'<div id="{cid}-all">{"".join(rows)}</div>', "\n".join(js), transparent=True)


def ov_stamp(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A rubber stamp slammed over the frame. p: t, x, y (0-1), size, rot, at (frames), color."""
    c, size = p.get("color", "#E5352B"), p.get("size", 150)
    at = cx.s(p.get("at", 2))
    css = f"""#{cid}-w {{ position: absolute; left: 0; width: {2 * p.get("x", 0.5) * cx.W:.0f}px; top: {p.get("y", 0.3) * cx.H - size * 0.7:.0f}px; text-align: center; }}
#{cid}-s {{ display: inline-block; font-family: 'Anton', 'Noto Sans Ethiopic'; font-weight: {p.get("weight", 900)}; font-synthesis: none; font-size: {size}px; line-height: 1.1; color: {c}; border: {max(8, size * 0.07):.0f}px solid {c};
  border-radius: {size * 0.16:.0f}px; padding: {size * 0.06:.0f}px {size * 0.26:.0f}px {size * 0.02:.0f}px; background: rgba(255,255,255,0.92); box-shadow: 0 24px 60px rgba(0,0,0,0.5); white-space: nowrap; }}"""
    js = [f'tl.fromTo("#{cid}-s", {{ opacity: 0, scale: 2.6, rotation: {p.get("rot", -8) - 16} }}, {{ opacity: 1, scale: 1, rotation: {p.get("rot", -8)}, duration: 0.2, ease: "power4.in" }}, {at});',
          f'tl.fromTo("#{cid}-w", {{ x: 0 }}, {{ x: 12, duration: 0.04, ease: "none", yoyo: true, repeat: 5 }}, {at + 0.2:.3f});',
          f'tl.to("#{cid}-w", {{ opacity: 0, filter: "blur(10px)", duration: 0.15, ease: "power2.in" }}, {max(at + 0.3, dur - 0.15):.3f});']
    return scene_file(cx, cid, cx.H, css, f'<div id="{cid}-w"><span id="{cid}-s">{esc(p["t"])}</span></div>', "\n".join(js), transparent=True)


OVERLAY_FN = {"FloatChips": ov_floatchips, "Halo": ov_halo, "SelectionBox": ov_selectionbox, "Counter": ov_counter, "BigWord": ov_bigword, "FloatIcons": ov_floaticons, "Stamp": ov_stamp}


# ============================================================================== captions
def captions_lockup(cx: Ctx, caps: list[dict], ys: list[float], size: float, framed: list[str] | None = None) -> str:
    """Lockup captions, built to the frame timings measured on the reference shorts at 30 fps.

    A keyword card: a dark band rises behind the caption (4 frames); the small words arrive on their
    spoken frames in a light sans line; the keyword - huge serif italic in the accent colour - wipes in
    left to right in 6 frames on its spoken frame and its neon glow builds over the next 8. Words after
    the keyword sit small below it. `framed` keywords get a selection frame with handles and guide
    lines that lands BEFORE the words (5 frames), and leave with a 3-frame push-blur.
    A card with no keyword is one bold white line. `size` is the keyword size in px."""
    a = cx.brand.get("accent", "#FFD21F")
    framed = [f.lower().strip(".,!?") for f in (framed or [])]
    fr = 1 / cx.fps
    groups, js = [], []
    sm = max(44.0, size * 0.3)
    for gi, (g, y) in enumerate(zip(caps, ys)):
        ws = g["words"]
        s_, e_ = cx.s(g["s"]), cx.s(g["e"])
        ki = next((i for i, w in enumerate(ws) if w["emph"]), None)

        def small(idx, plain=False):
            out = []
            for i in idx:
                out.append(f'<span id="cp{gi}w{i}" class="s">{esc(ws[i]["w"])}</span>')
                js.append(f'tl.fromTo("#cp{gi}w{i}", {{ opacity: 0, y: {18 if plain else 12} }}, {{ opacity: 1, y: 0, duration: {5 * fr:.3f}, ease: "power3.out" }}, {max(0.0, cx.s(ws[i]["s"]) - 0.04):.3f});')
            return " ".join(out)
        if ki is None:          # no keyword on this card: one plain bold line, never a fake keyword
            groups.append(f'<div id="cp{gi}" class="cg" style="top:{y * cx.H:.0f}px"><div class="in"><div class="l1 pl" style="font-size:{size * 0.46:.0f}px">{small(range(len(ws)), True)}</div></div></div>')
            js.append(f'tl.set("#cp{gi}", {{ visibility: "visible", opacity: 1, scale: 1, filter: "blur(0px)" }}, {s_:.3f});')
            js.append(f'tl.to("#cp{gi}", {{ opacity: 0, filter: "blur(12px)", duration: {3 * fr:.3f}, ease: "power2.in" }}, {max(s_, e_ - 3 * fr):.3f});')
            js.append(f'tl.set("#cp{gi}", {{ visibility: "hidden" }}, {e_:.3f});')
            continue
        kw = ws[ki]["w"]
        k = min(1.0, 940 / max(1.0, text_w(kw, size)))
        is_framed = kw.lower().strip(".,!?") in framed
        top, bot = small(range(0, ki)), small(range(ki + 1, len(ws)))
        t0 = max(s_, cx.s(ws[ki]["s"]) - 0.05)
        # keyword: 6-frame wipe from the left, then the glow layer builds over 8 frames
        js.append(f'tl.fromTo("#cp{gi}k", {{ clipPath: "inset(-20% 100% -30% -5%)", x: -26 }}, {{ clipPath: "inset(-20% -5% -30% -5%)", x: 0, duration: {6 * fr:.3f}, ease: "power2.out" }}, {t0:.3f});')
        js.append(f'tl.fromTo("#cp{gi}g", {{ opacity: 0 }}, {{ opacity: 1, duration: {8 * fr:.3f}, ease: "power1.out" }}, {t0 + 3 * fr:.3f});')
        js.append(f'tl.fromTo("#cp{gi}st", {{ opacity: 0, scaleX: 0.1, xPercent: -60 }}, {{ opacity: 0.9, scaleX: 1, xPercent: 60, duration: {6 * fr:.3f}, ease: "power2.out" }}, {t0:.3f});')
        js.append(f'tl.to("#cp{gi}st", {{ opacity: 0, duration: {3 * fr:.3f} }}, {t0 + 6 * fr:.3f});')
        js.append(f'tl.fromTo("#cp{gi}d", {{ opacity: 0 }}, {{ opacity: 1, duration: {4 * fr:.3f}, ease: "none" }}, {s_:.3f});')
        frame = ""
        if is_framed:
            frame = (f'<div class="fr" id="cp{gi}f"><b></b><b></b><b></b><b></b><b></b><b></b><b></b><b></b></div>'
                     f'<u class="gh" id="cp{gi}g0" style="top:0"></u><u class="gh" id="cp{gi}g1" style="bottom:0"></u>'
                     f'<u class="gv" id="cp{gi}g2" style="left:0"></u><u class="gv" id="cp{gi}g3" style="right:0"></u>')
            tf = max(s_, t0 - 6 * fr)       # the frame lands 6 frames before its keyword, never sits empty for longer
            js.append(f'tl.fromTo("#cp{gi}f", {{ opacity: 0, scale: 1.14 }}, {{ opacity: 1, scale: 1, duration: {5 * fr:.3f}, ease: "expo.out" }}, {tf:.3f});')
            js.append(f'tl.fromTo("#cp{gi}g0, #cp{gi}g1", {{ scaleX: 0, opacity: 0 }}, {{ scaleX: 1, opacity: 0.55, duration: {6 * fr:.3f}, ease: "expo.out" }}, {tf:.3f});')
            js.append(f'tl.fromTo("#cp{gi}g2, #cp{gi}g3", {{ scaleY: 0, opacity: 0 }}, {{ scaleY: 1, opacity: 0.55, duration: {6 * fr:.3f}, ease: "expo.out" }}, {tf:.3f});')
        left = " lf" if is_framed else ""
        groups.append(f'<div class="dim" id="cp{gi}d" style="top:{y * cx.H - 330:.0f}px;height:{cx.H - (y * cx.H - 330):.0f}px"></div>'
                      f'<div id="cp{gi}" class="cg" style="top:{y * cx.H:.0f}px"><div class="in{left}">{frame}'
                      f'<div class="l1" style="font-size:{sm:.0f}px">{top or "&nbsp;"}</div>'
                      f'<div class="kwrap" style="font-size:{size * k:.0f}px"><i class="st" id="cp{gi}st"></i>'
                      f'<div class="kw" id="cp{gi}k">{esc(kw)}<div class="kg" id="cp{gi}g">{esc(kw)}</div></div></div>'
                      f'<div class="l1 l2" style="font-size:{sm:.0f}px">{bot or "&nbsp;"}</div></div></div>')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "visible", opacity: 1, scale: 1, filter: "blur(0px)" }}, {s_:.3f});')
        js.append(f'tl.set("#cp{gi}d", {{ visibility: "visible" }}, {s_:.3f});')
        if is_framed:           # leaves with a push-blur (the flash that follows is an fx entry)
            js.append(f'tl.to("#cp{gi}", {{ opacity: 0, scale: 1.16, filter: "blur(14px)", duration: {3 * fr:.3f}, ease: "power2.in" }}, {max(s_, e_ - 3 * fr):.3f});')
        else:
            js.append(f'tl.to("#cp{gi}", {{ opacity: 0, filter: "blur(12px)", duration: {3 * fr:.3f}, ease: "power2.in" }}, {max(s_, e_ - 3 * fr):.3f});')
        js.append(f'tl.to("#cp{gi}d", {{ opacity: 0, duration: {3 * fr:.3f}, ease: "none" }}, {max(s_, e_ - 3 * fr):.3f});')
        js.append(f'tl.set("#cp{gi}, #cp{gi}d", {{ visibility: "hidden" }}, {e_:.3f});')
    css = f"""#caps {{ position: absolute; inset: 0; }}
#caps .dim {{ position: absolute; left: 0; width: {cx.W}px; visibility: hidden; background: linear-gradient(180deg, rgba(4,3,8,0) 0%, rgba(4,3,8,0.62) 34%, rgba(4,3,8,0.78) 100%); }}
#caps .cg {{ position: absolute; left: 0; right: 0; transform: translateY(-50%); text-align: center; visibility: hidden; overflow: visible; }}
#caps .in {{ position: relative; display: inline-block; padding: 14px 40px 16px; }}
#caps .in.lf {{ text-align: left; }}
#caps .l1 {{ font-family: {FONT_UI}; font-weight: 600; letter-spacing: -0.01em; line-height: 1.15; color: #fff; white-space: nowrap; text-shadow: 0 2px 10px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.7); }}
#caps .l2 {{ text-align: right; }}
#caps .l1 span {{ display: inline-block; }}
#caps .pl {{ font-weight: 800; letter-spacing: -0.035em; text-shadow: 0 4px 0 rgba(0,0,0,0.4), 0 10px 34px rgba(0,0,0,0.8); }}
#caps .kwrap {{ position: relative; line-height: 0.92; }}
#caps .kw {{ position: relative; display: inline-block; font-family: {FONT_HERO}; font-style: italic; font-weight: 400; font-synthesis: none; letter-spacing: -0.02em; color: {a}; white-space: nowrap; padding: 0 0.1em 0.08em;
  text-shadow: 0 6px 24px rgba(0,0,0,0.75); }}
#caps .kg {{ position: absolute; left: 0; top: 0; padding: 0 0.1em 0.08em; color: #fffbe6; opacity: 0; text-shadow: 0 0 12px {a}, 0 0 36px {a}, 0 0 90px {a}cc, 0 0 160px {a}88; }}
#caps .st {{ position: absolute; left: 0; top: 46%; width: 100%; height: 0.07em; background: linear-gradient(90deg, {a}00, #fff 50%, {a}00); opacity: 0; }}
#caps .fr {{ position: absolute; inset: 0; border: 2px solid {a}; background: {a}12; }}
#caps .fr b {{ position: absolute; width: 14px; height: 14px; margin: -8px; border-radius: 50%; background: #fff; border: 2px solid {a}; box-sizing: border-box; }}
#caps .fr b:nth-child(1) {{ left: 0; top: 0; }} #caps .fr b:nth-child(2) {{ left: 50%; top: 0; }} #caps .fr b:nth-child(3) {{ left: 100%; top: 0; }}
#caps .fr b:nth-child(4) {{ left: 0; top: 50%; }} #caps .fr b:nth-child(5) {{ left: 100%; top: 50%; }}
#caps .fr b:nth-child(6) {{ left: 0; top: 100%; }} #caps .fr b:nth-child(7) {{ left: 50%; top: 100%; }} #caps .fr b:nth-child(8) {{ left: 100%; top: 100%; }}
#caps .gh {{ position: absolute; left: -1200px; width: 3400px; height: 1.5px; background: {a}; }}
#caps .gv {{ position: absolute; top: -2200px; height: 4600px; width: 1.5px; background: {a}; }}"""
    return scene_file(cx, "captions", cx.H, css, f'<div id="caps">{"".join(groups)}</div>', "\n".join(js), transparent=True)


def captions_box(cx: Ctx, caps: list[dict], ys: list[float], size: float) -> str:
    """Box captions: ONE voice for the whole video. Heavy sans, white with a hard shadow, up to two
    balanced lines; the emphasis word sits in an accent-colour box with ink text. Every word pops on
    its spoken frame; the box scales in. Same font, size and place on every card."""
    a = cx.brand.get("accent", "#FFD21F")
    groups, js = [], []
    for gi, (g, y) in enumerate(zip(caps, ys)):
        longest = max(len(w["w"]) for w in g["words"])
        k = min(1.0, 900 / max(1.0, longest * 0.66 * size + 0.5 * size))       # only a single over-long word shrinks the card
        spans = []
        for wi, w in enumerate(g["words"]):
            cls = "e" if w["emph"] else "w"
            spans.append(f'<span id="cp{gi}w{wi}" class="{cls}">{esc(w["w"])}</span>')
            t0 = max(0.0, cx.s(w["s"]) - 0.04)
            if w["emph"]:
                js.append(f'tl.fromTo("#cp{gi}w{wi}", {{ opacity: 0, scale: 0.6, rotation: -5 }}, {{ opacity: 1, scale: 1, rotation: -2, duration: 0.26, ease: "back.out(2.6)" }}, {t0:.3f});')
            else:
                js.append(f'tl.fromTo("#cp{gi}w{wi}", {{ opacity: 0, y: 22, scale: 0.9 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.18, ease: "power3.out" }}, {t0:.3f});')
        s_, e_ = cx.s(g["s"]), cx.s(g["e"])
        groups.append(f'<div id="cp{gi}" class="cg" style="top:{y * cx.H:.0f}px;font-size:{size * k:.1f}px"><div class="in">{" ".join(spans)}</div></div>')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "visible", opacity: 1 }}, {s_:.3f});')
        js.append(f'tl.to("#cp{gi}", {{ opacity: 0, duration: 0.1, ease: "power2.in" }}, {max(s_, e_ - 0.1):.3f});')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "hidden" }}, {e_:.3f});')
    css = f"""#caps {{ position: absolute; inset: 0; }}
#caps .cg {{ position: absolute; left: 0; right: 0; transform: translateY(-50%); text-align: center; visibility: hidden; line-height: 1.14; padding: 0 70px; overflow: visible; }}
#caps .in {{ display: inline-block; max-width: 940px; text-wrap: balance; }}
#caps .cg span {{ display: inline-block; font-family: {FONT_UI}; font-weight: 800; letter-spacing: -0.035em; }}
#caps .w {{ color: #fff; text-shadow: 0 4px 0 rgba(0,0,0,0.45), 0 10px 34px rgba(0,0,0,0.75), 0 0 3px rgba(0,0,0,0.6); }}
#caps .e {{ color: {INK}; background: {a}; padding: 0 0.2em; border-radius: 0.16em; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}"""
    return scene_file(cx, "captions", cx.H, css, f'<div id="caps">{"".join(groups)}</div>', "\n".join(js), transparent=True)


def captions_file(cx: Ctx, caps: list[dict], ys: list[float], size: float, scrims: list[bool] | None = None) -> str:
    """Phrase captions: each word arrives on its spoken frame with a blur-in rise; emphasis words
    switch to the serif italic in the accent colour at 1.32x with a soft glow; the group leaves with
    a quick blur-out, then a hard kill."""
    gold = cx.brand.get("accent", "#F4C76B")
    groups, js = [], []
    for gi, (g, y) in enumerate(zip(caps, ys)):
        # fit: estimate the line width and shrink the group, never the words individually
        est = sum(len(w["w"]) * (0.43 * 1.32 if w["emph"] else 0.58) * size + 0.24 * size for w in g["words"])
        k = min(1.0, 940 / max(1.0, est))
        spans = []
        for wi, w in enumerate(g["words"]):
            cls = "e" if w["emph"] else "w"
            spans.append(f'<span id="cp{gi}w{wi}" class="{cls}">{esc(w["w"])}</span>')
            js.append(f'tl.fromTo("#cp{gi}w{wi}", {{ opacity: 0, y: 16, filter: "blur(9px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.2, ease: "power3.out" }}, {max(0.0, cx.s(w["s"]) - 0.04):.3f});')
        s, e = cx.s(g["s"]), cx.s(g["e"])
        scr = " scrim" if scrims and scrims[gi] else ""
        groups.append(f'<div id="cp{gi}" class="cg" style="top:{y * cx.H:.0f}px;font-size:{size * k:.1f}px"><div class="in{scr}">{" ".join(spans)}</div></div>')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "visible", opacity: 1, filter: "blur(0px)" }}, {s:.3f});')
        js.append(f'tl.to("#cp{gi}", {{ opacity: 0, filter: "blur(10px)", duration: 0.14, ease: "power2.in" }}, {max(s, e - 0.14):.3f});')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "hidden" }}, {e:.3f});')
    css = f"""#caps {{ position: absolute; inset: 0; }}
#caps .cg {{ position: absolute; left: 0; right: 0; transform: translateY(-50%); text-align: center; visibility: hidden; line-height: 1.08; padding: 0 76px; overflow: visible; }}
#caps .cg span {{ display: inline-block; }}
#caps .in {{ display: inline-block; padding: 0.08em 0.4em 0.14em; border-radius: 0.4em; }}
#caps .in.scrim {{ background: rgba(8,6,20,0.62); box-shadow: 0 10px 30px rgba(0,0,0,0.35); }}
#caps .w {{ font-family: 'Inter'; font-weight: 800; letter-spacing: -0.025em; color: #fff; text-shadow: 0 4px 18px rgba(0,0,0,0.6), 0 1px 2px rgba(0,0,0,0.5); }}
#caps .e {{ font-family: 'Instrument Serif'; font-style: italic; font-weight: 400; font-size: 1.32em; letter-spacing: -0.01em; color: {gold}; text-shadow: 0 0 28px {gold}66, 0 4px 18px rgba(0,0,0,0.55); }}"""
    # translateY on .cg is CSS; GSAP only tweens opacity/filter/visibility on the group, y on the words
    return scene_file(cx, "captions", cx.H, css, f'<div id="caps">{"".join(groups)}</div>', "\n".join(js), transparent=True)


# ============================================================================== root
def root_file(cx: Ctx, T: float, layout: list[dict], scenes: list[dict], overlays: list[dict], fx: list[dict], bg: list[dict],
              face_y: float, has_fg: bool, has_soft: bool, has_bw: bool, splits: list[tuple], glass: list[tuple],
              camera: list[dict] | None = None, finish: dict | None = None, has_raw: bool = False) -> str:
    W, H = cx.W, cx.H
    gold, g = cx.brand.get("accent", "#F4C76B"), cx.brand.get("glow", "#6C4CF1")
    el, js = [], []
    track = [10]

    def tr() -> int:
        track[0] += 1
        return track[0]
    vid = f'style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover"'
    cam = [f'<video id="base" class="clip" data-start="0" data-duration="{T}" data-track-index="0" src="assets/base.mp4" muted playsinline {vid}></video>']
    for i, b in enumerate(bg if has_bw else []):
        s, e = cx.s(b["s"]), cx.s(b["e"])
        if b["color"] == "bw":
            cam.append(f'<video id="bw{i}" class="clip" data-start="{s}" data-duration="{round(e - s, 4)}" data-media-start="{s}" data-track-index="1" src="assets/base_bw.mp4" muted playsinline {vid}></video>')
    # raw (ungraded, e.g. camera log) footage wiped against the graded picture: bg {s, e, color: "raw",
    # x0 (0-1 raw share at s, from the left), wipe [{at, x, dur, ease}], labels [left, right], line}
    for i, b in enumerate(bg if has_raw else []):
        if b["color"] != "raw":
            continue
        s, e = cx.s(b["s"]), cx.s(b["e"])
        d = round(e - s, 4)
        x0 = float(b.get("x0", 1.0))
        cam.append(f'<video id="raw{i}" class="clip" data-start="{s}" data-duration="{d}" data-media-start="{s}" data-track-index="1" src="assets/base_raw.mp4" muted playsinline {vid}></video>')
        js.append(f'tl.set("#raw{i}", {{ clipPath: "inset(0% {100 - x0 * 100:.2f}% 0% 0%)" }}, {s});')
        lab = b.get("labels") or ["LOG", "GRADED"]
        if b.get("line", True):
            acc = cx.brand.get("accent", "#FF9A2E")
            cam.append(f'<div id="rawl{i}" class="clip" data-start="{s}" data-duration="{d}" data-track-index="2" style="position:absolute;left:0;top:0;width:0;height:{H}px">'
                       f'<div style="position:absolute;left:-3px;top:0;width:6px;height:{H}px;background:#fff;box-shadow:0 0 24px rgba(255,255,255,0.9),0 0 60px {acc}"></div>'
                       f'<div class="rlab{i}" style="position:absolute;right:26px;top:{int(H * b.get('label_y', 0.55))}px;font:700 34px/1 JetBrains Mono,monospace;color:#fff;padding:10px 16px;border-radius:10px;background:rgba(0,0,0,0.55);white-space:nowrap">{lab[0]}</div>'
                       f'<div class="rlab{i}" style="position:absolute;left:26px;top:{int(H * b.get('label_y', 0.55))}px;font:700 34px/1 JetBrains Mono,monospace;color:#0B1220;padding:10px 16px;border-radius:10px;background:{acc};white-space:nowrap">{lab[1]}</div></div>')
            js.append(f'tl.set("#rawl{i}", {{ x: {x0 * W:.1f} }}, {s});')
            if x0 >= 0.999 and b.get("wipe"):          # line parked off the right edge: labels wait for the first move
                js.append(f'tl.set(".rlab{i}", {{ opacity: 0 }}, {s});')
                js.append(f'tl.to(".rlab{i}", {{ opacity: 1, duration: 0.2 }}, {cx.s(b["wipe"][0]["at"])});')
        for w in b.get("wipe", []):
            at, du, ez = cx.s(w["at"]), max(0.04, cx.s(w.get("dur", 12))), w.get("ease", "expo.inOut")
            js.append(f'tl.to("#raw{i}", {{ clipPath: "inset(0% {100 - w["x"] * 100:.2f}% 0% 0%)", duration: {du}, ease: "{ez}" }}, {at});')
            if b.get("line", True):
                js.append(f'tl.to("#rawl{i}", {{ x: {w["x"] * W:.1f}, duration: {du}, ease: "{ez}" }}, {at});')
    el.append(f'<div id="cam" style="position:absolute;inset:0;z-index:1;overflow:hidden;transform-origin:50% {face_y * 100:.1f}%">{"".join(cam)}</div>')
    # split layouts: blurred copy fills the lower half, the speaker sits in it at SPLIT_SCALE, feathered
    sc = SPLIT_SCALE
    sx, sy = (W - W * sc) / 2, H / 2 + SPLIT_FACE_AT * (H / 2) - face_y * H * sc
    feather = "linear-gradient(90deg, transparent 0%, #000 12%, #000 88%, transparent 100%)"
    for i, (s, e) in enumerate(splits):
        el.append(f'<video id="spb{i}" class="clip" data-start="{s}" data-duration="{round(e - s, 4)}" data-media-start="{s}" data-track-index="2" src="assets/base_soft.mp4" muted playsinline '
                  f'style="position:absolute;left:0;top:{H // 2}px;width:{W}px;height:{H // 2}px;object-fit:cover;z-index:2"></video>')
        el.append(f'<video id="sps{i}" class="clip" data-start="{s}" data-duration="{round(e - s, 4)}" data-media-start="{s}" data-track-index="3" src="assets/base.mp4" muted playsinline '
                  f'style="position:absolute;left:{sx:.0f}px;top:{sy:.0f}px;width:{W * sc:.0f}px;height:{H * sc:.0f}px;z-index:2;-webkit-mask-image:{feather};mask-image:{feather}"></video>')
        el.append(f'<div id="spl{i}" class="clip" data-start="{s}" data-duration="{round(e - s, 4)}" data-track-index="4" '
                  f'style="position:absolute;left:0;top:{H // 2 - 3}px;width:{W}px;height:6px;background:rgba(0,0,0,0.6);z-index:2"></div>')
    for i, (s, e) in enumerate(glass):
        el.append(f'<video id="gls{i}" class="clip" data-start="{s}" data-duration="{round(e - s, 4)}" data-media-start="{s}" data-track-index="2" src="assets/base_soft.mp4" muted playsinline '
                  f'style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover;z-index:2"></video>')
    for sc_ in scenes:
        el.append(f'<div id="{sc_["cid"]}" data-composition-id="{sc_["cid"]}" data-composition-src="compositions/{sc_["cid"]}.html" data-start="{sc_["s"]}" '
                  f'data-duration="{sc_["d"]}" data-track-index="{tr()}" data-track-kind="graphics" data-width="{W}" data-height="{H}" style="position:absolute;inset:0;z-index:{0 if sc_.get("under") else 3}"></div>')
    for o in overlays:
        if o["behind"]:
            el.append(f'<div id="{o["cid"]}" data-composition-id="{o["cid"]}" data-composition-src="compositions/{o["cid"]}.html" data-start="{o["s"]}" '
                      f'data-duration="{o["d"]}" data-track-index="{tr()}" data-track-kind="graphics" data-width="{W}" data-height="{H}" style="position:absolute;inset:0;z-index:4"></div>')
    if has_fg:
        # The cut-out only matters where something sits behind the speaker. An alpha source is extracted as
        # full-size PNG for every frame its clip covers (~1.5 MB a frame at 1080x1920), so a whole-film clip
        # filled 9 GB on a 139 s edit (2026-11-20); play it only over those spans (padded a few frames).
        spans = fg_spans([(o["s"], o["s"] + o["d"]) for o in overlays if o["behind"]] +
                         [(c["s"], c["s"] + c["d"]) for c in scenes if c.get("under")], T)
        clips = "".join(f'<video id="fg{"" if k == 0 else k}" class="clip" data-start="{a}" data-duration="{round(b - a, 4)}" data-media-start="{a}" '
                        f'data-track-index="5" src="assets/fg.webm" muted playsinline data-layout-allow-occlusion {vid}></video>'
                        for k, (a, b) in enumerate(spans))
        el.append(f'<div id="camfg" style="position:absolute;inset:0;z-index:5;transform-origin:50% {face_y * 100:.1f}%">{clips}</div>')
    for o in overlays:
        if not o["behind"]:
            el.append(f'<div id="{o["cid"]}" data-composition-id="{o["cid"]}" data-composition-src="compositions/{o["cid"]}.html" data-start="{o["s"]}" '
                      f'data-duration="{o["d"]}" data-track-index="{tr()}" data-track-kind="graphics" data-width="{W}" data-height="{H}" style="position:absolute;inset:0;z-index:6"></div>')
    frame = f'<div id="frame" style="position:absolute;inset:0;overflow:hidden;z-index:1">{"".join(el)}<div id="vig"></div></div>'
    caps = (f'<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{T}" '
            f'data-track-index="40" data-track-kind="captions" data-width="{W}" data-height="{H}" style="position:absolute;inset:0;z-index:10"></div>')

    # ---- layouts: camera state per span (cuts are hard sets; a zoomed span eases in)
    cams = "#cam, #camfg" if has_fg else "#cam"
    for L in layout:
        s = cx.s(L["s"])
        z = float(L.get("zoom", 1) or 1)
        if L["mode"] == "full" and z != 1:
            js.append(f'tl.fromTo("{cams}", {{ scale: 1 }}, {{ scale: {z}, duration: 0.24, ease: "expo.out" }}, {s});')
        else:
            js.append(f'tl.set("{cams}", {{ scale: 1 }}, {s});')

    # ---- camera moves: {s, e, z0, z1, rot0, rot1, x, y (origin 0-1), ease}. z0 != 1 at s is a snap punch-in;
    # z0 -> z1 is the push across the span. The move ends with a hard reset (the next cut hides it).
    for m in camera or []:
        s0, s1 = cx.s(m["s"]), cx.s(m["e"])
        if m.get("card"):
            from .hf_explainer import card_js
            js.extend(card_js(cams, s0, s1, m["card"], W, H))
            continue
        org = f'{m.get("x", 0.5) * 100:.0f}% {m.get("y", face_y) * 100:.0f}%'
        js.append(f'tl.fromTo("{cams}", {{ scale: {m.get("z0", 1)}, rotation: {m.get("rot0", 0)}, transformOrigin: "{org}" }}, '
                  f'{{ scale: {m.get("z1", m.get("z0", 1))}, rotation: {m.get("rot1", m.get("rot0", 0))}, duration: {max(0.05, s1 - s0):.3f}, ease: "{m.get("ease", "sine.inOut")}", immediateRender: false }}, {s0});')
        js.append(f'tl.set("{cams}", {{ scale: 1, rotation: 0 }}, {s1});')
        if m.get("shake"):
            from .hf_ae import shake_js
            js.extend(shake_js("#frame", s0, min(s1, s0 + float(m.get("shake_s", 0.35))), cx.fps, float(m["shake"]), seed=int(s0 * 1000) % 997))

    # ---- the speaker cut-out shows only while something sits behind the speaker in a full layout: the
    # matte also catches hands and held objects, which must never float above scenes or captions
    if has_fg:
        spans = sorted([(o["s"], o["s"] + o["d"]) for o in overlays if o["behind"]] + [(cx.s(b["s"]), cx.s(b["e"])) for b in bg])
        full = [(cx.s(L["s"]), cx.s(L["e"])) for L in layout if L["mode"] == "full"]
        on = []
        for a, b in sorted((max(a, c), min(b, e)) for a, b in spans for c, e in full if min(b, e) > max(a, c)):
            if on and a <= on[-1][1] + 1e-6:          # overlapping or touching spans: one stretch, or the
                on[-1] = (on[-1][0], max(on[-1][1], b))   # first span's end hides the cut-out under the second
            else:
                on.append((a, b))
        js.append('tl.set("#camfg", { opacity: 0 }, 0);')
        for a, b in on:
            js.append(f'tl.set("#camfg", {{ opacity: 1 }}, {a:.3f});')
            js.append(f'tl.set("#camfg", {{ opacity: 0 }}, {b:.3f});')
    # ---- transitions
    fxl = []
    js.append('tl.set("#frame", { scale: 1, x: 0, y: 0 }, 0);')
    for i, x in enumerate(fx):
        t, k = cx.s(x["at"]), x["type"]
        if k == "bands":
            from .hf_ae import fx_bands
            bel, bjs = fx_bands(i, t, cx.fps, x.get("colors") or [cx.brand.get("ink", "#121318"), gold], bool(x.get("vertical")), int(x.get("n", 5)))
            fxl.append(bel)
            js.extend(bjs)
            continue
        if k in ("overexpose", "flash"):
            pre = 0.16 if k == "overexpose" else 0.04
            a = max(0.0, t - pre)
            fxl.append(f'<div id="fx{i}w" class="fxl" style="background:#fffdf8"></div>'
                       f'<div id="fx{i}c" class="fxl" style="inset:-18%;mix-blend-mode:screen;background:radial-gradient(ellipse 68% 92% at 40% 45%, #fff 0%, rgba(255,253,248,0.9) 40%, rgba(255,174,105,0.32) 66%, transparent 86%)"></div>')
            js.append(f'tl.fromTo("#fx{i}w", {{ opacity: 0 }}, {{ opacity: {0.95 if k == "overexpose" else 0.85}, duration: {max(0.02, t - a):.3f}, ease: "power4.in" }}, {a:.3f});')
            js.append(f'tl.to("#fx{i}w", {{ opacity: 0, duration: {0.3 if k == "overexpose" else 0.18}, ease: "power3.out" }}, {t + 0.04:.3f});')
            js.append(f'tl.fromTo("#fx{i}c", {{ opacity: 0, scale: 0.86 }}, {{ opacity: 1, scale: 1, duration: {max(0.03, t - a):.3f}, ease: "power4.in" }}, {a:.3f});')
            js.append(f'tl.to("#fx{i}c", {{ opacity: 0, scale: 1.18, duration: 0.42, ease: "power2.out" }}, {t + 0.04:.3f});')
        elif k == "zoomblur":
            a = max(0.0, t - 0.16)
            js.append(f'tl.fromTo("#frame", {{ scale: 1 }}, {{ scale: 1.12, duration: {t - a:.3f}, ease: "power3.in", immediateRender: false }}, {a:.3f});')
            js.append(f'tl.fromTo("#frame", {{ scale: 1.14 }}, {{ scale: 1, duration: 0.26, ease: "expo.out", immediateRender: false }}, {t:.3f});')
        elif k == "flip3d":
            from .hf_explainer import flip_js
            js.extend(flip_js(t, x.get("dir", "left")))
        elif k == "whip":
            d = x.get("dir", "left")
            prop, sign = ("x", -1) if d == "left" else ("x", 1) if d == "right" else ("y", -1) if d == "up" else ("y", 1)
            amt = 300
            a = max(0.0, t - 0.12)
            js.append(f'tl.fromTo("#frame", {{ {prop}: 0 }}, {{ {prop}: {sign * amt}, duration: {t - a:.3f}, ease: "power3.in", immediateRender: false }}, {a:.3f});')
            js.append(f'tl.fromTo("#frame", {{ {prop}: {-sign * amt} }}, {{ {prop}: 0, duration: 0.2, ease: "expo.out", immediateRender: false }}, {t:.3f});')
        elif k in ("leakdip", "leak"):
            if k == "leakdip":
                fxl.append(f'<div id="fx{i}d" class="fxl" style="background:#000"></div>')
                js.append(f'tl.fromTo("#fx{i}d", {{ opacity: 0 }}, {{ opacity: 0.4, duration: 0.1, ease: "power2.in" }}, {max(0, t - 0.12):.3f});')
                js.append(f'tl.set("#fx{i}d", {{ opacity: 0 }}, {t:.3f});')
            fxl.append(f'<div id="fx{i}l" class="fxl leak" style="inset:-16%"><div class="la"></div><div class="lr"></div><div class="lg"></div></div>')
            a = max(0.0, t - 0.3)
            js.append(f'tl.fromTo("#fx{i}l", {{ opacity: 0 }}, {{ opacity: 0.92, duration: {t - a + 0.04:.3f}, ease: "sine.out" }}, {a:.3f});')
            js.append(f'tl.to("#fx{i}l", {{ opacity: 0, duration: 0.8, ease: "sine.in" }}, {t + 0.12:.3f});')
            js.append(f'tl.fromTo("#fx{i}l .la", {{ xPercent: -20, scale: 0.92 }}, {{ xPercent: 18, scale: 1.1, duration: 1.3, ease: "sine.inOut" }}, {a:.3f});')
            js.append(f'tl.fromTo("#fx{i}l .lg", {{ xPercent: -28 }}, {{ xPercent: 24, duration: 1.3, ease: "sine.inOut" }}, {a:.3f});')
        elif k == "wash":
            col = x.get("color") or gold
            corner = {"bl": "0% 100%", "br": "100% 100%", "tl": "0% 0%", "tr": "100% 0%"}.get(x.get("from", "bl"), "0% 100%")
            fxl.append(f'<div id="fx{i}x" class="fxl" style="background:{col}"></div>')
            a = max(0.0, t - 0.3)
            js.append(f'tl.fromTo("#fx{i}x", {{ opacity: 1, clipPath: "circle(0% at {corner})" }}, {{ clipPath: "circle(150% at {corner})", duration: {t - a:.3f}, ease: "power2.inOut" }}, {a:.3f});')
            js.append(f'tl.to("#fx{i}x", {{ opacity: 0, duration: 0.35, ease: "power2.out" }}, {t + 0.03:.3f});')
        elif k == "smoke":
            fxl.append(f'<div id="fx{i}s" class="fxl smoke"><i style="left:-10%;top:20%"></i><i style="left:40%;top:-5%"></i><i style="left:15%;top:55%"></i><i style="left:55%;top:45%"></i></div>')
            a = max(0.0, t - 0.25)
            js.append(f'tl.fromTo("#fx{i}s", {{ opacity: 0, scale: 0.9 }}, {{ opacity: 0.97, scale: 1.05, duration: {t - a:.3f}, ease: "power2.in" }}, {a:.3f});')
            js.append(f'tl.to("#fx{i}s", {{ opacity: 0, scale: 1.35, duration: 0.6, ease: "power2.out" }}, {t + 0.04:.3f});')
    if finish and finish.get("vignette"):
        # optical falloff, under the grain: a soft radial darkening of the corners (0-1 strength)
        v = max(0.0, min(1.0, float(finish["vignette"])))
        fxl.insert(0, f'<div id="vign" style="position:absolute;inset:0;background:radial-gradient(ellipse 75% 62% at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,{0.75 * v:.3f}) 100%)"></div>')
    if finish and finish.get("grain"):
        from .hf_ae import grain_layer
        gel, gjs = grain_layer(T, cx.fps, float(finish["grain"]))
        fxl.insert(0, gel)
        js.extend(gjs)
    fx_html = f'<div id="fxlayer" style="position:absolute;inset:0;z-index:20;pointer-events:none">{"".join(fxl)}</div>'
    audio = f'<audio id="mix" class="clip" data-start="0" data-duration="{T}" data-track-index="50" data-volume="1" src="assets/master.wav"></audio>'
    return f"""<!doctype html>
<html lang="en" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<script src="{GSAP}"></script>
<style>
{cx.fonts_css}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
#vig {{ position: absolute; inset: 0; z-index: 7; pointer-events: none; background: radial-gradient(ellipse 75% 60% at 50% 45%, transparent 55%, rgba(0,0,0,0.45) 100%); }}
.fxl {{ position: absolute; inset: 0; opacity: 0; }}
.bands i {{ position: absolute; left: 0; width: 100%; }}
.bands.v i {{ top: 0; height: 100%; }}
.leak {{ mix-blend-mode: screen; overflow: hidden; }}
.leak div {{ position: absolute; inset: -20%; }}
.leak .la {{ background: radial-gradient(ellipse 52% 110% at 10% 58%, rgb(255 241 197 / 92%), transparent 45%), radial-gradient(ellipse 72% 120% at 24% 54%, rgb(255 126 57 / 78%), transparent 66%); filter: blur(3vmin); }}
.leak .lr {{ background: radial-gradient(ellipse 58% 105% at 78% 34%, rgb(255 79 61 / 60%), rgb(255 44 92 / 22%) 48%, transparent 76%); filter: blur(4vmin); }}
.leak .lg {{ background: linear-gradient(104deg, transparent 24%, rgb(255 144 62 / 30%) 40%, rgb(255 247 205 / 72%) 51%, rgb(255 124 48 / 22%) 62%, transparent 78%); filter: blur(2vmin); }}
.smoke i {{ position: absolute; width: 90%; height: 60%; border-radius: 50%; background: radial-gradient(circle, rgba(250,248,255,0.98) 0%, rgba(220,215,235,0.8) 45%, transparent 70%); filter: blur(30px); }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{T}" data-width="{W}" data-height="{H}" data-motion-blur="on">
{frame}
{caps}
{fx_html}
{audio}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""


# ============================================================================== build
def build(d: dict, caps: list[dict], cap_ys: list[float], fps: float, W: int, H: int, total_f: int, hf: Path, assets: dict, fonts_css: str,
          cap_scrims: list[bool] | None = None) -> Path:
    """Write the HyperFrames project into `hf`. `assets` maps base/fg/bw/soft/master to existing
    files (copied into hf/assets). Returns the project folder."""
    if hf.exists():
        for sub in ("compositions",):
            shutil.rmtree(hf / sub, ignore_errors=True)
    (hf / "compositions").mkdir(parents=True, exist_ok=True)
    (hf / "assets").mkdir(exist_ok=True)
    for k, src in assets.items():
        if src is None:
            continue
        dst = hf / "assets" / {"base": "base.mp4", "fg": "fg.webm", "bw": "base_bw.mp4", "soft": "base_soft.mp4", "master": "master.wav",
                               "raw": "base_raw.mp4", "wave": "scope_wave.mp4", "wave_raw": "scope_wave_raw.mp4",
                               "vec": "scope_vec.mp4", "vec_raw": "scope_vec_raw.mp4"}[k]
        if not dst.exists() or dst.stat().st_size != Path(src).stat().st_size or dst.stat().st_mtime < Path(src).stat().st_mtime:
            shutil.copy2(src, dst)
    from .hf_ae import write_textures
    write_textures(hf / "assets")
    cx = Ctx(fps, W, H, d.get("brand") or {}, fonts_css)
    T = round(total_f / fps, 4)
    layout = d.get("layout", []) or [{"s": 0, "e": total_f, "mode": "full"}]
    mode_at = lambda f: next((L["mode"] for L in layout if L["s"] <= f < L["e"]), "full")  # noqa: E731
    scenes, glass = [], []
    for i, s in enumerate(d.get("scenes", [])):
        cid = f"s{i:02d}{s['type'].lower()}"
        h = H // 2 if mode_at(s["s"]) == "split" else H
        dur = (s["e"] - s["s"]) / fps
        (hf / "compositions" / f"{cid}.html").write_text(SCENE_FN[s["type"]](cx, cid, h, dur, s["p"]), encoding="utf-8")
        scenes.append({"cid": cid, "s": cx.s(s["s"]), "d": round(dur, 4), "under": bool(s["p"].get("under"))})
        if s["p"].get("glass"):
            glass.append((cx.s(s["s"]), cx.s(s["e"])))
    overlays = []
    for i, o in enumerate(d.get("overlays", [])):
        cid = f"o{i:02d}{o['type'].lower()}"
        dur = (o["e"] - o["s"]) / fps
        (hf / "compositions" / f"{cid}.html").write_text(OVERLAY_FN[o["type"]](cx, cid, dur, o.get("p", {})), encoding="utf-8")
        overlays.append({"cid": cid, "s": cx.s(o["s"]), "d": round(dur, 4), "behind": bool(o.get("behind")) and bool(assets.get("fg"))})
    size = float(d.get("caption_size") or 66)
    style = d.get("caption_style", "phrase")
    from .hf_ae import captions_ink
    from .hf_grade import captions_cine
    from .hf_creator import captions_pop
    from .hf_editorial import captions_whisper
    from .hf_spec import captions_plate
    from .hf_objects import captions_glint
    cap_html = (captions_pop(cx, caps, cap_ys, size, d.get("caption_font"), d.get("caption_font_emph")) if style == "pop" else
                captions_whisper(cx, caps, cap_ys, size, d.get("caption_font"), d.get("caption_font_emph")) if style == "whisper" else
                captions_plate(cx, caps, cap_ys, size, d.get("caption_font"), d.get("caption_font_emph")) if style == "plate" else
                captions_glint(cx, caps, cap_ys, size, d.get("caption_font"), d.get("caption_font_emph")) if style == "glint" else
                captions_cine(cx, caps, cap_ys, size) if style == "cine" else
                captions_ink(cx, caps, cap_ys, size, cx.brand.get("accent", "#C6FF3D"), cx.brand.get("ink", "#0E0F12")) if style == "ink" else
                captions_lockup(cx, caps, cap_ys, size, d.get("caption_framed")) if style == "lockup" else
                captions_box(cx, caps, cap_ys, size) if style == "box" else captions_file(cx, caps, cap_ys, size, cap_scrims))
    (hf / "compositions" / "captions.html").write_text(cap_html, encoding="utf-8")
    splits = [(cx.s(L["s"]), cx.s(L["e"])) for L in layout if L["mode"] == "split"]
    (hf / "index.html").write_text(root_file(cx, T, layout, scenes, overlays, d.get("fx", []), d.get("bg", []), float(d.get("face_y", 0.3)),
                                             bool(assets.get("fg")), bool(assets.get("soft")), bool(assets.get("bw")), splits, glass, d.get("camera"), d.get("finish"),
                                             bool(assets.get("raw"))), encoding="utf-8")
    if not (hf / "hyperframes.json").exists():
        (hf / "hyperframes.json").write_text(json.dumps({"name": hf.parent.name + "-design", "skill": "pro-video-editor"}, indent=1), encoding="utf-8")
    return hf


def fg_spans(spans: list, total: float, pad: float = 0.2) -> list:
    """Merged [start, end] seconds where the speaker cut-out must play: each span padded by `pad`, clipped to
    the film, overlapping or touching spans joined."""
    out = []
    for a, b in sorted((max(0.0, a - pad), min(total, b + pad)) for a, b in spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(round(a, 4), round(b, 4)) for a, b in out if b > a]


def fonts_inline(fonts_dir: Path, rel: str = "assets/fonts") -> str:
    """@font-face rules from fetch_fonts.py's fonts.css with URLs pointing into the project assets."""
    css = (fonts_dir / "fonts.css").read_text(encoding="utf-8") if (fonts_dir / "fonts.css").exists() else ""
    return re.sub(r"""url\((['"]?)([^'")]+)\1\)""", lambda m: f"url('{rel}/{m.group(2)}')", css)   # either quote style


# ---- After Effects finishing kit (lib/hf_ae.py)
from . import hf_ae as _ae  # noqa: E402

SCENE_FN["Formula"] = _ae.sc_formula
OVERLAY_FN["Kinetic"] = _ae.ov_kinetic
SCENE_FN["Versus"] = _ae.sc_versus
SCENE_FN["Checklist"] = _ae.sc_checklist
OVERLAY_FN["Annotate"] = _ae.ov_annotate
SCENES |= {"Versus", "Checklist"}
OVERLAYS |= {"Annotate"}

from . import hf_grade as _gr  # noqa: E402  colour-grading motion design (2026-11-16)
SCENE_FN["LutCube"] = _gr.sc_lutcube
OVERLAY_FN["Hud"] = _gr.ov_hud
OVERLAY_FN["Scopes"] = _gr.ov_scopes
SCENES |= {"LutCube"}
CAPTION_STYLES |= {"cine", "pop"}
OVERLAYS |= {"Hud", "Scopes"}

from . import hf_sport as _sp  # noqa: E402  sports-broadcast analysis graphics (2026-11-17)
OVERLAY_FN["Telestrate"] = _sp.ov_telestrate
OVERLAY_FN["ReasonPanel"] = _sp.ov_reasonpanel
OVERLAY_FN["Standings"] = _sp.ov_standings
OVERLAYS |= {"Telestrate", "ReasonPanel", "Standings"}

# ---- 3D explainer stages (lib/hf_explainer.py)
from . import hf_explainer as _ex  # noqa: E402

SCENE_FN["Stage3D"] = _ex.sc_stage3d
SCENE_FN["Podium3D"] = _ex.sc_podium3d
SCENES |= {"Stage3D", "Podium3D"}
OVERLAY_FN["Title3D"] = _ex.ov_title3d
OVERLAYS |= {"Title3D"}

# ---- editorial motion kit (lib/hf_editorial.py, 2026-11-19): graphics drawn from the story
from . import hf_editorial as _ed  # noqa: E402

OVERLAY_FN.update(_ed.OVERLAYS)
OVERLAYS |= set(_ed.OVERLAYS)
CAPTION_STYLES |= {"whisper"}

# ---- spec-sheet explainer kit (lib/hf_spec.py, 2026-11-19): branded 3D world, glass spec panels
from . import hf_spec as _sp  # noqa: E402

OVERLAY_FN.update(_sp.OVERLAYS)
OVERLAYS |= set(_sp.OVERLAYS)
SCENE_FN.update(_sp.SCENES)
SCENES |= set(_sp.SCENES)
CAPTION_STYLES |= {"plate"}

# ---- 3D objects, light sweeps, glint captions (lib/hf_objects.py, 2026-11-19)
from . import hf_objects as _ob  # noqa: E402

OVERLAY_FN.update(_ob.OVERLAYS)
OVERLAYS |= set(_ob.OVERLAYS)
CAPTION_STYLES |= {"glint"}
