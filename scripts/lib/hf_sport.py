"""Sports-broadcast analysis graphics (2026-11-17): a telestrator for freeze frames, a reason panel
with an odometer index, and a standings board where one row overtakes to #1.

Motion language, from the LottieFiles motion-design rules (references/craft-human.md): one personality
(Energetic-broadcast: entrances 0.35-0.5 s expo/power3 out, exits 0.25 s power2 in, overshoot only on
pops), primary + secondary + ambient layers (a dot pops, its ripple follows 60 ms later; a sheen
crosses a panel once), stagger budgets under 0.5 s, nothing travels a third of the frame in one move.
All timings are seconds inside the overlay; `at` values in p are frames, overlay-relative."""
from __future__ import annotations

import math

FONT_GZ = "'Noto Sans Ethiopic', 'Montserrat', sans-serif"
FONT_NUM = "'Anton', 'Montserrat', sans-serif"
FONT_META = "'JetBrains Mono', 'Noto Sans Ethiopic', monospace"
PANEL = "rgba(10,10,12,0.86)"


def _esc(t: str) -> str:
    from .hf_ae import esc
    return esc(t)


def _scene(cx, cid, css, body, js):
    from .hf_design import scene_file
    return scene_file(cx, cid, cx.H, css, body, "\n".join(js), transparent=True)


