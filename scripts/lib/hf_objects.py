"""3D objects, light sweeps and glint captions for HyperFrames (2026-11-19).

The owner rejected flat glass panels and plain caption plates as generic: a premium explainer is built
around real 3D objects with light on them. Objects are modelled and rendered in Blender (a project script,
e.g. work/amh3/objects3d.py: transparent film, 30 fps PNG sequence) and encoded to VP9 webm with alpha in
P/objects/; render.py copies them to assets/objects/.

Overlays:
  Object3D  a rendered object in a light pool with a contact shadow: arrives with depth (rise, fly, drop),
            floats one way, leaves through the lens (push), falls (drop) or cuts; optional label with a big
            gold number.
  Sweep     a light sweep over a cut: a soft glare band and two thin streaks cross the frame.
Captions: captions_glint, words flip up in 3D on their spoken frame; emphasis words in the title face in a
gold gradient crossed once by a specular glint, with a rule drawn under them.

objvid() is the clip markup, also used by hf_spec's scenes for 3D icons.
"""
from __future__ import annotations

from .hf_ae import esc
from .hf_design import Ctx, scene_file
from .hf_explainer import PERSP


def _c(cx: Ctx) -> dict:
    from .hf_spec import _c as spec_c
    return spec_c(cx)


def objvid(vid: str, name: str, start: float, dur: float, style: str, media_start: float = 0.0) -> str:
    """A rendered 3D object (assets/objects/<name>.webm, VP9 with alpha) as a timed clip inside a composition."""
    ms = f' data-media-start="{media_start:.3f}"' if media_start else ""
    return (f'<video id="{vid}" class="clip" data-start="{start:.3f}" data-duration="{max(0.05, dur):.3f}"{ms} data-track-index="1" '
            f'src="assets/objects/{name}.webm" muted playsinline style="{style}"></video>')


