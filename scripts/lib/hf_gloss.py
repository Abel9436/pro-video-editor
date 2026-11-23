"""Glossy extruded type, liquid glass, knowledge-graph walls and brand scenes (2026-11-23), from a 30 fps frame
study of two creator Shorts (work/xafb/refs/watch_a, watch_b: deep_watch sheets, every frame looked at).

What the references do, measured on the sheets (frame counts at 30 fps):
  - a huge word in the brand colour sits behind the seated speaker on a pale studio wall: condensed heavy type,
    a glossy face (light top, brand mid, dark foot), a solid extrusion down-right, a soft floor shadow; letters
    drop in through blur in ~8-10 frames, one or two frames apart, then the block drifts ~3 % larger;
  - a white handwritten script word overlaps it, written on left to right in ~10-12 frames;
  - a hand-drawn swoosh line in the brand colour draws itself under or around the word (~14 frames);
  - section changes go through white: the frame overexposes to paper white in 3-4 frames, holds 1-2, and the
    next shot develops out of it in 6-8 frames (a bloom, not a plain fade);
  - full-screen brand scenes: a deep brand-colour radial gradient, blurred glass shapes in the corners, a glass
    3D hero object in the middle, a serif title with a script accent at the top, words arriving one at a time
    with motion blur;
  - liquid glass (the second reference is half an After Effects liquid-glass tutorial): refraction blur,
    a bright specular rim, a faint chromatic fringe (red one side, blue the other), a soft brand-tinted shadow.
Every number marked STARTING DEFAULT is a reading of those sheets, not a measured optimum.

Overlays (times are frames relative to the overlay's start):
  Extrude    {t, y, size, font, face: [top, mid, foot], side, depth, at, in_f 9, track,
              script: {t, x, y, size, rot, at, color}, swoosh: {at, y, color, w}}
  Bloom      {peak, color}                                  white overexposure flash peaking at frame `peak`
  GlassCard  {x, y, w, h, at, icon, title, sub, badge, strike_at, stamp: {t, at, color}, from, ink}
  GraphWall  {x, y, w, h, at, nodes, seed, labels, trace_at, trace_len, ink, fade_at}
  BrandScene {mode: name|stat, at, kicker, title, script, words: [[text, at]], stat, bars: {at, before, after}}
  CommentBox {y, at, text, type_at, send_at, dm_at, dm_title, dm_sub, avatar}
"""
from __future__ import annotations

import math
import random

from .hf_ae import esc
from .hf_design import Ctx, scene_file

BRAND = "#013220"
FACE = ["#2FA36B", "#04603C", "#013220"]       # glossy face: light top -> brand mid -> brand foot
SIDE = "#00170E"                                # extrusion colour (darker than the brand)
F_EXT = "'Anton', 'Manrope', sans-serif"
F_SCRIPT = "'Great Vibes', cursive"
F_SERIF = "'Instrument Serif', serif"
F_UI = "'Manrope', sans-serif"


def _mix(a: str, b: str, k: float) -> str:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * k):02x}" for x, y in zip(ca, cb))


def _rgba(c: str, a: float) -> str:
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{a})"


def _extrude_shadow(depth: int, side: str, dx: float = 0.55, dy: float = 1.0) -> str:
    """Stacked hard shadows make a solid extrusion down-right; the last two are the soft floor shadow."""
    out = [f"{dx * i:.1f}px {dy * i:.1f}px 0 {_mix(side, '#000000', 0.25 * i / depth)}" for i in range(1, depth + 1)]
    out.append(f"{dx * depth + 6:.0f}px {dy * depth + 18:.0f}px 26px rgba(0,20,12,0.38)")
    out.append(f"{dx * depth + 2:.0f}px {dy * depth + 40:.0f}px 60px rgba(0,20,12,0.22)")
    return ", ".join(out)


def _swoosh_path(w: float, seed: int) -> str:
    r = random.Random(seed)
    y0 = 40
    pts = [(0, y0 + r.uniform(-6, 6))]
    for i in range(1, 5):
        pts.append((w * i / 4, y0 + (-1) ** i * r.uniform(10, 26)))
    d = f"M {pts[0][0]:.0f} {pts[0][1]:.0f} "
    for (x0, y0_), (x1, y1) in zip(pts, pts[1:]):
        cx_ = (x0 + x1) / 2
        d += f"Q {cx_:.0f} {y0_ + (y1 - y0_) * 0.1 - 18:.0f} {x1:.0f} {y1:.0f} "
    return d


def _track(cid: str, p: dict, inner: str) -> tuple[str, list]:
    """3D tracking to the baked camera: `cam` is [[t_s, scale, rot_deg, dx_px], ...] relative to the overlay,
    read off the camera bake (zoom about `cam_origin`, cv2 rotation sign); every frame it changes gets a set, so
    whatever sits on the wall moves with the wall through punch-ins, framing changes, whips and pans."""
    keys = p.get("cam")
    if not keys:
        return inner, []
    ox, oy = p.get("cam_origin", [540, 845])
    js = [f'tl.set("#{cid}-cam", {{ scale: {s_:.5f}, rotation: {-r_:.3f}, x: {dx:.1f}, transformOrigin: "{ox:.0f}px {oy:.0f}px" }}, {t:.4f});'
          for t, s_, r_, dx in keys]
    return f'<div id="{cid}-cam" style="position:absolute;inset:0">{inner}</div>', js