# ------------------------------------------------------------------------------------------ telestrator
def ov_telestrate(cx, cid: str, dur: float, p: dict) -> str:
    """Telestrator over a frozen frame. p: joints {name: [x, y]} (screen fractions); bones [[a, b, at]];
    dots [[name, at]]; angle {at, j, a, b, r} (arc at joint j from a to b); force {x0, y0, x1, y1, at}
    (line of action with an arrow head); tags [{t, x, y, at, anchor: name, side: 'l'|'r'}];
    spotlight {x, y, rx, ry, at, dim} (darken outside an ellipse); kicker {t, at} (top-left meta)."""
    W, H, fps = cx.W, cx.H, cx.fps
    a = cx.brand.get("accent", "#FF4438")
    J = {k: (v[0] * W, v[1] * H) for k, v in p.get("joints", {}).items()}
    s = lambda f: f / fps  # noqa: E731
    svg, html, js = [], [], []
    sp = p.get("spotlight")
    if sp:
        html.append(f'<div id="{cid}-sp" style="position:absolute;inset:0;opacity:0;background:radial-gradient(ellipse {sp["rx"] * 100:.0f}% {sp["ry"] * 100:.0f}% at {sp["x"] * 100:.0f}% {sp["y"] * 100:.0f}%, rgba(0,0,0,0) 60%, rgba(0,0,0,{sp.get("dim", 0.6)}) 100%)"></div>')
        js.append(f'tl.to("#{cid}-sp", {{ opacity: 1, duration: 0.5, ease: "power2.out" }}, {s(sp["at"]):.3f});')
    for i, (ja, jb, at) in enumerate(p.get("bones", [])):
        (x0, y0), (x1, y1) = J[ja], J[jb]
        L = math.hypot(x1 - x0, y1 - y0)
        svg.append(f'<line id="{cid}-b{i}" x1="{x0:.0f}" y1="{y0:.0f}" x2="{x1:.0f}" y2="{y1:.0f}" stroke="#fff" stroke-width="7" stroke-linecap="round" '
                   f'stroke-dasharray="{L:.0f}" stroke-dashoffset="{L:.0f}" opacity="0" filter="url(#{cid}-gl)"/>')
        js.append(f'tl.set("#{cid}-b{i}", {{ opacity: 1 }}, {s(at):.3f});')
        js.append(f'tl.to("#{cid}-b{i}", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 0.32, ease: "power2.out" }}, {s(at):.3f});')
    an = p.get("angle")
    if an:
        (jx, jy), (ax, ay), (bx, by) = J[an["j"]], J[an["a"]], J[an["b"]]
        r = an.get("r", 80)
        t0, t1 = math.atan2(ay - jy, ax - jx), math.atan2(by - jy, bx - jx)
        d = (t1 - t0 + math.pi) % (2 * math.pi) - math.pi
        sweep = 1 if d > 0 else 0
        p0 = (jx + r * math.cos(t0), jy + r * math.sin(t0))
        p1 = (jx + r * math.cos(t0 + d), jy + r * math.sin(t0 + d))
        arc = f"M {p0[0]:.1f} {p0[1]:.1f} A {r} {r} 0 0 {sweep} {p1[0]:.1f} {p1[1]:.1f}"
        alen = abs(d) * r
        svg.append(f'<path id="{cid}-wedge" d="M {jx:.1f} {jy:.1f} L {p0[0]:.1f} {p0[1]:.1f} A {r} {r} 0 0 {sweep} {p1[0]:.1f} {p1[1]:.1f} Z" fill="{a}" opacity="0"/>')
        svg.append(f'<path id="{cid}-arc" d="{arc}" fill="none" stroke="{a}" stroke-width="8" stroke-linecap="round" stroke-dasharray="{alen:.0f}" stroke-dashoffset="{alen:.0f}" opacity="0"/>')
        js.append(f'tl.set("#{cid}-arc", {{ opacity: 1 }}, {s(an["at"]):.3f});')
        js.append(f'tl.to("#{cid}-arc", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 0.45, ease: "expo.out" }}, {s(an["at"]):.3f});')
        js.append(f'tl.to("#{cid}-wedge", {{ opacity: 0.28, duration: 0.35, ease: "power2.out" }}, {s(an["at"]) + 0.06:.3f});')
    fo = p.get("force")
    if fo:
        x0, y0, x1, y1 = fo["x0"] * W, fo["y0"] * H, fo["x1"] * W, fo["y1"] * H
        L = math.hypot(x1 - x0, y1 - y0)
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        svg.append(f'<line id="{cid}-f" x1="{x0:.0f}" y1="{y0:.0f}" x2="{x1:.0f}" y2="{y1:.0f}" stroke="{a}" stroke-width="6" stroke-linecap="round" '
                   f'stroke-dasharray="{L:.0f}" stroke-dashoffset="{L:.0f}" opacity="0"/>')
        svg.append(f'<g transform="translate({x1:.0f} {y1:.0f}) rotate({ang:.1f})"><path id="{cid}-fh" d="M -30 -17 L 4 0 L -30 17 Z" fill="{a}" opacity="0"/></g>')
        svg.append(f'<ellipse id="{cid}-fg" cx="{x1:.0f}" cy="{y1 + 8:.0f}" rx="70" ry="16" fill="none" stroke="{a}" stroke-width="4" opacity="0"/>')
        js.append(f'tl.set("#{cid}-f", {{ opacity: 1 }}, {s(fo["at"]):.3f});')
        js.append(f'tl.to("#{cid}-f", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 0.5, ease: "power3.inOut" }}, {s(fo["at"]):.3f});')
        js.append(f'tl.to("#{cid}-fh", {{ opacity: 1, duration: 0.12 }}, {s(fo["at"]) + 0.45:.3f});')
        js.append(f'tl.fromTo("#{cid}-fg", {{ opacity: 0, attr: {{ rx: 20 }} }}, {{ opacity: 0.9, attr: {{ rx: 70 }}, duration: 0.35, ease: "expo.out", immediateRender: false }}, {s(fo["at"]) + 0.5:.3f});')
    for i, (jn, at) in enumerate(p.get("dots", [])):
        x, y = J[jn]
        svg.append(f'<circle id="{cid}-r{i}" cx="{x:.0f}" cy="{y:.0f}" r="12" fill="none" stroke="{a}" stroke-width="4" opacity="0"/>')
        svg.append(f'<circle id="{cid}-d{i}" cx="{x:.0f}" cy="{y:.0f}" r="0" fill="#fff" stroke="{a}" stroke-width="6"/>')
        js.append(f'tl.to("#{cid}-d{i}", {{ attr: {{ r: 13 }}, duration: 0.28, ease: "back.out(3)" }}, {s(at):.3f});')
        js.append(f'tl.fromTo("#{cid}-r{i}", {{ attr: {{ r: 12 }}, opacity: 0.9 }}, {{ attr: {{ r: 54 }}, opacity: 0, duration: 0.6, ease: "power2.out", immediateRender: false }}, {s(at) + 0.06:.3f});')
    for i, tg in enumerate(p.get("tags", [])):
        x, y = tg["x"] * W, tg["y"] * H
        ax_, ay_ = J[tg["anchor"]]
        right = tg.get("side", "r") == "r"
        ex = x if right else x
        L = math.hypot(ex - ax_, y - ay_)
        svg.append(f'<line id="{cid}-tl{i}" x1="{ax_:.0f}" y1="{ay_:.0f}" x2="{ex:.0f}" y2="{y:.0f}" stroke="#fff" stroke-width="3" '
                   f'stroke-dasharray="{L:.0f}" stroke-dashoffset="{L:.0f}" opacity="0"/>')
        anchor_css = f"left:{x:.0f}px" if right else f"right:{W - x:.0f}px"
        html.append(f'<div id="{cid}-t{i}" class="tag" style="{anchor_css};top:{y - 40:.0f}px;clip-path:inset(0% {"100% 0% 0%" if right else "0% 0% 100%"})">'
                    f'<i style="background:{a}"></i><span>{_esc(tg["t"])}</span></div>')
        js.append(f'tl.set("#{cid}-tl{i}", {{ opacity: 0.9 }}, {s(tg["at"]):.3f});')
        js.append(f'tl.to("#{cid}-tl{i}", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 0.22, ease: "power2.out" }}, {s(tg["at"]):.3f});')
        js.append(f'tl.to("#{cid}-t{i}", {{ clipPath: "inset(0% 0% 0% 0%)", duration: 0.38, ease: "expo.out" }}, {s(tg["at"]) + 0.16:.3f});')
    k = p.get("kicker")
    if k:
        html.append(f'<div id="{cid}-k" class="kick" style="clip-path:inset(0% 100% 0% 0%)"><b style="background:{a}"></b>{_esc(k["t"])}</div>')
        js.append(f'tl.to("#{cid}-k", {{ clipPath: "inset(0% 0% 0% 0%)", duration: 0.4, ease: "expo.out" }}, {s(k["at"]):.3f});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, duration: 0.2, ease: "power2.in" }}, {max(0, dur - 0.2):.3f});')
    css = f"""#{cid}-all {{ position: absolute; inset: 0; }}
#{cid}-all svg {{ position: absolute; left: 0; top: 0; overflow: visible; }}
#{cid}-all .tag {{ position: absolute; height: 80px; display: flex; align-items: center; background: {PANEL}; padding: 0 30px 0 0;
  font-family: {FONT_GZ}; font-weight: 900; font-size: 46px; color: #fff; white-space: nowrap; box-shadow: 0 14px 34px rgba(0,0,0,0.3); }}
#{cid}-all .tag i {{ display: block; width: 10px; height: 100%; margin-right: 22px; }}
#{cid}-all .kick {{ position: absolute; left: 64px; top: 130px; font-family: {FONT_META}; font-weight: 700; font-size: 30px; letter-spacing: 0.18em;
  color: #fff; display: flex; align-items: center; gap: 16px; }}
#{cid}-all .kick b {{ display: block; width: 18px; height: 18px; border-radius: 50%; }}"""
    defs = f'<defs><filter id="{cid}-gl" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#000" flood-opacity="0.55"/></filter></defs>'
    body = f'<div id="{cid}-all">{"".join(html[:1])}<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">{defs}{"".join(svg)}</svg>{"".join(html[1:])}</div>'
    return _scene(cx, cid, css, body, js)


