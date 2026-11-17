"""After Effects finishing kit for the HyperFrames design engine.

What an AE motion designer layers on a talking-head short, rebuilt as deterministic HTML/GSAP:
  * text animators: per-character range-selector reveals with overshoot (Ease High), not whole-word fades
  * Echo: ghost copies trailing a moving title by a few frames
  * self-writing strokes: SVG stroke-dashoffset write-on, then the fill
  * soft shadows (~20 % opacity, big blur) instead of default hard drop shadows / outlines
  * paper and halftone textures on graphics, and film grain over everything so graphics sit in the footage
  * shape-layer band wipes, and seeded camera shake on impacts

Every random value comes from a seeded generator in Python, so every render is identical.
Timings marked STARTING DEFAULT are not measured on references; the rest follow effects-catalog.md §9
(30 fps study: keyword wipe ~6 frames, glow 6-8 frames, exits 2-4 frames)."""
from __future__ import annotations

import html
import random
from pathlib import Path
from urllib.parse import quote

esc = html.escape
FONT_HEAVY = "'Montserrat', 'Noto Sans Ethiopic'"
SOFT = "0 18px 40px rgba(0,0,0,0.22), 0 4px 10px rgba(0,0,0,0.20)"     # ~20 % soft shadow (AE tutorials' default)


def _svg_uri(svg: str) -> str:
    return "url(\"data:image/svg+xml;utf8," + quote(svg, safe=" =:/;,'()-.") + "\")"


def write_textures(assets: Path, seed: int = 5) -> None:
    """Seeded texture tiles as PNG files (the renderer draws SVG feTurbulence backgrounds as solid
    black, so noise is baked into images): grain.png - mid-grey film grain for an overlay layer;
    paper.png - transparent fibre speckle for paper cards."""
    import cv2
    import numpy as np
    assets.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    g = rng.normal(0, 1, (256, 256)).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 0.7)
    g = np.clip(128 + g / g.std() * 34, 0, 255).astype(np.uint8)
    cv2.imwrite(str(assets / "grain.png"), g)
    f = rng.normal(0, 1, (300, 300)).astype(np.float32)
    f = cv2.GaussianBlur(f, (0, 0), 1.1) + 0.5 * cv2.GaussianBlur(rng.normal(0, 1, (300, 300)).astype(np.float32), (0, 0), 6)
    f = (f - f.min()) / (f.max() - f.min())
    a = np.clip((np.abs(f - 0.5) * 2) ** 2 * 60, 0, 255).astype(np.uint8)       # speckle strength as alpha
    rgba = np.dstack([np.full_like(a, 70), np.full_like(a, 60), np.full_like(a, 45), a])
    cv2.imwrite(str(assets / "paper.png"), rgba)


def paper_css(sel: str, base: str = "#F3F0E8", ink: str = "#14141A") -> str:
    """Off-white paper: fibre noise + a faint halftone in one corner + an inner vignette."""
    return (f"{sel} {{ background-color: {base}; background-image: url('assets/paper.png'), "
            f"radial-gradient(circle at 1.6px 1.6px, {ink}22 1.3px, transparent 1.6px), "
            f"radial-gradient(ellipse 90% 80% at 50% 45%, transparent 55%, rgba(60,50,30,0.16) 100%); "
            f"background-size: 300px 300px, 14px 14px, 100% 100%; }}")


def halftone(color: str, dot: float = 2.2, step: int = 14) -> str:
    return f"radial-gradient(circle at {step / 2}px {step / 2}px, {color} {dot}px, transparent {dot + 0.6}px) 0 0 / {step}px {step}px"