def ov_object3d(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{obj, x, y (centre 0-1), size (px), at, enter rise|fly|drop, exit push|drop|cut, from left|right,
    media_start (s into the clip), glow, label {big, t, sub, side below|right|left, at, size}}."""
    C = _c(cx)
    size = p.get("size", 520)
    x, y, at = p.get("x", 0.5) * cx.W, p.get("y", 0.55) * cx.H, cx.s(p.get("at", 0))
    sg = -1 if p.get("from", "right") == "left" else 1
    lab = p.get("label")
    lab_html = ""
    if lab:
        side = lab.get("side", "below")
        pos = {"right": f"left:{size * 0.42:.0f}px;top:{-90}px;text-align:left",
               "left": f"right:{size * 0.42:.0f}px;top:{-90}px;text-align:right",
               "below": f"left:-450px;width:900px;top:{size * 0.4:.0f}px;text-align:center"}[side]
        big = ""
        if lab.get("big"):
            big = (f'<div style="font:700 {lab.get("size", 150)}px/0.95 {C["title"]};color:transparent;'
                   f'background:linear-gradient(180deg,#fff6dc 10%,{C["gold"]} 55%,#9a6b1f 100%);-webkit-background-clip:text;background-clip:text;'
                   f'filter:drop-shadow(0 10px 30px rgba(0,0,0,0.5))">{esc(lab["big"])}</div>')
        lab_html = (f'<div id="{cid}-lab" style="position:absolute;{pos};white-space:nowrap">{big}'
                    f'<div style="font:700 58px/1.1 {C["title"]};color:#fff;text-shadow:0 6px 24px rgba(0,0,0,0.6)">{esc(lab.get("t", ""))}</div>'
                    f'<div style="margin-top:10px;font:500 22px/1 {C["meta"]};letter-spacing:0.34em;color:{C["mint"]}">{esc(lab.get("sub", ""))}</div></div>')
    vid = objvid(f"{cid}-v", p["obj"], 0, dur, f"position:absolute;left:{-size / 2:.0f}px;top:{-size / 2:.0f}px;width:{size}px;height:{size}px",
                 p.get("media_start", 0.0))
    glow = p.get("glow", C["gold"])
    body = (f'<div id="{cid}-all" style="position:absolute;left:{x:.0f}px;top:{y:.0f}px;width:0;height:0">'
            f'<div id="{cid}-pool" style="position:absolute;left:{-size * 0.6:.0f}px;top:{-size * 0.6:.0f}px;width:{size * 1.2:.0f}px;height:{size * 1.2:.0f}px;border-radius:50%;'
            f'background:radial-gradient(circle, {glow}55 0%, {glow}1a 38%, transparent 68%);filter:blur(10px)"></div>'
            f'<div id="{cid}-sh" style="position:absolute;left:{-size * 0.3:.0f}px;top:{size * 0.36:.0f}px;width:{size * 0.6:.0f}px;height:{size * 0.09:.0f}px;border-radius:50%;'
            f'background:radial-gradient(ellipse, rgba(0,0,0,0.55) 0%, transparent 70%);filter:blur(6px)"></div>'
            f'<div id="{cid}-o" style="position:absolute;left:0;top:0;width:0;height:0">{vid}</div>{lab_html}</div>')
    enter = p.get("enter", "rise")
    js = []
    if enter == "fly":
        js.append(f'tl.fromTo("#{cid}-o", {{ x: {sg * 620}, y: -120, scale: 0.35, rotationY: {sg * -70}, filter: "blur(14px)", transformPerspective: {PERSP} }}, '
                  f'{{ x: 0, y: 0, scale: 1, rotationY: 0, filter: "blur(0px)", duration: 0.75, ease: "expo.out" }}, {at:.3f});')
    elif enter == "drop":
        js.append(f'tl.fromTo("#{cid}-o", {{ y: -900, filter: "blur(10px)" }}, {{ y: 0, filter: "blur(0px)", duration: 0.5, ease: "power4.in" }}, {at:.3f});')
        js.append(f'tl.fromTo("#{cid}-o", {{ scaleY: 1 }}, {{ scaleY: 0.94, duration: 0.07, ease: "power2.out" }}, {at + 0.5:.3f});')
        js.append(f'tl.to("#{cid}-o", {{ scaleY: 1, duration: 0.3, ease: "expo.out" }}, {at + 0.57:.3f});')
    elif enter == "rise":
        js.append(f'tl.fromTo("#{cid}-o", {{ y: 220, scale: 0.55, rotationX: 50, filter: "blur(16px)", opacity: 0, transformPerspective: {PERSP} }}, '
                  f'{{ y: 0, scale: 1, rotationX: 0, filter: "blur(0px)", opacity: 1, duration: 0.8, ease: "expo.out" }}, {at:.3f});')
    else:
        raise ValueError(f"enter must be rise, fly or drop, not {enter!r}")
    js += [f'tl.fromTo("#{cid}-pool", {{ opacity: 0, scale: 0.6 }}, {{ opacity: 1, scale: 1, duration: 0.7, ease: "expo.out" }}, {at + 0.1:.3f});',
           f'tl.fromTo("#{cid}-sh", {{ opacity: 0, scaleX: 0.4 }}, {{ opacity: 1, scaleX: 1, duration: 0.6, ease: "expo.out" }}, {at + 0.2:.3f});',
           f'tl.fromTo("#{cid}-all", {{ y: 0 }}, {{ y: -30, duration: {max(0.2, dur - at):.3f}, ease: "sine.inOut" }}, {at:.3f});']
    if lab:
        a2 = cx.s(lab.get("at", p.get("at", 0) + 10))
        js.append(f'tl.fromTo("#{cid}-lab", {{ opacity: 0, y: 40, filter: "blur(8px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.55, ease: "expo.out" }}, {a2:.3f});')
    ex = p.get("exit", "push")
    if ex == "push":
        js.append(f'tl.to("#{cid}-all", {{ scale: 1.9, opacity: 0, filter: "blur(18px)", duration: 0.32, ease: "power2.in" }}, {max(0, dur - 0.32):.3f});')
    elif ex == "drop":
        js.append(f'tl.to("#{cid}-all", {{ y: 900, rotation: {sg * 18}, duration: 0.45, ease: "power3.in" }}, {max(0, dur - 0.45):.3f});')
    elif ex != "cut":
        raise ValueError(f"exit must be push, drop or cut, not {ex!r}")
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


def ov_sweep(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{angle}: a soft glare band and two thin streaks cross the frame in `dur` seconds. The bands keep a
    static CSS rotate; GSAP moves their wrappers."""
    C = _c(cx)
    W, H = cx.W, cx.H
    a = p.get("angle", -24)
    band = (f"left:{-W * 0.6:.0f}px;top:{-H * 0.3:.0f}px;width:{W * 0.55:.0f}px;height:{H * 1.6:.0f}px;transform:rotate({a}deg);"
            f"background:linear-gradient(90deg, transparent 10%, rgba(255,248,225,0.55) 50%, transparent 90%);filter:blur(18px)")
    s1 = f"left:{-W * 0.3:.0f}px;top:{-H * 0.3:.0f}px;width:6px;height:{H * 1.6:.0f}px;transform:rotate({a}deg);background:{C['mint']};box-shadow:0 0 24px {C['mint']}"
    s2 = f"left:{-W * 0.45:.0f}px;top:{-H * 0.3:.0f}px;width:3px;height:{H * 1.6:.0f}px;transform:rotate({a}deg);background:#fff;box-shadow:0 0 18px #fff"
    body = "".join(f'<div id="{cid}-w{i}" style="position:absolute;inset:0;mix-blend-mode:screen"><div style="position:absolute;{st}"></div></div>'
                   for i, st in enumerate((band, s1, s2)))
    js = [f'tl.fromTo("#{cid}-w{i}", {{ x: 0 }}, {{ x: {W * k:.0f}, duration: {dur * f:.3f}, ease: "power3.inOut" }}, {d:.3f});'
          for i, (k, f, d) in enumerate(((2.2, 1.0, 0.0), (2.0, 0.9, 0.02), (2.1, 0.95, 0.05)))]
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


def captions_glint(cx: Ctx, caps: list[dict], ys: list[float], size: float, font: str | None = None, font_emph: str | None = None) -> str:
    C = _c(cx)
    f1, f2 = font or C["body"], font_emph or C["title"]
    groups, js = [], []
    for gi, (g, y) in enumerate(zip(caps, ys)):
        s_, e_ = cx.s(g["s"]), cx.s(g["e"])
        if gi + 1 < len(caps):
            e_ = min(e_, cx.s(caps[gi + 1]["s"]))
        spans = []
        for wi, w in enumerate(g["words"]):
            if w["emph"]:
                spans.append(f'<span class="gw ge" id="cg{gi}w{wi}"><b id="cg{gi}b{wi}">{esc(w["w"])}</b><i id="cg{gi}u{wi}"></i></span>')
            else:
                spans.append(f'<span class="gw" id="cg{gi}w{wi}">{esc(w["w"])}</span>')
        groups.append(f'<div id="cg{gi}" class="cg" style="top:{y * cx.H:.0f}px">{" ".join(spans)}</div>')
        js.append(f'tl.set("#cg{gi}", {{ visibility: "visible" }}, {s_:.3f});')
        ws = g["words"]
        for wi, w in enumerate(ws):
            t0 = max(s_, cx.s(w["s"]) - 1 / cx.fps)
            js.append(f'tl.fromTo("#cg{gi}w{wi}", {{ opacity: 0, rotationX: -85, yPercent: 40, transformPerspective: 900, transformOrigin: "50% 100%" }}, '
                      f'{{ opacity: 1, rotationX: 0, yPercent: 0, duration: 0.42, ease: "expo.out" }}, {t0:.3f});')
            if wi + 1 < len(ws):
                js.append(f'tl.to("#cg{gi}w{wi}", {{ opacity: 0.72, duration: 0.25 }}, {max(t0 + 0.42, cx.s(ws[wi + 1]["s"]) - 1 / cx.fps):.3f});')
            if w["emph"]:
                js.append(f'tl.fromTo("#cg{gi}b{wi}", {{ backgroundPosition: "160% 0%" }}, {{ backgroundPosition: "-60% 0%", duration: 0.9, ease: "power2.inOut" }}, {t0 + 0.15:.3f});')
                js.append(f'tl.fromTo("#cg{gi}u{wi}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.45, ease: "expo.out" }}, {t0 + 0.12:.3f});')
        js.append(f'tl.set("#cg{gi}", {{ visibility: "hidden" }}, {e_:.3f});')
    css = f"""#capg {{ position: absolute; inset: 0; }}
#capg .cg {{ position: absolute; left: 60px; right: 60px; transform: translateY(-50%); text-align: center; visibility: hidden; line-height: 1.3; text-wrap: balance; }}
#capg .gw {{ position: relative; display: inline-block; margin: 0 0.1em; font-family: {f1}; font-weight: 700; font-size: {size}px; color: #fff; font-synthesis: none;
  text-shadow: 0 2px 3px rgba(0,0,0,0.55), 0 10px 34px rgba(0,0,0,0.6); }}
#capg .ge b {{ font-family: {f2}; font-weight: 700; font-size: {size * 1.22:.0f}px; color: transparent; text-shadow: none;
  background: linear-gradient(100deg, #f7d58a 0%, {C['gold']} 35%, #fffaf0 48%, {C['gold']} 60%, #b07d2a 100%); background-size: 250% 100%; background-position: 160% 0%;
  -webkit-background-clip: text; background-clip: text; filter: drop-shadow(0 6px 18px rgba(0,0,0,0.55)) drop-shadow(0 0 20px rgba(232,194,104,0.35)); }}
#capg .ge i {{ position: absolute; left: 4%; right: 4%; bottom: 0.02em; height: 5px; border-radius: 3px; background: linear-gradient(90deg, transparent, {C['gold']}, transparent); }}"""
    return scene_file(cx, "captions", cx.H, css, f'<div id="capg">{"".join(groups)}</div>', "\n".join(js), transparent=True)


OVERLAYS = {"Object3D": ov_object3d, "Sweep": ov_sweep}
