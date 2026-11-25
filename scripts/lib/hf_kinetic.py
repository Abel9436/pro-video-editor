"""Kinetic-collage creator grammar (2026-11-25), from a 30 fps frame study of one reference Short the owner asked
to match closely (work/gvqo/ref: deep_watch sheets plus detail strips z_a..z_i, 871 frames, 75 visual events,
90 sound hits in 29 s). Most of that reference is motion graphics, with the face on screen about a quarter of
the time. Every number marked STARTING DEFAULT is a reading of those sheets, not a measured optimum.

What the reference does (frame counts at 30 fps):
  - the speaker's silhouette is filled with one flat accent colour (4 frames), with "???" on the head and white
    doodle strokes; then the silhouette turns white with a soft glow (3 frames), then a hard cut to the picture;
  - words build up and stay on screen in a loose stack: a lowercase geometric sans in white, a heavy condensed
    word in the accent, a grey script word; some words run vertically. Each word arrives in 3-4 frames
    (scale 1.3 -> 1 through blur); a stack clears all at once on the cut;
  - frame card: the picture shrinks into a rounded landscape card on black in ~6 frames, with a warm glow under
    it, and a curled printed sticker flies in over it (rendered in Blender);
  - full-screen accent paper: a white lowercase word, a big accent number behind it, then the paper tears
    open across the middle (white fibre edge) and real money shows through; a heavy condensed word lands;
  - collage: crops of the speaker's own face (eyes, mouth) as tiles on a flat ground, words between them;
  - real B-roll with a 3D extruded word standing on the keyboard (Blender);
  - words on a ring that turns around the speaker (the back half goes behind him);
  - a neon outline word behind the speaker while the room darkens to black;
  - outro: a white dot bounces on black, the logo builds with a glitch, the handle and the call to action.

Overlays (times are frames relative to the overlay's start unless named *_s; `t0` is the overlay's start on the
film in seconds, filled in by the EDL builder, so the footage inside a card stays in sync):
  Silhouette {t0, color, color_f 4, white_f 3, glyph, head: [x, y], strokes: [x, y]}
  KStack     {words: [{t, at, x, y, size, style sans|heavy|script|eth|ethheavy|bar|box, color, rot, align, mark}], out}
  FrameCard  {t0, w, h, y, at, scale, glow, obj, obj_at, words}
  PaperTear  {paper, reveal, tint, tear_at, gap, words}
  Collage    {t0, ground, tiles: [{x, y, w, h, fx, fy, zoom, at, rot}], words}
  Ring       {t, cx, cy, r, tilt, turns, at, half back|front|all, color, size}
  Neon       {t, y, size, at, color, dark}
  Broll      {obj, media_start, push, words, tint}
  LogoHit    {img, w, num, title, sub, at, ground}
  NoiseSweep {lines, at, sweep_at, clean, y}
  DocSquash  {title, lines, at, strike_at, squash_at, before, after}
  Collapse   {img, at, n, collapse_at, summary, stats}
  DotEnd     {at, handle, cta, sub, logo}
"""
from __future__ import annotations

import math
import random

from .hf_ae import esc
from .hf_design import Ctx, scene_file

ACC = "#013220"           # the owner's brand green: big fills, paper, silhouettes
ACC_TXT = "#13874F"       # the same hue lifted for type that sits on footage (#013220 vanishes on a dark room)
CREAM = "#F3EBDD"
F = {"sans": "'Poppins', sans-serif", "heavy": "'Anton', sans-serif", "script": "'Mrs Saint Delafield', cursive",
     "eth": "'Noto Sans Ethiopic', sans-serif", "ethheavy": "'Noto Sans Ethiopic', sans-serif", "mono": "'JetBrains Mono', monospace"}


def _fonts(cx: Ctx):
    b = cx.brand or {}
    global ACC, ACC_TXT, CREAM
    ACC, ACC_TXT, CREAM = b.get("brand", ACC), b.get("accent_text", ACC_TXT), b.get("cream", CREAM)
    for k in list(F):
        if b.get("font_" + k):
            F[k] = b["font_" + k]


def _vid(vid: str, src: str, start: float, dur: float, media_start: float, style: str, extra: str = "") -> str:
    ms = f' data-media-start="{media_start:.3f}"' if media_start else ""
    return (f'<video id="{vid}" class="clip" data-start="{start:.3f}" data-duration="{max(0.05, dur):.3f}"{ms} data-track-index="1" '
            f'src="{src}" muted playsinline {extra} style="{style}"></video>')


def _obj(name: str) -> str:
    return name if name.startswith("assets/") else f"assets/objects/{name}.webm"


def _img(name: str) -> str:
    return name if name.startswith("assets/") else f"assets/images/{name}"