# ============================================================================== grain (finish layer)
def grain_layer(T: float, fps: float, amount: float = 0.10, every_frames: int = 2, seed: int = 11) -> tuple[str, list[str]]:
    """Film grain over the whole frame: one noise tile, re-positioned every `every_frames` frames
    (12-15 Hz boil like scanned film). amount = layer opacity (STARTING DEFAULT 0.10, overlay blend)."""
    rnd = random.Random(seed)
    el = (f'<div id="grain" style="position:absolute;inset:-10%;z-index:15;pointer-events:none;mix-blend-mode:overlay;opacity:{amount};'
          f'background-image:url(assets/grain.png);background-size:256px 256px"></div>')
    js = []
    for k in range(-(-round(T * fps) // every_frames)):          # integer frames: no float drift
        js.append(f'tl.set("#grain", {{ backgroundPosition: "{rnd.randint(0, 255)}px {rnd.randint(0, 255)}px" }}, {k * every_frames / fps:.3f});')
    return el, js


def shake_js(sel: str, s: float, e: float, fps: float, amp: float = 14.0, rot: float = 0.6, seed: int = 4) -> list[str]:
    """Seeded camera shake that decays over the span (an impact, not a handheld drift)."""
    rnd, js = random.Random(seed), []
    n = max(2, round((e - s) * fps / 2))
    for i in range(n):
        k = (1 - i / n) ** 1.6
        js.append(f'tl.set("{sel}", {{ x: {rnd.uniform(-1, 1) * amp * k:.1f}, y: {rnd.uniform(-1, 1) * amp * k:.1f}, rotation: {rnd.uniform(-1, 1) * rot * k:.2f} }}, {s + i * 2 / fps:.3f});')
    js.append(f'tl.set("{sel}", {{ x: 0, y: 0, rotation: 0 }}, {e:.3f});')
    return js


# ============================================================================== text animators
def chars_html(t: str, cls: str = "c") -> str:
    """Split into characters (an Ethiopic syllable is one code point) so each can be animated."""
    return "".join(f'<span class="{cls}">{"&nbsp;" if ch == " " else esc(ch)}</span>' for ch in t)


def reveal_js(sel: str, at: float, fps: float, stagger_f: float = 0.6, rise: float = 70, over: float = 2.2, dur_f: int = 9) -> str:
    """Range-selector style: characters rise from below with blur, each overshooting (back.out)."""
    return (f'tl.fromTo("{sel}", {{ opacity: 0, yPercent: {rise}, rotation: 6, filter: "blur(8px)" }}, '
            f'{{ opacity: 1, yPercent: 0, rotation: 0, filter: "blur(0px)", duration: {dur_f / fps:.3f}, ease: "back.out({over})", '
            f'stagger: {stagger_f / fps:.4f} }}, {at:.3f});')


def underline_svg(cid: str, w: float, color: str, thick: float = 14, seed: int = 1) -> str:
    """A hand-drawn marker stroke under a word (slightly curved, tapered by round caps)."""
    rnd = random.Random(seed)
    y0, y1 = 18 + rnd.uniform(-4, 4), 14 + rnd.uniform(-4, 4)
    d = f"M 6 {y0:.1f} C {w * 0.3:.0f} {y0 + 6:.1f}, {w * 0.65:.0f} {y1 - 7:.1f}, {w - 6:.0f} {y1:.1f}"
    return (f'<svg class="ul" width="{w:.0f}" height="34" viewBox="0 0 {w:.0f} 34"><path id="{cid}" d="{d}" pathLength="1" fill="none" '
            f'stroke="{color}" stroke-width="{thick}" stroke-linecap="round" stroke-dasharray="1 1" stroke-dashoffset="1"/></svg>')


# ============================================================================== caption style "ink"
def captions_ink(cx, caps: list[dict], ys: list[float], size: float, accent: str, ink: str = "#0E0F12") -> str:
    """Kinetic captions: every word builds character by character with overshoot on its spoken frame;
    the emphasis word is accent-coloured, 1.3x, trails two Echo ghosts and gets a marker stroke that
    writes on underneath. Soft shadows, a soft dark pool behind the card instead of a box or an outline.
    Cards alternate a slight tilt so consecutive cards never look stamped from one template."""
    from .hf_design import scene_file, text_w
    fps = cx.fps
    fr = 1 / fps
    groups, js = [], []
    for gi, (g, y) in enumerate(zip(caps, ys)):
        ws = g["words"]
        s_, e_ = cx.s(g["s"]), cx.s(g["e"])
        tilt = (-1.6, 1.2, -0.8, 1.6)[gi % 4]
        width = sum(text_w(w["w"], size * (1.3 if w["emph"] else 1), 0.62, 0.92) for w in ws) + 30 * len(ws)
        k = min(1.0, 960 / max(1.0, width))
        parts = []
        for i, w in enumerate(ws):
            wid = f"ck{gi}w{i}"
            if w["emph"]:
                ww = text_w(w["w"], size * 1.3 * k, 0.62, 0.92)
                parts.append(f'<span class="w em" id="{wid}" style="font-size:{size * 1.3 * k:.0f}px">'
                             f'<span class="gh g2" aria-hidden="true" data-layout-ignore>{esc(w["w"])}</span><span class="gh g1" aria-hidden="true" data-layout-ignore>{esc(w["w"])}</span>'
                             f'{underline_svg(wid + "u", ww + 20, accent, max(10, size * 0.11), gi)}<span class="t">{chars_html(w["w"])}</span></span>')
                t = max(s_, cx.s(w["s"]) - 0.03)
                js.append(reveal_js(f"#{wid} .t .c", t, fps, 0.8, 80, 2.6, 10))
                js.append(f'tl.fromTo("#{wid} .g1", {{ opacity: 0.45, x: -34, y: 10 }}, {{ opacity: 0, x: 0, y: 0, duration: {7 * fr:.3f}, ease: "power2.out" }}, {t + 2 * fr:.3f});')
                js.append(f'tl.fromTo("#{wid} .g2", {{ opacity: 0.25, x: -68, y: 20 }}, {{ opacity: 0, x: 0, y: 0, duration: {9 * fr:.3f}, ease: "power2.out" }}, {t + 2 * fr:.3f});')
                js.append(f'tl.fromTo("#{wid}u", {{ attr: {{ "stroke-dashoffset": 1 }} }}, {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {8 * fr:.3f}, ease: "power2.inOut" }}, {t + 6 * fr:.3f});')
            else:
                parts.append(f'<span class="w" id="{wid}" style="font-size:{size * k:.0f}px"><span class="t">{chars_html(w["w"])}</span></span>')
                js.append(reveal_js(f"#{wid} .t .c", max(s_, cx.s(w["s"]) - 0.03), fps, 0.5, 60, 1.8, 7))
        groups.append(f'<div class="pool" id="ck{gi}p" style="top:{y * cx.H - 210:.0f}px"></div>'
                      f'<div class="cg" id="ck{gi}" style="top:{y * cx.H:.0f}px;transform:translateY(-50%) rotate({tilt}deg)">{" ".join(parts)}</div>')
        js.append(f'tl.set("#ck{gi}, #ck{gi}p", {{ visibility: "visible", opacity: 1 }}, {s_:.3f});')
        js.append(f'tl.fromTo("#ck{gi}p", {{ opacity: 0 }}, {{ opacity: 1, duration: {4 * fr:.3f} }}, {s_:.3f});')
        js.append(f'tl.to("#ck{gi} .c", {{ opacity: 0, yPercent: -40, filter: "blur(6px)", duration: {3 * fr:.3f}, ease: "power2.in", stagger: {0.3 * fr:.4f} }}, {max(s_, e_ - 4 * fr):.3f});')
        js.append(f'tl.to("#ck{gi}p", {{ opacity: 0, duration: {3 * fr:.3f} }}, {max(s_, e_ - 3 * fr):.3f});')
        js.append(f'tl.set("#ck{gi}, #ck{gi}p", {{ visibility: "hidden" }}, {e_:.3f});')
    css = f"""#caps {{ position: absolute; inset: 0; }}
#caps .pool {{ position: absolute; left: -10%; width: 120%; height: 420px; visibility: hidden;
  background: radial-gradient(ellipse 52% 50% at 50% 50%, rgba(8,9,12,0.55) 0%, rgba(8,9,12,0.28) 45%, transparent 75%); }}
#caps .cg {{ position: absolute; left: 0; right: 0; text-align: center; visibility: hidden; white-space: nowrap; line-height: 1.05; }}
#caps .w {{ position: relative; display: inline-block; margin: 0 0.12em; font-family: {FONT_HEAVY}; font-weight: 900; font-synthesis: none;
  letter-spacing: -0.03em; color: #fff; text-shadow: {SOFT}; }}
#caps .w .c {{ display: inline-block; will-change: transform; }}
#caps .w.em {{ color: {accent}; }}
#caps .w.em .t {{ position: relative; z-index: 2; }}
#caps .gh {{ position: absolute; left: 0; top: 0; z-index: 1; color: {accent}; opacity: 0; text-shadow: none; }}
#caps .ul {{ position: absolute; left: -10px; bottom: -0.1em; z-index: 0; overflow: visible; filter: drop-shadow(0 6px 10px rgba(0,0,0,0.25)); }}"""
    return scene_file(cx, "captions", cx.H, css, f'<div id="caps">{"".join(groups)}</div>', "\n".join(js), transparent=True)


# ============================================================================== overlay: Kinetic title
def ov_kinetic(cx, cid: str, dur: float, p: dict) -> str:
    """Kinetic display type (often `behind: true` the speaker). items: {t, at, y, size, color, weight,
    mode: 'build' (characters overshoot in, Echo trail) | 'write' (outline writes on, then fills),
    out (frames)}. Words hold with a slow scale drift and leave with a fast blur."""
    from .hf_design import scene_file
    fps, a = cx.fps, cx.brand.get("accent", "#C6FF3D")
    rows, js = [], []
    for i, it in enumerate(p["items"]):
        size, col, at = it.get("size", 260), it.get("color", "#ffffff"), cx.s(it["at"])
        top = it["y"] * cx.H - size * 0.55
        xoff = (it.get("x", 0.5) - 0.5) * cx.W
        if it.get("mode") == "write":
            rows.append(f'<svg class="kw" id="{cid}-w{i}" style="top:{top:.0f}px;left:{xoff:.0f}px" width="{cx.W}" height="{size * 1.3:.0f}" viewBox="0 0 {cx.W} {size * 1.3:.0f}">'
                        f'<text x="50%" y="{size * 0.98:.0f}" text-anchor="middle" font-size="{size}" font-family="{esc(it.get('font') or FONT_HEAVY)}" font-weight="{it.get("weight", 900)}" '
                        f'fill="{col}" fill-opacity="0" stroke="{col}" stroke-width="{max(2, size * 0.012):.1f}" stroke-dasharray="1400" stroke-dashoffset="1400">{esc(it["t"])}</text></svg>')
            js.append(f'tl.set("#{cid}-w{i}", {{ opacity: 1 }}, {at:.3f});')
            js.append(f'tl.fromTo("#{cid}-w{i} text", {{ attr: {{ "stroke-dashoffset": 1400 }} }}, {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {18 / fps:.3f}, ease: "power1.inOut" }}, {at:.3f});')
            js.append(f'tl.fromTo("#{cid}-w{i} text", {{ attr: {{ "fill-opacity": 0 }} }}, {{ attr: {{ "fill-opacity": {it.get("alpha", 1)} }}, duration: {8 / fps:.3f}, ease: "power2.out" }}, {at + 14 / fps:.3f});')
        else:
            ghost = "".join(f'<div class="gh" data-layout-ignore id="{cid}-w{i}g{k}" style="color:{col};opacity:0">{esc(it["t"])}</div>' for k in (1, 2, 3))
            ff = f"font-family:{it['font']};" if it.get("font") else ""
            rows.append(f'<div class="kw" id="{cid}-w{i}" style="top:{top:.0f}px;left:{xoff:.0f}px;{ff}font-size:{size}px;font-weight:{it.get("weight", 900)};color:{col};opacity:0">'
                        f'{ghost}<div class="tx">{chars_html(it["t"])}</div></div>')
            js.append(f'tl.set("#{cid}-w{i}", {{ opacity: {it.get("alpha", 1)} }}, {at:.3f});')
            js.append(reveal_js(f"#{cid}-w{i} .tx .c", at, fps, 1.0, 90, 2.4, 11))
            for k, (dx, op) in enumerate(((-40, 0.4), (-80, 0.22), (-120, 0.12)), 1):
                js.append(f'tl.fromTo("#{cid}-w{i}g{k}", {{ opacity: {op}, x: {dx}, scale: {1 + 0.05 * k} }}, {{ opacity: 0, x: 0, scale: 1, duration: {(6 + 3 * k) / fps:.3f}, ease: "power2.out" }}, {at + k / fps:.3f});')
        js.append(f'tl.fromTo("#{cid}-w{i}", {{ scale: 1 }}, {{ scale: 1.05, duration: {max(0.2, dur - at):.3f}, ease: "none" }}, {at:.3f});')
        if "out" in it:
            js.append(f'tl.to("#{cid}-w{i}", {{ opacity: 0, filter: "blur(14px)", scale: 1.12, duration: {4 / fps:.3f}, ease: "power2.in" }}, {cx.s(it["out"])});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, filter: "blur(12px)", duration: {4 / fps:.3f}, ease: "power2.in" }}, {max(0, dur - 4 / fps):.3f});')
    css = (f"#{cid}-all {{ position: absolute; inset: 0; }}\n"
           f"#{cid}-all .kw {{ position: absolute; left: 0; width: {cx.W}px; text-align: center; white-space: nowrap; line-height: 0.9; "
           f"font-family: {FONT_HEAVY}; font-synthesis: none; letter-spacing: -0.04em; text-shadow: 0 20px 50px rgba(0,0,0,0.25); }}\n"
           f"#{cid}-all .kw .c {{ display: inline-block; }}\n"
           f"#{cid}-all .gh {{ position: absolute; left: 0; width: 100%; top: 0; text-shadow: none; }}\n"
           f"#{cid}-all svg.kw {{ overflow: visible; filter: drop-shadow(0 16px 30px rgba(0,0,0,0.25)); }}")
    return scene_file(cx, cid, cx.H, css, f'<div id="{cid}-all">{"".join(rows)}</div>', "\n".join(js), transparent=True)


# ============================================================================== scene: Formula on paper
def sc_formula(cx, cid: str, h: int, dur: float, p: dict) -> str:
    """A worked formula on a paper card, the way a designer would lay it out in AE:
    kicker tag, the formula in terms (each builds in on its frame), the multiplier gets a marker sweep
    behind it and a hand-drawn ring that writes on, then a worked example counts up to the result.
    p: kicker, terms [{t, at, sub}] (ops are terms too: '×', '='), ring (index of the term to circle) / ringAt,
       example {a, op, b, res, unit, at, countDur} - all times in frames, scene-relative."""
    from .hf_design import scene_file
    fps, a = cx.fps, cx.brand.get("accent", "#C6FF3D")
    ink = cx.brand.get("ink", "#121318")
    js, fr = [], 1 / fps
    terms = []
    for i, t in enumerate(p["terms"]):
        op = t["t"] in ("×", "=", "+", "÷", "-")
        cls = "op" if op else ("hl" if i == p.get("ring") else "tm")
        sub = f'<div class="sub">{esc(t["sub"])}</div>' if t.get("sub") else ""
        ring = ""
        if i == p.get("ring"):
            ring = (f'<svg class="ring" viewBox="0 0 300 200" preserveAspectRatio="none"><path id="{cid}-ring" pathLength="1" fill="none" stroke="{ink}" stroke-width="5" '
                    f'stroke-linecap="round" stroke-dasharray="1 1" stroke-dashoffset="1" d="M 160 18 C 60 8, 8 60, 22 118 C 36 182, 214 196, 274 132 C 312 88, 268 14, 140 22"/></svg>'
                    f'<i class="mk" id="{cid}-mk"></i>')
        terms.append(f'<div class="term {cls}" id="{cid}-t{i}">{ring}<div class="tt">{chars_html(t["t"])}</div>{sub}</div>')
        js.append(reveal_js(f"#{cid}-t{i} .tt .c", cx.s(t["at"]), fps, 0.7, 80, 2.2, 10))
        if t.get("sub"):
            js.append(f'tl.fromTo("#{cid}-t{i} .sub", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: {6 * fr:.3f}, ease: "power3.out" }}, {cx.s(t["at"]) + 4 * fr:.3f});')
    if p.get("ring") is not None:
        ra = cx.s(p.get("ringAt", p["terms"][p["ring"]]["at"] + 8))
        js.append(f'tl.fromTo("#{cid}-mk", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {6 * fr:.3f}, ease: "power2.out" }}, {ra - 6 * fr:.3f});')
        js.append(f'tl.fromTo("#{cid}-ring", {{ attr: {{ "stroke-dashoffset": 1 }} }}, {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {12 * fr:.3f}, ease: "power2.inOut" }}, {ra:.3f});')
    ex_html = ""
    ex = p.get("example")
    if ex:
        ea = cx.s(ex["at"])
        lab = f'<div class="el">{esc(ex["label"])}</div>' if ex.get("label") else ""
        ex_html = (f'<div id="{cid}-ex">{lab}<span class="ea">{esc(str(ex["a"]))}</span><span class="eo">{esc(ex.get("op", "×"))}</span>'
                   f'<span class="ea">{esc(str(ex["b"]))}</span><span class="eo">=</span><span class="er"><b id="{cid}-v">0</b>'
                   f'<small>{esc(ex.get("unit", ""))}</small></span></div>')
        js.append(f'tl.fromTo("#{cid}-ex", {{ opacity: 0, y: 60, rotation: -2 }}, {{ opacity: 1, y: 0, rotation: -2, duration: {10 * fr:.3f}, ease: "back.out(1.8)" }}, {ea:.3f});')
        js.append(f'count("#{cid}-v", 0, {ex["res"]}, {ea + 6 * fr:.3f}, {cx.s(ex.get("countDur", 24)):.3f}, "power3.out");')
        js.append(f'tl.fromTo("#{cid}-ex .er", {{ scale: 1 }}, {{ scale: 1.08, duration: {5 * fr:.3f}, ease: "power2.out", yoyo: true, repeat: 1 }}, {ea + 6 * fr + cx.s(ex.get("countDur", 24)):.3f});')
    kick = p.get("kicker")
    if kick:
        js.append(f'tl.fromTo("#{cid}-k", {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: {7 * fr:.3f}, ease: "expo.out" }}, {2 * fr:.3f});')
    # the card itself: drops in with a tilt and settles; the stage drifts like a slow AE camera
    js.insert(0, f'tl.fromTo("#{cid}-card", {{ y: {h * 0.6:.0f}, rotation: 7, scale: 0.92 }}, {{ y: 0, rotation: -1.5, scale: 1, duration: {14 * fr:.3f}, ease: "expo.out" }}, 0);')
    js.append(f'tl.fromTo("#{cid}-card", {{ rotation: -1.5 }}, {{ rotation: 0.8, duration: {max(0.3, dur - 0.5):.3f}, ease: "sine.inOut", immediateRender: false }}, {14 * fr:.3f});')
    js.append(f'tl.fromTo("#{cid}-bg", {{ scale: 1.0 }}, {{ scale: 1.08, duration: {dur:.3f}, ease: "none" }}, 0);')
    js.append(f'tl.to("#{cid}-card", {{ y: {-h * 0.7:.0f}, rotation: -6, duration: {7 * fr:.3f}, ease: "power3.in" }}, {max(0, dur - 7 * fr):.3f});')
    W = cx.W
    css = f"""#{cid}-bg {{ position: absolute; inset: -6%; background: {ink}; }}
#{cid}-bg::after {{ content: ""; position: absolute; inset: 0; background: {halftone(a + "30", 2.4, 18)}; -webkit-mask-image: radial-gradient(ellipse 70% 60% at 85% 10%, #000, transparent 70%); mask-image: radial-gradient(ellipse 70% 60% at 85% 10%, #000, transparent 70%); }}
#{cid}-card {{ position: absolute; left: {W * 0.06:.0f}px; width: {W * 0.88:.0f}px; top: {h * 0.2:.0f}px; height: {h * 0.56:.0f}px; border-radius: 28px; box-shadow: 0 50px 90px rgba(0,0,0,0.35), 0 8px 18px rgba(0,0,0,0.2); overflow: visible; }}
{paper_css(f"#{cid}-card", "#F3F0E8", ink)}
#{cid}-k {{ position: absolute; left: 56px; top: 52px; font-family: {FONT_HEAVY}; font-weight: 800; font-size: 36px; color: {ink}; background: {a}; padding: 8px 22px 10px; border-radius: 10px; letter-spacing: 0.02em; }}
#{cid}-f {{ position: absolute; left: 0; right: 0; top: {h * 0.13:.0f}px; display: flex; justify-content: center; align-items: flex-start; gap: 18px; row-gap: 6px; flex-wrap: wrap; padding: 0 40px; }}
#{cid}-f .term {{ position: relative; text-align: center; font-family: {FONT_HEAVY}; font-weight: 900; color: {ink}; }}
#{cid}-f .term .tt {{ font-size: {p.get("size", 104)}px; line-height: 1.05; letter-spacing: -0.03em; white-space: nowrap; }}
#{cid}-f .term.op .tt {{ color: {ink}88; font-weight: 600; }}
#{cid}-f .term .c {{ display: inline-block; }}
#{cid}-f .sub {{ margin-top: 10px; font-family: {FONT_HEAVY}; font-weight: 700; font-size: 34px; color: {ink}aa; white-space: nowrap; }}
#{cid}-f .mk {{ position: absolute; left: -6%; width: 112%; top: 18%; height: 66%; background: {a}; border-radius: 10px; transform-origin: 0 50%; z-index: -1; transform: scaleX(0) skewX(-6deg); }}
#{cid}-f .ring {{ position: absolute; left: -34%; top: -30%; width: 168%; height: 160%; overflow: visible; }}
#{cid}-ex {{ position: absolute; left: 0; right: 0; top: {p.get('exTop', 0.36) * h:.0f}px; text-align: center; font-family: {FONT_HEAVY}; font-weight: 900; color: {ink}; white-space: nowrap; }}
#{cid}-ex span {{ display: inline-block; vertical-align: baseline; margin: 0 8px; }}
#{cid}-ex .ea {{ font-size: 66px; }}
#{cid}-ex .el {{ font-family: {FONT_HEAVY}; font-weight: 800; font-size: 34px; color: {ink}99; margin-bottom: 6px; letter-spacing: 0.04em; }}
#{cid}-ex .eo {{ font-size: 52px; color: {ink}77; font-weight: 600; }}
#{cid}-ex .er {{ font-size: 104px; background: {ink}; color: {a}; padding: 4px 30px 10px; border-radius: 22px; box-shadow: {SOFT}; letter-spacing: -0.04em; }}
#{cid}-ex .er small {{ font-size: 44px; margin-left: 10px; color: #fff; font-weight: 800; }}"""
    body = (f'<div id="{cid}-bg"></div><div id="{cid}-card">' + (f'<div id="{cid}-k">{esc(kick)}</div>' if kick else "") +
            f'<div id="{cid}-f">{"".join(terms)}</div>{ex_html}</div>')
    return scene_file(cx, cid, h, css, body, "\n".join(js))


# ============================================================================== fx: band wipe
def fx_bands(i: int, t: float, fps: float, colors: list[str], vertical: bool = False, n: int = 5) -> tuple[str, list[str]]:
    """Shape-layer band wipe through a cut at t: n bands sweep in staggered (covering by t), then out
    the far side. ~10 frames on screen (STARTING DEFAULT)."""
    fr = 1 / fps
    bands = "".join(f'<i style="background:{colors[k % len(colors)]};{"left" if vertical else "top"}:{k * 100 / n:.2f}%;'
                    f'{"width" if vertical else "height"}:{100 / n + 0.4:.2f}%"></i>' for k in range(n))
    el = f'<div id="fx{i}b" class="fxl bands{" v" if vertical else ""}" style="opacity:1">{bands}</div>'
    ax = "yPercent" if vertical else "xPercent"
    start = t - 5 * fr - 0.6 * fr * (n - 1)
    js = [f'tl.set("#fx{i}b i", {{ {ax}: -101 }}, 0);',
          f'tl.fromTo("#fx{i}b i", {{ {ax}: -101 }}, {{ {ax}: 0, duration: {5 * fr:.3f}, ease: "power3.in", stagger: {0.6 * fr:.4f}, immediateRender: false }}, {start:.3f});',
          f'tl.fromTo("#fx{i}b i", {{ {ax}: 0 }}, {{ {ax}: 101, duration: {5 * fr:.3f}, ease: "power3.out", stagger: {0.6 * fr:.4f}, immediateRender: false }}, {t + fr:.3f});',
          f'tl.set("#fx{i}b", {{ opacity: 0 }}, {t + fr + 5 * fr + 0.6 * fr * n + fr:.3f});']
    return el, js


FX_CSS = """.bands i { position: absolute; left: 0; width: 100%; }
.bands.v i { top: 0; height: 100%; }"""


import math


# ============================================================================== overlay: Annotate (marker on footage)
def ov_annotate(cx, cid: str, dur: float, p: dict) -> str:
    """Marker strokes drawn over the footage, the way an editor circles something in AE with a
    write-on stroke: items {kind: ring|arrow|line, at (frames), and for ring x, y, w, h (0-1 frame
    fractions, centre + size); for arrow/line x0, y0, x1, y1}, plus optional label {t, x, y, size, at, rot}.
    Strokes are slightly irregular (seeded), round-capped, with a soft shadow so they sit on the image."""
    from .hf_design import scene_file
    fps, a = cx.fps, cx.brand.get("accent", "#C6FF3D")
    col, wpx = p.get("color", a), p.get("width", 12)
    W, H = cx.W, cx.H
    paths, js = [], []
    for i, it in enumerate(p["items"]):
        rnd = random.Random(i + 7)
        at = cx.s(it["at"])
        if it["kind"] == "ring":
            x, y, rw, rh = it["x"] * W, it["y"] * H, it["w"] * W / 2, it["h"] * H / 2
            pts = []
            for k in range(15):
                ang = -2.2 + k * (2 * math.pi * 1.08) / 14      # a little over one turn: the overlap reads as hand-drawn
                j = 1 + rnd.uniform(-0.05, 0.05)
                pts.append((x + math.cos(ang) * rw * j, y + math.sin(ang) * rh * j))
            d = f"M {pts[0][0]:.0f} {pts[0][1]:.0f} " + " ".join(
                f"Q {pts[k][0]:.0f} {pts[k][1]:.0f} {(pts[k][0] + pts[k + 1][0]) / 2:.0f} {(pts[k][1] + pts[k + 1][1]) / 2:.0f}"
                for k in range(1, len(pts) - 1))
            dur_f = it.get("dur", 14)
        else:
            x0, y0, x1, y1 = it["x0"] * W, it["y0"] * H, it["x1"] * W, it["y1"] * H
            mx, my = (x0 + x1) / 2 + rnd.uniform(-60, 60), (y0 + y1) / 2 + rnd.uniform(-60, 60)
            d = f"M {x0:.0f} {y0:.0f} Q {mx:.0f} {my:.0f} {x1:.0f} {y1:.0f}"
            dur_f = it.get("dur", 10)
            if it["kind"] == "arrow":
                ang = math.atan2(y1 - my, x1 - mx)
                L = 50
                for nm, s_ in (("a", -0.5), ("b", 0.5)):
                    hx, hy = x1 - L * math.cos(ang + s_), y1 - L * math.sin(ang + s_)
                    paths.append(f'<path id="{cid}-h{i}{nm}" d="M {x1:.0f} {y1:.0f} L {hx:.0f} {hy:.0f}" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1"/>')
                js.append(f'tl.fromTo("#{cid}-h{i}a, #{cid}-h{i}b", {{ attr: {{ "stroke-dashoffset": 1 }} }}, '
                          f'{{ attr: {{ "stroke-dashoffset": 0 }}, duration: {4 / fps:.3f}, ease: "power2.out" }}, {at + dur_f / fps:.3f});')
        paths.append(f'<path id="{cid}-p{i}" d="{d}" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1"/>')
        js.append(f'tl.fromTo("#{cid}-p{i}", {{ attr: {{ "stroke-dashoffset": 1 }} }}, '
                  f'{{ attr: {{ "stroke-dashoffset": 0 }}, duration: {dur_f / fps:.3f}, ease: "power2.inOut" }}, {at:.3f});')
    lab, L = "", p.get("label")
    if L:
        lab = (f'<div id="{cid}-l" style="position:absolute;left:{L["x"] * W:.0f}px;top:{L["y"] * H:.0f}px;'
               f'transform:translate(-50%,-50%) rotate({L.get("rot", -6)}deg)"><span class="lt">{chars_html(L["t"])}</span></div>')
        js.append(f'tl.fromTo("#{cid}-l .lt", {{ scale: 0.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: {9 / fps:.3f}, ease: "back.out(2.4)" }}, {cx.s(L["at"]):.3f});')
        js.append(reveal_js(f"#{cid}-l .c", cx.s(L["at"]) + 2 / fps, fps, 1.0, 80, 2.6, 10))
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, duration: {4 / fps:.3f}, ease: "power2.in" }}, {max(0, dur - 4 / fps):.3f});')
    lsize = (L or {}).get("size", 120)
    css = (f"#{cid}-all {{ position: absolute; inset: 0; }}\n"
           f"#{cid}-all svg {{ position: absolute; inset: 0; overflow: visible; filter: drop-shadow(0 6px 10px rgba(0,0,0,0.30)); }}\n"
           f"#{cid}-all path {{ fill: none; stroke: {col}; stroke-width: {wpx}; stroke-linecap: round; stroke-linejoin: round; }}\n"
           f"#{cid}-all .lt {{ display: inline-block; white-space: nowrap; font-family: {FONT_HEAVY}; font-weight: 900; font-size: {lsize}px; "
           f"color: {p.get('label_color', '#0E0F12')}; background: {col}; padding: 0.04em 0.28em 0.12em; border-radius: 0.16em; box-shadow: {SOFT}; letter-spacing: -0.02em; }}\n"
           f"#{cid}-all .lt .c {{ display: inline-block; }}")
    body = f'<div id="{cid}-all"><svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">{"".join(paths)}</svg>{lab}</div>'
    return scene_file(cx, cid, cx.H, css, body, "\n".join(js), transparent=True)


