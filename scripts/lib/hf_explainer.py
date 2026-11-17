"""Explainer stages in 3D: the speaker's footage folds into a floating card and a studio set builds
behind it (2026-11-17, after "where is the motion design" on the snap edit).

- `card_js`: camera move `{"card": {...}}`. The footage (#cam) folds into a tilted, rounded 3D card,
  holds with a slow drift, and unfolds back to full frame. Pair it with an `under: true` scene.
- `flip_js`: the `flip3d` fx. The whole frame turns on its vertical axis like a card and lands on the
  next shot.
- `sc_stage3d` (scene `Stage3D`, `under: true`): a studio set (glow, perspective floor grid, seeded
  dust) with a claim that is struck through, a headline, and cards that flip in with 3D icons.
- `sc_podium3d` (scene `Podium3D`, `under: true`): pillars rise in perspective one after another; the
  hero pillar rises highest and a 3D trophy drops onto it.
- `ov_title3d` (overlay `Title3D`, usually `behind`): extruded display type that stands up from the
  floor, drifts in 3D, and leaves forwards; optional 3D icons that spin in.

Every number marked STARTING DEFAULT was set by eye on the snap edit and isn't a measurement."""
from __future__ import annotations

PERSP = 2200          # STARTING DEFAULT: px, camera distance for the card and the flip
FONT_TITLE = "'Zemach', 'Noto Sans Ethiopic', sans-serif"
FONT_BODY = "'Menbere', 'Noto Sans Ethiopic', sans-serif"
FONT_NUM = "'Anton', 'Montserrat', sans-serif"
FONT_META = "'JetBrains Mono', monospace"


def _esc(t: str) -> str:
    from .hf_ae import esc
    return esc(t)


def _icon(name: str) -> str:
    from .hf_design import icon3d
    return icon3d(name)


def _shade(hex_: str, k: float) -> str:
    """Darken a #rrggbb colour by factor k (0-1)."""
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"#{int(r * k):02x}{int(g * k):02x}{int(b * k):02x}"


def _tint(hex_: str, k: float) -> str:
    """Mix a #rrggbb colour toward white by k (0-1): a readable highlight of a dark brand colour."""
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"#{int(r + (255 - r) * k):02x}{int(g + (255 - g) * k):02x}{int(b + (255 - b) * k):02x}"


def extrude(color: str, depth: int, dx: float = 0.55, dy: float = 1.0) -> str:
    """text-shadow stack that reads as a solid extrusion below and to the right, then a soft contact shadow."""
    side = _shade(color, 0.42)
    layers = [f"{i * dx:.1f}px {i * dy:.1f}px 0 {side}" for i in range(1, depth + 1)]
    layers.append(f"{depth * dx + 6:.0f}px {depth * dy + 18:.0f}px 34px rgba(0,0,0,0.6)")
    return ", ".join(layers)


# ---------------------------------------------------------------------------------------- root hooks
def card_js(sel: str, s0: float, s1: float, c: dict, W: int, H: int) -> list[str]:
    """c: scale, x, y (offset of the card centre, fractions of the frame), ry, rx (degrees), ry1 (drift
    target), radius (px at full size), inn / out (seconds). The card unfolds again at s1."""
    sc, x, y = c.get("scale", 0.5), c.get("x", 0.0) * W, c.get("y", 0.0) * H
    ry, rx, ry1 = c.get("ry", -10), c.get("rx", 4), c.get("ry1", c.get("ry", -10) * 0.4)
    rad = c.get("radius", 64) / sc
    inn, out = c.get("inn", 0.55), c.get("out", 0.45)
    full = f'scale: 1, x: 0, y: 0, rotationY: 0, rotationX: 0, borderRadius: 0, boxShadow: "0 0 0 0 rgba(0,0,0,0)"'
    card = (f'scale: {sc}, x: {x:.1f}, y: {y:.1f}, rotationY: {ry}, rotationX: {rx}, borderRadius: {rad:.0f}, '
            f'boxShadow: "0 60px 140px rgba(0,0,0,0.75), 0 0 0 {3 / sc:.0f}px rgba(255,255,255,0.14)"')
    hold = max(0.05, (s1 - out) - (s0 + inn))
    return [f'tl.fromTo("{sel}", {{ {full}, transformOrigin: "50% 50%", transformPerspective: {PERSP} }}, '
            f'{{ {card}, duration: {inn}, ease: "expo.inOut", immediateRender: false }}, {s0:.3f});',
            f'tl.to("{sel}", {{ rotationY: {ry1}, rotationX: {rx * 0.5:.1f}, duration: {hold:.3f}, ease: "sine.inOut" }}, {s0 + inn:.3f});',
            f'tl.to("{sel}", {{ {full}, duration: {out}, ease: "expo.inOut" }}, {s1 - out:.3f});',
            f'tl.set("{sel}", {{ scale: 1, x: 0, y: 0, rotationY: 0, rotationX: 0, borderRadius: 0 }}, {s1:.3f});']


