"""Colour-grading motion design for HyperFrames (2026-11-16): graphics that show the grade with the
clip's own data, the way a colourist's screen looks, instead of generic shapes.

- ov_hud: a camera-monitor HUD (corner brackets, REC, running timecode, picture profile, LUT state).
- ov_scopes: the real waveform or vectorscope of the footage, LOG beside GRADED. The scope videos are
  ffmpeg's own `waveform` / `vectorscope` of base_raw.mp4 and base.mp4, made by render.py.
- sc_lutcube: pixels sampled from the shot plotted in a 3D RGB cube; they start where the log puts
  them (huddled in the middle) and fly to where the conversion and grade send them.
- raw wipe (in hf_design.root_file, bg color "raw"): the untouched log footage wiped against the
  graded picture by a glowing line with labels.

All motion is a function of timeline time (GSAP on a paused timeline, no randomness)."""
from __future__ import annotations

FONT_UI = "'Space Grotesk', 'Montserrat', sans-serif"
FONT_MONO = "'JetBrains Mono', 'Space Grotesk', monospace"
SOFT = "0 18px 40px rgba(0,0,0,0.2)"          # soft ~20 % shadow, the AE drop-shadow default people pull back to


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb[:3])


# ---------------------------------------------------------------- HUD
def ov_hud(cx, cid: str, dur: float, p: dict) -> str:
    """p: {tc0 (s), profile0, profile1, lut0, lut1, switchAt (frames, optional), inset (px)}."""
    from .hf_design import scene_file
    W, H, a = cx.W, cx.H, cx.brand.get("accent", "#FF9A2E")
    ins, arm, th = p.get("inset", 54), 92, 5
    top, bot = p.get("top", 196), p.get("bottom", 1330)
    br = []
    for k, (x, y, sx, sy) in enumerate(((ins, ins, 1, 1), (W - ins, ins, -1, 1), (ins, H - ins, 1, -1), (W - ins, H - ins, -1, -1))):
        br.append(f'<path class="br" d="M{x} {y + sy * arm} L{x} {y} L{x + sx * arm} {y}" />')
    css = f"""
#{cid}-svg {{ position:absolute; inset:0; }}
#{cid}-svg .br {{ fill:none; stroke:rgba(255,255,255,0.92); stroke-width:{th}; stroke-linecap:square; filter: drop-shadow(0 2px 6px rgba(0,0,0,0.35)); }}
#{cid}-svg .cr {{ stroke:rgba(255,255,255,0.45); stroke-width:2; }}
.{cid}-t {{ position:absolute; font-family:{FONT_MONO}; font-weight:500; font-size:34px; letter-spacing:0.06em; color:#fff;
  text-shadow: 0 2px 10px rgba(0,0,0,0.45); white-space:nowrap; }}
#{cid}-rec {{ left:{ins + 30}px; top:{top}px; }}
#{cid}-dot {{ display:inline-block; width:22px; height:22px; border-radius:50%; background:#FF3B30; margin-right:14px; vertical-align:-2px;
  box-shadow:0 0 18px rgba(255,59,48,0.8); }}
#{cid}-tc {{ right:{ins + 30}px; top:{top}px; }}
#{cid}-prof {{ left:{ins + 30}px; top:{bot}px; padding:8px 18px; border:3px solid rgba(255,255,255,0.9); border-radius:10px; }}
#{cid}-prof1 {{ left:{ins + 30}px; top:{bot}px; padding:8px 18px; border:3px solid {a}; background:{a}; color:#0B1220; border-radius:10px;
  text-shadow:none; opacity:0; }}
#{cid}-lut {{ right:{ins + 30}px; top:{bot + 11}px; }}
#{cid}-lut b {{ color:{a}; font-weight:700; }}
"""
    body = (f'<svg id="{cid}-svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{"".join(br)}'
            f'<line class="cr" x1="{W / 2 - 26}" y1="{H / 2}" x2="{W / 2 + 26}" y2="{H / 2}"/>'
            f'<line class="cr" x1="{W / 2}" y1="{H / 2 - 26}" x2="{W / 2}" y2="{H / 2 + 26}"/></svg>'
            f'<div id="{cid}-rec" class="{cid}-t"><span id="{cid}-dot"></span>REC</div>'
            f'<div id="{cid}-tc" class="{cid}-t">00:00:00:00</div>'
            f'<div id="{cid}-prof" class="{cid}-t">{p.get("profile0", "LOG")}</div>'
            f'<div id="{cid}-prof1" class="{cid}-t">{p.get("profile1", "REC.709")}</div>'
            f'<div id="{cid}-lut" class="{cid}-t">LUT <span id="{cid}-lv0">{p.get("lut0", "OFF")}</span>'
            f'<b id="{cid}-lv1" style="position:absolute;right:0;opacity:0">{p.get("lut1", "ON")}</b></div>')
    fps, tc0 = cx.fps, float(p.get("tc0", 0))
    js = [f'tl.from("#{cid}-svg .br", {{ opacity: 0, scale: 1.12, transformOrigin: "50% 50%", duration: 0.45, ease: "expo.out", stagger: 0.04 }}, 0);',
          f'tl.from(".{cid}-t", {{ opacity: 0, y: 14, duration: 0.35, ease: "power3.out", stagger: 0.05 }}, 0.1);',
          f'const tcEl = document.querySelector("#{cid}-tc"); const tco = {{ v: {tc0 * fps:.0f} }};',
          f'const pad = (x) => String(Math.floor(x)).padStart(2, "0");',
          f'tl.fromTo(tco, {{ v: {tc0 * fps:.0f} }}, {{ v: {(tc0 + dur) * fps:.0f}, duration: {dur:.3f}, ease: "none", onUpdate: () => {{ '
          f'const f = Math.floor(tco.v); tcEl.textContent = pad(f / {fps * 3600:.0f}) + ":" + pad(f / {fps * 60:.0f} % 60) + ":" + pad(f / {fps:.0f} % 60) + ":" + pad(f % {fps:.0f}); }} }}, 0);']
    t, k = 0.0, 0
    while t < dur:                                                      # REC dot blinks at 1 Hz
        js.append(f'tl.set("#{cid}-dot", {{ opacity: {0.15 if k % 2 else 1} }}, {t:.3f});')
        t, k = t + 0.5, k + 1
    for hs, he in p.get("hide_bottom", []):                            # make room for captions under a panel
        js.append(f'tl.to("#{cid}-prof, #{cid}-prof1, #{cid}-lut", {{ autoAlpha: 0, duration: 0.15 }}, {cx.s(hs):.3f});')
        back = f"#{cid}-prof1" if p.get("switchAt") is not None and he > p["switchAt"] else f"#{cid}-prof"
        js.append(f'tl.to("{back}, #{cid}-lut", {{ autoAlpha: 1, duration: 0.2 }}, {cx.s(he):.3f});')
    if p.get("switchAt") is not None:
        s = cx.s(p["switchAt"])
        js += [f'tl.to("#{cid}-prof", {{ opacity: 0, scaleX: 0.2, duration: 0.12, ease: "power2.in" }}, {s:.3f});',
               f'tl.fromTo("#{cid}-prof1", {{ autoAlpha: 0, scaleX: 0.2 }}, {{ autoAlpha: 1, scaleX: 1, duration: 0.3, ease: "back.out(2.2)" }}, {s + 0.1:.3f});',
               f'tl.set("#{cid}-lv0", {{ opacity: 0 }}, {s + 0.1:.3f});',
               f'tl.set("#{cid}-lv1", {{ opacity: 1 }}, {s + 0.1:.3f});',
               f'tl.fromTo("#{cid}-lut", {{ scale: 1.35 }}, {{ scale: 1, duration: 0.35, ease: "back.out(2.5)" }}, {s + 0.1:.3f});']
    return scene_file(cx, cid, H, css, body, "\n".join(js))