# ============================================================================== scene: Versus (bars that swap)
def sc_versus(cx, cid: str, h: int, dur: float, p: dict) -> str:
    """Two labelled bars on a dark halftone stage. They grow to the WRONG proportions, a red cross
    writes on over them, then the bars swap (elastic) to the RIGHT proportions and a tick writes on.
    p: kicker (html allowed: <b> = accent), left {t}, right {t}, wrong [l, r], right_h [l, r] (0-1 heights),
       tags {more, less}, growAt, crossAt, swapAt, tickAt (frames)."""
    from .hf_design import scene_file
    fps, a = cx.fps, cx.brand.get("accent", "#C6FF3D")
    ink, red = cx.brand.get("ink", "#121318"), p.get("red", "#FF4B3E")
    W, fr = cx.W, 1 / fps
    BH = h * 0.40
    wl, wr = p["wrong"]
    rl, rr = p["right_h"]
    js = [f'tl.fromTo("#{cid}-k", {{ opacity: 0, y: -30 }}, {{ opacity: 1, y: 0, duration: {7 * fr:.3f}, ease: "expo.out" }}, {2 * fr:.3f});']
    ga = cx.s(p.get("growAt", 4))
    for side, hh in (("L", wl), ("R", wr)):
        t0 = ga + (3 * fr if side == "R" else 0)
        js.append(f'tl.fromTo("#{cid}-b{side}", {{ height: 0 }}, {{ height: {BH * hh:.0f}, duration: {12 * fr:.3f}, ease: "back.out(1.6)" }}, {t0:.3f});')
        js.append(reveal_js(f"#{cid}-n{side} .c", t0 + 4 * fr, fps, 0.8, 80, 2.2, 9))
        js.append(f'tl.fromTo("#{cid}-t{side}", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: {6 * fr:.3f}, ease: "power3.out" }}, {t0 + 8 * fr:.3f});')
    ca = cx.s(p["crossAt"])
    js.append(f'tl.fromTo("#{cid}-x1, #{cid}-x2", {{ attr: {{ "stroke-dashoffset": 1 }} }}, {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {6 * fr:.3f}, ease: "power2.out", stagger: {3 * fr:.3f} }}, {ca:.3f});')
    js.append(f'tl.fromTo("#{cid}-bars", {{ x: 0 }}, {{ x: 14, duration: {fr:.3f}, ease: "none", yoyo: true, repeat: 5, immediateRender: false }}, {ca + 6 * fr:.3f});')
    sa = cx.s(p["swapAt"])
    js.append(f'tl.to("#{cid}-x", {{ opacity: 0, scale: 1.2, duration: {4 * fr:.3f}, ease: "power2.in" }}, {sa - 2 * fr:.3f});')
    for side, hh in (("L", rl), ("R", rr)):
        js.append(f'tl.to("#{cid}-b{side}", {{ height: {BH * hh:.0f}, duration: {16 * fr:.3f}, ease: "elastic.out(1, 0.55)" }}, {sa:.3f});')
    js.append(f'tl.to("#{cid}-bR", {{ backgroundColor: "{a}", duration: {6 * fr:.3f} }}, {sa:.3f});')
    js.append(f'tl.to("#{cid}-bL", {{ backgroundColor: "#3A3D46", duration: {6 * fr:.3f} }}, {sa:.3f});')
    for side, word in (("L", p["tags"]["less"]), ("R", p["tags"]["more"])):
        js.append(f'tl.fromTo("#{cid}-t{side}", {{ scale: 1 }}, {{ scale: 1.25, duration: {3 * fr:.3f}, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }}, {sa + 2 * fr:.3f});')
        js.append(f'tl.set("#{cid}-t{side} span", {{ textContent: "{word}" }}, {sa + 4 * fr:.3f});')
    js.append(f'tl.fromTo("#{cid}-tick", {{ attr: {{ "stroke-dashoffset": 1 }} }}, {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {8 * fr:.3f}, ease: "power2.out" }}, {cx.s(p.get("tickAt", p["swapAt"] + 10)):.3f});')
    js.append(f'tl.fromTo("#{cid}-wrap", {{ scale: 1 }}, {{ scale: 1.05, duration: {dur:.3f}, ease: "none" }}, 0);')
    js.append(f'tl.to("#{cid}-wrap", {{ opacity: 0, y: -80, filter: "blur(10px)", duration: {6 * fr:.3f}, ease: "power3.in" }}, {max(0, dur - 6 * fr):.3f});')

    def col(side, name, tag, c0):
        return (f'<div class="col"><div class="tag" id="{cid}-t{side}"><span>{esc(tag)}</span></div><div class="well"><div class="bar" id="{cid}-b{side}" style="background-color:{c0}"></div></div>'
                f'<div class="nm" id="{cid}-n{side}">{chars_html(name)}</div></div>')
    cross = (f'<svg id="{cid}-x" class="ov" viewBox="0 0 100 100" preserveAspectRatio="none"><path id="{cid}-x1" d="M 12 14 L 88 86" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1"/>'
             f'<path id="{cid}-x2" d="M 88 12 L 13 88" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1"/></svg>')
    tick = f'<svg class="tk" viewBox="0 0 120 100"><path id="{cid}-tick" d="M 10 56 L 44 88 L 110 10" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1"/></svg>'
    css = f"""#{cid}-bg {{ position: absolute; inset: 0; background: {ink}; }}
#{cid}-bg::after {{ content: ""; position: absolute; inset: 0; background: {halftone("#ffffff14", 2.0, 16)}; -webkit-mask-image: linear-gradient(180deg, #000, transparent 60%); mask-image: linear-gradient(180deg, #000, transparent 60%); }}
#{cid}-wrap {{ position: absolute; inset: 0; }}
#{cid}-k {{ position: absolute; left: 0; right: 0; top: {h * 0.12:.0f}px; text-align: center; font-family: {FONT_HEAVY}; font-weight: 900; font-size: 66px; color: #fff; letter-spacing: -0.02em; }}
#{cid}-k b {{ color: {a}; }}
#{cid}-bars {{ position: absolute; left: {W * 0.08:.0f}px; width: {W * 0.84:.0f}px; top: {h * 0.22:.0f}px; height: {h * 0.62:.0f}px; display: flex; justify-content: space-around; align-items: flex-end; }}
#{cid}-bars .col {{ width: 38%; text-align: center; }}
#{cid}-bars .well {{ position: relative; height: {BH:.0f}px; display: flex; align-items: flex-end; justify-content: center; border-bottom: 6px solid #ffffff30; }}
#{cid}-bars .bar {{ width: 100%; border-radius: 22px 22px 6px 6px; box-shadow: 0 30px 60px rgba(0,0,0,0.35); background-image: {halftone("#00000026", 2.2, 12)}; }}
#{cid}-bars .nm {{ margin-top: 26px; font-family: {FONT_HEAVY}; font-weight: 900; font-size: 62px; color: #fff; white-space: nowrap; letter-spacing: -0.02em; }}
#{cid}-bars .nm .c {{ display: inline-block; }}
#{cid}-bars .tag {{ font-family: {FONT_HEAVY}; font-weight: 800; font-size: 50px; color: #ffffffdd; margin-bottom: 16px; white-space: nowrap; }}
#{cid}-bars .tag span {{ display: inline-block; }}
#{cid}-x {{ position: absolute; left: 0; top: 4%; width: 100%; height: 74%; overflow: visible; }}
#{cid}-x path {{ fill: none; stroke: {red}; stroke-width: 7; stroke-linecap: round; filter: drop-shadow(0 8px 14px rgba(0,0,0,0.4)); }}
#{cid}-bars .tk {{ position: absolute; right: -2%; top: -4%; width: 190px; height: 160px; overflow: visible; }}
#{cid}-bars .tk path {{ fill: none; stroke: {a}; stroke-width: 16; stroke-linecap: round; stroke-linejoin: round; filter: drop-shadow(0 10px 16px rgba(0,0,0,0.4)); }}"""
    body = (f'<div id="{cid}-bg"></div><div id="{cid}-wrap"><div id="{cid}-k">{p.get("kicker", "")}</div>'
            f'<div id="{cid}-bars">{col("L", p["left"]["t"], p["tags"]["more"], red)}{col("R", p["right"]["t"], p["tags"]["less"], "#3A3D46")}{cross}{tick}</div></div>')
    return scene_file(cx, cid, h, css, body, "\n".join(js))