# ------------------------------------------------------------------------------------------ reason panel
def ov_reasonpanel(cx, cid: str, dur: float, p: dict) -> str:
    """A broadcast panel: optional claim that gets struck through, then numbered states whose index
    rolls like an odometer while the text swaps. p: x, y (top-left, fractions), w (px), kicker,
    claim {t, at, strikeAt}, states [{n, t, at}], in (frames, default 0)."""
    a = cx.brand.get("accent", "#FF4438")
    fps = cx.fps
    s = lambda f: f / fps  # noqa: E731
    x, y, w = p.get("x", 0.06) * cx.W, p.get("y", 0.1) * cx.H, p.get("w", 900)
    NH = 150
    states = p.get("states", [])
    nums = "".join(f'<div class="n">{_esc(st["n"])}</div>' for st in [{"n": "—"}] + states)
    texts = []
    cl = p.get("claim")
    if cl:
        texts.append(f'<div id="{cid}-c" class="tx claim">“{_esc(cl["t"])}”<svg class="strike" width="100%" height="40" viewBox="0 0 600 40" preserveAspectRatio="none">'
                     f'<path id="{cid}-cs" d="M 4 26 L 596 12" stroke="{a}" stroke-width="10" stroke-linecap="round" fill="none" stroke-dasharray="600" stroke-dashoffset="600"/></svg></div>')
    for i, st in enumerate(states):
        texts.append(f'<div id="{cid}-s{i}" class="tx" style="opacity:0">{_esc(st["t"])}</div>')
    js = []
    t_in = s(p.get("in", 0))
    js.append(f'tl.fromTo("#{cid}-bar", {{ scaleY: 0 }}, {{ scaleY: 1, duration: 0.25, ease: "power3.out" }}, {t_in:.3f});')
    js.append(f'tl.to("#{cid}-p", {{ clipPath: "inset(0% 0% 0% 0%)", duration: 0.45, ease: "expo.out" }}, {t_in + 0.08:.3f});')
    js.append(f'tl.fromTo("#{cid}-sh", {{ x: -300 }}, {{ x: {w + 300}, duration: 0.9, ease: "power2.inOut" }}, {t_in + 0.3:.3f});')
    if cl:
        js.append(f'tl.fromTo("#{cid}-c", {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.4, ease: "power3.out" }}, {t_in + 0.18:.3f});')
        js.append(f'tl.to("#{cid}-cs", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 0.3, ease: "power2.inOut" }}, {s(cl["strikeAt"]):.3f});')
        js.append(f'tl.to("#{cid}-c", {{ opacity: 0.45, duration: 0.3 }}, {s(cl["strikeAt"]) + 0.3:.3f});')
    prev = f"#{cid}-c" if cl else None
    for i, st in enumerate(states):
        t = s(st["at"])
        js.append(f'tl.to("#{cid}-col", {{ y: {-(i + 1) * NH}, duration: 0.55, ease: "power4.inOut" }}, {t:.3f});')
        if prev:
            js.append(f'tl.to("{prev}", {{ y: -36, opacity: 0, duration: 0.22, ease: "power2.in" }}, {t:.3f});')
        js.append(f'tl.fromTo("#{cid}-s{i}", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.42, ease: "power3.out" }}, {t + 0.12:.3f});')
        js.append(f'tl.fromTo("#{cid}-sh", {{ x: -300 }}, {{ x: {w + 300}, duration: 0.8, ease: "power2.inOut" }}, {t + 0.2:.3f});')
        prev = f"#{cid}-s{i}"
    js.append(f'tl.to("#{cid}-p", {{ clipPath: "inset(0% 0% 0% 100%)", duration: 0.28, ease: "power2.in" }}, {max(0, dur - 0.3):.3f});')
    js.append(f'tl.to("#{cid}-bar", {{ scaleY: 0, duration: 0.2, ease: "power2.in" }}, {max(0, dur - 0.2):.3f});')
    kick = f'<div class="k">{_esc(p["kicker"])}</div>' if p.get("kicker") else ""
    css = f"""#{cid}-w {{ position: absolute; left: {x:.0f}px; top: {y:.0f}px; width: {w}px; }}
#{cid}-bar {{ position: absolute; left: 0; top: 0; width: 12px; height: {NH + 30}px; background: {a}; transform-origin: 50% 0%; }}
#{cid}-p {{ position: absolute; left: 12px; top: 0; width: {w - 12}px; height: {NH + 30}px; background: {PANEL}; overflow: hidden;
  clip-path: inset(0% 100% 0% 0%); box-shadow: 0 18px 40px rgba(0,0,0,0.3); }}
#{cid}-sh {{ position: absolute; top: 0; left: 0; width: 160px; height: 100%; background: linear-gradient(100deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0) 100%); }}
#{cid}-win {{ position: absolute; left: 26px; top: 15px; height: {NH}px; width: 190px; overflow: hidden; }}
#{cid}-col .n {{ height: {NH}px; line-height: {NH}px; font-family: {FONT_NUM}; font-size: 150px; color: {a}; }}
#{cid}-p .k {{ position: absolute; left: 236px; top: 26px; font-family: {FONT_META}; font-weight: 700; font-size: 26px; letter-spacing: 0.2em; color: rgba(255,255,255,0.6); }}
#{cid}-p .tx {{ position: absolute; left: 236px; right: 24px; top: 70px; font-family: {FONT_GZ}; font-weight: 900; font-size: 56px; line-height: 1.12; color: #fff; }}
#{cid}-p .claim {{ font-size: 64px; }}
#{cid}-p .strike {{ position: absolute; left: -6px; top: 24px; width: 104%; overflow: visible; }}"""
    body = (f'<div id="{cid}-w"><div id="{cid}-p"><div id="{cid}-sh"></div><div id="{cid}-win"><div id="{cid}-col">{nums}</div></div>{kick}{"".join(texts)}</div>'
            f'<div id="{cid}-bar"></div></div>')
    return _scene(cx, cid, css, body, js)


