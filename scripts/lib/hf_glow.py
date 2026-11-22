"""Glow type, glass lists and a follow card (2026-11-22), from a frame study of premium tech Shorts.

Measured on the references (the angt edit's refs_a/refs_b reports):
  - hero lines type on at one character a frame; each character arrives white-hot and blurred and settles
    to the accent in 3 frames (power2.out), with a 2-frame glyph decode on key words; a three-layer glow
    (6/18/48 px) and a soft radial spill behind the block light the body;
  - big words sit behind the speaker (overlay `behind: true`) and arrive through focus: blur 24 px and
    115 % scale to sharp over ~14 frames (expo.out), letters one frame apart;
  - list rows arrive the same way (blur + 40 px, 12 frames, expo.out), never bounce.
Every value marked STARTING DEFAULT is a reading of those references, not a measured optimum.

Overlays (frames are relative to the overlay's start):
  Hero     {lines: [{x, y, align, parts: [[text, "key"|"conn"|"white"], ...]}], at, size, conn_size,
            glow, font_key, font_conn, spill, exit_blink}
  Backdrop {t, y, size, font, weight, color, glow, at, track, in_f 14, sub: {t, size, font, italic, color, dy, at, above}}
  GlassList {x, y, w, row_h, gap, text_scale 0.36, rows: [{t, sub, icons: [path], mark: x|check|num|None, n, at,
             swap: [{at, mark}], dim: at}], title: {t, at, size 30}}
  Follow   {name, sub, avatar, y, at, cursor_at, click_at}
"""
from __future__ import annotations

import hashlib

from .hf_ae import esc
from .hf_design import Ctx, scene_file

GLOW = "#40FF97"
GLYPHS = "ABCDEFGHJKMNPQRSTUVWXYZ0123456789#%&@$"
DECODE_F = 2          # STARTING DEFAULT: frames of scrambled glyphs before a key character locks
SETTLE_F = 3          # STARTING DEFAULT: frames for a character to cool from white-hot to the accent
FONT_KEY = "'Plus Jakarta Sans', sans-serif"
FONT_CONN = "'Plus Jakarta Sans', sans-serif"


def _glow(c: str, k: float = 1.0) -> str:
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return (f"0 0 {6 * k:.0f}px {c}, 0 0 {18 * k:.0f}px rgba({r},{g},{b},0.75), 0 0 {48 * k:.0f}px rgba({r},{g},{b},0.5)")


def _seed(*a) -> int:
    return int(hashlib.md5("|".join(map(str, a)).encode()).hexdigest()[:8], 16)