# ============================================================================== scene: Checklist (recap on paper)
def sc_checklist(cx, cid: str, h: int, dur: float, p: dict) -> str:
    """A recap card: numbered rows build in one after another, each ticked with a written-on stroke.
    p: kicker, rows [{n, t, at}] (frames)."""
    from .hf_design import scene_file
    fps, a = cx.fps, cx.brand.get("accent", "#C6FF3D")
    ink, W, fr = cx.brand.get("ink", "#121318"), cx.W, 1 / fps
    rows, js = [], []
    js.append(f'tl.fromTo("#{cid}-card", {{ y: {h * 0.5:.0f}, rotation: -6 }}, {{ y: 0, rotation: 1.2, duration: {12 * fr:.3f}, ease: "expo.out" }}, 0);')
    for i, r in enumerate(p["rows"]):
        at = cx.s(r["at"])
        rows.append(f'<div class="row" id="{cid}-r{i}"><span class="n">{esc(r["n"])}</span><span class="t">{chars_html(r["t"])}</span>'
                    f'<svg class="ck" viewBox="0 0 100 80"><path id="{cid}-c{i}" d="M 8 44 L 36 70 L 92 8" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1"/></svg></div>')
        js.append(f'tl.fromTo("#{cid}-r{i} .n", {{ scale: 0, rotation: -30 }}, {{ scale: 1, rotation: 0, duration: {8 * fr:.3f}, ease: "back.out(2.4)" }}, {at:.3f});')
        js.append(reveal_js(f"#{cid}-r{i} .t .c", at + 2 * fr, fps, 0.6, 70, 2.0, 8))
        js.append(f'tl.fromTo("#{cid}-c{i}", {{ attr: {{ "stroke-dashoffset": 1 }} }}, {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {6 * fr:.3f}, ease: "power2.out" }}, {at + 7 * fr:.3f});')
    if p.get("kicker"):
        js.append(f'tl.fromTo("#{cid}-k", {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: {7 * fr:.3f}, ease: "expo.out" }}, {3 * fr:.3f});')
    js.append(f'tl.to("#{cid}-card", {{ y: {-h * 0.7:.0f}, rotation: 6, duration: {7 * fr:.3f}, ease: "power3.in" }}, {max(0, dur - 7 * fr):.3f});')
    css = f"""#{cid}-bg {{ position: absolute; inset: 0; background: {a}; }}
#{cid}-bg::after {{ content: ""; position: absolute; inset: 0; background: {halftone(ink + "26", 2.6, 18)}; -webkit-mask-image: radial-gradient(ellipse 80% 60% at 15% 90%, #000, transparent 70%); mask-image: radial-gradient(ellipse 80% 60% at 15% 90%, #000, transparent 70%); }}
#{cid}-card {{ position: absolute; left: {W * 0.07:.0f}px; width: {W * 0.86:.0f}px; top: {h * 0.22:.0f}px; padding: 64px 56px 56px; border-radius: 28px; box-shadow: 0 50px 90px rgba(0,0,0,0.30), 0 8px 18px rgba(0,0,0,0.18); }}
{paper_css(f"#{cid}-card", "#F3F0E8", ink)}
#{cid}-k {{ display: inline-block; font-family: {FONT_HEAVY}; font-weight: 800; font-size: 40px; color: #fff; background: {ink}; padding: 8px 22px 10px; border-radius: 10px; margin-bottom: 26px; }}
#{cid}-card .row {{ position: relative; display: flex; align-items: center; gap: 30px; margin: 20px 0; padding-bottom: 20px; border-bottom: 3px dashed {ink}22; }}
#{cid}-card .row:last-child {{ border-bottom: none; padding-bottom: 0; }}
#{cid}-card .n {{ flex: none; width: 104px; height: 104px; border-radius: 50%; background: {ink}; color: {a}; display: flex; align-items: center; justify-content: center; font-family: {FONT_HEAVY}; font-weight: 900; font-size: 56px; }}
#{cid}-card .t {{ font-family: {FONT_HEAVY}; font-weight: 900; font-size: 60px; color: {ink}; white-space: nowrap; letter-spacing: -0.02em; }}
#{cid}-card .t .c {{ display: inline-block; }}
#{cid}-card .ck {{ position: absolute; right: 0; width: 92px; height: 74px; overflow: visible; }}
#{cid}-card .ck path {{ fill: none; stroke: #1E9E4A; stroke-width: 12; stroke-linecap: round; stroke-linejoin: round; }}"""
    body = (f'<div id="{cid}-bg"></div><div id="{cid}-card">' + (f'<div id="{cid}-k">{esc(p["kicker"])}</div>' if p.get("kicker") else "") +
            "".join(rows) + "</div>")
    return scene_file(cx, cid, h, css, body, "\n".join(js))