# ---------------------------------------------------------------------------------------------- words
def _word(cx: Ctx, wid: str, w: dict) -> tuple[str, list]:
    """One placed word; returns (html, js). Arrives in ~4 frames (scale 1.3 -> 1 through blur), STARTING DEFAULT."""
    fr = 1 / cx.fps
    st = w.get("style", "sans")
    size = w.get("size", 90)
    col = w.get("color") or {"heavy": ACC_TXT, "ethheavy": ACC_TXT, "script": "#D9D4CC", "bar": ACC, "box": "#FFFFFF"}.get(st, "#FFFFFF")
    fam = F["heavy"] if st in ("heavy", "box") else F["script"] if st == "script" else F["eth"] if st in ("eth", "ethheavy") else F["sans"]
    wt = {"heavy": 400, "ethheavy": 900, "eth": 600, "script": 400, "box": 400, "bar": 600}.get(st, 600)
    lsp = "-0.01em" if st in ("heavy", "box") else "0"
    up = "text-transform:uppercase;" if st in ("heavy", "box") else ""
    sh = "text-shadow:0 4px 18px rgba(0,0,0,0.45);" if st not in ("bar",) else ""
    align = w.get("align", "center")
    tx = {"center": "-50%", "left": "0%", "right": "-100%"}[align]
    rot = w.get("rot", 0)
    x, y = w.get("x", 0.5) * cx.W, w.get("y", 0.5) * cx.H
    inner = esc(w["t"])
    deco, js = "", []
    if st == "bar":         # a white bar wipes in behind the word (reference 13.2-14.9 s)
        deco = f'<i id="{wid}-bar" style="position:absolute;left:-0.18em;right:-0.18em;top:0.08em;bottom:0.02em;background:#fff;transform-origin:0 50%;z-index:-1"></i>'
    if st == "box":         # a heavy word in a filled accent box
        deco = f'<i id="{wid}-bar" style="position:absolute;left:-0.12em;right:-0.12em;top:0.02em;bottom:-0.02em;background:{ACC};transform-origin:0 50%;z-index:-1;border-radius:4px"></i>'
    mark = w.get("mark")
    if mark == "scribble":  # a hand-drawn loop drawn round the word in the accent
        deco += (f'<svg id="{wid}-m" viewBox="0 0 200 80" preserveAspectRatio="none" style="position:absolute;left:-14%;top:-30%;width:128%;height:160%;overflow:visible">'
                 f'<path d="M 18 52 C 6 22, 70 4, 120 8 C 175 12, 198 34, 182 56 C 160 80, 60 82, 24 62 C 10 52, 30 30, 70 22" fill="none" '
                 f'stroke="{w.get("mark_color", ACC_TXT)}" stroke-width="5" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>')
    elif mark == "underline":
        deco += (f'<svg id="{wid}-m" viewBox="0 0 200 20" preserveAspectRatio="none" style="position:absolute;left:-4%;bottom:-0.22em;width:108%;height:0.3em;overflow:visible">'
                 f'<path d="M 2 12 C 50 6, 120 16, 198 8" fill="none" stroke="{w.get("mark_color", ACC_TXT)}" stroke-width="7" stroke-linecap="round" '
                 f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>')
    html = (f'<div id="{wid}" style="position:absolute;left:{x:.0f}px;top:{y:.0f}px;transform:translate({tx},-50%) rotate({rot}deg);white-space:nowrap"><div id="{wid}-d">'
            f'<div id="{wid}-i" style="position:relative;font-family:{fam};font-weight:{wt};font-size:{size}px;line-height:1;color:{col};letter-spacing:{lsp};{up}{sh}">'
            f'{deco}<span style="position:relative">{inner}</span></div></div></div>')
    a = cx.s(w.get("at", 0))
    js.append(f'tl.fromTo("#{wid}-i", {{ opacity: 0, scale: {w.get("from_scale", 1.3)}, filter: "blur(10px)" }}, '
              f'{{ opacity: 1, scale: 1, filter: "blur(0px)", duration: {4 * fr:.3f}, ease: "power3.out" }}, {a:.3f});')
    if st in ("bar", "box"):
        js.append(f'tl.fromTo("#{wid}-bar", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {6 * fr:.3f}, ease: "expo.out" }}, {a:.3f});')
    if mark:
        js.append(f'draw("#{wid}-m path", {a + 3 * fr:.3f}, {(12 if mark == "scribble" else 7) * fr:.3f});')
    if w.get("drift", True):
        js.append(f'tl.to("#{wid}-d", {{ y: {w.get("dy", -10)}, duration: 2.5, ease: "none" }}, {a:.3f});')
    if w.get("out") is not None:
        js.append(f'tl.to("#{wid}-i", {{ opacity: 0, scale: 0.9, filter: "blur(8px)", duration: {3 * fr:.3f}, ease: "power2.in" }}, {cx.s(w["out"]):.3f});')
    return html, js


def _words(cx: Ctx, cid: str, words: list) -> tuple[str, list]:
    body, js = [], []
    for i, w in enumerate(words or []):
        h, j = _word(cx, f"{cid}-w{i}", w)
        body.append(h)
        js += j
    return "".join(body), js


def ov_kstack(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Stacked kinetic words over the picture; they stay until the stack clears (`out`, frames) or the overlay ends."""
    body, js = _words(cx, cid, p["words"])
    if p.get("out") is not None:
        js.append(f'tl.to("#{cid}-all", {{ opacity: 0, duration: 0.06 }}, {cx.s(p["out"]):.3f});')
    return scene_file(cx, cid, cx.H, f"#{cid}-all{{position:absolute;inset:0}}", f'<div id="{cid}-all">{body}</div>', "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- silhouette
def ov_silhouette(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """The speaker cut-out (assets/fg.webm) filled flat: accent for `color_f` frames with a glyph on the head and
    doodle strokes, then white with a glow for `white_f` frames (reference 0-0.2 s and 4.43-4.5 s)."""
    fr = 1 / cx.fps
    cf, wf = int(p.get("color_f", 4)), int(p.get("white_f", 3))
    col = p.get("color", ACC)
    t0 = float(p.get("t0", 0))
    st = f"position:absolute;left:0;top:0;width:{cx.W}px;height:{cx.H}px;object-fit:cover"
    svg = (f'<svg width="0" height="0" style="position:absolute"><defs>'
           f'<filter id="{cid}-fc" x="0" y="0" width="1" height="1"><feFlood flood-color="{col}"/><feComposite in2="SourceAlpha" operator="in"/></filter>'
           f'<filter id="{cid}-fw" x="-20%" y="-20%" width="140%" height="140%"><feFlood flood-color="#FFFFFF"/><feComposite in2="SourceAlpha" operator="in" result="w"/>'
           f'<feGaussianBlur in="w" stdDeviation="38" result="g"/><feFlood flood-color="#FFF4D8" flood-opacity="0.9"/><feComposite in2="g" operator="in" result="gg"/>'
           f'<feMerge><feMergeNode in="gg"/><feMergeNode in="gg"/><feMergeNode in="w"/></feMerge></filter></defs></svg>')
    body = [svg,
            f'<div id="{cid}-c" style="position:absolute;inset:0">{_vid(cid + "-vc", "assets/fg.webm", 0, cf * fr, t0, st + f";filter:url(#{cid}-fc)")}</div>',
            f'<div id="{cid}-w" style="position:absolute;inset:0">{_vid(cid + "-vw", "assets/fg.webm", cf * fr, max(fr, dur - cf * fr), t0 + cf * fr, st + f";filter:url(#{cid}-fw)")}</div>']
    hx, hy = p.get("head", [0.5, 0.30])
    if p.get("glyph"):
        body.append(f'<div id="{cid}-g" style="position:absolute;left:{hx * cx.W:.0f}px;top:{hy * cx.H:.0f}px;transform:translate(-50%,-50%);'
                    f'font-family:{F["heavy"]};font-size:{p.get("glyph_size", 170)}px;color:#fff;letter-spacing:-0.04em">{esc(p["glyph"])}</div>')
    sx, sy = p.get("strokes", [hx + 0.2, hy - 0.12])
    body.append(f'<svg id="{cid}-s" viewBox="0 0 100 100" style="position:absolute;left:{sx * cx.W - 70:.0f}px;top:{sy * cx.H - 90:.0f}px;width:140px;height:140px;overflow:visible">'
                f'<path d="M 30 80 L 52 18 M 52 86 L 76 30 M 72 90 L 96 52" stroke="#fff" stroke-width="7" stroke-linecap="round" fill="none"/></svg>')
    js = [f'tl.set("#{cid}-c, #{cid}-g", {{ opacity: 1 }}, 0);', f'tl.set("#{cid}-c, #{cid}-g", {{ opacity: 0 }}, {cf * fr:.3f});',
          f'tl.fromTo("#{cid}-w", {{ opacity: 1 }}, {{ opacity: 0.0, duration: {wf * fr:.3f}, ease: "power2.in" }}, {cf * fr:.3f});',
          f'tl.fromTo("#{cid}-s", {{ scale: 0.6, rotation: -8 }}, {{ scale: 1, rotation: 0, duration: {3 * fr:.3f}, ease: "back.out(3)" }}, 0);',
          f'tl.to("#{cid}-s", {{ opacity: 0, duration: {fr:.3f} }}, {max(0, dur - fr):.3f});']
    return scene_file(cx, cid, cx.H, "", "".join(body), "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- frame card
def ov_framecard(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """The picture shrinks into a rounded card on black with a warm glow under it; a Blender object (`obj`, alpha
    webm) can fly in over it. Card size and the 6-frame shrink are STARTING DEFAULTS from reference 3.3-4.4 s."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    t0 = float(p.get("t0", 0))
    cw, ch = p.get("w", 0.86) * W, p.get("h", 0.40) * H
    cy = p.get("y", 0.44) * H
    glow = p.get("glow", "#FFB45A")
    body = [f'<div id="{cid}-bk" style="position:absolute;inset:0;background:#030303"></div>',
            f'<div id="{cid}-gl" style="position:absolute;left:-10%;right:-10%;top:{cy + ch * 0.42:.0f}px;height:{H * 0.42:.0f}px;'
            f'background:radial-gradient(ellipse 50% 40% at 50% 30%, {glow}88 0%, {glow}33 40%, transparent 70%);filter:blur(30px)"></div>',
            f'<div id="{cid}-cd" style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;overflow:hidden;transform-origin:50% {cy / H * 100:.1f}%">'
            f'{_vid(cid + "-v", "assets/base.mp4", 0, dur, t0, f"position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover")}</div>']
    if p.get("obj"):
        body.append(f'<div id="{cid}-ob" style="position:absolute;inset:0">'
                    f'{_vid(cid + "-o", _obj(p["obj"]), cx.s(p.get("obj_at", 4)), dur - cx.s(p.get("obj_at", 4)), 0, f"position:absolute;left:0;top:{p.get("obj_y", 0) * H:.0f}px;width:{W}px;height:{H}px")}</div>')
    wb, wj = _words(cx, cid, p.get("words"))
    body.append(wb)
    a = cx.s(p.get("at", 0))
    s = p.get("scale", cw / W)
    # inset() keeps the card's landscape shape while the whole picture scales down
    ix = (W - cw / s) / 2
    iy_t = cy - ch / s / 2
    iy_b = H - (cy + ch / s / 2)
    js = [f'tl.fromTo("#{cid}-cd", {{ scale: 1, clipPath: "inset(0px 0px 0px 0px round 0px)" }}, '
          f'{{ scale: {s:.3f}, clipPath: "inset({max(0, iy_t):.0f}px {ix:.0f}px {max(0, iy_b):.0f}px {ix:.0f}px round {48 / s:.0f}px)", duration: {6 * fr:.3f}, ease: "expo.out" }}, {a:.3f});',
          f'tl.to("#{cid}-cd", {{ scale: {s * 0.96:.3f}, y: -14, duration: {max(0.2, dur - a - 6 * fr):.3f}, ease: "sine.inOut" }}, {a + 6 * fr:.3f});',
          f'tl.fromTo("#{cid}-gl", {{ opacity: 0 }}, {{ opacity: 1, duration: {8 * fr:.3f} }}, {a + 2 * fr:.3f});',
          f'tl.fromTo("#{cid}-bk", {{ opacity: 0 }}, {{ opacity: 1, duration: {2 * fr:.3f} }}, {a:.3f});']
    return scene_file(cx, cid, cx.H, "", "".join(body), "\n".join(js + wj), transparent=True)


# ---------------------------------------------------------------------------------------------- paper tear
def _tear_path(W: float, y: float, seed: int, amp: float = 34) -> list[tuple[float, float]]:
    r = random.Random(seed)
    pts, x = [], -20.0
    while x < W + 40:
        pts.append((x, y + r.uniform(-amp, amp) + 26 * math.sin(x / 140)))
        x += r.uniform(18, 46)
    return pts


def ov_papertear(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Full-screen accent paper (a real crumpled-paper clip, tinted, `paper`) with words; at `tear_at` it rips open
    across the middle (white fibre edge on both lips) and the `reveal` image shows through, pushing in.
    Reference 5.6-7.1 s; the 9-frame rip and the ~22 % gap are STARTING DEFAULTS."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    ty = p.get("tear_y", 0.48) * H
    pts = _tear_path(W, ty, int(p.get("seed", 3)))
    top = "polygon(" + ", ".join([f"0px 0px", f"{W}px 0px"] + [f"{x:.0f}px {y:.0f}px" for x, y in reversed(pts)]) + ")"
    bot = "polygon(" + ", ".join([f"{x:.0f}px {y:.0f}px" for x, y in pts] + [f"{W}px {H}px", f"0px {H}px"]) + ")"
    edge = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
    tint = p.get("tint", ACC)
    paper = f"position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover"

    def half(n, clip, dy):
        v = _vid(f"{cid}-p{n}", _obj(p["paper"]), 0, dur, p.get("paper_start", 0.0), paper) if p.get("paper") else ""
        return (f'<div id="{cid}-h{n}" style="position:absolute;inset:0;clip-path:{clip}">'
                f'<div style="position:absolute;inset:0;background:{tint}"></div>{v}'
                + ("" if p.get("pretinted") else f'<div style="position:absolute;inset:0;background:{tint};mix-blend-mode:color;opacity:0.9"></div>') +
                f'<div style="position:absolute;inset:0;background:radial-gradient(ellipse 80% 60% at 50% 40%, transparent 30%, rgba(0,0,0,0.45) 100%)"></div></div>'
                f'<svg id="{cid}-e{n}" viewBox="0 0 {W} {H}" style="position:absolute;inset:0;overflow:visible"><polyline points="{edge}" fill="none" '
                f'stroke="#F6F1E6" stroke-width="{16 if n == 0 else 12}" stroke-linejoin="round" transform="translate(0,{dy})" '
                f'style="filter:drop-shadow(0 {6 if n == 0 else -6}px 8px rgba(0,0,0,0.5))"/></svg>')
    rev = p.get("reveal")
    body = [f'<div id="{cid}-rv" style="position:absolute;inset:0;background:#111">'
            + (f'<img src="{_img(rev)}" alt="" style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover">' if rev else "") + "</div>",
            f'<div id="{cid}-top" style="position:absolute;inset:0">{half(0, top, 4)}</div>',
            f'<div id="{cid}-bot" style="position:absolute;inset:0">{half(1, bot, -4)}</div>']
    wb, wj = _words(cx, cid, p.get("words"))
    body.append(f'<div id="{cid}-wd" style="position:absolute;inset:0">{wb}</div>')
    a = cx.s(p.get("tear_at", 20))
    gap = p.get("gap", 0.22) * H
    js = [f'tl.fromTo("#{cid}-top", {{ y: 0, rotation: 0 }}, {{ y: {-gap * 0.55:.0f}, rotation: -1.2, duration: {9 * fr:.3f}, ease: "expo.out" }}, {a:.3f});',
          f'tl.fromTo("#{cid}-bot", {{ y: 0, rotation: 0 }}, {{ y: {gap * 0.45:.0f}, rotation: 1.0, duration: {9 * fr:.3f}, ease: "expo.out" }}, {a:.3f});',
          f'tl.fromTo("#{cid}-rv", {{ scale: 1.25 }}, {{ scale: 1.05, duration: {max(0.3, dur - a):.3f}, ease: "power2.out" }}, {a:.3f});',
          f'tl.fromTo("#{cid}-h0, #{cid}-h1", {{ scale: 1.0 }}, {{ scale: 1.04, duration: {dur:.3f}, ease: "sine.inOut" }}, 0);']
    if p.get("zoom_in", True):
        js.append(f'tl.fromTo("#{cid}-top, #{cid}-bot, #{cid}-wd", {{ scale: 1.18, filter: "blur(14px)" }}, {{ scale: 1, filter: "blur(0px)", duration: {6 * fr:.3f}, ease: "expo.out" }}, 0);')
    return scene_file(cx, cid, cx.H, "", "".join(body), "\n".join(js + wj), transparent=True)


# ---------------------------------------------------------------------------------------------- collage
def ov_collage(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Tiles cropped from the speaker's own picture (assets/base.mp4, in sync) on a flat ground, words between.
    tile {x, y, w, h (0-1 of the frame), fx, fy (the crop centre in the source, 0-1), zoom, at, rot}."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    t0 = float(p.get("t0", 0))
    body = [f'<div id="{cid}-gr" style="position:absolute;inset:0;background:{p.get("ground", CREAM)}"></div>']
    if p.get("grain", True):
        body.append(f'<div style="position:absolute;inset:0;background:radial-gradient(ellipse 70% 55% at 50% 45%, transparent 40%, rgba(0,0,0,0.18) 100%)"></div>')
    js = []
    for i, t in enumerate(p["tiles"]):
        tw, th = t["w"] * W, t["h"] * H
        z = t.get("zoom", 2.2)
        vw, vh = W * z, H * z
        vx, vy = tw / 2 - t["fx"] * vw, th / 2 - t["fy"] * vh
        a = cx.s(t.get("at", 0))
        body.append(f'<div id="{cid}-t{i}" style="position:absolute;left:{t["x"] * W - tw / 2:.0f}px;top:{t["y"] * H - th / 2:.0f}px;width:{tw:.0f}px;height:{th:.0f}px;'
                    f'overflow:hidden;border-radius:{t.get("radius", 18)}px;box-shadow:0 18px 40px rgba(0,0,0,0.35);transform:rotate({t.get("rot", 0)}deg)">'
                    f'{_vid(f"{cid}-v{i}", "assets/base.mp4", 0, dur, t0, f"position:absolute;left:{vx:.0f}px;top:{vy:.0f}px;width:{vw:.0f}px;height:{vh:.0f}px;object-fit:cover")}</div>')
        js.append(f'tl.fromTo("#{cid}-t{i}", {{ opacity: 0, scale: 0.6, y: 60 }}, {{ opacity: 1, scale: 1, y: 0, duration: {6 * fr:.3f}, ease: "back.out(1.8)" }}, {a:.3f});')
        js.append(f'tl.to("#{cid}-t{i}", {{ y: {(-1) ** i * 16}, duration: {max(0.3, dur - a):.3f}, ease: "sine.inOut" }}, {a + 6 * fr:.3f});')
    wb, wj = _words(cx, cid, p.get("words"))
    body.append(wb)
    js.append(f'tl.fromTo("#{cid}-gr", {{ opacity: 0 }}, {{ opacity: 1, duration: {2 * fr:.3f} }}, 0);')
    return scene_file(cx, cid, cx.H, "", "".join(body), "\n".join(js + wj), transparent=True)


# ---------------------------------------------------------------------------------------------- ring
def ov_ring(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Words on a ring round the speaker, tilted into perspective and turning. Use two overlays: half "back"
    (behind: true, the far side passes behind him) and half "front" (over him)."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    r = p.get("r", 430)
    cxp, cyp = p.get("cx", 0.5) * W, p.get("cy", 0.42) * H
    txt = esc((p["t"] + "  •  ") * int(p.get("repeat", 3)))
    size = p.get("size", 64)
    half = p.get("half", "all")
    clip = {"back": "inset(0 0 50% 0)", "front": "inset(50% 0 0 0)"}.get(half, "none")
    body = (f'<div id="{cid}-cl" style="position:absolute;left:{cxp - r - 80:.0f}px;top:{cyp - r - 80:.0f}px;width:{2 * r + 160:.0f}px;height:{2 * r + 160:.0f}px;'
            f'clip-path:{clip};perspective:1400px">'
            f'<div id="{cid}-tl" style="position:absolute;inset:0;transform:rotateX({p.get("tilt", 72)}deg) rotateZ({p.get("roll", -8)}deg)">'
            f'<svg id="{cid}-rg" viewBox="0 0 {2 * r + 160} {2 * r + 160}" style="position:absolute;inset:0;overflow:visible">'
            f'<defs><path id="{cid}-c" d="M {r + 80} {r + 80} m -{r} 0 a {r} {r} 0 1 0 {2 * r} 0 a {r} {r} 0 1 0 -{2 * r} 0"/></defs>'
            f'<text style="font-family:{F["heavy"] if p.get("heavy", True) else F["sans"]};font-size:{size}px;letter-spacing:0.04em;fill:{p.get("color", "#FFFFFF")};'
            f'text-transform:uppercase;paint-order:stroke;stroke:rgba(0,0,0,0.35);stroke-width:6px"><textPath href="#{cid}-c">{txt}</textPath></text></svg></div></div>')
    a = cx.s(p.get("at", 0))
    js = [f'tl.fromTo("#{cid}-rg", {{ rotation: 0, transformOrigin: "50% 50%" }}, {{ rotation: {360 * p.get("turns", 0.5):.0f}, duration: {dur:.3f}, ease: "none" }}, 0);',
          f'tl.fromTo("#{cid}-cl", {{ opacity: 0, scale: 0.7 }}, {{ opacity: 1, scale: 1, duration: {6 * fr:.3f}, ease: "expo.out" }}, {a:.3f});',
          f'tl.to("#{cid}-cl", {{ opacity: 0, duration: {3 * fr:.3f} }}, {max(0, dur - 3 * fr):.3f});']
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- neon
def ov_neon(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A neon outline word on the wall behind the speaker (use behind: true), flickering on, while the room darkens
    (reference 23.1-24 s). `dark` 0-1 is how far the room goes to black."""
    fr = 1 / cx.fps
    col = p.get("color", "#3DFFA0")
    y = p.get("y", 0.25) * cx.H
    body = (f'<div id="{cid}-dk" style="position:absolute;inset:0;background:#000"></div>'
            f'<div id="{cid}-n" style="position:absolute;left:0;right:0;top:{y:.0f}px;transform:translateY(-50%);text-align:center;font-family:{F["heavy"]};'
            f'font-size:{p.get("size", 330)}px;line-height:1;color:transparent;-webkit-text-stroke:5px {col};text-transform:uppercase;'
            f'filter:drop-shadow(0 0 10px {col}) drop-shadow(0 0 34px {col}) drop-shadow(0 0 80px {col}88)">{esc(p["t"])}</div>')
    a = cx.s(p.get("at", 0))
    js = [f'tl.fromTo("#{cid}-dk", {{ opacity: 0 }}, {{ opacity: {p.get("dark", 0.82)}, duration: {10 * fr:.3f}, ease: "power2.inOut" }}, {a:.3f});',
          f'tl.set("#{cid}-n", {{ opacity: 0 }}, 0);']
    for k, (on, off) in enumerate(((2, 4), (6, 7), (9, 99))):     # flicker on: three hits, STARTING DEFAULT
        js.append(f'tl.set("#{cid}-n", {{ opacity: 1 }}, {a + on * fr:.3f});')
        if off < 99:
            js.append(f'tl.set("#{cid}-n", {{ opacity: 0.15 }}, {a + off * fr:.3f});')
    js.append(f'tl.fromTo("#{cid}-n", {{ scale: 0.96 }}, {{ scale: 1.03, duration: {dur:.3f}, ease: "sine.inOut" }}, 0);')
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- b-roll
def ov_broll(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Full-screen real footage (assets/objects/<obj>.webm, opaque, prepared at the delivery size) with a slow push
    and kinetic words; it snaps in from a 1.12 blur-zoom over 5 frames (STARTING DEFAULT)."""
    fr = 1 / cx.fps
    body = [f'<div id="{cid}-v" style="position:absolute;inset:0;background:#000">'
            f'{_vid(cid + "-c", _obj(p["obj"]), 0, dur, p.get("media_start", 0.0), f"position:absolute;left:0;top:0;width:{cx.W}px;height:{cx.H}px;object-fit:cover")}</div>']
    if p.get("shade", 0.0):
        body.append(f'<div style="position:absolute;inset:0;background:linear-gradient(180deg, rgba(0,0,0,{p["shade"]}) 0%, transparent 45%, transparent 70%, rgba(0,0,0,{p["shade"]}) 100%)"></div>')
    wb, wj = _words(cx, cid, p.get("words"))
    body.append(wb)
    js = [f'tl.fromTo("#{cid}-v", {{ scale: 1.12, filter: "blur(12px)" }}, {{ scale: 1, filter: "blur(0px)", duration: {5 * fr:.3f}, ease: "expo.out" }}, 0);',
          f'tl.to("#{cid}-v", {{ scale: {p.get("push", 1.06)}, duration: {max(0.2, dur - 5 * fr):.3f}, ease: "sine.inOut" }}, {5 * fr:.3f});']
    return scene_file(cx, cid, cx.H, "", "".join(body), "\n".join(js + wj), transparent=True)


# ---------------------------------------------------------------------------------------------- logo hit
def ov_logohit(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A skill's real logo on a deep accent stage: the big number slams in behind, the logo card swings in on a 3D
    turn with a light sweep, title and line land under it."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    lw = p.get("w", 860)
    ground = p.get("ground", ACC)
    centre, edge = p.get("centre", "#0B5E38"), p.get("edge", "#000d07")
    ncol = p.get("num_color", "rgba(255,255,255,0.12)")
    body = [f'<div id="{cid}-g" style="position:absolute;inset:0;background:radial-gradient(ellipse 90% 60% at 50% 42%, {centre} 0%, {ground} 55%, {edge} 100%)"></div>',
            f'<div id="{cid}-n" style="position:absolute;left:0;right:0;top:{H * 0.30:.0f}px;transform:translateY(-50%);text-align:center;font-family:{F["heavy"]};'
            f'font-size:900px;line-height:1;color:{ncol}">{esc(p.get("num", ""))}</div>',
            f'<div id="{cid}-lc" style="position:absolute;left:{(W - lw) / 2:.0f}px;top:{H * p.get("y", 0.36) - lw * 0.25:.0f}px;width:{lw}px;perspective:1200px">'
            f'<div id="{cid}-l" style="position:relative;border-radius:28px;overflow:hidden;box-shadow:0 40px 90px rgba(0,0,0,0.55),0 0 0 2px rgba(255,255,255,0.12)">'
            f'<img src="{_img(p["img"])}" alt="" style="display:block;width:100%">'
            f'<i id="{cid}-sw" style="position:absolute;top:-20%;bottom:-20%;width:30%;left:-40%;background:linear-gradient(100deg,transparent,rgba(255,255,255,0.55),transparent);transform:skewX(-18deg)"></i>'
            f'</div></div>']
    wb, wj = _words(cx, cid, p.get("words"))
    body.append(wb)
    a = cx.s(p.get("at", 0))
    js = [f'tl.fromTo("#{cid}-g", {{ scale: 1.2 }}, {{ scale: 1, duration: {dur:.3f}, ease: "power2.out" }}, 0);',
          f'tl.fromTo("#{cid}-n", {{ scale: 1.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: {5 * fr:.3f}, ease: "expo.out" }}, 0);',
          f'tl.fromTo("#{cid}-l", {{ rotationY: -70, rotationX: 18, z: -500, opacity: 0 }}, {{ rotationY: 0, rotationX: 0, z: 0, opacity: 1, duration: {10 * fr:.3f}, ease: "expo.out" }}, {a:.3f});',
          f'tl.to("#{cid}-l", {{ rotationY: 8, rotationX: -4, duration: {max(0.3, dur - a - 10 * fr):.3f}, ease: "sine.inOut" }}, {a + 10 * fr:.3f});',
          f'tl.fromTo("#{cid}-sw", {{ xPercent: 0 }}, {{ xPercent: 560, duration: {14 * fr:.3f}, ease: "power2.inOut" }}, {a + 6 * fr:.3f});']
    return scene_file(cx, cid, cx.H, "", "".join(body), "\n".join(js + wj), transparent=True)


# ---------------------------------------------------------------------------------------------- terminal noise
def ov_noisesweep(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Terminal noise over the code footage: log lines pile up fast (one every 1-2 frames), then a bright bar sweeps
    down and wipes them, leaving the few clean lines (`clean`) that matter."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    lines = p["lines"]
    y0 = p.get("y", 0.30) * H
    lh = 42
    body = [f'<div id="{cid}-pn" style="position:absolute;left:60px;right:60px;top:{y0 - 40:.0f}px;height:{lh * 14 + 80}px;border-radius:26px;'
            f'background:rgba(3,10,7,0.82);box-shadow:0 30px 80px rgba(0,0,0,0.6),inset 0 0 0 2px rgba(80,255,170,0.18);overflow:hidden">'
            f'<div style="position:absolute;left:28px;top:20px;display:flex;gap:12px">' + "".join(f'<b style="width:18px;height:18px;border-radius:50%;background:{c}"></b>' for c in ("#FF5F57", "#FEBC2E", "#28C840")) + '</div>']
    js = []
    a = p.get("at", 0)
    for i, ln in enumerate(lines[:14]):
        body.append(f'<div id="{cid}-l{i}" style="position:absolute;left:30px;right:30px;top:{70 + i * lh}px;font:500 28px/1 {F["mono"]};color:{"#FF8A7A" if "ERR" in ln or "WARN" in ln else "#9FB8AA"};white-space:nowrap;overflow:hidden">{esc(ln)}</div>')
        js.append(f'tl.fromTo("#{cid}-l{i}", {{ opacity: 0, x: -20 }}, {{ opacity: 1, x: 0, duration: {2 * fr:.3f} }}, {cx.s(a + i * 1.6):.3f});')
    sw = cx.s(p.get("sweep_at", 30))
    body.append(f'<i id="{cid}-bar" style="position:absolute;left:0;right:0;top:0;height:26px;background:linear-gradient(180deg,transparent,#B9FFD9,transparent);box-shadow:0 0 40px #5DFFA8"></i>')
    for k, c in enumerate(p.get("clean", [])):
        body.append(f'<div id="{cid}-c{k}" style="position:absolute;left:30px;top:{90 + k * 64}px;font:700 40px/1 {F["mono"]};color:#E9FFF2">'
                    f'<span style="color:#5DFFA8">✓</span> {esc(c)}</div>')
        js.append(f'tl.fromTo("#{cid}-c{k}", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: {5 * fr:.3f}, ease: "expo.out" }}, {sw + (10 + 4 * k) * fr:.3f});')
    body.append("</div>")
    js += [f'tl.fromTo("#{cid}-pn", {{ opacity: 0, y: 40, scale: 0.94 }}, {{ opacity: 1, y: 0, scale: 1, duration: {6 * fr:.3f}, ease: "expo.out" }}, 0);',
           f'tl.fromTo("#{cid}-bar", {{ y: -30, opacity: 0 }}, {{ y: {lh * 14 + 90}, opacity: 1, duration: {10 * fr:.3f}, ease: "power2.inOut" }}, {sw:.3f});',
           f'tl.to("#{cid}-bar", {{ opacity: 0, duration: {2 * fr:.3f} }}, {sw + 10 * fr:.3f});']
    for i in range(min(14, len(lines))):
        js.append(f'tl.to("#{cid}-l{i}", {{ opacity: 0, x: 60, filter: "blur(6px)", duration: {3 * fr:.3f} }}, {sw + (i * 0.7) * fr:.3f});')
    wb, wj = _words(cx, cid, p.get("words"))
    return scene_file(cx, cid, cx.H, "", "".join(body) + wb, "\n".join(js + wj), transparent=True)


# ---------------------------------------------------------------------------------------------- CLAUDE.md squash
def ov_docsquash(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A CLAUDE.md page on the deep accent stage: long lines get struck one by one, then the page squashes to a
    short note and a token counter drops (`before` -> `after`, shown only when given)."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    pw, ph = 820, 1040
    lines = p["lines"]
    body = [f'<div id="{cid}-g" style="position:absolute;inset:0;background:radial-gradient(ellipse 90% 70% at 50% 40%, {p.get("centre", "#0A5232")} 0%, {p.get("ground", ACC)} 55%, {p.get("edge", "#000d07")} 100%)"></div>',
            f'<div id="{cid}-pg" style="position:absolute;left:{(W - pw) / 2:.0f}px;top:{H * 0.20:.0f}px;width:{pw}px;height:{ph}px;transform-origin:50% 0%;'
            f'background:{CREAM};border-radius:22px;box-shadow:0 40px 100px rgba(0,0,0,0.55);overflow:hidden">'
            f'<div style="position:absolute;left:50px;top:44px;font:700 52px/1 {F["mono"]};color:{ACC}">{esc(p.get("title", "CLAUDE.md"))}</div>']
    js = []
    for i, ln in enumerate(lines[:16]):
        y = 140 + i * 56
        keep = ln.startswith("!")
        t = ln[1:] if keep else ln
        body.append(f'<div id="{cid}-l{i}" style="position:absolute;left:50px;right:50px;top:{y}px;font:500 30px/1.2 {F["mono"]};color:{"#0A3D25" if keep else "#5B5B55"};white-space:nowrap;overflow:hidden;transform-origin:0 50%">'
                    f'{esc(t)}<i id="{cid}-s{i}" style="position:absolute;left:0;right:0;top:52%;height:5px;background:{ACC_TXT};transform-origin:0 50%"></i></div>')
        if not keep:
            k = sum(1 for x in lines[:i] if not x.startswith("!"))
            js.append(f'tl.fromTo("#{cid}-s{i}", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {4 * fr:.3f}, ease: "power2.out" }}, {cx.s(p.get("strike_at", 12) + k * 3):.3f});')
            js.append(f'tl.to("#{cid}-l{i}", {{ opacity: 0, scaleY: 0.2, duration: {6 * fr:.3f}, ease: "expo.inOut" }}, {cx.s(p.get("squash_at", 60)):.3f});')
    body.append("</div>")
    sq = cx.s(p.get("squash_at", 60))
    nkeep = sum(1 for x in lines if x.startswith("!"))
    js += [f'tl.fromTo("#{cid}-pg", {{ y: 900, rotation: 6 }}, {{ y: 0, rotation: -1.5, duration: {9 * fr:.3f}, ease: "expo.out" }}, 0);',
           f'tl.fromTo("#{cid}-pg", {{ clipPath: "inset(0px 0px 0px 0px round 22px)" }}, {{ clipPath: "inset(0px 0px {ph - (140 + nkeep * 56 + 60)}px 0px round 22px)", rotation: 0, duration: {8 * fr:.3f}, ease: "back.out(1.6)", immediateRender: false }}, {sq:.3f});']
    # the kept lines close up as the struck ones collapse: recompute their tops
    kk = 0
    for i, ln in enumerate(lines[:16]):
        if ln.startswith("!"):
            js.append(f'tl.to("#{cid}-l{i}", {{ y: {(140 + kk * 56) - (140 + i * 56)}, duration: {8 * fr:.3f}, ease: "expo.inOut" }}, {sq:.3f});')
            kk += 1
    if p.get("before"):
        body.append(f'<div id="{cid}-ct" style="position:absolute;left:0;right:0;top:{H * 0.80:.0f}px;text-align:center;font-family:{F["heavy"]};font-size:150px;color:#fff">'
                    f'<span id="{cid}-cn">{esc(p["before"])}</span></div>')
        js.append(f'tl.fromTo("#{cid}-ct", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: {5 * fr:.3f}, ease: "expo.out" }}, {cx.s(p.get("strike_at", 12)):.3f});')
        js.append(f'tl.call(() => {{ document.querySelector("#{cid}-cn").textContent = {p["after"]!r}; }}, null, {sq + 4 * fr:.3f});')
        js.append(f'tl.call(() => {{ document.querySelector("#{cid}-cn").textContent = {p["before"]!r}; }}, null, {sq + 3 * fr:.3f});')
        js.append(f'tl.fromTo("#{cid}-ct", {{ scale: 1.25, color: "#5DFFA8" }}, {{ scale: 1, color: "#FFFFFF", duration: {8 * fr:.3f}, ease: "expo.out", immediateRender: false }}, {sq + 4 * fr:.3f});')
    wb, wj = _words(cx, cid, p.get("words"))
    return scene_file(cx, cid, cx.H, "", "".join(body) + wb, "\n".join(js + wj), transparent=True)


# ---------------------------------------------------------------------------------------------- collapse
def ov_collapse(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """A wall of raw tool output scrolls up fast, then folds into one summary card; the real product image
    (`img`) tilts in under it."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    rnd = random.Random(5)
    n = int(p.get("n", 40))
    words = ["GET", "200", "{", "}", "\"id\":", "\"data\":", "null,", "true,", "rows", "...", "0x7f", "Δ", "chunk", "#", "->", "[]", "log:", "ok"]
    rows = []
    for i in range(n):
        s = " ".join(rnd.choice(words) for _ in range(rnd.randint(6, 12)))
        rows.append(f'<div style="height:34px;font:500 24px/34px {F["mono"]};color:#7FA594;white-space:nowrap">{esc(s)}</div>')
    body = [f'<div id="{cid}-g" style="position:absolute;inset:0;background:#020805"></div>',
            f'<div id="{cid}-wl" style="position:absolute;left:40px;right:40px;top:0;height:{H}px;overflow:hidden;transform-origin:50% 45%">'
            f'<div id="{cid}-sc" style="position:absolute;left:0;right:0;top:0">{"".join(rows)}</div></div>',
            f'<div id="{cid}-cd" style="position:absolute;left:90px;right:90px;top:{H * 0.36:.0f}px;padding:44px 50px;border-radius:30px;background:{CREAM};'
            f'box-shadow:0 40px 100px rgba(0,0,0,0.6)">'
            f'<div style="font:700 28px/1 {F["mono"]};color:{ACC_TXT};letter-spacing:0.08em">SUMMARY</div>'
            f'<div style="margin-top:22px;font:600 46px/1.25 {F["sans"]};color:{ACC}">{esc(p.get("summary", ""))}</div></div>']
    if p.get("img"):
        body.append(f'<div id="{cid}-ic" style="position:absolute;left:80px;right:80px;top:{H * 0.62:.0f}px;perspective:1400px">'
                    f'<img id="{cid}-im" src="{_img(p["img"])}" alt="" style="display:block;width:100%;border-radius:22px;box-shadow:0 30px 80px rgba(0,0,0,0.6)"></div>')
    ca = cx.s(p.get("collapse_at", 30))
    js = [f'tl.fromTo("#{cid}-sc", {{ y: {H * 0.6:.0f} }}, {{ y: {-n * 34 + H * 0.5:.0f}, duration: {ca:.3f}, ease: "power1.in" }}, 0);',
          f'tl.to("#{cid}-wl", {{ scaleY: 0.02, scaleX: 0.6, opacity: 0, filter: "blur(6px)", duration: {8 * fr:.3f}, ease: "expo.in" }}, {ca:.3f});',
          f'tl.fromTo("#{cid}-cd", {{ scale: 0.2, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: {9 * fr:.3f}, ease: "back.out(1.7)" }}, {ca + 7 * fr:.3f});',
          f'tl.fromTo("#{cid}-g", {{ backgroundColor: "#020805" }}, {{ backgroundColor: "{p.get("end_ground", ACC)}", duration: {8 * fr:.3f} }}, {ca + 4 * fr:.3f});']
    if p.get("img"):
        ia = cx.s(p.get("img_at", p.get("collapse_at", 30) + 16))
        js.append(f'tl.fromTo("#{cid}-im", {{ rotationX: 60, y: 300, opacity: 0 }}, {{ rotationX: 14, y: 0, opacity: 1, duration: {10 * fr:.3f}, ease: "expo.out" }}, {ia:.3f});')
        js.append(f'tl.to("#{cid}-im", {{ rotationX: 4, rotationY: -6, duration: {max(0.3, dur - ia - 10 * fr):.3f}, ease: "sine.inOut" }}, {ia + 10 * fr:.3f});')
    wb, wj = _words(cx, cid, p.get("words"))
    return scene_file(cx, cid, cx.H, "", "".join(body) + wb, "\n".join(js + wj), transparent=True)


# ---------------------------------------------------------------------------------------------- dot outro
def ov_dotend(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """Outro (reference 24-29 s): black; a white dot drops and bounces three times, swells into a disc, the handle
    builds out of it letter by letter with an RGB-split glitch, the call to action lands under it."""
    fr = 1 / cx.fps
    W, H = cx.W, cx.H
    a = cx.s(p.get("at", 0))
    floor = H * 0.48
    hd = esc(p.get("handle", ""))
    letters = "".join(f'<span class="{cid}-ch" style="display:inline-block">{c if c != " " else "&nbsp;"}</span>' for c in p.get("handle", ""))
    body = [f'<div id="{cid}-bk" style="position:absolute;inset:0;background:#000"></div>',
            f'<div id="{cid}-d" style="position:absolute;left:{W / 2 - 30:.0f}px;top:{floor - 60:.0f}px;width:60px;height:60px;border-radius:50%;background:#fff;'
            f'box-shadow:0 0 40px rgba(255,255,255,0.6)"></div>',
            f'<div id="{cid}-ring" style="position:absolute;left:{W / 2 - 260:.0f}px;top:{floor - 290:.0f}px;width:520px;height:520px;border-radius:50%;border:6px solid {ACC_TXT};opacity:0"></div>']
    for k, (col, dx) in enumerate((("#FF3355", -8), ("#33E0FF", 8), ("#FFFFFF", 0))):
        body.append(f'<div id="{cid}-h{k}" style="position:absolute;left:0;right:0;top:{floor - 30 - p.get("size", 170) / 2:.0f}px;margin-left:{dx * 2}px;text-align:center;font-family:{F["heavy"]};'
                    f'font-size:{p.get("size", 170)}px;line-height:1;color:{col};{"mix-blend-mode:screen;" if k < 2 else ""}white-space:nowrap">{letters if k == 2 else hd}</div>')
    body.append(f'<div id="{cid}-cta" style="position:absolute;left:0;right:0;top:{floor + 140:.0f}px;text-align:center;font-family:{F["eth"]};font-weight:600;font-size:56px;color:#fff">{esc(p.get("cta", ""))}</div>')
    if p.get("sub"):
        body.append(f'<div id="{cid}-sub" style="position:absolute;left:0;right:0;top:{floor + 230:.0f}px;text-align:center;font-family:{F["sans"]};font-weight:500;font-size:40px;letter-spacing:0.1em;color:rgba(255,255,255,0.7)">{esc(p["sub"])}</div>')
    js = [f'tl.fromTo("#{cid}-bk", {{ opacity: 0 }}, {{ opacity: 1, duration: {4 * fr:.3f} }}, {a:.3f});',
          f'tl.set("#{cid}-h0, #{cid}-h1, #{cid}-h2, #{cid}-cta, #{cid}-sub", {{ opacity: 0 }}, 0);']
    # bounces: drop from above, three hops of falling height (STARTING DEFAULT 12/9/6 frames each)
    t = a
    js.append(f'tl.fromTo("#{cid}-d", {{ y: -900 }}, {{ y: 0, duration: {10 * fr:.3f}, ease: "power2.in" }}, {t:.3f});')
    t += 10 * fr
    for hop, n in ((320, 12), (150, 9), (60, 6)):
        js.append(f'tl.fromTo("#{cid}-d", {{ scaleY: 0.7, scaleX: 1.3 }}, {{ scaleY: 1, scaleX: 1, duration: {2 * fr:.3f} }}, {t:.3f});')
        js.append(f'tl.to("#{cid}-d", {{ y: {-hop}, duration: {n / 2 * fr:.3f}, ease: "power2.out" }}, {t:.3f});')
        js.append(f'tl.to("#{cid}-d", {{ y: 0, duration: {n / 2 * fr:.3f}, ease: "power2.in" }}, {t + n / 2 * fr:.3f});')
        t += n * fr
    js.append(f'tl.to("#{cid}-d", {{ scale: 9, opacity: 0, duration: {6 * fr:.3f}, ease: "expo.out" }}, {t:.3f});')
    js.append(f'tl.fromTo("#{cid}-ring", {{ scale: 0.3, opacity: 1 }}, {{ scale: 1, opacity: 0.0, duration: {14 * fr:.3f}, ease: "expo.out" }}, {t:.3f});')
    js.append(f'tl.set("#{cid}-h2", {{ opacity: 1 }}, {t:.3f});')
    js.append(f'tl.fromTo(".{cid}-ch", {{ opacity: 0, y: 40, scale: 1.4 }}, {{ opacity: 1, y: 0, scale: 1, duration: {4 * fr:.3f}, ease: "expo.out", stagger: {1.2 * fr:.3f} }}, {t:.3f});')
    for k, g in enumerate((2, 3, 7, 8, 13)):             # glitch hits: the red/cyan copies jump out of register
        js.append(f'tl.set("#{cid}-h0, #{cid}-h1", {{ opacity: 0.9, x: {(-1) ** k * 14} }}, {t + g * fr:.3f});')
        js.append(f'tl.set("#{cid}-h0, #{cid}-h1", {{ opacity: 0, x: 0 }}, {t + (g + 1) * fr:.3f});')
    js.append(f'tl.fromTo("#{cid}-cta", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: {6 * fr:.3f}, ease: "expo.out" }}, {t + 14 * fr:.3f});')
    js.append(f'tl.fromTo("#{cid}-sub", {{ opacity: 0 }}, {{ opacity: 1, duration: {6 * fr:.3f} }}, {t + 20 * fr:.3f});')
    return scene_file(cx, cid, cx.H, "", "".join(body), "\n".join(js), transparent=True)


def _fonted(fn):
    def run(cx, cid, dur, p):
        _fonts(cx)
        return fn(cx, cid, dur, p)
    run.__name__, run.__doc__ = fn.__name__, fn.__doc__
    return run


OVERLAYS = {k: _fonted(v) for k, v in {
    "KStack": ov_kstack, "Silhouette": ov_silhouette, "FrameCard": ov_framecard, "PaperTear": ov_papertear, "Collage": ov_collage,
    "Ring": ov_ring, "Neon": ov_neon, "Broll": ov_broll, "LogoHit": ov_logohit, "NoiseSweep": ov_noisesweep, "DocSquash": ov_docsquash,
    "Collapse": ov_collapse, "DotEnd": ov_dotend}.items()}