# ---------------------------------------------------------------- scopes
SCOPE_ASSETS = {"wave": ("scope_wave_raw.mp4", "scope_wave.mp4"), "vector": ("scope_vec_raw.mp4", "scope_vec.mp4")}


def ov_scopes(cx, cid: str, dur: float, p: dict) -> str:
    """p: {kind: wave|vector, t0 (s, the overlay's start on the timeline), y (0-1 panel top), title,
    labels [left, right], sub}. Two live scope videos side by side in a dark glass panel."""
    from .hf_design import scene_file
    W, H, a = cx.W, cx.H, cx.brand.get("accent", "#FF9A2E")
    kind = p.get("kind", "wave")
    raw, graded = SCOPE_ASSETS[kind]
    pw, gap = 960, 24
    cw = (pw - 3 * gap) // 2
    ch = int(cw * 0.56)                       # vectorscope is cropped to its centre, where the colour lives
    ph = ch + 150
    left, top = (W - pw) // 2, int(p.get("y", 0.12) * H)
    t0 = float(p.get("t0", 0))
    lab = p.get("labels", ["LOG", "GRADED"])
    grat = ""
    if kind == "wave":
        for q in (0, 0.25, 0.5, 0.75, 1.0):
            y = 8 + (ch - 16) * (1 - q)
            grat += f'<line x1="0" y1="{y:.0f}" x2="{cw}" y2="{y:.0f}"/><text x="6" y="{y - 6:.0f}">{int(q * 100)}</text>'
    else:
        c = cw / 2
        cy_ = ch / 2
        for r in (0.18, 0.34, 0.48):
            grat += f'<circle cx="{c}" cy="{cy_}" r="{cw * r:.0f}"/>'
        grat += f'<line x1="{c}" y1="0" x2="{c}" y2="{ch}"/><line x1="8" y1="{cy_}" x2="{cw - 8}" y2="{cy_}"/>'
    cells = ""
    for i, (src, lb) in enumerate(((raw, lab[0]), (graded, lab[1]))):
        x = gap + i * (cw + gap)
        cells += (f'<div class="{cid}-cell" id="{cid}-c{i}" style="left:{x}px;top:96px;width:{cw}px;height:{ch}px">'
                  f'<video id="{cid}-v{i}" class="clip" data-start="0" data-duration="{dur:.4f}" data-media-start="{t0:.4f}" data-track-index="{i + 1}" '
                  f'src="assets/{src}" muted playsinline style="position:absolute;inset:0;width:100%;height:100%;object-fit:{'fill' if kind == 'wave' else 'cover'}"></video>'
                  f'<svg class="{cid}-g" width="{cw}" height="{ch}" viewBox="0 0 {cw} {ch}">{grat}</svg>'
                  f'<div class="{cid}-lab {"hot" if i else ""}">{lb}</div></div>')
    css = f"""
#{cid}-panel {{ position:absolute; left:{left}px; top:{top}px; width:{pw}px; height:{ph}px; border-radius:28px;
  background:linear-gradient(160deg, rgba(14,20,34,0.86), rgba(6,9,16,0.9)); border:1.5px solid rgba(255,255,255,0.14);
  box-shadow:{SOFT}, inset 0 1px 0 rgba(255,255,255,0.12); overflow:hidden; }}
#{cid}-title {{ position:absolute; left:{gap + 6}px; top:28px; font-family:{FONT_UI}; font-weight:700; font-size:40px; color:#fff; letter-spacing:0.01em; }}
#{cid}-sub {{ position:absolute; right:{gap + 6}px; top:38px; font-family:{FONT_MONO}; font-size:26px; color:rgba(255,255,255,0.55); }}
.{cid}-cell {{ position:absolute; border-radius:14px; overflow:hidden; background:#000; border:1px solid rgba(255,255,255,0.1); }}
.{cid}-g {{ position:absolute; inset:0; }}
.{cid}-g line, .{cid}-g circle {{ stroke:rgba(255,255,255,0.18); stroke-width:1.5; fill:none; }}
.{cid}-g text {{ fill:rgba(255,255,255,0.45); font-family:{FONT_MONO}; font-size:18px; }}
.{cid}-lab {{ position:absolute; left:14px; bottom:12px; font-family:{FONT_MONO}; font-weight:700; font-size:26px; color:#fff;
  padding:4px 12px; border-radius:8px; background:rgba(0,0,0,0.55); }}
.{cid}-lab.hot {{ background:{a}; color:#0B1220; }}
"""
    body = (f'<div id="{cid}-panel"><div id="{cid}-title">{p.get("title", "Waveform" if kind == "wave" else "Vectorscope")}</div>'
            f'<div id="{cid}-sub">{p.get("sub", "")}</div>{cells}</div>')
    js = [f'tl.fromTo("#{cid}-panel", {{ opacity: 0, y: 70, scale: 0.94, filter: "blur(12px)" }}, '
          f'{{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)", duration: 0.55, ease: "expo.out" }}, 0);',
          f'tl.from(".{cid}-cell", {{ opacity: 0, y: 30, duration: 0.45, ease: "power3.out", stagger: 0.12 }}, 0.15);',
          f'tl.from(".{cid}-lab", {{ opacity: 0, x: -16, duration: 0.3, ease: "back.out(2)", stagger: 0.12 }}, 0.45);',
          f'tl.to("#{cid}-panel", {{ opacity: 0, y: -40, scale: 0.97, filter: "blur(10px)", duration: 0.3, ease: "power2.in" }}, {max(0.0, dur - 0.32):.3f});']
    return scene_file(cx, cid, H, css, body, "\n".join(js))