def ov_hero(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    glow = p.get("glow", cx.brand.get("accent", GLOW))
    size, csize = p.get("size", 70), p.get("conn_size", 42)
    fk, fc = p.get("font_key", FONT_KEY), p.get("font_conn", FONT_CONN)
    t = cx.s(p.get("at", 0)) + 2 * fr
    rows, js, ci = [], [], 0
    for li, ln in enumerate(p["lines"]):
        spans = []
        for part, kind in ln["parts"]:
            key = kind == "key"
            col = glow if key else "#FFFFFF"
            fs = size if kind != "conn" else csize
            style = (f"font-family:{fk if kind != 'conn' else fc};font-weight:{800 if kind != 'conn' else 300};"
                     f"font-style:{'italic' if kind == 'conn' else 'normal'};font-size:{fs}px;color:{col};"
                     f"text-shadow:{_glow(col if key else '#FFFFFF', 1.0 if key else 0.55)}")
            for ch in part:
                if ch == " ":
                    spans.append(f'<span style="display:inline-block;width:{fs * 0.26:.0f}px"></span>')
                    continue
                cid_c = f"{cid}-c{ci}"
                dec = ""
                if key and ch.strip():
                    rnd = _seed(cid, ci)
                    for d in range(DECODE_F):
                        g = GLYPHS[(rnd >> (5 * d)) % len(GLYPHS)]
                        dec += f'<span id="{cid_c}d{d}" class="dc" style="{style};color:#FFFFFF">{esc(g)}</span>'
                        js.append(f'tl.set("#{cid_c}d{d}", {{ opacity: 1 }}, {t + d * fr:.3f});')
                        js.append(f'tl.set("#{cid_c}d{d}", {{ opacity: 0 }}, {t + (d + 1) * fr:.3f});')
                lock = t + (DECODE_F * fr if dec else 0)
                spans.append(f'<span class="ch" style="{style}"><span id="{cid_c}" class="rl">{esc(ch)}</span>{dec}</span>')
                js.append(f'tl.fromTo("#{cid_c}", {{ opacity: 0, filter: "blur(4px) brightness(3)", color: "#FFFFFF" }}, '
                          f'{{ opacity: 1, filter: "blur(0px) brightness(1)", color: "{col}", duration: {SETTLE_F * fr:.3f}, ease: "power2.out" }}, {lock:.3f});')
                t += fr
                ci += 1
            t += fr
        x = ln.get("x", 160)
        align = ln.get("align", "left")
        pos = (f"left:{x}px" if align == "left" else f"left:0;right:0;text-align:center")
        rows.append(f'<div class="ln" style="{pos};top:{ln["y"] * cx.H:.0f}px">{"".join(spans)}</div>')
    spill = ""
    if p.get("spill", True):
        y0 = min(l_["y"] for l_ in p["lines"]) * cx.H
        r_, g_, b_ = (int(glow[i:i + 2], 16) for i in (1, 3, 5))
        spill = (f'<div id="{cid}-sp" style="position:absolute;left:{cx.W / 2 - 520:.0f}px;top:{y0 - 260:.0f}px;width:1040px;height:760px;'
                 f'background:radial-gradient(closest-side, rgba({r_},{g_},{b_},0.16), transparent);mix-blend-mode:screen;opacity:0"></div>')
        js.append(f'tl.to("#{cid}-sp", {{ opacity: 1, duration: 0.3, ease: "sine.out" }}, {cx.s(p.get("at", 0)):.3f});')
    if p.get("exit_blink", True):
        js.append(f'tl.set("#{cid}-all", {{ opacity: 0.25 }}, {max(0, dur - 4 * fr):.3f});')
        js.append(f'tl.set("#{cid}-all", {{ opacity: 1 }}, {max(0, dur - 3 * fr):.3f});')
        js.append(f'tl.to("#{cid}-all", {{ opacity: 0, filter: "blur(8px)", duration: {2 * fr:.3f}, ease: "power2.in" }}, {max(0, dur - 2 * fr):.3f});')
    css = (f"#{cid}-all {{ position:absolute; inset:0; }} #{cid}-all .ln {{ position:absolute; white-space:nowrap; line-height:0.95; }} "
           f"#{cid}-all .ch {{ position:relative; display:inline-block; font-synthesis:none; }} "
           f"#{cid}-all .dc {{ position:absolute; left:0; top:0; opacity:0; }} #{cid}-all .rl {{ display:inline-block; opacity:0; }}")
    return scene_file(cx, cid, cx.H, css, f'<div id="{cid}-all">{spill}{"".join(rows)}</div>', "\n".join(js), transparent=True)


def ov_backdrop(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    at = cx.s(p.get("at", 0))
    col, size = p.get("color", "#FFFFFF"), p.get("size", 230)
    glow = p.get("glow")
    sh = f"text-shadow:{_glow(glow, 1.6)};" if glow else "text-shadow:0 20px 60px rgba(0,0,0,0.35);"
    chars = "".join(f'<span class="{cid}-c" style="display:inline-block">{esc(c) if c != " " else "&nbsp;"}</span>' for c in p["t"])
    rows = [f'<div id="{cid}-w" style="position:absolute;left:0;right:0;top:{p.get("y", 0.2) * cx.H - size * 0.55:.0f}px;text-align:center;'
            f'white-space:nowrap;font-family:{p.get("font", FONT_KEY)};font-weight:{p.get("weight", 800)};font-size:{size}px;line-height:1;'
            f'letter-spacing:{p.get("track", -0.03)}em;color:{col};{sh}font-synthesis:none">{chars}</div>']
    js = [f'tl.fromTo(".{cid}-c", {{ opacity: 0, filter: "blur(24px)", scale: 1.15 }}, {{ opacity: 1, filter: "blur(0px)", scale: 1, '
          f'duration: {p.get("in_f", 14) * fr:.3f}, ease: "expo.out", stagger: {fr:.4f} }}, {at:.3f});',
          f'tl.fromTo("#{cid}-w", {{ scale: 1 }}, {{ scale: 1.04, duration: {max(0.2, dur - at):.3f}, ease: "none" }}, {at:.3f});']
    sub = p.get("sub")
    if sub:
        ss = sub.get("size", 54)
        # above: true sets the line as a kicker over the word (clear of a head that sits under the word)
        s_top = (p.get("y", 0.2) * cx.H - size * 0.55 - ss * 1.15 - sub.get("dy", 10)) if sub.get("above") else             (p.get("y", 0.2) * cx.H + size * 0.5 + sub.get("dy", 10))
        rows.append(f'<div id="{cid}-s" style="position:absolute;left:0;right:0;top:{s_top:.0f}px;'
                    f'text-align:center;white-space:nowrap;font-family:{sub.get("font", FONT_CONN)};font-weight:{sub.get("weight", 300)};'
                    f'font-style:{"italic" if sub.get("italic", True) else "normal"};font-size:{ss}px;color:{sub.get("color", "#FFFFFF")};'
                    f'text-shadow:{_glow(sub.get("glow", "#FFFFFF"), 0.5)}">{esc(sub["t"])}</div>')
        js.append(f'tl.fromTo("#{cid}-s", {{ opacity: 0, filter: "blur(12px)", y: 14 }}, {{ opacity: 1, filter: "blur(0px)", y: 0, '
                  f'duration: {12 * fr:.3f}, ease: "expo.out" }}, {cx.s(sub.get("at", p.get("at", 0) + 8)):.3f});')
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, filter: "blur(14px)", scale: 1.06, duration: {8 * fr:.3f}, ease: "power2.in" }}, {max(0, dur - 8 * fr):.3f});')
    return scene_file(cx, cid, cx.H, f"#{cid}-all {{ position:absolute; inset:0; transform-origin:50% {p.get('y', 0.2) * 100:.0f}%; }}",
                      f'<div id="{cid}-all">{"".join(rows)}</div>', "\n".join(js), transparent=True)