# ------------------------------------------------------------------------------------------ standings
def ov_standings(cx, cid: str, dur: float, p: dict) -> str:
    """Standings rows slide in as they are named; the hero row enters last at the bottom and overtakes
    to the top, the others step down, a #1 badge pops. p: x (centre), y (top), w, title {t, at},
    rows [{t, at}], hero {t, at, rankAt}, badge."""
    a = cx.brand.get("accent", "#FF4438")
    fps = cx.fps
    s = lambda f: f / fps  # noqa: E731
    w, RH, GAP = p.get("w", 860), p.get("rh", 96), 12
    x0, y0 = p.get("x", 0.5) * cx.W - w / 2, p.get("y", 0.06) * cx.H
    rows = p["rows"]
    hero = p["hero"]
    n = len(rows) + 1
    html, js = [], []
    ttl = p.get("title")
    top0 = 64 if ttl else 0
    if ttl:
        html.append(f'<div id="{cid}-ti" class="ti" style="clip-path:inset(0% 100% 0% 0%)"><b style="background:{a}"></b>{_esc(ttl["t"])}</div>')
        js.append(f'tl.to("#{cid}-ti", {{ clipPath: "inset(0% 0% 0% 0%)", duration: 0.4, ease: "expo.out" }}, {s(ttl["at"]):.3f});')
    for i, r in enumerate(rows):
        html.append(f'<div id="{cid}-r{i}" class="row" style="top:{top0 + i * (RH + GAP)}px;opacity:0"><em><u id="{cid}-o{i}">{i + 1}</u><u id="{cid}-n{i}" style="opacity:0">{i + 2}</u></em><span>{_esc(r["t"])}</span></div>')
        js.append(f'tl.fromTo("#{cid}-r{i}", {{ x: 70, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.4, ease: "power3.out" }}, {s(r["at"]):.3f});')
    hy = top0 + (n - 1) * (RH + GAP)
    html.append(f'<div id="{cid}-h" class="row hero" style="top:{hy}px;opacity:0"><i id="{cid}-hf" style="background:{a}"></i><em id="{cid}-hn">{n}</em><span>{_esc(hero["t"])}</span>'
                f'<b id="{cid}-bd" style="color:{a}">{_esc(p.get("badge", "#1"))}</b></div>')
    js.append(f'tl.fromTo("#{cid}-h", {{ x: 70, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.4, ease: "power3.out" }}, {s(hero["at"]):.3f});')
    js.append(f'tl.fromTo("#{cid}-hf", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.45, ease: "expo.out" }}, {s(hero["at"]) + 0.12:.3f});')
    tr = s(hero["rankAt"])
    js.append(f'tl.to("#{cid}-h", {{ y: {-hy + top0}, scale: 1.04, duration: 0.6, ease: "power3.inOut" }}, {tr:.3f});')
    js.append(f'tl.to("#{cid}-h", {{ scale: 1, duration: 0.25, ease: "power2.out" }}, {tr + 0.6:.3f});')
    for i in range(len(rows)):
        js.append(f'tl.to("#{cid}-r{i}", {{ y: {RH + GAP}, opacity: 0.55, duration: 0.6, ease: "power3.inOut" }}, {tr + 0.04 * (i + 1):.3f});')
        js.append(f'tl.to("#{cid}-o{i}", {{ y: -{RH * 0.6:.0f}, opacity: 0, duration: 0.3, ease: "power2.in" }}, {tr + 0.25:.3f});')
        js.append(f'tl.fromTo("#{cid}-n{i}", {{ y: {RH * 0.6:.0f}, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: "power3.out" }}, {tr + 0.4:.3f});')
    js.append(f'tl.to("#{cid}-hn", {{ opacity: 0, duration: 0.15 }}, {tr + 0.2:.3f});')
    js.append(f'tl.fromTo("#{cid}-bd", {{ scale: 0, rotation: -20 }}, {{ scale: 1, rotation: 0, duration: 0.4, ease: "back.out(3)" }}, {tr + 0.55:.3f});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, y: -20, duration: 0.25, ease: "power2.in" }}, {max(0, dur - 0.25):.3f});')
    css = f"""#{cid}-all {{ position: absolute; left: {x0:.0f}px; top: {y0:.0f}px; width: {w}px; }}
#{cid}-all .ti {{ position: absolute; left: 0; top: 0; height: 50px; display: flex; align-items: center; gap: 16px; font-family: {FONT_GZ}; font-weight: 800; font-size: 34px;
  color: rgba(255,255,255,0.85); letter-spacing: 0.02em; }}
#{cid}-all .ti b {{ display: block; width: 14px; height: 14px; border-radius: 50%; }}
#{cid}-all .row {{ position: absolute; left: 0; width: {w}px; height: {RH}px; background: {PANEL}; display: flex; align-items: center;
  box-shadow: 0 14px 30px rgba(0,0,0,0.28); overflow: hidden; }}
#{cid}-all .row em {{ position: relative; width: 96px; text-align: center; font-style: normal; font-family: {FONT_NUM}; font-size: {RH * 0.62:.0f}px; color: rgba(255,255,255,0.45); }}
#{cid}-all .row span {{ position: relative; font-family: {FONT_GZ}; font-weight: 900; font-size: {RH * 0.5:.0f}px; color: #fff; white-space: nowrap; }}
#{cid}-all .row em {{ height: {RH}px; overflow: hidden; }}
#{cid}-all .row em u {{ position: absolute; left: 0; right: 0; top: 0; line-height: {RH}px; text-decoration: none; }}
#{cid}-all .hero i {{ position: absolute; inset: 0; transform-origin: 0% 50%; }}
#{cid}-all .hero em {{ color: #fff; }}
#{cid}-all .hero b {{ position: absolute; right: 22px; top: 14px; width: 68px; height: 68px; border-radius: 50%; background: #fff; display: flex;
  align-items: center; justify-content: center; font-family: {FONT_NUM}; font-size: 36px; font-weight: 400; }}"""
    return _scene(cx, cid, css, f'<div id="{cid}-all">{"".join(html)}</div>', js)