def flip_js(t: float, d: str = "left") -> list[str]:
    sg = -1 if d == "left" else 1
    a = max(0.0, t - 0.15)
    return [f'tl.fromTo("#frame", {{ rotationY: 0, scale: 1, transformPerspective: {PERSP}, transformOrigin: "50% 50%" }}, '
            f'{{ rotationY: {sg * 88}, scale: 0.86, duration: {t - a:.3f}, ease: "power3.in", immediateRender: false }}, {a:.3f});',
            f'tl.fromTo("#frame", {{ rotationY: {-sg * 88}, scale: 0.86 }}, {{ rotationY: 0, scale: 1, duration: 0.34, ease: "expo.out", immediateRender: false }}, {t:.3f});']


# ---------------------------------------------------------------------------------------- the set
def _set(cx, cid: str, dur: float, accent: str, ink: str, seed: int = 7, glow=(50, 18)) -> tuple[str, str, str]:
    """Studio set: ink base, accent glow, perspective floor grid that travels, seeded dust drifting up."""
    W, H = cx.W, cx.H
    css = f"""#{cid}-bg {{ position: absolute; inset: 0; background: radial-gradient(ellipse 85% 48% at {glow[0]}% {glow[1]}%, {accent}55 0%, {accent}10 45%, {ink} 78%), {ink}; }}
#{cid}-floorw {{ position: absolute; left: -50%; width: 200%; top: {H * 0.58:.0f}px; height: {H * 0.9:.0f}px; perspective: 900px; perspective-origin: 50% 0%; }}
#{cid}-floor {{ position: absolute; inset: 0; transform: rotateX(72deg); transform-origin: 50% 0%;
  background-image: linear-gradient({accent}55 2px, transparent 2px), linear-gradient(90deg, {accent}40 2px, transparent 2px);
  background-size: 120px 120px; -webkit-mask-image: linear-gradient(180deg, transparent 0%, #000 30%, #000 70%, transparent 100%); mask-image: linear-gradient(180deg, transparent 0%, #000 30%, #000 70%, transparent 100%); }}
#{cid}-hz {{ position: absolute; left: 0; right: 0; top: {H * 0.58 - 2:.0f}px; height: 4px; background: linear-gradient(90deg, transparent, {accent}, transparent); opacity: 0.55; filter: blur(1px); }}
#{cid}-dust i {{ position: absolute; border-radius: 50%; background: #fff; }}"""
    import random
    rnd = random.Random(seed)
    dots, js = [], []
    for i in range(26):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(2, 5)
        o = rnd.uniform(0.08, 0.3)
        dots.append(f'<i id="{cid}-d{i}" style="left:{x:.0f}px;top:{y:.0f}px;width:{r:.1f}px;height:{r:.1f}px;opacity:{o:.2f}"></i>')
        js.append(f'tl.fromTo("#{cid}-d{i}", {{ y: 0, x: 0 }}, {{ y: {-rnd.uniform(60, 180):.0f}, x: {rnd.uniform(-30, 30):.0f}, duration: {dur:.3f}, ease: "none" }}, 0);')
    js.append(f'tl.fromTo("#{cid}-floor", {{ backgroundPosition: "0px 0px" }}, {{ backgroundPosition: "0px {120 * max(1, round(dur * 1.2))}px", duration: {dur:.3f}, ease: "none" }}, 0);')
    js.append(f'tl.fromTo("#{cid}-bg", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, ease: "power2.out" }}, 0);')
    body = (f'<div id="{cid}-bg"></div><div id="{cid}-floorw"><div id="{cid}-floor"></div></div><div id="{cid}-hz"></div>'
            f'<div id="{cid}-dust">{"".join(dots)}</div>')
    return css, body, "\n".join(js)