# ---------------------------------------------------------------- LUT cube
def sc_lutcube(cx, cid: str, h: int, dur: float, p: dict) -> str:
    """p: {points: [[r,g,b, R,G,B], ...] 0-1 (log value, graded value of the same pixel), at (frames: the
    pixels fly), kicker, title, sub, count_label, rot (degrees of slow turn)}."""
    from .hf_design import scene_file
    W, a = cx.W, cx.brand.get("accent", "#FF9A2E")
    S = int(p.get("size", 560))
    cy = int(h * p.get("cube_y", 0.56))
    pts = p["points"]
    dots = "".join(f'<i class="{cid}-d" id="{cid}-d{i}" style="background:{_hex(q[:3])}"></i>' for i, q in enumerate(pts))
    half = S / 2
    edges = []
    for ax in range(3):                       # 12 edges: 4 parallel to each axis
        for u in (-half, half):
            for v in (-half, half):
                if ax == 0:
                    tr = f"translate3d(-50%,0,0) translate3d(0,{u}px,{v}px)"
                    st = f"width:{S}px;height:2px"
                elif ax == 1:
                    tr = f"translate3d(0,-50%,0) translate3d({u}px,0,{v}px)"
                    st = f"width:2px;height:{S}px"
                else:
                    tr = f"translate3d(-50%,0,0) translate3d({u}px,{v}px,0) rotateY(90deg)"
                    st = f"width:{S}px;height:2px"
                edges.append(f'<b class="{cid}-e" style="{st};transform:{tr}"></b>')
    css = f"""
#{cid}-stage {{ background: radial-gradient(120% 80% at 50% 58%, #1A2540 0%, #0B1220 55%, #05070C 100%); }}
#{cid}-k {{ position:absolute; left:0; right:0; top:{int(h * 0.12)}px; text-align:center; font-family:{FONT_MONO}; font-size:30px;
  letter-spacing:0.3em; color:{a}; }}
#{cid}-t {{ position:absolute; left:0; right:0; top:{int(h * 0.12) + 50}px; text-align:center; font-family:{FONT_UI}; font-weight:700;
  font-size:118px; line-height:1; color:#fff; letter-spacing:-0.02em; }}
#{cid}-s {{ position:absolute; left:0; right:0; top:{int(h * 0.12) + 190}px; text-align:center; font-family:{FONT_MONO}; font-size:34px;
  color:rgba(255,255,255,0.7); }}
#{cid}-s b {{ color:{a}; }}
#{cid}-persp {{ position:absolute; left:{W // 2}px; top:{cy}px; width:0; height:0; perspective:1900px; }}
#{cid}-cube {{ position:absolute; left:0; top:0; width:0; height:0; transform-style:preserve-3d; }}
.{cid}-e {{ position:absolute; left:0; top:0; background:rgba(255,255,255,0.22); }}
.{cid}-d {{ position:absolute; left:-11px; top:-11px; width:22px; height:22px; border-radius:50%; }}
#{cid}-n {{ position:absolute; left:0; right:0; top:{min(h - 200, cy + int(S * 0.78))}px; text-align:center; font-family:{FONT_MONO};
  font-size:28px; color:rgba(255,255,255,0.6); }}
"""
    body = (f'<div id="{cid}-k">{p.get("kicker", "")}</div><div id="{cid}-t">{p.get("title", "")}</div>'
            f'<div id="{cid}-s">{p.get("sub", "")}</div>'
            f'<div id="{cid}-persp"><div id="{cid}-cube">{"".join(edges)}{dots}</div></div>'
            f'<div id="{cid}-n">{p.get("count_label", "")}</div>')
    at = cx.s(p.get("at", 30))
    rot = float(p.get("rot", 50))
    js = [f'tl.set("#{cid}-cube", {{ rotationX: -24, rotationY: -28 }}, 0);',
          f'tl.to("#{cid}-cube", {{ rotationY: {-28 + rot}, duration: {dur:.3f}, ease: "none" }}, 0);',
          f'tl.from("#{cid}-k, #{cid}-t, #{cid}-s", {{ opacity: 0, y: 40, filter: "blur(10px)", duration: 0.5, ease: "expo.out", stagger: 0.08 }}, 0);',
          f'tl.from(".{cid}-e", {{ opacity: 0, duration: 0.5, ease: "power2.out" }}, 0.1);',
          f'tl.from("#{cid}-n", {{ opacity: 0, duration: 0.4 }}, 0.4);']
    for i, q in enumerate(pts):
        x0, y0, z0 = (q[0] - 0.5) * S, (0.5 - q[1]) * S, (q[2] - 0.5) * S
        x1, y1, z1 = (q[3] - 0.5) * S, (0.5 - q[4]) * S, (q[5] - 0.5) * S
        js.append(f'tl.set("#{cid}-d{i}", {{ x: {x0:.1f}, y: {y0:.1f}, z: {z0:.1f}, scale: 0 }}, 0);')
        js.append(f'tl.to("#{cid}-d{i}", {{ scale: 1, duration: 0.3, ease: "back.out(2)" }}, {0.15 + (i % 40) * 0.008:.3f});')
        js.append(f'tl.to("#{cid}-d{i}", {{ x: {x1:.1f}, y: {y1:.1f}, z: {z1:.1f}, backgroundColor: "{_hex(q[3:6])}", '
                  f'duration: 0.9, ease: "expo.inOut" }}, {at + (i % 30) * 0.01:.3f});')
    js.append(f'tl.to("#{cid}-stage", {{ opacity: 0, duration: 0.2 }}, {max(0.0, dur - 0.2):.3f});')
    return scene_file(cx, cid, h, css, body, "\n".join(js))