def _mark_svg(rid: str, kind: str, col: str) -> str:
    if kind == "x":
        return (f'<svg id="{rid}" class="mk" viewBox="0 0 48 48"><circle cx="24" cy="24" r="21" fill="rgba(255,93,93,0.14)" stroke="rgba(255,93,93,0.55)" stroke-width="2"/>'
                f'<path d="M16 16 L32 32 M32 16 L16 32" stroke="#FF6B6B" stroke-width="4" stroke-linecap="round" fill="none" pathLength="1" stroke-dasharray="1.1" stroke-dashoffset="1.1"/></svg>')
    return (f'<svg id="{rid}" class="mk" viewBox="0 0 48 48"><circle cx="24" cy="24" r="21" fill="rgba(64,255,151,0.16)" stroke="{col}" stroke-width="2"/>'
            f'<path d="M14 25 L21 32 L34 17" stroke="{col}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round" fill="none" pathLength="1" stroke-dasharray="1.1" stroke-dashoffset="1.1"/></svg>')


def ov_glasslist(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    acc = cx.brand.get("accent", GLOW)
    x, y, w = p.get("x", 90), p.get("y", 0.1) * cx.H, p.get("w", 900)
    rh, gap = p.get("row_h", 104), p.get("gap", 18)
    ts = p.get("text_scale", 0.36)          # row text size as a share of row height
    rows, js = [], []
    top = y
    if p.get("title"):
        tt = p["title"]
        rows.append(f'<div id="{cid}-t" style="position:absolute;left:{x + 8}px;top:{top:.0f}px;font-family:{FONT_KEY};font-weight:800;font-size:{tt.get("size", 30)}px;'
                    f'letter-spacing:0.22em;color:{acc};text-shadow:{_glow(acc, 0.45)}">{esc(tt["t"])}</div>')
        js.append(f'tl.fromTo("#{cid}-t", {{ opacity: 0, filter: "blur(10px)", x: -20 }}, {{ opacity: 1, filter: "blur(0px)", x: 0, duration: {12 * fr:.3f}, ease: "expo.out" }}, {cx.s(tt.get("at", 0)):.3f});')
        top += tt.get("size", 30) * 2.05
    for i, r in enumerate(p["rows"]):
        rid = f"{cid}-r{i}"
        icons = "".join(f'<img src="{ic}" style="width:{rh * 0.62:.0f}px;height:{rh * 0.62:.0f}px;object-fit:contain;margin-right:10px;'
                        f'filter:drop-shadow(0 6px 14px rgba(0,0,0,0.45))"/>' for ic in r.get("icons", []))
        num = (f'<div style="font-family:{FONT_KEY};font-weight:800;font-size:{rh * ts:.0f}px;color:{acc};text-shadow:{_glow(acc, 0.5)};'
               f'width:{rh * 0.8:.0f}px">{r.get("n", f"{i + 1:02d}")}</div>') if r.get("mark") == "num" else ""
        sub = (f'<div style="font-family:{FONT_KEY};font-weight:600;font-size:{rh * ts * 0.62:.0f}px;color:rgba(255,255,255,0.66);margin-top:4px">{esc(r["sub"])}</div>'
               if r.get("sub") else "")
        mark = _mark_svg(f"{rid}m", r["mark"], acc) if r.get("mark") in ("x", "check") else ""
        swaps = "".join(_mark_svg(f"{rid}s{k}", s_["mark"], acc) for k, s_ in enumerate(r.get("swap", [])))
        rows.append(f'<div id="{rid}" class="row" style="left:{x}px;top:{top:.0f}px;width:{w}px;height:{rh}px">'
                    f'{num}{icons}<div style="flex:1;min-width:0"><div style="font-family:{FONT_KEY};font-weight:700;font-size:{rh * ts:.0f}px;color:#fff;'
                    f'white-space:nowrap">{esc(r["t"])}</div>{sub}</div><div class="mkw">{mark}{swaps}</div></div>')
        at = cx.s(r.get("at", 0))
        js.append(f'tl.fromTo("#{rid}", {{ opacity: 0, filter: "blur(12px)", x: -40 }}, {{ opacity: 1, filter: "blur(0px)", x: 0, duration: {12 * fr:.3f}, ease: "expo.out" }}, {at:.3f});')
        if mark:
            js.append(f'tl.to("#{rid}m path", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {7 * fr:.3f}, ease: "power2.out" }}, {at + 5 * fr:.3f});')
            js.append(f'tl.fromTo("#{rid}m", {{ scale: 0.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: {6 * fr:.3f}, ease: "back.out(2)" }}, {at + 4 * fr:.3f});')
        for k, s_ in enumerate(r.get("swap", [])):
            sa = cx.s(s_["at"])
            js.append(f'tl.to("#{rid}m", {{ opacity: 0, scale: 0.5, duration: {4 * fr:.3f}, ease: "power2.in" }}, {sa:.3f});')
            js.append(f'tl.fromTo("#{rid}s{k}", {{ opacity: 0, scale: 0.6 }}, {{ opacity: 1, scale: 1, duration: {6 * fr:.3f}, ease: "back.out(2)" }}, {sa + 3 * fr:.3f});')
            js.append(f'tl.to("#{rid}s{k} path", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: {7 * fr:.3f}, ease: "power2.out" }}, {sa + 4 * fr:.3f});')
            if s_["mark"] == "check":
                js.append(f'tl.to("#{rid}", {{ borderColor: "rgba(64,255,151,0.65)", boxShadow: "0 0 0 1px rgba(64,255,151,0.35), 0 0 40px rgba(64,255,151,0.25)", duration: {8 * fr:.3f}, ease: "power2.out" }}, {sa + 3 * fr:.3f});')
        if r.get("dim") is not None:
            js.append(f'tl.to("#{rid}", {{ opacity: 0.38, filter: "saturate(0.2)", duration: {8 * fr:.3f}, ease: "power2.out" }}, {cx.s(r["dim"]):.3f});')
        top += rh + gap
    js.append(f'tl.to("#{cid}-all", {{ opacity: 0, filter: "blur(12px)", y: -30, duration: {8 * fr:.3f}, ease: "power2.in" }}, {max(0, dur - 8 * fr):.3f});')
    css = (f"#{cid}-all {{ position:absolute; inset:0; }} #{cid}-all .row {{ position:absolute; display:flex; align-items:center; padding:0 30px; box-sizing:border-box; "
           f"border-radius:26px; background:linear-gradient(135deg, rgba(14,52,34,0.78), rgba(6,22,15,0.72)); border:1.5px solid rgba(64,255,151,0.20); "
           f"box-shadow:0 18px 50px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.10); backdrop-filter:blur(18px); }} "
           f"#{cid}-all .mkw {{ position:relative; width:{rh * 0.52:.0f}px; height:{rh * 0.52:.0f}px; }} "
           f"#{cid}-all .mk {{ position:absolute; inset:0; width:100%; height:100%; }}")
    return scene_file(cx, cid, cx.H, css, f'<div id="{cid}-all">{"".join(rows)}</div>', "\n".join(js), transparent=True)


CURSOR = ('<svg viewBox="0 0 28 28" width="84" height="84"><path d="M5 3 L5 23 L10.5 17.8 L14.2 26 L17.6 24.5 L13.9 16.5 L21 16.5 Z" '
          'fill="#FFFFFF" stroke="#0B0F0D" stroke-width="1.6" stroke-linejoin="round"/></svg>')


def ov_follow(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    fr = 1 / cx.fps
    acc = cx.brand.get("accent", GLOW)
    y = p.get("y", 0.2) * cx.H
    av = (f'<img src="{p["avatar"]}" style="width:118px;height:118px;border-radius:50%;object-fit:cover;border:3px solid {acc}"/>' if p.get("avatar") else
          f'<div style="width:118px;height:118px;border-radius:50%;background:radial-gradient(circle at 35% 30%, #2BD47D, #0F5132 70%);'
          f'border:3px solid {acc};box-shadow:{_glow(acc, 0.4).replace("0 0", "0 0", 1)}"></div>')
    body = (f'<div id="{cid}-card" class="card" style="top:{y:.0f}px">{av}<div style="flex:1;margin-left:26px;min-width:0">'
            f'<div style="font-family:{p.get("font_name", FONT_KEY)};font-weight:800;font-size:46px;color:#fff;white-space:nowrap">{esc(p["name"])}</div>'
            f'<div style="font-family:{FONT_KEY};font-weight:600;font-size:26px;color:rgba(255,255,255,0.6);margin-top:6px;white-space:nowrap">{esc(p.get("sub", ""))}</div></div>'
            f'<div id="{cid}-btn" class="btn"><span id="{cid}-b1">Follow</span><span id="{cid}-b2" style="position:absolute;inset:0;display:flex;'
            f'align-items:center;justify-content:center;opacity:0">Following ✓</span></div></div>'
            f'<div id="{cid}-cur" style="position:absolute;left:0;top:0;filter:drop-shadow(0 10px 18px rgba(0,0,0,0.5))">{CURSOR}</div>')
    at, ca, ck = cx.s(p.get("at", 0)), cx.s(p.get("cursor_at", 8)), cx.s(p.get("click_at", 24))
    bx, by = cx.W - 90 - 130, y + 66          # the button's centre
    js = [f'tl.fromTo("#{cid}-card", {{ opacity: 0, filter: "blur(14px)", y: 40, scale: 0.96 }}, {{ opacity: 1, filter: "blur(0px)", y: 0, scale: 1, duration: {14 * fr:.3f}, ease: "expo.out" }}, {at:.3f});',
          f'tl.fromTo("#{cid}-cur", {{ x: {cx.W + 60}, y: {by + 420:.0f}, opacity: 1 }}, {{ x: {bx - 6:.0f}, y: {by - 8:.0f}, duration: {max(0.2, ck - ca - 2 * fr):.3f}, ease: "power3.inOut" }}, {ca:.3f});',
          f'tl.to("#{cid}-cur", {{ scale: 0.84, duration: {2 * fr:.3f}, ease: "power2.in", transformOrigin: "10% 10%" }}, {ck - 2 * fr:.3f});',
          f'tl.to("#{cid}-cur", {{ scale: 1, duration: {5 * fr:.3f}, ease: "power2.out" }}, {ck:.3f});',
          f'tl.to("#{cid}-btn", {{ scale: 0.92, duration: {2 * fr:.3f}, ease: "power2.in" }}, {ck - 2 * fr:.3f});',
          f'tl.to("#{cid}-btn", {{ scale: 1, backgroundColor: "{acc}", color: "#04150C", boxShadow: "0 0 40px rgba(64,255,151,0.55)", duration: {8 * fr:.3f}, ease: "back.out(2)" }}, {ck:.3f});',
          f'tl.set("#{cid}-b1", {{ opacity: 0 }}, {ck:.3f});', f'tl.set("#{cid}-b2", {{ opacity: 1 }}, {ck:.3f});',
          f'tl.to("#{cid}-cur", {{ x: {bx + 160:.0f}, y: {by + 260:.0f}, opacity: 0, duration: {12 * fr:.3f}, ease: "power2.in" }}, {ck + 10 * fr:.3f});']
    css = (f"#{cid}-all {{ position:absolute; inset:0; }} #{cid}-all .card {{ position:absolute; left:70px; right:70px; height:150px; display:flex; align-items:center; "
           f"padding:0 26px; box-sizing:border-box; border-radius:40px; background:linear-gradient(135deg, rgba(14,52,34,0.82), rgba(6,22,15,0.78)); "
           f"border:1.5px solid rgba(64,255,151,0.25); box-shadow:0 24px 60px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1); backdrop-filter:blur(20px); }} "
           f"#{cid}-all .btn {{ position:relative; width:260px; height:84px; border-radius:42px; background:#FFFFFF; color:#04150C; display:flex; align-items:center; "
           f"justify-content:center; font-family:{FONT_KEY}; font-weight:800; font-size:32px; }}")
    return scene_file(cx, cid, cx.H, css, f'<div id="{cid}-all">{body}</div>', "\n".join(js), transparent=True)


OVERLAYS = {"Hero": ov_hero, "Backdrop": ov_backdrop, "GlassList": ov_glasslist, "Follow": ov_follow}