def sc_stage3d(cx, cid: str, h: int, dur: float, p: dict) -> str:
    """p: under, kicker {t}, claim {t, at, strikeAt, out, icon, y}, head {t, n, at, out, y},
    cards [{n, t, icon, at, y}], dimPrev (true). Frames are relative to the scene start."""
    from .hf_design import scene_file
    a, ink = cx.brand.get("accent", "#FF4438"), cx.brand.get("ink", "#0B0B0D")
    W = cx.W
    scss, sbody, sjs = _set(cx, cid, dur, a, ink)
    css = [scss, f"""#{cid}-k {{ position: absolute; left: 0; right: 0; top: 96px; text-align: center; font-family: {FONT_META}; font-weight: 700; font-size: 30px; letter-spacing: 0.22em; color: rgba(255,255,255,0.7); }}
#{cid}-k b {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: {a}; margin-right: 16px; vertical-align: 2px; box-shadow: 0 0 14px {a}; }}
.{cid}-3d {{ position: absolute; left: 0; right: 0; text-align: center; }}
.{cid}-claim {{ font-family: {FONT_TITLE}; font-size: 168px; color: #fff; line-height: 1; text-shadow: {extrude("#ffffff", 16)}; }}
.{cid}-strike {{ position: absolute; left: 12%; right: 12%; height: 26px; border-radius: 14px; background: {_tint(a, 0.45)}; box-shadow: 0 0 30px {_tint(a, 0.3)}, 0 10px 20px rgba(0,0,0,0.5); transform-origin: 0 50%; }}
.{cid}-hn {{ display: inline-block; font-family: {FONT_NUM}; font-size: 330px; line-height: 0.9; color: {a}; text-shadow: {extrude(a, 22)}; vertical-align: middle; margin-right: 26px; }}
.{cid}-ht {{ display: inline-block; font-family: {FONT_TITLE}; font-size: 124px; color: #fff; line-height: 1.05; text-shadow: {extrude("#ffffff", 12)}; vertical-align: middle; text-align: left; }}
.{cid}-card {{ position: absolute; left: 70px; width: {W - 140}px; height: 250px; border-radius: 34px;
  background: linear-gradient(135deg, rgba(255,255,255,0.13), rgba(255,255,255,0.04)); border: 2px solid rgba(255,255,255,0.16);
  box-shadow: 0 40px 80px rgba(0,0,0,0.55), inset 0 2px 0 rgba(255,255,255,0.18); overflow: visible; }}
.{cid}-card .ic {{ position: absolute; left: 18px; top: -40px; width: 300px; height: 300px; filter: drop-shadow(0 26px 30px rgba(0,0,0,0.6)); }}
.{cid}-card .n {{ position: absolute; left: 318px; top: 26px; font-family: {FONT_NUM}; font-size: 64px; color: {a}; letter-spacing: 0.04em; }}
.{cid}-card .t {{ position: absolute; left: 318px; right: 40px; top: 98px; font-family: {FONT_BODY}; font-weight: 800; font-size: 50px; white-space: nowrap; color: #fff; line-height: 1.08; }}
.{cid}-card .bar {{ position: absolute; left: 0; top: 30px; bottom: 30px; width: 10px; border-radius: 0 8px 8px 0; background: {a}; box-shadow: 0 0 20px {a}; }}"""]
    body, js = [sbody], [sjs]
    S = cx.s
    if p.get("kicker"):
        body.append(f'<div id="{cid}-k"><b></b>{_esc(p["kicker"]["t"])}</div>')
        js.append(f'tl.fromTo("#{cid}-k", {{ opacity: 0, y: -20 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, 0.15);')
    c = p.get("claim")
    if c:
        y = c.get("y", 0.2) * cx.H
        ic = f'<img src="{_icon(c["icon"])}" style="position:absolute;left:{W / 2 + 250:.0f}px;top:-150px;width:220px;height:220px;filter:drop-shadow(0 20px 26px rgba(0,0,0,0.6))" id="{cid}-ci">' if c.get("icon") else ""
        body.append(f'<div id="{cid}-cl" class="{cid}-3d" style="top:{y:.0f}px"><span class="{cid}-claim">{_esc(c["t"])}</span>'
                    f'<div id="{cid}-cs" class="{cid}-strike" style="top:76px"></div>{ic}</div>')
        at = S(c.get("at", 0))
        js.append(f'tl.fromTo("#{cid}-cl", {{ opacity: 0, rotationX: -80, y: 60, transformPerspective: 1200, transformOrigin: "50% 100%" }}, '
                  f'{{ opacity: 1, rotationX: 0, y: 0, duration: 0.55, ease: "back.out(1.4)" }}, {at + 0.1:.3f});')
        js.append(f'tl.fromTo("#{cid}-cs", {{ scaleX: 0 }}, {{ scaleX: 0, duration: 0.01 }}, 0);')
        if c.get("icon"):
            js.append(f'tl.fromTo("#{cid}-ci", {{ opacity: 0, scale: 0.3, rotationY: 160, transformPerspective: 900 }}, {{ opacity: 1, scale: 1, rotationY: 0, duration: 0.6, ease: "back.out(1.8)" }}, {at + 0.3:.3f});')
            js.append(f'tl.fromTo("#{cid}-ci", {{ y: 0, rotation: 0 }}, {{ y: -18, rotation: -6, duration: 1.6, ease: "sine.inOut", yoyo: true, repeat: 1, immediateRender: false }}, {at + 0.9:.3f});')
        if "strikeAt" in c:
            js.append(f'tl.to("#{cid}-cs", {{ scaleX: 1, duration: 0.22, ease: "power4.out" }}, {S(c["strikeAt"]):.3f});')
            js.append(f'tl.to("#{cid}-cl .{cid}-claim", {{ opacity: 0.45, duration: 0.2 }}, {S(c["strikeAt"]) + 0.05:.3f});')
        if "out" in c:
            js.append(f'tl.to("#{cid}-cl", {{ opacity: 0, z: -900, rotationX: 30, y: -120, duration: 0.4, ease: "power3.in", transformPerspective: 1200 }}, {S(c["out"]):.3f});')
    hd = p.get("head")
    if hd:
        y = hd.get("y", 0.2) * cx.H
        body.append(f'<div id="{cid}-hd" class="{cid}-3d" style="top:{y:.0f}px"><span id="{cid}-hn" class="{cid}-hn">{_esc(hd["n"])}</span>'
                    f'<span id="{cid}-ht" class="{cid}-ht">{_esc(hd["t"])}</span></div>')
        at = S(hd["at"])
        js.append(f'tl.fromTo("#{cid}-hd", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.01 }}, {at:.3f});')
        js.append(f'tl.fromTo("#{cid}-hn", {{ opacity: 0, rotationY: -120, scale: 0.4, transformPerspective: 1000 }}, {{ opacity: 1, rotationY: 0, scale: 1, duration: 0.6, ease: "back.out(1.6)" }}, {at:.3f});')
        js.append(f'tl.fromTo("#{cid}-ht", {{ opacity: 0, x: 80, rotationY: 40, transformPerspective: 1000 }}, {{ opacity: 1, x: 0, rotationY: 0, duration: 0.5, ease: "expo.out" }}, {at + 0.12:.3f});')
        if "out" in hd:
            js.append(f'tl.to("#{cid}-hd", {{ opacity: 0, scale: 0.7, y: -260, rotationX: 40, transformPerspective: 1200, duration: 0.4, ease: "power3.in" }}, {S(hd["out"]):.3f});')
    cards = p.get("cards", [])
    for i, cd in enumerate(cards):
        y = cd.get("y", 0.12 + i * 0.16) * cx.H
        ic = f'<img class="ic" src="{_icon(cd["icon"])}" id="{cid}-ci{i}">' if cd.get("icon") else ""
        body.append(f'<div id="{cid}-c{i}" class="{cid}-card" style="top:{y:.0f}px"><div class="bar"></div>{ic}'
                    f'<div class="n">{_esc(cd["n"])}</div><div class="t">{_esc(cd["t"])}</div></div>')
        at = S(cd["at"])
        js.append(f'tl.fromTo("#{cid}-c{i}", {{ opacity: 0, rotationY: -95, x: -200, transformPerspective: 1600, transformOrigin: "0% 50%" }}, '
                  f'{{ opacity: 1, rotationY: 0, x: 0, duration: 0.6, ease: "expo.out" }}, {at:.3f});')
        if cd.get("icon"):
            js.append(f'tl.fromTo("#{cid}-ci{i}", {{ scale: 0.2, rotationY: 200, rotation: -30, transformPerspective: 900 }}, {{ scale: 1, rotationY: 0, rotation: 0, duration: 0.7, ease: "back.out(1.7)" }}, {at + 0.12:.3f});')
            js.append(f'tl.fromTo("#{cid}-ci{i}", {{ y: 0 }}, {{ y: -16, duration: 1.4, ease: "sine.inOut", yoyo: true, repeat: 1, immediateRender: false }}, {at + 0.85:.3f});')
        if i and p.get("dimPrev", True):
            js.append(f'tl.to("#{cid}-c{i - 1}", {{ opacity: 0.42, scale: 0.95, duration: 0.35, ease: "power2.out" }}, {at:.3f});')
    js.append(f'tl.to("#{cid}-stage", {{ opacity: 0, duration: 0.25, ease: "power2.in" }}, {max(0, dur - 0.25):.3f});')
    return scene_file(cx, cid, cx.H, "\n".join(css), "".join(body), "\n".join(js))