# ============================================================================== Extrude
def ov_extrude(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    at = cx.s(p.get("at", 0))
    size, y = p.get("size", 300), p.get("y", 0.2) * cx.H
    face = p.get("face", FACE)
    depth = p.get("depth", max(8, int(size / 22)))      # STARTING DEFAULT: extrusion ~4.5 % of the type size
    side = p.get("side", SIDE)
    font = p.get("font", F_EXT)
    sh = _extrude_shadow(depth, side)
    grad = f"linear-gradient(180deg, {face[0]} 0%, {face[1]} 46%, {face[2]} 100%)"
    letters = []
    for i, ch in enumerate(p["t"]):
        if ch == " ":
            letters.append(f'<span style="display:inline-block;width:{size * 0.22:.0f}px"></span>')
            continue
        c = esc(ch)
        letters.append(
            f'<span class="{cid}-l" style="position:relative;display:inline-block">'
            f'<span style="color:{side};text-shadow:{sh}">{c}</span>'
            f'<span style="position:absolute;left:0;top:0;background:{grad};-webkit-background-clip:text;background-clip:text;color:transparent">{c}</span>'
            f'<span class="{cid}-g" style="position:absolute;left:0;top:0;background:linear-gradient(104deg, transparent 38%, rgba(255,255,255,0.75) 47%, '
            f'rgba(255,255,255,0.15) 53%, transparent 62%);background-size:400% 100%;background-position:120% 0;-webkit-background-clip:text;'
            f'background-clip:text;color:transparent">{c}</span>'
            f'<span style="position:absolute;left:0;top:0;background:linear-gradient(180deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 22%);'
            f'-webkit-background-clip:text;background-clip:text;color:transparent">{c}</span></span>')
    word = (f'<div id="{cid}-w" style="position:absolute;left:0;right:0;top:{y - size * 0.62:.0f}px;text-align:center;white-space:nowrap;'
            f'font-family:{font};font-weight:{p.get("weight", 400)};font-size:{size}px;line-height:1.05;letter-spacing:{p.get("track", 0.0)}em;'
            f'font-synthesis:none;transform-origin:50% 60%">{"".join(letters)}</div>')
    js = [f'tl.fromTo(".{cid}-l", {{ opacity: 0, y: {-size * 0.35:.0f}, scaleY: 1.25, filter: "blur(18px)" }}, '
          f'{{ opacity: 1, y: 0, scaleY: 1, filter: "blur(0px)", duration: {p.get("in_f", 9) * fr:.3f}, ease: "expo.out", stagger: {p.get("stagger_f", 1.5) * fr:.4f} }}, {at:.3f});',
          f'tl.fromTo("#{cid}-w", {{ scale: 1 }}, {{ scale: 1.035, duration: {max(0.2, dur - at):.3f}, ease: "none" }}, {at:.3f});',
          f'tl.fromTo(".{cid}-g", {{ backgroundPosition: "120% 0" }}, {{ backgroundPosition: "-30% 0", duration: {22 * fr:.3f}, ease: "power2.inOut", stagger: {fr:.4f} }}, {at + 6 * fr:.3f});']
    body = [word]
    sc = p.get("script")
    if sc:
        sid = f"{cid}-s"
        body.append(f'<div id="{sid}" style="position:absolute;left:{sc.get("x", 0.5) * cx.W:.0f}px;top:{sc.get("y", 0.2) * cx.H:.0f}px;transform:translate(-50%,-50%) rotate({sc.get("rot", -8)}deg);'
                    f'white-space:nowrap;font-family:{F_SCRIPT};font-size:{sc.get("size", 140)}px;color:{sc.get("color", "#FFFFFF")};line-height:1.2;padding:0 30px;'
                    f'text-shadow:0 6px 18px rgba(0,30,18,0.45), 0 0 2px rgba(0,30,18,0.4)">'
                    f'<span id="{sid}i" style="display:inline-block;clip-path:inset(-20% 100% -20% 0%)">{esc(sc["t"])}</span></div>')
        sa = cx.s(sc.get("at", p.get("at", 0) + 6))
        js.append(f'tl.to("#{sid}i", {{ clipPath: "inset(-20% 0% -20% 0%)", duration: {sc.get("in_f", 12) * fr:.3f}, ease: "power1.inOut" }}, {sa:.3f});')
        js.append(f'tl.fromTo("#{sid}", {{ opacity: 0 }}, {{ opacity: 1, duration: {2 * fr:.3f} }}, {sa:.3f});')
    sw = p.get("swoosh")
    if sw:
        w = sw.get("w", 0.72) * cx.W
        col = sw.get("color", "#0B7A4B")
        body.append(f'<svg id="{cid}-sw" style="position:absolute;left:{(cx.W - w) / 2:.0f}px;top:{sw.get("y", 0.3) * cx.H - 40:.0f}px;overflow:visible" width="{w:.0f}" height="90">'
                    f'<path d="{_swoosh_path(w, len(p["t"]))}" fill="none" stroke="{col}" stroke-width="{sw.get("stroke", 9)}" stroke-linecap="round" '
                    f'pathLength="1" stroke-dasharray="1.02" stroke-dashoffset="1.02" style="filter:drop-shadow(0 4px 8px rgba(0,40,24,0.35))"/></svg>')
        js.append(f'tl.to("#{cid}-sw path", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {14 * fr:.3f}, ease: "power2.inOut" }}, {cx.s(sw.get("at", 10)):.3f});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, filter: "blur(16px)", scale: 1.08, duration: {7 * fr:.3f}, ease: "power2.in" }}, {max(0, dur - 7 * fr):.3f});')
    inner, tj = _track(cid, p, f'<div id="{cid}-all">{"".join(body)}</div>')
    return scene_file(cx, cid, cx.H, f"#{cid}-all {{ position:absolute; inset:0; transform-origin:50% {p.get('y', 0.2) * 100:.0f}%; }}",
                      inner, "\n".join(tj + js), transparent=True)


# ============================================================================== Bloom
def ov_bloom(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """White overexposure through a section change (STARTING DEFAULT 4 frames up, 2 held, 7 down)."""
    fr = 1 / cx.fps
    pk = cx.s(p.get("peak", 4))
    col = p.get("color", "#F6FFF9")
    body = (f'<div id="{cid}-a" style="position:absolute;inset:-10%;background:radial-gradient(ellipse at 50% 42%, #FFFFFF 0%, {col} 45%, '
            f'rgba(214,246,228,0.92) 80%, rgba(170,230,200,0.85) 100%);opacity:0;mix-blend-mode:screen"></div>'
            f'<div id="{cid}-b" style="position:absolute;inset:0;background:{col};opacity:0"></div>')
    js = [f'tl.fromTo("#{cid}-a", {{ opacity: 0 }}, {{ opacity: 1, duration: {4 * fr:.3f}, ease: "power2.in" }}, {max(0, pk - 4 * fr):.3f});',
          f'tl.fromTo("#{cid}-b", {{ opacity: 0 }}, {{ opacity: 0.96, duration: {2 * fr:.3f}, ease: "power2.in" }}, {max(0, pk - 2 * fr):.3f});',
          f'tl.to("#{cid}-b", {{ opacity: 0, duration: {6 * fr:.3f}, ease: "power2.out" }}, {pk + 2 * fr:.3f});',
          f'tl.to("#{cid}-a", {{ opacity: 0, duration: {8 * fr:.3f}, ease: "power2.out" }}, {pk + 2 * fr:.3f});']
    if p.get("kind") == "burn":
        # reference B 5.6-6.0 s: a glow grows out of the frame, whites out, and a coloured leak sweeps across
        # (diagonal, ~14 frames, screen blend); tinted to the brand: mint and a warm gold
        for i, (c1, x0, y0, x1, y1, sz) in enumerate((("rgba(150,255,200,0.95)", 85, 95, 10, 20, 1500), ("rgba(255,226,160,0.9)", 110, 60, 35, -10, 1200))):
            body += (f'<div id="{cid}-l{i}" style="position:absolute;left:0;top:0;width:{sz}px;height:{sz}px;margin:{-sz / 2:.0f}px 0 0 {-sz / 2:.0f}px;border-radius:50%;'
                     f'background:radial-gradient(circle, {c1} 0%, rgba(255,255,255,0) 68%);mix-blend-mode:screen;opacity:0"></div>')
            js.append(f'tl.fromTo("#{cid}-l{i}", {{ x: {x0 * cx.W / 100:.0f}, y: {y0 * cx.H / 100:.0f}, scale: 0.3, opacity: 0 }}, '
                      f'{{ x: {x1 * cx.W / 100:.0f}, y: {y1 * cx.H / 100:.0f}, scale: 1.4, opacity: 1, duration: {9 * fr:.3f}, ease: "power2.in" }}, {max(0, pk - 6 * fr + i * fr):.3f});')
            js.append(f'tl.to("#{cid}-l{i}", {{ opacity: 0, scale: 1.8, duration: {7 * fr:.3f}, ease: "power2.out" }}, {pk + 3 * fr:.3f});')
    return scene_file(cx, cid, cx.H, f"#{cid}-all {{ position:absolute; inset:0; }}", f'<div id="{cid}-all">{body}</div>', "\n".join(js), transparent=True)


# ============================================================================== liquid glass
def glass_css(radius: float, tint: str = "#FFFFFF", alpha: float = 0.16) -> str:
    """Liquid glass: refraction blur and saturation of what is behind, a bright rim, a faint chromatic fringe
    (red left, blue right), a top specular band and a brand-tinted shadow."""
    return (f"border-radius:{radius:.0f}px;background:linear-gradient(160deg, {_rgba(tint, alpha + 0.10)}, {_rgba(tint, alpha)} 45%, {_rgba(tint, alpha * 0.6)});"
            f"backdrop-filter:blur(16px) saturate(1.7) brightness(1.06);-webkit-backdrop-filter:blur(16px) saturate(1.7) brightness(1.06);"
            f"border:1.5px solid rgba(255,255,255,0.62);"
            f"box-shadow:inset 0 2px 1px rgba(255,255,255,0.85), inset 0 -2px 2px rgba(255,255,255,0.28), inset 3px 0 4px rgba(255,70,90,0.16), "
            f"inset -3px 0 4px rgba(70,140,255,0.18), 0 28px 60px rgba(1,50,32,0.30), 0 6px 16px rgba(1,50,32,0.18);")


def _spec(radius: float) -> str:
    return (f'<div style="position:absolute;left:4%;right:4%;top:3px;height:38%;border-radius:{radius:.0f}px {radius:.0f}px 50% 50%;'
            f'background:linear-gradient(180deg, rgba(255,255,255,0.55), rgba(255,255,255,0));pointer-events:none"></div>')


def ov_glasscard(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    x, y, w, h = p.get("x", 90), p.get("y", 0.7) * cx.H, p.get("w", 900), p.get("h", 190)
    ink = p.get("ink", BRAND)
    rad = p.get("radius", h * 0.32)
    icon = (f'<img src="{p["icon"]}" style="width:{h * 0.58:.0f}px;height:{h * 0.58:.0f}px;object-fit:contain;margin-right:{h * 0.16:.0f}px;'
            f'filter:drop-shadow(0 8px 14px rgba(1,50,32,0.35))"/>' if p.get("icon") else "")
    badge = (f'<div style="margin-left:auto;padding:{h * 0.07:.0f}px {h * 0.16:.0f}px;border-radius:999px;background:{ink};color:#EAF7EF;'
             f'font-family:{F_UI};font-weight:800;font-size:{h * 0.20:.0f}px;white-space:nowrap">{esc(p["badge"])}</div>' if p.get("badge") else "")
    sub = (f'<div style="font-family:{F_UI};font-weight:700;font-size:{h * 0.17:.0f}px;color:{_rgba(ink, 0.62)};margin-top:2px;white-space:nowrap">{esc(p["sub"])}</div>'
           if p.get("sub") else "")
    title = (f'<div style="position:relative;display:inline-block;font-family:{F_UI};font-weight:800;font-size:{h * 0.27:.0f}px;color:{ink};white-space:nowrap">{esc(p["title"])}'
             f'<div id="{cid}-st" style="position:absolute;left:-4%;right:-4%;top:52%;height:{max(5, h * 0.035):.0f}px;border-radius:9px;background:#E5484D;'
             f'box-shadow:0 2px 8px rgba(229,72,77,0.5)"></div></div>')
    card = (f'<div id="{cid}-c" style="position:absolute;left:{x}px;top:{y:.0f}px;width:{w}px;height:{h}px;display:flex;align-items:center;'
            f'padding:0 {h * 0.2:.0f}px;box-sizing:border-box;{glass_css(rad, "#F4FFF8", p.get("glass_alpha", 0.66))}">{_spec(rad)}{icon}<div style="min-width:0">{title}{sub}</div>{badge}</div>')
    body = [card]
    from_ = p.get("from", "bottom")
    x0, y0 = {"bottom": (0, 160), "left": (-260, 0), "right": (260, 0), "sweep": (-980, 40)}[from_]
    at = cx.s(p.get("at", 0))
    rot0 = "rotationY: 78, rotationX: 10, rotationZ: -10" if from_ == "sweep" else f'rotationX: 38, rotationZ: {-6 if from_ != "right" else 6}'
    js = [f'tl.fromTo("#{cid}-c", {{ opacity: 0, x: {x0}, y: {y0}, {rot0}, scale: 0.9, filter: "blur(14px)", transformPerspective: 900 }}, '
          f'{{ opacity: 1, x: 0, y: 0, rotationX: 0, rotationY: 0, rotationZ: 0, scale: 1, filter: "blur(0px)", duration: {(18 if from_ == "sweep" else 14) * fr:.3f}, ease: "expo.out" }}, {at:.3f});',
          f'tl.to("#{cid}-c", {{ y: -10, rotationZ: -0.8, duration: {max(0.3, dur - at - 0.5):.3f}, ease: "sine.inOut" }}, {at + 14 * fr:.3f});']
    js.append(f'tl.set("#{cid}-st", {{ scaleX: 0, transformOrigin: "0% 50%" }}, 0);')
    if p.get("strike_at") is not None:
        sa = cx.s(p["strike_at"])
        js.append(f'tl.to("#{cid}-st", {{ scaleX: 1, duration: {6 * fr:.3f}, ease: "power3.out" }}, {sa:.3f});')
        js.append(f'tl.to("#{cid}-c", {{ x: -12, duration: {2 * fr:.3f}, ease: "power2.out", yoyo: true, repeat: 3 }}, {sa:.3f});')
    st = p.get("stamp")
    if st:
        col = st.get("color", "#E5484D")
        body.append(f'<div id="{cid}-sp" style="position:absolute;left:{x + w - 330}px;top:{y - 70:.0f}px;padding:14px 34px;border-radius:20px;border:5px solid {col};'
                    f'color:{col};font-family:{F_EXT};font-size:84px;letter-spacing:0.04em;line-height:1;background:rgba(255,255,255,0.78);'
                    f'transform:rotate(-12deg);opacity:0;box-shadow:0 14px 30px rgba(120,20,20,0.25)">{esc(st["t"])}</div>')
        js.append(f'tl.fromTo("#{cid}-sp", {{ opacity: 0, scale: 2.2, rotation: -24 }}, {{ opacity: 1, scale: 1, rotation: -12, duration: {5 * fr:.3f}, ease: "power4.in" }}, {cx.s(st["at"]):.3f});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, y: 60, filter: "blur(12px)", duration: {7 * fr:.3f}, ease: "power2.in" }}, {max(0, dur - 7 * fr):.3f});')
    return scene_file(cx, cid, cx.H, f"#{cid}-all {{ position:absolute; inset:0; }}", f'<div id="{cid}-all">{"".join(body)}</div>', "\n".join(js), transparent=True)


# ============================================================================== knowledge graph
def _graph(n: int, x: float, y: float, w: float, h: float, seed: int):
    """Seeded node layout (jittered rings around a hub) and a spanning tree plus a few cross links."""
    r = random.Random(seed)
    nodes = [(x + w / 2, y + h / 2, 1.0)]
    rings = [(0.26, 5), (0.47, max(1, n - 6))]
    for rf, k in rings:
        off = r.uniform(0, math.tau)
        for i in range(k):
            a = off + math.tau * i / k + r.uniform(-0.18, 0.18)
            rr = rf * (1 + r.uniform(-0.12, 0.12))
            nodes.append((x + w / 2 + math.cos(a) * rr * w, y + h / 2 + math.sin(a) * rr * h, 0.62 if rf < 0.4 else 0.44))
    nodes = nodes[:n]
    edges = []
    for i in range(1, len(nodes)):
        j = min(range(i), key=lambda k: (nodes[k][0] - nodes[i][0]) ** 2 + (nodes[k][1] - nodes[i][1]) ** 2 + (0 if nodes[k][2] > nodes[i][2] else 1e9))
        edges.append((j, i))
    for _ in range(max(2, n // 4)):
        a, b = r.sample(range(1, len(nodes)), 2)
        if (a, b) not in edges and (b, a) not in edges:
            edges.append((a, b))
    return nodes, edges


def _sphere(rid: str, cx_: float, cy_: float, rad: float, extra: str = "") -> str:
    return (f'<div id="{rid}" class="nd" style="left:{cx_ - rad:.0f}px;top:{cy_ - rad:.0f}px;width:{2 * rad:.0f}px;height:{2 * rad:.0f}px;{extra}">'
            f'<div class="hl"></div></div>')


def ov_graphwall(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    x, y, w, h = p.get("x", 60), p.get("y", 0.03) * cx.H, p.get("w", cx.W - 120), p.get("h", 0.34) * cx.H
    nodes, edges = _graph(p.get("nodes", 15), x, y, w, h, p.get("seed", 7))
    ink = p.get("ink", BRAND)
    labels = p.get("labels", [])
    at = cx.s(p.get("at", 0))
    svg = [f'<svg style="position:absolute;left:0;top:0;overflow:visible" width="{cx.W}" height="{cx.H}">']
    js = []
    order = sorted(range(len(edges)), key=lambda k: edges[k][1])
    for rank, k in enumerate(order):
        a, b = edges[k]
        (x1, y1, _), (x2, y2, _) = nodes[a], nodes[b]
        svg.append(f'<line id="{cid}-e{k}" x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{_rgba(ink, 0.55)}" stroke-width="4" '
                   f'stroke-linecap="round" pathLength="1" stroke-dasharray="1.02" stroke-dashoffset="1.02"/>')
        js.append(f'tl.to("#{cid}-e{k}", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {7 * fr:.3f}, ease: "power2.out" }}, {at + (4 + rank * 1.6) * fr:.3f});')
    svg.append("</svg>")
    divs = []
    for i, (nx, ny, s) in enumerate(nodes):
        rad = 34 * s + 8
        divs.append(_sphere(f"{cid}-n{i}", nx, ny, rad))
        js.append(f'tl.fromTo("#{cid}-n{i}", {{ scale: 0, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: {8 * fr:.3f}, ease: "back.out(2.2)" }}, {at + (i * 1.6) * fr:.3f});')
        if i - 1 < len(labels) and i >= 1:
            ly = ny + rad + 6
            divs.append(f'<div id="{cid}-lb{i}" class="lb" style="left:{nx - 90:.0f}px;top:{ly:.0f}px">{esc(labels[i - 1])}</div>')
            js.append(f'tl.fromTo("#{cid}-lb{i}", {{ opacity: 0, y: -8 }}, {{ opacity: 1, y: 0, duration: {6 * fr:.3f}, ease: "power2.out" }}, {at + (i * 1.6 + 5) * fr:.3f});')
    if p.get("trace_at") is not None:
        # a lit path from the hub outward: the pulse rides each edge, each node it reaches lights up
        path = [0]
        for _ in range(p.get("trace_len", 3)):
            nxt = [b for a, b in edges if a == path[-1] and b not in path]
            if not nxt:
                break
            path.append(nxt[len(path) % len(nxt)])
        ta = cx.s(p["trace_at"])
        svg_t = []
        for k, (a, b) in enumerate(zip(path, path[1:])):
            (x1, y1, _), (x2, y2, _) = nodes[a], nodes[b]
            svg_t.append(f'<line id="{cid}-t{k}" x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#36E08A" stroke-width="9" stroke-linecap="round" '
                         f'pathLength="1" stroke-dasharray="1.02" stroke-dashoffset="1.02" style="filter:drop-shadow(0 0 10px #36E08A) drop-shadow(0 0 22px rgba(54,224,138,0.6))"/>')
            js.append(f'tl.to("#{cid}-t{k}", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {6 * fr:.3f}, ease: "power1.inOut" }}, {ta + k * 7 * fr:.3f});')
        for k, nidx in enumerate(path):
            js.append(f'tl.to("#{cid}-n{nidx}", {{ scale: 1.35, boxShadow: "0 0 0 6px rgba(54,224,138,0.35), 0 0 46px rgba(54,224,138,0.9)", duration: {4 * fr:.3f}, ease: "power2.out" }}, {ta + k * 7 * fr:.3f});')
            js.append(f'tl.to("#{cid}-n{nidx}", {{ scale: 1.12, duration: {8 * fr:.3f}, ease: "power2.out" }}, {ta + (k * 7 + 4) * fr:.3f});')
        svg.insert(-1, "".join(svg_t))
    if p.get("fade_at") is not None:
        js.append(f'tl.to("#{cid}-all", {{ opacity: 0.35, duration: {8 * fr:.3f}, ease: "power2.out" }}, {cx.s(p["fade_at"]):.3f});')
    js.append(f'tl.fromTo("#{cid}-all", {{ scale: 1 }}, {{ scale: 1.04, duration: {max(0.2, dur):.3f}, ease: "none" }}, 0);')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, filter: "blur(14px)", duration: {7 * fr:.3f}, ease: "power2.in" }}, {max(0, dur - 7 * fr):.3f});')
    css = (f"#{cid}-all {{ position:absolute; inset:0; transform-origin:50% {(y + h / 2) / cx.H * 100:.0f}%; }} "
           f"#{cid}-all .nd {{ position:absolute; border-radius:50%; background:radial-gradient(circle at 34% 30%, #BFF5D6 0%, #3DBA7C 18%, #04603C 52%, {ink} 78%, #00140C 100%); "
           f"box-shadow:inset -6px -8px 14px rgba(0,0,0,0.35), 0 10px 22px rgba(1,50,32,0.35); }} "
           f"#{cid}-all .hl {{ position:absolute; left:18%; top:12%; width:36%; height:26%; border-radius:50%; background:radial-gradient(ellipse, rgba(255,255,255,0.95), rgba(255,255,255,0)); }} "
           f"#{cid}-all .lb {{ position:absolute; width:180px; text-align:center; font-family:{F_UI}; font-weight:800; font-size:26px; color:{ink}; letter-spacing:0.02em; }}")
    inner, tj = _track(cid, p, f'<div id="{cid}-all">{"".join(svg)}{"".join(divs)}</div>')
    return scene_file(cx, cid, cx.H, css, inner, "\n".join(tj + js), transparent=True)


# ============================================================================== full-screen brand scene
def _bokeh(cx: Ctx) -> str:
    """Blurred glass shapes in the corners (the references' out-of-focus foreground objects)."""
    shapes = [(-120, 0.06, 380, 26, 0.55), (cx.W - 220, 0.78, 420, 30, 0.5), (cx.W - 160, 0.02, 220, 18, 0.35), (-60, 0.86, 260, 22, 0.4)]
    out = []
    for i, (x, yf, s, b, a) in enumerate(shapes):
        out.append(f'<div class="bk" id="bk{i}" style="left:{x}px;top:{yf * cx.H:.0f}px;width:{s}px;height:{s * 0.8:.0f}px;filter:blur({b}px);opacity:{a}"></div>')
    return "".join(out)


def ov_brandscene(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    at = cx.s(p.get("at", 0))
    js = [f'tl.fromTo("#{cid}-bg", {{ scale: 1.08 }}, {{ scale: 1, duration: {max(0.3, dur):.3f}, ease: "power1.out" }}, 0);',
          f'tl.fromTo("#{cid}-all .bk", {{ y: 30 }}, {{ y: -40, duration: {max(0.3, dur):.3f}, ease: "none" }}, 0);']
    body = [f'<div id="{cid}-bg" style="position:absolute;inset:-4%;background:radial-gradient(ellipse at 50% 46%, #0E6B45 0%, #03442A 32%, {BRAND} 58%, #000F09 100%)"></div>',
            _bokeh(cx)]
    # serif title with a script accent above it, top third
    ty = p.get("title_y", 0.17) * cx.H
    if p.get("kicker"):
        body.append(f'<div id="{cid}-k" style="position:absolute;left:0;right:0;top:{ty - 120:.0f}px;text-align:center;font-family:{F_SCRIPT};font-size:96px;color:#9FF0C4;'
                    f'transform:rotate(-6deg);text-shadow:0 0 24px rgba(159,240,196,0.45)"><span id="{cid}-ki" style="display:inline-block;clip-path:inset(-30% 100% -30% 0%);padding:0 24px">{esc(p["kicker"])}</span></div>')
        js.append(f'tl.to("#{cid}-ki", {{ clipPath: "inset(-30% 0% -30% 0%)", duration: {11 * fr:.3f}, ease: "power1.inOut" }}, {at + 4 * fr:.3f});')
    if p.get("title"):
        chars = "".join(f'<span class="{cid}-tc" style="display:inline-block">{esc(c) if c != " " else "&nbsp;"}</span>' for c in p["title"])
        body.append(f'<div style="position:absolute;left:0;right:0;top:{ty:.0f}px;text-align:center;font-family:{F_SERIF};font-size:{p.get("title_size", 170)}px;line-height:1;'
                    f'color:#F2FFF7;text-shadow:0 0 30px rgba(120,255,180,0.35), 0 10px 30px rgba(0,0,0,0.4)">{chars}</div>')
        js.append(f'tl.fromTo(".{cid}-tc", {{ opacity: 0, y: 40, filter: "blur(16px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: {12 * fr:.3f}, ease: "expo.out", stagger: {1.2 * fr:.4f} }}, {at:.3f});')
    mode = p.get("mode", "name")
    hy = p.get("hero_y", 0.50) * cx.H
    if mode == "name":
        # the hero: a glass knowledge-graph object turning slowly in 3D
        nodes, edges = _graph(9, -230, -230, 460, 460, p.get("seed", 3))
        svg = [f'<svg style="position:absolute;left:0;top:0;overflow:visible" width="1" height="1">']
        for k, (a, b) in enumerate(edges):
            (x1, y1, _), (x2, y2, _) = nodes[a], nodes[b]
            svg.append(f'<line class="{cid}-he" x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="rgba(190,255,220,0.75)" stroke-width="6" stroke-linecap="round" '
                       f'pathLength="1" stroke-dasharray="1.02" stroke-dashoffset="1.02" style="filter:drop-shadow(0 0 8px rgba(120,255,180,0.7))"/>')
        svg.append("</svg>")
        sph = "".join(_sphere(f"{cid}-hn{i}", nx, ny, 40 * s + 12) for i, (nx, ny, s) in enumerate(nodes))
        body.append(f'<div id="{cid}-hero" style="position:absolute;left:{cx.W / 2:.0f}px;top:{hy:.0f}px;width:0;height:0;transform-style:preserve-3d">'
                    f'<div id="{cid}-plate" style="position:absolute;left:-300px;top:-300px;width:600px;height:600px;{glass_css(150, "#C8FFE2", 0.10)}"></div>'
                    f'{_spec(150).replace("left:4%", "left:-280px").replace("right:4%", "width:560px").replace("top:3px", "top:-296px")}'
                    f'{"".join(svg)}{sph}</div>')
        js += [f'tl.fromTo("#{cid}-hero", {{ scale: 0.4, rotationY: -70, rotationX: 20, opacity: 0, transformPerspective: 1200 }}, '
               f'{{ scale: 1, rotationY: 0, rotationX: 0, opacity: 1, duration: {18 * fr:.3f}, ease: "expo.out" }}, {at + 2 * fr:.3f});',
               f'tl.to("#{cid}-hero", {{ rotationY: 16, rotationX: -6, duration: {max(0.3, dur - at - 0.6):.3f}, ease: "sine.inOut", transformPerspective: 1200 }}, {at + 20 * fr:.3f});',
               f'tl.to(".{cid}-he", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {8 * fr:.3f}, ease: "power2.out", stagger: {1.5 * fr:.4f} }}, {at + 8 * fr:.3f});',
               f'tl.fromTo("#{cid}-hero .nd", {{ scale: 0 }}, {{ scale: 1, duration: {8 * fr:.3f}, ease: "back.out(2.4)", stagger: {1.5 * fr:.4f} }}, {at + 5 * fr:.3f});']
    else:
        # the stat: a huge glass number with a gloss sweep, and two bars (before / after) at their true ratio
        st = p.get("stat", "71×")
        body.append(f'<div id="{cid}-num" style="position:absolute;left:0;right:0;top:{hy - 260:.0f}px;text-align:center;font-family:{F_EXT};font-size:430px;line-height:1;'
                    f'white-space:nowrap"><span style="position:relative;display:inline-block">'
                    f'<span style="color:#012616;text-shadow:{_extrude_shadow(20, "#00140C")}">{esc(st)}</span>'
                    f'<span style="position:absolute;left:0;top:0;background:linear-gradient(180deg, #FFFFFF 0%, #C9F7DD 40%, #5FD497 100%);-webkit-background-clip:text;background-clip:text;color:transparent">{esc(st)}</span>'
                    f'<span id="{cid}-gl" style="position:absolute;left:0;top:0;background:linear-gradient(104deg, transparent 38%, rgba(255,255,255,0.95) 48%, transparent 60%);'
                    f'background-size:400% 100%;background-position:120% 0;-webkit-background-clip:text;background-clip:text;color:transparent">{esc(st)}</span></span></div>')
        js += [f'tl.fromTo("#{cid}-num", {{ scale: 2.4, opacity: 0, filter: "blur(30px)" }}, {{ scale: 1, opacity: 1, filter: "blur(0px)", duration: {12 * fr:.3f}, ease: "expo.out" }}, {at:.3f});',
               f'tl.fromTo("#{cid}-gl", {{ backgroundPosition: "120% 0" }}, {{ backgroundPosition: "-30% 0", duration: {20 * fr:.3f}, ease: "power2.inOut" }}, {at + 10 * fr:.3f});',
               f'tl.fromTo("#{cid}-num", {{ y: 0 }}, {{ y: -14, duration: {max(0.3, dur - at):.3f}, ease: "sine.inOut" }}, {at + 12 * fr:.3f});']
        bars = p.get("bars")
        if bars:
            by = p.get("bars_y", 0.70) * cx.H
            bw = cx.W - 220
            ratio = bars.get("ratio", 1 / 71)
            body.append(f'<div id="{cid}-bars" style="position:absolute;left:110px;top:{by:.0f}px;width:{bw}px">'
                        f'<div class="bl">{esc(bars["before"])}</div><div class="bt"><div id="{cid}-b0" class="bf" style="background:linear-gradient(90deg,#6E8F7E,#A9C6B6)"></div></div>'
                        f'<div class="bl" style="margin-top:34px">{esc(bars["after"])}</div><div class="bt"><div id="{cid}-b1" class="bf" style="width:{max(0.6, ratio * 100):.2f}%;'
                        f'background:#4BF09A;box-shadow:0 0 18px #4BF09A"></div></div></div>')
            ba = cx.s(bars.get("at", 14))
            js += [f'tl.fromTo("#{cid}-bars", {{ opacity: 0, y: 30, filter: "blur(10px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: {10 * fr:.3f}, ease: "expo.out" }}, {ba:.3f});',
                   f'tl.fromTo("#{cid}-b0", {{ width: "0%" }}, {{ width: "100%", duration: {14 * fr:.3f}, ease: "power3.out" }}, {ba + 4 * fr:.3f});',
                   f'tl.fromTo("#{cid}-b1", {{ scaleX: 0, transformOrigin: "0 50%" }}, {{ scaleX: 1, duration: {6 * fr:.3f}, ease: "power3.out" }}, {ba + 16 * fr:.3f});']
    # words one at a time with motion blur, under the hero
    wy = p.get("words_y", 0.80) * cx.H
    for i, (wt, wat) in enumerate(p.get("words", [])):
        body.append(f'<div id="{cid}-w{i}" class="wd" style="top:{wy + i * 0:.0f}px">{esc(wt)}</div>')
        wa = cx.s(wat)
        js.append(f'tl.fromTo("#{cid}-w{i}", {{ opacity: 0, x: 80, filter: "blur(14px)" }}, {{ opacity: 1, x: 0, filter: "blur(0px)", duration: {8 * fr:.3f}, ease: "expo.out" }}, {wa:.3f});')
        if i + 1 < len(p["words"]):
            js.append(f'tl.to("#{cid}-w{i}", {{ opacity: 0, x: -80, filter: "blur(14px)", duration: {5 * fr:.3f}, ease: "power2.in" }}, {cx.s(p["words"][i + 1][1]) - 3 * fr:.3f});')
    css = (f"#{cid}-all {{ position:absolute; inset:0; background:{BRAND}; }} "
           f"#{cid}-all .bk {{ position:absolute; border-radius:38%; background:radial-gradient(circle at 35% 30%, rgba(190,255,220,0.9), rgba(40,170,105,0.65) 45%, rgba(1,50,32,0.2) 80%); }} "
           f"#{cid}-all .nd {{ position:absolute; border-radius:50%; background:radial-gradient(circle at 34% 30%, #E6FFF1 0%, #7CF2B4 16%, #18A464 46%, #035233 78%, #00180E 100%); "
           f"box-shadow:inset -6px -8px 14px rgba(0,0,0,0.35), 0 0 30px rgba(80,240,160,0.45); }} "
           f"#{cid}-all .hl {{ position:absolute; left:18%; top:12%; width:36%; height:26%; border-radius:50%; background:radial-gradient(ellipse, rgba(255,255,255,0.95), rgba(255,255,255,0)); }} "
           f"#{cid}-all .wd {{ position:absolute; left:0; right:0; text-align:center; font-family:{F_SERIF}; font-style:italic; font-size:92px; color:#E8FFF1; "
           f"text-shadow:0 0 22px rgba(120,255,180,0.35); white-space:nowrap; }} "
           f"#{cid}-all .bl {{ font-family:{F_UI}; font-weight:800; font-size:34px; color:#BFE8D1; margin-bottom:12px; letter-spacing:0.06em; }} "
           f"#{cid}-all .bt {{ height:34px; border-radius:17px; background:rgba(255,255,255,0.10); border:1.5px solid rgba(255,255,255,0.25); overflow:hidden; }} "
           f"#{cid}-all .bf {{ height:100%; border-radius:17px; }}")
    # in through white, out through white handled by Bloom overlays around it; a 2-frame fade guards the edges
    js.append(f'tl.fromTo("#{cid}-all", {{ opacity: 0 }}, {{ opacity: 1, duration: {2 * fr:.3f} }}, 0);')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, duration: {2 * fr:.3f} }}, {max(0, dur - 2 * fr):.3f});')
    return scene_file(cx, cid, cx.H, css, f'<div id="{cid}-all">{"".join(body)}</div>', "\n".join(js), transparent=True)


# ============================================================================== comment box CTA
def ov_commentbox(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    y = p.get("y", 0.70) * cx.H
    at = cx.s(p.get("at", 0))
    txt = p.get("text", "map")
    av = (f'<img src="{p["avatar"]}" style="width:92px;height:92px;border-radius:50%;object-fit:cover;margin-right:22px"/>' if p.get("avatar") else "")
    chars = "".join(f'<span class="{cid}-ch" style="opacity:0">{esc(c)}</span>' for c in txt)
    body = [f'<div id="{cid}-c" style="position:absolute;left:70px;right:70px;top:{y:.0f}px;height:150px;display:flex;align-items:center;padding:0 28px;box-sizing:border-box;{glass_css(75, "#F4FFF8", 0.66)}">'
            f'{_spec(75)}{av}<div style="flex:1;font-family:{F_UI};font-weight:800;font-size:58px;color:{BRAND}">{chars}<span id="{cid}-car" style="display:inline-block;width:4px;height:58px;'
            f'background:{BRAND};margin-left:4px;vertical-align:-8px"></span></div>'
            f'<div id="{cid}-send" style="width:104px;height:104px;border-radius:50%;background:{BRAND};display:flex;align-items:center;justify-content:center;'
            f'box-shadow:0 8px 20px rgba(1,50,32,0.4)"><svg viewBox="0 0 24 24" width="52" height="52"><path d="M4 12 L20 4 L14 20 L11.5 13 Z" fill="#EAF7EF"/></svg></div></div>']
    js = [f'tl.fromTo("#{cid}-c", {{ opacity: 0, y: 140, rotationX: 40, filter: "blur(12px)", transformPerspective: 900 }}, '
          f'{{ opacity: 1, y: 0, rotationX: 0, filter: "blur(0px)", duration: {14 * fr:.3f}, ease: "expo.out" }}, {at:.3f});']
    ta = cx.s(p.get("type_at", 8))
    for i in range(len(txt)):
        js.append(f'tl.set(".{cid}-ch:nth-child({i + 1})", {{ opacity: 1 }}, {ta + i * 3 * fr:.3f});')
    for k in range(int(dur * 2)):
        js.append(f'tl.set("#{cid}-car", {{ opacity: {0 if k % 2 else 1} }}, {k * 0.5:.3f});')
    sa = cx.s(p.get("send_at", 20))
    js += [f'tl.to("#{cid}-send", {{ scale: 0.82, duration: {2 * fr:.3f}, ease: "power2.in" }}, {sa - 2 * fr:.3f});',
           f'tl.to("#{cid}-send", {{ scale: 1, backgroundColor: "#1FB46E", boxShadow: "0 0 36px rgba(31,180,110,0.8)", duration: {8 * fr:.3f}, ease: "back.out(2.5)" }}, {sa:.3f});']
    if p.get("dm_at") is not None:
        dy = y - 230
        body.append(f'<div id="{cid}-dm" style="position:absolute;left:150px;right:150px;top:{dy:.0f}px;height:150px;display:flex;align-items:center;padding:0 30px;'
                    f'box-sizing:border-box;{glass_css(40, "#013220", 0.80)}">{_spec(40)}'
                    f'<div style="width:86px;height:86px;border-radius:24px;background:linear-gradient(160deg,#36E08A,#04603C);display:flex;align-items:center;justify-content:center;margin-right:24px">'
                    f'<svg viewBox="0 0 24 24" width="50" height="50"><path d="M3 6 h18 v11 h-11 l-5 4 v-4 h-2 z" fill="none" stroke="#EAF7EF" stroke-width="2" stroke-linejoin="round"/></svg></div>'
                    f'<div><div style="font-family:{F_UI};font-weight:800;font-size:40px;line-height:1.2;color:#F2FFF7;white-space:nowrap">{esc(p.get("dm_title", "DM"))}</div>'
                    f'<div style="font-family:{F_UI};font-weight:700;font-size:28px;line-height:1.2;margin-top:6px;color:rgba(234,247,239,0.7);white-space:nowrap">{esc(p.get("dm_sub", ""))}</div></div></div>')
        js.append(f'tl.fromTo("#{cid}-dm", {{ opacity: 0, y: 60, scale: 0.85, filter: "blur(12px)" }}, {{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)", duration: {12 * fr:.3f}, ease: "back.out(1.6)" }}, {cx.s(p["dm_at"]):.3f});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, y: 40, filter: "blur(10px)", duration: {6 * fr:.3f}, ease: "power2.in" }}, {max(0, dur - 6 * fr):.3f});')
    return scene_file(cx, cid, cx.H, f"#{cid}-all {{ position:absolute; inset:0; }}", f'<div id="{cid}-all">{"".join(body)}</div>', "\n".join(js), transparent=True)


# ============================================================================== card fan
def _card_inner(cid: str, k: int, c: dict, w: float, h: float) -> str:
    kind = c.get("kind", "logo")
    if kind == "logo":
        hero = f'<img src="{c["icon"]}" style="width:{w * 0.52:.0f}px;height:{w * 0.52:.0f}px;object-fit:contain;filter:drop-shadow(0 12px 20px rgba(0,0,0,0.45))"/>'
    elif kind == "graph":
        nodes, edges = _graph(7, -w * 0.3, -w * 0.3, w * 0.6, w * 0.6, 5 + k)
        lines = "".join(f'<line x1="{nodes[a][0]:.0f}" y1="{nodes[a][1]:.0f}" x2="{nodes[b][0]:.0f}" y2="{nodes[b][1]:.0f}" stroke="rgba(190,255,220,0.8)" stroke-width="4"/>' for a, b in edges)
        sph = "".join(_sphere(f"{cid}-k{k}n{i}", nx, ny, 22 * s_ + 6) for i, (nx, ny, s_) in enumerate(nodes))
        hero = (f'<div style="position:relative;width:{w * 0.6:.0f}px;height:{w * 0.6:.0f}px"><div style="position:absolute;left:50%;top:50%;width:0;height:0">'
                f'<svg style="position:absolute;overflow:visible" width="1" height="1">{lines}</svg>{sph}</div></div>')
    else:
        hero = (f'<div style="font-family:{F_EXT};font-size:{w * 0.42:.0f}px;line-height:1;background:linear-gradient(180deg,#FFFFFF,#7FF0B4);-webkit-background-clip:text;'
                f'background-clip:text;color:transparent;filter:drop-shadow(0 8px 0 #00170E)">{esc(c["t"])}</div>')
    return (f'{_spec(34)}<div style="flex:1;display:flex;align-items:center;justify-content:center">{hero}</div>'
            f'<div style="font-family:{F_UI};font-weight:800;font-size:{w * 0.13:.0f}px;color:#F2FFF7;white-space:nowrap">{esc(c.get("title", ""))}</div>'
            f'<div style="font-family:{F_UI};font-weight:700;font-size:{w * 0.085:.0f}px;color:#9FF0C4;margin:4px 0 {h * 0.07:.0f}px;white-space:nowrap">{esc(c.get("sub", ""))}</div>')


def ov_cardfan(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Reference B 1.6-2.0 s: a light streak shoots up from below, bursts, and three tall cards fan out above the
    speaker (outer ones tilted ~13 deg and lower, the middle one in front), then float. STARTING DEFAULTS."""
    fr = 1 / cx.fps
    at = cx.s(p.get("at", 0))
    w, h = p.get("w", 270), p.get("h", 440)
    ccx, ccy = p.get("x", 0.5) * cx.W, p.get("y", 0.17) * cx.H
    spread, tilt = p.get("spread", 300), p.get("tilt", 13)
    cards = p["cards"]
    n = len(cards)
    body = [f'<div id="{cid}-sk" style="position:absolute;left:{ccx - 5:.0f}px;top:{ccy:.0f}px;width:10px;height:{cx.H * 0.85 - ccy:.0f}px;border-radius:5px;'
            f'background:linear-gradient(180deg,#FFFFFF,#7CF2B4 30%,rgba(54,224,138,0));box-shadow:0 0 24px #7CF2B4,0 0 60px rgba(54,224,138,0.8);transform-origin:50% 100%;opacity:0"></div>',
            f'<div id="{cid}-fl" style="position:absolute;left:{ccx - 300:.0f}px;top:{ccy - 300:.0f}px;width:600px;height:600px;border-radius:50%;'
            f'background:radial-gradient(circle,#FFFFFF 0%,rgba(160,255,205,0.85) 22%,rgba(54,224,138,0) 65%);mix-blend-mode:screen;opacity:0"></div>']
    js = [f'tl.fromTo("#{cid}-sk", {{ scaleY: 0, opacity: 1 }}, {{ scaleY: 1, opacity: 1, duration: {5 * fr:.3f}, ease: "power3.in" }}, {at:.3f});',
          f'tl.to("#{cid}-sk", {{ opacity: 0, duration: {4 * fr:.3f} }}, {at + 5 * fr:.3f});',
          f'tl.fromTo("#{cid}-fl", {{ scale: 0.1, opacity: 0 }}, {{ scale: 1.3, opacity: 1, duration: {4 * fr:.3f}, ease: "power2.out" }}, {at + 4 * fr:.3f});',
          f'tl.to("#{cid}-fl", {{ scale: 1.8, opacity: 0, duration: {8 * fr:.3f}, ease: "power2.out" }}, {at + 8 * fr:.3f});']
    order = sorted(range(n), key=lambda k: -abs(k - (n - 1) / 2))      # outer cards painted first, middle on top
    for k in order:
        off = k - (n - 1) / 2
        x, y = ccx + off * spread - w / 2, ccy - h / 2 + abs(off) * 34
        body.append(f'<div id="{cid}-c{k}" class="cd" style="left:{x:.0f}px;top:{y:.0f}px;width:{w}px;height:{h}px;z-index:{10 - int(abs(off) * 2)}">'
                    f'{_card_inner(cid, k, cards[k], w, h)}</div>')
        t0 = at + (5 + abs(off) * 2) * fr
        js.append(f'tl.fromTo("#{cid}-c{k}", {{ x: {-off * spread:.0f}, y: {-abs(off) * 34 + 60:.0f}, scale: 0.25, rotationY: {-off * 70:.0f}, rotationZ: 0, opacity: 0, filter: "blur(16px)", transformPerspective: 1100 }}, '
                  f'{{ x: 0, y: 0, scale: 1, rotationY: {off * -14:.0f}, rotationZ: {off * tilt:.1f}, opacity: 1, filter: "blur(0px)", duration: {13 * fr:.3f}, ease: "back.out(1.5)" }}, {t0:.3f});')
        bob = max(0.3, dur - (t0 + 13 * fr) - 0.3)
        js.append(f'tl.to("#{cid}-c{k}", {{ y: {-14 if k % 2 else 12}, rotationY: {off * -6:.0f}, duration: {bob:.3f}, ease: "sine.inOut" }}, {t0 + 13 * fr:.3f});')
    js.append(f'tl.to("#{cid}-all .cd", {{ y: -120, opacity: 0, filter: "blur(14px)", duration: {7 * fr:.3f}, ease: "power2.in", stagger: {fr:.4f} }}, {max(0, dur - 9 * fr):.3f});')
    css = (f"#{cid}-all {{ position:absolute; inset:0; }} #{cid}-all .cd {{ position:absolute; display:flex; flex-direction:column; align-items:center; box-sizing:border-box; "
           f"border-radius:34px; overflow:hidden; background:linear-gradient(165deg, #12804F 0%, #04603C 38%, {BRAND} 78%, #001A10 100%); "
           f"border:2px solid rgba(255,255,255,0.55); box-shadow:inset 0 2px 1px rgba(255,255,255,0.7), inset 3px 0 4px rgba(255,70,90,0.15), inset -3px 0 4px rgba(70,140,255,0.18), "
           f"0 34px 60px rgba(0,30,18,0.45), 0 8px 18px rgba(0,30,18,0.3); }} "
           f"#{cid}-all .nd {{ position:absolute; border-radius:50%; background:radial-gradient(circle at 34% 30%, #E6FFF1 0%, #7CF2B4 16%, #18A464 46%, #035233 78%, #00180E 100%); }} "
           f"#{cid}-all .hl {{ position:absolute; left:18%; top:12%; width:36%; height:26%; border-radius:50%; background:radial-gradient(ellipse, rgba(255,255,255,0.95), rgba(255,255,255,0)); }}")
    inner, tj = _track(cid, p, f'<div id="{cid}-all">{"".join(body)}</div>')
    return scene_file(cx, cid, cx.H, css, inner, "\n".join(tj + js), transparent=True)


# ============================================================================== perspective word
def ov_persptext(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Reference A 4.3-4.6 s: a word lying on a tilted plane across the speaker, whipping in sideways with
    motion blur, drifting, whipping out. STARTING DEFAULTS."""
    fr = 1 / cx.fps
    at = cx.s(p.get("at", 0))
    size, y = p.get("size", 230), p.get("y", 0.72) * cx.H
    d = p.get("dir", 1)
    word = (f'<div id="{cid}-w" style="position:absolute;left:0;right:0;top:{y - size * 0.6:.0f}px;text-align:center;white-space:nowrap;font-family:{F_EXT};font-size:{size}px;'
            f'line-height:1.05;transform:perspective(900px) rotateX({p.get("rx", 48)}deg) rotateZ({p.get("rz", -7)}deg)">'
            f'<span style="position:relative;display:inline-block"><span style="color:{SIDE};text-shadow:{_extrude_shadow(14, SIDE, 0.3, 1.1)}">{esc(p["t"])}</span>'
            f'<span style="position:absolute;left:0;top:0;background:linear-gradient(180deg,#FFFFFF 0%,#D5FBE6 55%,#7FE0AE 100%);-webkit-background-clip:text;background-clip:text;color:transparent">{esc(p["t"])}</span></span></div>')
    js = [f'tl.fromTo("#{cid}-m", {{ x: {-1300 * d}, opacity: 0, filter: "blur(26px)" }}, {{ x: 0, opacity: 1, filter: "blur(0px)", duration: {9 * fr:.3f}, ease: "expo.out" }}, {at:.3f});',
          f'tl.to("#{cid}-m", {{ x: {40 * d}, duration: {max(0.2, dur - at - 0.6):.3f}, ease: "none" }}, {at + 9 * fr:.3f});',
          f'tl.to("#{cid}-m", {{ x: {1400 * d}, opacity: 0, filter: "blur(26px)", duration: {6 * fr:.3f}, ease: "power3.in" }}, {max(0, dur - 6 * fr):.3f});']
    inner, tj = _track(cid, p, f'<div id="{cid}-all"><div id="{cid}-m" style="position:absolute;inset:0">{word}</div></div>')
    return scene_file(cx, cid, cx.H, f"#{cid}-all {{ position:absolute; inset:0; }}", inner, "\n".join(tj + js), transparent=True)


OVERLAYS = {"CardFan": ov_cardfan, "PerspText": ov_persptext, "Extrude": ov_extrude, "Bloom": ov_bloom, "GlassCard": ov_glasscard, "GraphWall": ov_graphwall,
            "BrandScene": ov_brandscene, "CommentBox": ov_commentbox}
