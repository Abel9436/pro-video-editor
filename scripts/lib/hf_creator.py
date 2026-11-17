"""Creator-style captions without the machine tells (2026-11-17).

caption_style "pop": the whole phrase enters as one unit (one short rise, no per-word blur), the word
being spoken lights up in the accent with a small overshoot and hands the light to the next word,
emphasis words (rationed: lib/restraint.py) sit in a serif in the accent, the phrase leaves on a hard
cut. Soft shadow, no box, no outline. Fonts: design.caption_font / caption_font_emph, defaults below;
they must be in the project's fonts.css (fetch_fonts.py) unless HyperFrames bundles them."""
from __future__ import annotations

FONT_POP = "'Noto Sans Ethiopic', 'Montserrat', sans-serif"
FONT_POP_EMPH = "'Noto Serif Ethiopic', 'Noto Sans Ethiopic', serif"
ENTER_F = 5            # STARTING DEFAULT: frames for the phrase rise
LIGHT_F = 6            # STARTING DEFAULT: frames for the active-word overshoot
ACTIVE_SCALE = 1.08    # STARTING DEFAULT
DIM = "rgba(255,255,255,0.62)"   # STARTING DEFAULT: words not being spoken


def captions_pop(cx, caps: list[dict], ys: list[float], size: float, font: str | None = None, font_emph: str | None = None) -> str:
    from .hf_ae import esc
    from .hf_design import scene_file
    a = cx.brand.get("accent", "#FF4438")
    fr = 1 / cx.fps
    groups, js = [], []
    for gi, (g, y) in enumerate(zip(caps, ys)):
        ws = g["words"]
        longest = sum(len(w["w"]) for w in ws) + len(ws)
        k = min(1.0, 940 / max(1.0, longest * 0.62 * size))
        spans = []
        for wi, w in enumerate(ws):
            cls = "e" if w["emph"] else "w"
            spans.append(f'<span id="cp{gi}w{wi}" class="{cls}">{esc(w["w"])}</span>')
        s_, e_ = cx.s(g["s"]), cx.s(g["e"])
        if gi + 1 < len(caps):                 # never two phrases on screen: the next one cuts this one off
            e_ = min(e_, cx.s(caps[gi + 1]["s"]))
        groups.append(f'<div id="cp{gi}" class="cg" style="top:{y * cx.H:.0f}px;font-size:{size * k:.1f}px"><div id="cp{gi}i" class="in">{" ".join(spans)}</div></div>')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "visible" }}, {s_:.3f});')
        js.append(f'tl.fromTo("#cp{gi}i", {{ opacity: 0, y: 22 }}, {{ opacity: 1, y: 0, duration: {ENTER_F * fr:.3f}, ease: "power3.out" }}, {s_:.3f});')
        for wi, w in enumerate(ws):
            t0 = max(s_, cx.s(w["s"]) - fr)
            t1 = cx.s(ws[wi + 1]["s"]) - fr if wi + 1 < len(ws) else e_
            on = "#ffffff" if not w["emph"] else a           # the spoken word comes up to full white; emphasis stays accent
            base = DIM if not w["emph"] else a
            js.append(f'tl.to("#cp{gi}w{wi}", {{ color: "{on}", scale: {ACTIVE_SCALE}, duration: {LIGHT_F * fr:.3f}, ease: "back.out(2.2)" }}, {t0:.3f});')
            if t1 < e_ - fr:
                js.append(f'tl.to("#cp{gi}w{wi}", {{ color: "{base}", scale: 1, duration: {4 * fr:.3f}, ease: "power2.out" }}, {t1:.3f});')
        js.append(f'tl.set("#cp{gi}", {{ visibility: "hidden" }}, {e_:.3f});')
    f1, f2 = font or FONT_POP, font_emph or FONT_POP_EMPH
    css = f"""#caps {{ position: absolute; inset: 0; }}
#caps .cg {{ position: absolute; left: 0; right: 0; transform: translateY(-50%); text-align: center; visibility: hidden; padding: 0 64px; }}
#caps .in {{ display: inline-block; max-width: 950px; line-height: 1.22; text-wrap: balance; }}
#caps span {{ display: inline-block; margin: 0 0.1em; font-synthesis: none; }}
#caps .w {{ font-family: {f1}; font-weight: 900; color: {DIM}; letter-spacing: -0.01em;
  text-shadow: 0 3px 3px rgba(0,0,0,0.35), 0 10px 34px rgba(0,0,0,0.45); }}
#caps .e {{ font-family: {f2}; font-weight: 900; color: {a}; font-size: 1.1em;
  text-shadow: 0 3px 3px rgba(0,0,0,0.35), 0 10px 34px rgba(0,0,0,0.45); }}"""
    return scene_file(cx, "captions", cx.H, css, f'<div id="caps">{"".join(groups)}</div>', "\n".join(js), transparent=True)