def sc_podium3d(cx, cid: str, h: int, dur: float, p: dict) -> str:
    """p: under, kicker {t}, base (y fraction of the floor line), pillars [{t, rank, at, slot (0 left,
    1 centre, 2 right), h (px)}], hero (index into pillars), trophy {icon, at}."""
    from .hf_design import scene_file
    a, ink = cx.brand.get("accent", "#FF4438"), cx.brand.get("ink", "#0B0B0D")
    W, H, S = cx.W, cx.H, cx.s
    scss, sbody, sjs = _set(cx, cid, dur, a, ink, seed=19, glow=(50, 62))
    base = p.get("base", 0.94) * H
    pw = 300
    xs = [W * 0.2, W * 0.5, W * 0.8]
    css = [scss, f"""#{cid}-k {{ position: absolute; left: 0; right: 0; top: {H * 0.565:.0f}px; text-align: center; font-family: {FONT_META}; font-weight: 700; font-size: 28px; letter-spacing: 0.22em; color: rgba(255,255,255,0.7); }}
.{cid}-p {{ position: absolute; width: {pw}px; }}
.{cid}-p .fr {{ position: absolute; left: 0; right: 0; bottom: 0; border-radius: 6px 6px 0 0; background: linear-gradient(180deg, #2a2a30 0%, #141417 100%); border: 2px solid rgba(255,255,255,0.1); box-shadow: inset 0 2px 0 rgba(255,255,255,0.15), 0 30px 60px rgba(0,0,0,0.5); }}
.{cid}-p .tp {{ position: absolute; left: 0; right: 0; height: 34px; background: linear-gradient(180deg, #4a4a52, #2a2a30); clip-path: polygon(8% 0, 92% 0, 100% 100%, 0 100%); }}
.{cid}-p .rk {{ position: absolute; left: 0; right: 0; top: 34px; text-align: center; font-family: {FONT_NUM}; font-size: 150px; line-height: 1; color: rgba(255,255,255,0.9); text-shadow: {extrude("#bbbbbb", 8)}; }}
.{cid}-p .lb {{ position: absolute; left: -190px; right: -190px; text-align: center; font-family: {FONT_BODY}; font-weight: 800; font-size: 50px; line-height: 1.05; color: #fff; text-shadow: 0 6px 20px rgba(0,0,0,0.8); }}
.{cid}-p.hero .fr {{ background: linear-gradient(180deg, {a} 0%, {_shade(a, 0.45)} 100%); border-color: rgba(255,255,255,0.3); box-shadow: inset 0 2px 0 rgba(255,255,255,0.4), 0 0 80px {a}88, 0 30px 60px rgba(0,0,0,0.5); }}
.{cid}-p.hero .tp {{ background: linear-gradient(180deg, #ff8a7d, {a}); }}
.{cid}-p.hero .rk {{ color: #fff; text-shadow: {extrude(_shade(a, 0.9), 10)}; }}
#{cid}-beam {{ position: absolute; left: {xs[1] - 260:.0f}px; width: 520px; top: -200px; height: {base + 200:.0f}px; background: linear-gradient(180deg, rgba(255,255,255,0) 0%, {a}30 60%, {a}55 100%); clip-path: polygon(40% 0, 60% 0, 100% 100%, 0 100%); mix-blend-mode: screen; }}
#{cid}-tr {{ position: absolute; width: 300px; height: 300px; filter: drop-shadow(0 30px 30px rgba(0,0,0,0.6)) drop-shadow(0 0 40px {a}66); }}"""]
    body, js = [sbody], [sjs]
    if p.get("kicker"):
        body.append(f'<div id="{cid}-k">{_esc(p["kicker"]["t"])}</div>')
        js.append(f'tl.fromTo("#{cid}-k", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, 0.3);')
    hero = p.get("hero", 0)
    body.append(f'<div id="{cid}-beam"></div>')
    js.append(f'tl.fromTo("#{cid}-beam", {{ opacity: 0 }}, {{ opacity: 0, duration: 0.01 }}, 0);')
    for i, pl in enumerate(p["pillars"]):
        ph, x = pl["h"], xs[pl.get("slot", i)]
        cls = f"{cid}-p hero" if i == hero else f"{cid}-p"
        body.append(f'<div id="{cid}-p{i}" class="{cls}" style="left:{x - pw / 2:.0f}px;top:{base - ph:.0f}px;height:{ph}px">'
                    f'<div id="{cid}-pb{i}" style="position:absolute;inset:0"><div class="tp" style="top:-34px"></div><div class="fr" style="top:0"></div>'
                    f'<div class="rk">{_esc(str(pl["rank"]))}</div></div>'
                    f'<div id="{cid}-pl{i}" class="lb" style="bottom:{ph + 52}px">{_esc(pl["t"])}</div></div>')
        at = S(pl["at"])
        js.append(f'tl.fromTo("#{cid}-pb{i}", {{ scaleY: 0, transformOrigin: "50% 100%" }}, {{ scaleY: 1, duration: 0.65, ease: "expo.out" }}, {at:.3f});')
        js.append(f'tl.fromTo("#{cid}-pl{i}", {{ opacity: 0, y: {ph * 0.6:.0f}, rotationX: -70, transformPerspective: 900 }}, {{ opacity: 1, y: 0, rotationX: 0, duration: 0.55, ease: "back.out(1.5)" }}, {at + 0.1:.3f});')
        if i == hero:
            js.append(f'tl.to("#{cid}-beam", {{ opacity: 1, duration: 0.5, ease: "power2.out" }}, {at + 0.15:.3f});')
            for j in range(len(p["pillars"])):
                if j != i:
                    js.append(f'tl.to("#{cid}-p{j}", {{ opacity: 0.5, duration: 0.4 }}, {at + 0.2:.3f});')
    tr = p.get("trophy")
    if tr:
        pl = p["pillars"][hero]
        x, top = xs[pl.get("slot", hero)], base - pl["h"] - 52 - 62 - 300
        body.append(f'<img id="{cid}-tr" src="{_icon(tr["icon"])}" style="left:{x - 150:.0f}px;top:{top:.0f}px">')
        at = S(tr["at"])
        js.append(f'tl.fromTo("#{cid}-tr", {{ opacity: 0, y: -700, rotationY: 540, scale: 0.6, transformPerspective: 900 }}, '
                  f'{{ opacity: 1, y: 0, rotationY: 0, scale: 1, duration: 0.7, ease: "bounce.out" }}, {at:.3f});')
        js.append(f'tl.fromTo("#{cid}-tr", {{ rotationY: 0 }}, {{ rotationY: 24, duration: {max(0.3, dur - (at - 0) - 1.0):.3f}, ease: "sine.inOut", immediateRender: false }}, {at + 0.85:.3f});')
    js.append(f'tl.to("#{cid}-stage", {{ opacity: 0, duration: 0.25, ease: "power2.in" }}, {max(0, dur - 0.25):.3f});')
    return scene_file(cx, cid, cx.H, "\n".join(css), "".join(body), "\n".join(js))