# ---------------------------------------------------------------- captions
def captions_cine(cx, caps: list[dict], ys: list[float], size: float) -> str:
    """Cinematic captions: a clean grotesk in sentence case, each word racks focus in (blur to sharp, a
    small rise); key words take the accent colour and a bar that wipes in under them. Quiet on
    purpose, so the scopes and the grade carry the motion."""
    from .hf_design import scene_file
    from .hf_ae import esc
    a = cx.brand.get("accent", "#FF9A2E")
    groups, js = [], []
    for gi, (g, y) in enumerate(zip(caps, ys)):
        longest = max(len(w["w"]) for w in g["words"])
        k = min(1.0, 900 / max(1.0, longest * 0.6 * size + 0.5 * size))
        spans = []
        for wi, w in enumerate(g["words"]):
            wid = f"cp{gi}w{wi}"
            t0 = max(0.0, cx.s(w["s"]) - 0.05)
            if w["emph"]:
                spans.append(f'<span id="{wid}" class="e">{esc(w["w"])}<i id="{wid}u"></i></span>')
                js.append(f'tl.fromTo("#{wid}u", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.32, ease: "expo.out" }}, {t0 + 0.08:.3f});')
            else:
                spans.append(f'<span id="{wid}" class="w">{esc(w["w"])}</span>')
            js.append(f'tl.fromTo("#{wid}", {{ opacity: 0, y: 18, filter: "blur(10px)" }}, '
                      f'{{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.24, ease: "power3.out" }}, {t0:.3f});')
        s_, e_ = cx.s(g["s"]), cx.s(g["e"])
        groups.append(f'<div id="cp{gi}" class="cg" style="top:{y * cx.H:.0f}px;font-size:{size * k:.1f}px"><div class="in">{" ".join(spans)}</div></div>')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "visible", opacity: 1 }}, {s_:.3f});')
        js.append(f'tl.to("#cp{gi}", {{ opacity: 0, filter: "blur(6px)", duration: 0.12, ease: "power2.in" }}, {max(s_, e_ - 0.12):.3f});')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "hidden" }}, {e_:.3f});')
    css = f"""#caps {{ position: absolute; inset: 0; }}
#caps .cg {{ position: absolute; left: 0; right: 0; transform: translateY(-50%); text-align: center; visibility: hidden; line-height: 1.12; padding: 0 70px; }}
#caps .in {{ display: inline-block; max-width: 920px; text-wrap: balance; }}
#caps .cg span {{ display: inline-block; position: relative; font-family: {FONT_UI}; font-weight: 700; letter-spacing: -0.025em; }}
#caps .w {{ color: #fff; text-shadow: 0 2px 2px rgba(0,0,0,0.35), 0 8px 30px rgba(0,0,0,0.6); }}
#caps .e {{ color: {a}; text-shadow: 0 2px 2px rgba(0,0,0,0.35), 0 8px 30px rgba(0,0,0,0.6); }}
#caps .e i {{ position: absolute; left: 0.02em; right: 0.02em; bottom: -0.04em; height: 0.09em; background: {a}; border-radius: 0.05em;
  transform-origin: 0 50%; box-shadow: 0 4px 14px rgba(0,0,0,0.4); }}"""
    return scene_file(cx, "captions", cx.H, css, f'<div id="caps">{"".join(groups)}</div>', "\n".join(js), transparent=True)