def ov_title3d(cx, cid: str, dur: float, p: dict) -> str:
    """Extruded display type. items [{t, at, y, x (0-1, default 0.5), size, color, depth, font, enter
    ('rise'|'spin'), drift (deg)}], icons [{icon, at, x, y, size}]. Leaves forwards at the end."""
    from .hf_design import scene_file
    W, H, S = cx.W, cx.H, cx.s
    css, body, js = [f".{cid}-l {{ position: absolute; white-space: nowrap; line-height: 1; }}",
                     f".{cid}-i {{ position: absolute; filter: drop-shadow(0 26px 30px rgba(0,0,0,0.6)); }}"], [], []
    for i, it in enumerate(p.get("items", [])):
        col, size, depth = it.get("color", "#FFFFFF"), it.get("size", 160), it.get("depth", 18)
        x = it.get("x", 0.5) * W
        font = it.get("font", FONT_TITLE)
        body.append(f'<div id="{cid}-w{i}" class="{cid}-l" style="left:{x - 1500:.0f}px;width:3000px;text-align:center;top:{it["y"] * H - size * 0.55:.0f}px">'
                    f'<span id="{cid}-t{i}" style="display:inline-block;font-family:{font};font-size:{size}px;color:{col};text-shadow:{extrude(col, depth)}">{_esc(it["t"])}</span></div>')
        at = S(it.get("at", 0))
        if it.get("enter", "rise") == "spin":
            js.append(f'tl.fromTo("#{cid}-t{i}", {{ opacity: 0, rotationY: -180, scale: 0.3, transformPerspective: 1400 }}, {{ opacity: 1, rotationY: 0, scale: 1, duration: 0.7, ease: "back.out(1.5)" }}, {at:.3f});')
        else:
            js.append(f'tl.fromTo("#{cid}-t{i}", {{ opacity: 0, rotationX: -95, y: 80, transformPerspective: 1200, transformOrigin: "50% 100%" }}, {{ opacity: 1, rotationX: 0, y: 0, duration: 0.55, ease: "back.out(1.5)" }}, {at:.3f});')
        dr = it.get("drift", 8)
        js.append(f'tl.fromTo("#{cid}-w{i}", {{ rotationY: {-dr}, transformPerspective: 1600 }}, {{ rotationY: {dr}, duration: {max(0.1, dur):.3f}, ease: "sine.inOut" }}, 0);')
    for i, ic in enumerate(p.get("icons", [])):
        sz = ic.get("size", 260)
        body.append(f'<img id="{cid}-ic{i}" class="{cid}-i" src="{_icon(ic["icon"])}" style="left:{ic["x"] * W - sz / 2:.0f}px;top:{ic["y"] * H - sz / 2:.0f}px;width:{sz}px;height:{sz}px">')
        at = S(ic.get("at", 0))
        js.append(f'tl.fromTo("#{cid}-ic{i}", {{ opacity: 0, scale: 0.2, rotationY: 220, rotation: -40, transformPerspective: 900 }}, {{ opacity: 1, scale: 1, rotationY: 0, rotation: {ic.get("rot", -8)}, duration: 0.75, ease: "back.out(1.8)" }}, {at:.3f});')
        js.append(f'tl.fromTo("#{cid}-ic{i}", {{ y: 0 }}, {{ y: -22, duration: {max(0.2, dur - at - 0.8):.3f}, ease: "sine.inOut", immediateRender: false }}, {at + 0.75:.3f});')
    js.append(f'tl.to("#{cid}-stage", {{ opacity: 0, scale: 1.25, duration: 0.22, ease: "power2.in" }}, {max(0, dur - 0.22):.3f});')
    return scene_file(cx, cid, H, "\n".join(css), "".join(body), "\n".join(js), transparent=True)
