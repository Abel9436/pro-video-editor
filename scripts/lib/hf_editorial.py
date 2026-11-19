"""Editorial motion kit for HyperFrames (2026-11-19): graphics built from the subject of the video, not
from a template. Written for a real-estate talking head, kept generic enough to reuse when the story fits.

Overlays (all times in frames, relative to the overlay's start; positions 0-1 of the frame):
  Lockup     layered type: a small lead word, one huge word (usually behind the speaker), a front tail
             line, or a script word that writes itself on.
  PhotoCard  a listing-style card: real photo, kicker, title, meta, a status pill that rolls through
             statuses, an optional ink stamp; swings in, can be flicked out.
  Track      a status track: nodes on a line, a dot travels from one status to the next.
  Fan        cards (offers, letters) fly in from different sides and settle into a fanned stack.
  Call       a phone-call pill that grows out of the top of the frame: calling... then a running timer.
  Orbit      a 3D ring of photo cards around the speaker. Use two overlays with the same timing:
             half "back" behind the matte, half "front" over it; the ring turns with CSS 3D, so the
             halves line up on every frame.
  Strikes    a short list whose items are struck through with a hand-drawn line on cue.
  Web        a constellation of contacts: points pop and link outward from a hub.
Captions: captions_whisper, small light words that come up one by one (the reference look for
lifestyle and property content); emphasis words switch to the display serif.

Motion rules (references/craft-motion-design.md, "Finish"): one lens (PERSP), moves never reverse,
nothing bounces, exits push or flick out instead of fading.
"""
from __future__ import annotations

import math
import random

from .hf_ae import esc
from .hf_design import Ctx, scene_file
from .hf_explainer import PERSP

SERIF, SANS, SCRIPT, CAPS = "'Bodoni Moda', Georgia, serif", "'Hanken Grotesk', sans-serif", "'Pinyon Script', cursive", "'Italiana', serif"


def _f(cx: Ctx) -> dict:
    b = cx.brand
    return {"serif": b.get("font_title", SERIF), "sans": b.get("font_body", SANS), "script": b.get("font_script", SCRIPT),
            "caps": b.get("font_meta", CAPS), "acc": b.get("accent", "#B9825A"), "ink": b.get("ink", "#1C1A17"),
            "paper": b.get("paper", "#F5F0E8")}


def _img(path: str) -> str:
    return path if path.startswith("assets/") else f"assets/images/{path}"


def _exit(cid: str, dur: float, how: str = "flick") -> list[str]:
    if how == "cut":
        return [f'tl.set("#{cid}-all", {{ opacity: 0 }}, {max(0, dur - 1 / 60):.3f});']
    if how == "flick":
        a = max(0.0, dur - 0.28)
        return [f'tl.to("#{cid}-all", {{ x: -260, rotation: -6, opacity: 0, filter: "blur(10px)", duration: 0.28, ease: "power3.in" }}, {a:.3f});']
    if how == "rise":
        a = max(0.0, dur - 0.3)
        return [f'tl.to("#{cid}-all", {{ yPercent: -6, opacity: 0, filter: "blur(12px)", duration: 0.3, ease: "power2.in" }}, {a:.3f});']
    raise ValueError(f"exit must be flick, rise or cut, not {how!r}")


# ------------------------------------------------------------------------------------------- Lockup
def ov_lockup(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """items [{t, role: lead|big|tail|script, at, y, x (default 0.5), size, color, alpha, italic, track (em),
    out}], exit flick|rise|cut. big: letters turn up on their baseline one after another (3D, no
    overshoot) and the word keeps a slow push; lead/tail slide in from the side; script writes on left to
    right."""
    F = _f(cx)
    rows, js = [], []
    for i, it in enumerate(p["items"]):
        role, at = it.get("role", "big"), cx.s(it.get("at", 0))
        size = it.get("size", {"big": 300, "lead": 54, "tail": 58, "script": 170}[role])
        col = it.get("color", "#ffffff")
        font = it.get("font", {"big": F["serif"], "lead": F["serif"], "tail": F["sans"], "script": F["script"]}[role])
        ital = "italic" if it.get("italic", role == "lead") else "normal"
        wt = it.get("weight", {"big": 400, "lead": 400, "tail": 500, "script": 400}[role])
        track = f"letter-spacing:{it.get('track', -0.02 if role == 'big' else 0.01)}em;"
        x = it.get("x", 0.5) * cx.W
        top = it["y"] * cx.H - size * 0.6
        style = (f"position:absolute;left:{x - 1500:.0f}px;width:3000px;top:{top:.0f}px;text-align:center;white-space:nowrap;"
                 f"font-family:{font};font-style:{ital};font-weight:{wt};font-size:{size}px;line-height:1.2;color:{col};{track}font-synthesis:none;")
        if role == "big":
            chars = "".join(f'<span class="{cid}-c{i}" style="display:inline-block">{esc(ch) if ch != " " else "&nbsp;"}</span>' for ch in it["t"])
            rows.append(f'<div id="{cid}-i{i}" style="{style}opacity:{it.get("alpha", 1)};text-shadow:0 18px 60px rgba(0,0,0,0.28)">'
                        f'<span id="{cid}-p{i}" style="display:inline-block">{chars}</span></div>')
            js.append(f'tl.fromTo(".{cid}-c{i}", {{ opacity: 0, yPercent: 55, rotationX: -80, transformPerspective: {PERSP}, transformOrigin: "50% 100%" }}, '
                      f'{{ opacity: 1, yPercent: 0, rotationX: 0, duration: 0.7, ease: "expo.out", stagger: 0.035 }}, {at:.3f});')
            js.append(f'tl.fromTo("#{cid}-p{i}", {{ scale: 1 }}, {{ scale: 1.05, duration: {max(0.2, dur - at):.3f}, ease: "none" }}, {at:.3f});')
        elif role == "script":
            rows.append(f'<div id="{cid}-i{i}" style="{style}text-shadow:0 8px 30px rgba(0,0,0,0.35)">{esc(it["t"])}</div>')
            js.append(f'tl.fromTo("#{cid}-i{i}", {{ clipPath: "inset(0% 100% 0% 0%)", y: 10 }}, '
                      f'{{ clipPath: "inset(0% 0% 0% 0%)", y: 0, duration: {it.get("write", 0.9)}, ease: "power2.inOut" }}, {at:.3f});')
        else:
            rows.append(f'<div id="{cid}-i{i}" style="{style}text-shadow:0 4px 18px rgba(0,0,0,0.45)">{esc(it["t"])}</div>')
            dx = -40 if role == "lead" else 40
            js.append(f'tl.fromTo("#{cid}-i{i}", {{ opacity: 0, x: {dx} }}, {{ opacity: 1, x: 0, duration: 0.55, ease: "expo.out" }}, {at:.3f});')
        if "out" in it:
            js.append(f'tl.to("#{cid}-i{i}", {{ opacity: 0, yPercent: -8, filter: "blur(10px)", duration: 0.22, ease: "power2.in" }}, {cx.s(it["out"]):.3f});')
    js.extend(_exit(cid, dur, p.get("exit", "rise")))
    return scene_file(cx, cid, cx.H, f"#{cid}-all {{ position:absolute; inset:0; }}", f'<div id="{cid}-all">{"".join(rows)}</div>', "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------- PhotoCard
def ov_photocard(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{img, x, y (card centre), w (px, default 520), tilt (deg), kicker, title, meta, statuses [{t, at,
    bg, fg}], stamp {t, at, color}, at (enter), from: right|left, exit flick|rise|cut}. The status pill
    rolls to the next status like a split-flap; the stamp lands with ink weight and the card takes the hit
    (a one-way dip, no bounce)."""
    F = _f(cx)
    w = p.get("w", 520)
    ph = w * 0.78
    x, y = p.get("x", 0.5) * cx.W, p.get("y", 0.5) * cx.H
    at = cx.s(p.get("at", 0))
    sts = p.get("statuses") or []
    pill = ""
    if sts:
        spans = "".join(f'<div class="{cid}-st" style="height:56px;line-height:56px;padding:0 26px;background:{s.get("bg", F["ink"])};color:{s.get("fg", "#fff")}">{esc(s["t"])}</div>' for s in sts)
        pill = (f'<div style="position:absolute;left:24px;top:24px;height:56px;overflow:hidden;border-radius:28px;'
                f'font:500 28px/1 {F["sans"]};letter-spacing:0.14em;box-shadow:0 8px 24px rgba(0,0,0,0.25)"><div id="{cid}-roll">{spans}</div></div>')
    stamp = ""
    if p.get("stamp"):
        st = p["stamp"]
        c = st.get("color", "#B3442E")
        stamp = (f'<div id="{cid}-stamp" style="position:absolute;left:50%;top:{ph * 0.5:.0f}px;width:{w * 0.86:.0f}px;margin-left:{-w * 0.43:.0f}px;margin-top:-62px;'
                 f'height:124px;display:flex;align-items:center;justify-content:center;border:8px double {c};border-radius:12px;color:{c};'
                 f'font:500 {st.get('size', 50)}px/1 {F["sans"]};letter-spacing:0.14em;white-space:nowrap;background:rgba(245,240,232,0.94);'
                 f'box-shadow:0 10px 30px rgba(0,0,0,0.25);opacity:0">{esc(st["t"])}</div>')
    body = (f'<div id="{cid}-all" style="position:absolute;left:{x - w / 2:.0f}px;top:{y - (ph + 230) / 2:.0f}px;width:{w}px">'
            f'<div id="{cid}-card" style="position:relative;width:{w}px;background:{F["paper"]};border-radius:26px;overflow:hidden;'
            f'box-shadow:0 40px 90px rgba(0,0,0,0.42),0 6px 18px rgba(0,0,0,0.2)">'
            f'<div style="position:relative;width:{w}px;height:{ph:.0f}px;background:url({_img(p["img"])}) center 30%/cover">{pill}{stamp}</div>'
            f'<div style="padding:26px 30px 30px">'
            f'<div style="font:400 30px/1 {F["caps"]};letter-spacing:0.26em;color:{F["acc"]}">{esc(p.get("kicker", ""))}</div>'
            f'<div style="margin-top:14px;font:400 60px/1.05 {F["serif"]};color:{F["ink"]}">{esc(p.get("title", ""))}</div>'
            f'<div style="margin-top:14px;font:300 26px/1.2 {F["sans"]};color:{F["ink"]};opacity:0.72">{esc(p.get("meta", ""))}</div>'
            f'</div></div></div>')
    sg = -1 if p.get("from", "right") == "left" else 1
    tilt = p.get("tilt", -4 * sg)
    js = [f'tl.fromTo("#{cid}-card", {{ x: {sg * 700}, rotationY: {sg * -42}, rotation: {tilt * 3}, opacity: 0, transformPerspective: {PERSP} }}, '
          f'{{ x: 0, rotationY: 0, rotation: {tilt}, opacity: 1, duration: 0.8, ease: "expo.out" }}, {at:.3f});',
          f'tl.fromTo("#{cid}-all", {{ y: 0 }}, {{ y: -26, duration: {max(0.2, dur - at):.3f}, ease: "sine.out" }}, {at:.3f});']
    for k, s in enumerate(sts[1:], 1):
        js.append(f'tl.to("#{cid}-roll", {{ y: {-56 * k}, duration: 0.42, ease: "expo.inOut" }}, {cx.s(s["at"]):.3f});')
    if p.get("stamp"):
        sa = cx.s(p["stamp"]["at"])
        js.append(f'tl.fromTo("#{cid}-stamp", {{ opacity: 0, scale: 1.9, rotation: -4 }}, {{ opacity: 1, scale: 1, rotation: -11, duration: 0.24, ease: "power4.in" }}, {sa:.3f});')
        js.append(f'tl.fromTo("#{cid}-card", {{ scale: 1 }}, {{ scale: 0.965, duration: 0.06, ease: "power2.out" }}, {sa + 0.24:.3f});')
        js.append(f'tl.to("#{cid}-card", {{ scale: 1, duration: 0.5, ease: "power3.out" }}, {sa + 0.30:.3f});')
    js.extend(_exit(cid, dur, p.get("exit", "flick")))
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# -------------------------------------------------------------------------------------------- Track
def ov_track(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{y, steps [{t, at}], w (px), at (enter), exit}. A glass bar with one node per status; the line
    fills and a lit dot travels to each node on its cue; the reached label turns from dim to full."""
    F = _f(cx)
    n = len(p["steps"])
    w = p.get("w", 900)
    x0, y = (cx.W - w) / 2, p.get("y", 0.12) * cx.H
    gap = (w - 120) / max(1, n - 1)
    nodes = "".join(f'<div style="position:absolute;left:{60 + k * gap - 11:.0f}px;top:58px;width:22px;height:22px;border-radius:50%;border:3px solid rgba(255,255,255,0.7)"></div>'
                    f'<div id="{cid}-l{k}" style="position:absolute;left:{60 + k * gap - 200:.0f}px;width:400px;top:100px;text-align:center;font:500 28px/1.1 {F["sans"]};'
                    f'letter-spacing:0.16em;color:#fff;opacity:0.4;white-space:nowrap">{esc(s["t"]).upper()}</div>' for k, s in enumerate(p["steps"]))
    body = (f'<div id="{cid}-all" style="position:absolute;left:{x0:.0f}px;top:{y - 70:.0f}px;width:{w}px;height:160px;border-radius:28px;'
            f'background:rgba(20,18,16,0.42);backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,0.18)">'
            f'<div style="position:absolute;left:60px;top:66px;width:{w - 120}px;height:6px;border-radius:3px;background:rgba(255,255,255,0.22)"></div>'
            f'<div id="{cid}-fill" style="position:absolute;left:60px;top:66px;width:{w - 120}px;height:6px;border-radius:3px;background:{F["acc"]};transform-origin:0 50%"></div>'
            f'{nodes}<div id="{cid}-dot" style="position:absolute;left:{60 - 17}px;top:52px;width:34px;height:34px;border-radius:50%;background:{F["acc"]};'
            f'box-shadow:0 0 0 8px rgba(255,255,255,0.14),0 0 30px {F["acc"]}"></div></div>')
    at = cx.s(p.get("at", 0))
    js = [f'tl.set("#{cid}-fill", {{ scaleX: 0 }}, 0);',
          f'tl.fromTo("#{cid}-all", {{ opacity: 0, y: -40, rotationX: 50, transformPerspective: {PERSP} }}, {{ opacity: 1, y: 0, rotationX: 0, duration: 0.6, ease: "expo.out" }}, {at:.3f});']
    for k, s in enumerate(p["steps"]):
        t = cx.s(s["at"])
        if k:
            js.append(f'tl.to("#{cid}-dot", {{ x: {k * gap:.1f}, duration: 0.5, ease: "expo.inOut" }}, {t - 0.12:.3f});')
            js.append(f'tl.to("#{cid}-fill", {{ scaleX: {k / max(1, n - 1):.4f}, duration: 0.5, ease: "expo.inOut" }}, {t - 0.12:.3f});')
        js.append(f'tl.to("#{cid}-l{k}", {{ opacity: 1, duration: 0.25 }}, {t:.3f});')
        if k:
            js.append(f'tl.to("#{cid}-l{k - 1}", {{ opacity: 0.55, duration: 0.25 }}, {t:.3f});')
    js.extend(_exit(cid, dur, p.get("exit", "rise")))
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- Fan
def ov_fan(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{x, y, cards [{t, sub, at}], w, exit}. Each card flies in from its own side and lands fanned
    over the last (rotation steps of 7 deg); a seal in the accent sits on the top card."""
    F = _f(cx)
    w = p.get("w", 380)
    h = w * 0.66
    x, y = p.get("x", 0.5) * cx.W, p.get("y", 0.5) * cx.H
    cards, js = [], []
    m = len(p["cards"])
    for k, c in enumerate(p["cards"]):
        rot = (k - (m - 1) / 2) * 7
        cards.append(f'<div id="{cid}-k{k}" style="position:absolute;left:{x - w / 2:.0f}px;top:{y - h / 2 + k * -10:.0f}px;width:{w}px;height:{h:.0f}px;border-radius:18px;'
                     f'background:{F["paper"]};box-shadow:0 26px 60px rgba(0,0,0,0.38);transform-origin:50% 120%" data-layout-allow-overlap>'
                     f'<div style="position:absolute;left:28px;top:26px;font:400 28px/1 {F["caps"]};letter-spacing:0.24em;color:{F["acc"]}">{esc(c.get("sub", "PURCHASE AGREEMENT"))}</div>'
                     f'<div style="position:absolute;left:28px;top:62px;font:italic 400 54px/1 {F["serif"]};color:{F["ink"]}">{esc(c["t"])}</div>'
                     + "".join(f'<div style="position:absolute;left:28px;top:{h - 78 + j * 22:.0f}px;width:{(w - 120) * (1 - j * 0.3):.0f}px;height:5px;border-radius:3px;background:{F["ink"]};opacity:0.18"></div>' for j in range(3))
                     + f'<div style="position:absolute;right:26px;bottom:24px;width:62px;height:62px;border-radius:50%;background:{F["acc"]};box-shadow:inset 0 0 0 6px rgba(255,255,255,0.25)"></div></div>')
        sx = [-1, 1, -0.4, 0.6][k % 4] * 900
        sy = [200, -300, 700, 500][k % 4]
        js.append(f'tl.fromTo("#{cid}-k{k}", {{ x: {sx:.0f}, y: {sy}, rotation: {rot - 40 * (1 if sx > 0 else -1):.1f}, opacity: 0 }}, '
                  f'{{ x: 0, y: 0, rotation: {rot:.1f}, opacity: 1, duration: 0.6, ease: "expo.out" }}, {cx.s(c["at"]):.3f});')
    js.append(f'tl.fromTo("#{cid}-all", {{ y: 0 }}, {{ y: -20, duration: {dur:.3f}, ease: "sine.out" }}, 0);')
    js.extend(_exit(cid, dur, p.get("exit", "flick")))
    return scene_file(cx, cid, cx.H, "", f'<div id="{cid}-all" style="position:absolute;inset:0">{"".join(cards)}</div>', "\n".join(js), transparent=True)


# --------------------------------------------------------------------------------------------- Call
def ov_call(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{y, who, at (pill drops in), connect (frames: 'calling...' becomes a running timer), exit}. A dark
    pill grows out of the top edge and widens into a call bar; bars of a voice level move while
    connected (a fixed pattern on the timeline, not random)."""
    F = _f(cx)
    y = p.get("y", 0.075) * cx.H
    W = 860
    at, con = cx.s(p.get("at", 0)), cx.s(p.get("connect", p.get("at", 0) + 24))
    bars = "".join(f'<i class="{cid}-b" style="display:inline-block;width:7px;height:44px;margin:0 3px;border-radius:4px;background:#4BD07A;transform-origin:50% 50%"></i>' for _ in range(6))
    phone = ('<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8.1 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.8 2z"/></svg>')
    body = (f'<div id="{cid}-all" style="position:absolute;left:{(cx.W - W) / 2:.0f}px;top:{y:.0f}px;width:{W}px;height:150px">'
            f'<div id="{cid}-pill" style="position:absolute;inset:0;border-radius:75px;background:#0B0B0C;box-shadow:0 24px 60px rgba(0,0,0,0.45);overflow:hidden">'
            f'<div id="{cid}-in" style="position:absolute;inset:0;opacity:0">'
            f'<div style="position:absolute;left:28px;top:27px;width:96px;height:96px;border-radius:50%;background:{F["acc"]};display:flex;align-items:center;justify-content:center">{phone}</div>'
            f'<div style="position:absolute;left:150px;top:34px;font:500 38px/1 {F["sans"]};color:#fff">{esc(p.get("who", "Listing agent"))}</div>'
            f'<div style="position:absolute;left:150px;top:86px;font:300 30px/1 {F["sans"]};color:rgba(255,255,255,0.62)">'
            f'<span id="{cid}-calling">calling…</span><span id="{cid}-tm" style="position:absolute;left:0;top:0;opacity:0;color:#4BD07A">00:00</span></div>'
            f'<div style="position:absolute;right:44px;top:53px">{bars}</div></div></div></div>')
    js = [f'tl.set("#{cid}-in .{cid}-b", {{ scaleY: 0.25 }}, 0);',
          f'tl.fromTo("#{cid}-pill", {{ scaleX: 0.26, scaleY: 0.42, y: -110 }}, {{ scaleX: 0.26, scaleY: 0.42, y: 0, duration: 0.35, ease: "expo.out" }}, {at:.3f});',
          f'tl.to("#{cid}-pill", {{ scaleX: 1, scaleY: 1, duration: 0.55, ease: "expo.out" }}, {at + 0.3:.3f});',
          f'tl.to("#{cid}-in", {{ opacity: 1, duration: 0.3 }}, {at + 0.55:.3f});',
          f'tl.set("#{cid}-calling", {{ opacity: 0 }}, {con:.3f});',
          f'tl.set("#{cid}-tm", {{ opacity: 1 }}, {con:.3f});']
    secs = int(max(0, dur - (con - 0)))
    for s in range(1, secs + 1):
        js.append(f'tl.set("#{cid}-tm", {{ textContent: "00:{s:02d}" }}, {con + s:.3f});')
    for k in range(6):          # a fixed voice-level pattern while connected
        pat = [0.9, 0.4, 0.75, 0.3, 1.0, 0.5, 0.65][k % 7]
        js.append(f'tl.fromTo("#{cid}-in .{cid}-b:nth-child({k + 1})", {{ scaleY: 0.25 }}, {{ scaleY: {pat}, duration: {0.18 + 0.03 * k:.2f}, ease: "sine.inOut", '
                  f'repeat: {max(1, int((dur - con) / (0.18 + 0.03 * k)) - 1)}, yoyo: true }}, {con:.3f});')
    a = max(0.0, dur - 0.4)
    js.append(f'tl.to("#{cid}-in", {{ opacity: 0, duration: 0.15 }}, {a:.3f});')
    js.append(f'tl.to("#{cid}-pill", {{ scaleX: 0.26, scaleY: 0.42, duration: 0.25, ease: "power3.in" }}, {a + 0.05:.3f});')
    js.append(f'tl.to("#{cid}-pill", {{ y: -120, duration: 0.12, ease: "power2.in" }}, {a + 0.28:.3f});')
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# -------------------------------------------------------------------------------------------- Orbit
def ov_orbit(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{images [..], half: back|front, y (ring centre), r (px), card (px wide), tilt (deg), spin (deg over
    the overlay), at (enter), dark (0-1, back half only)}. The ring is a CSS 3D group turned by GSAP;
    each card sits at its angle on the ring. The front half shows a card's face only while it faces the
    lens; the back half shows the reverse face only, so the matte puts the speaker between them."""
    imgs = p["images"]
    n = len(imgs)
    r, cw = p.get("r", 460), p.get("card", 300)
    ch = cw * 1.25
    y = p.get("y", 0.42) * cx.H
    half = p.get("half", "front")
    if half not in ("front", "back"):
        raise ValueError("Orbit half must be front or back")
    cards = []
    for k, im in enumerate(imgs):
        a = k * 360 / n
        face = (f'<div style="position:absolute;inset:0;border-radius:22px;background:url({_img(im)}) center 30%/cover;'
                f'box-shadow:0 30px 70px rgba(0,0,0,0.45);border:3px solid rgba(255,255,255,0.85);backface-visibility:hidden;'
                f'{"transform:rotateY(180deg);" if half == "back" else ""}"></div>')
        cards.append(f'<div style="position:absolute;left:{-cw / 2:.0f}px;top:{-ch / 2:.0f}px;width:{cw}px;height:{ch:.0f}px;transform-style:preserve-3d;'
                     f'transform:rotateY({a:.2f}deg) translateZ({r}px)">{face}</div>')
    dark = f"filter:brightness({1 - p.get('dark', 0.25):.2f});" if half == "back" else ""
    body = (f'<div id="{cid}-all" style="position:absolute;inset:0;perspective:{PERSP}px;perspective-origin:50% {y:.0f}px;{dark}">'
            f'<div id="{cid}-tilt" style="position:absolute;left:{cx.W / 2:.0f}px;top:{y:.0f}px;transform-style:preserve-3d;transform:rotateX({-p.get("tilt", 8)}deg)">'
            f'<div id="{cid}-ring" style="position:absolute;left:0;top:0;transform-style:preserve-3d">{"".join(cards)}</div></div></div>')
    at = cx.s(p.get("at", 0))
    spin = p.get("spin", 140)
    js = [f'tl.fromTo("#{cid}-ring", {{ rotationY: {p.get("start", -40)} }}, {{ rotationY: {p.get("start", -40) + spin}, duration: {max(0.2, dur):.3f}, ease: "none" }}, 0);',
          f'tl.fromTo("#{cid}-all", {{ opacity: 0, scale: 0.6 }}, {{ opacity: 1, scale: 1, duration: 0.8, ease: "expo.out" }}, {at:.3f});']
    js.extend(_exit(cid, dur, p.get("exit", "rise")))
    return scene_file(cx, cid, cx.H, "", body, "\n".join(js), transparent=True)


# ------------------------------------------------------------------------------------------ Strikes
def ov_strikes(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{y, items [{t, at, strikeAt}], size, gap, exit}. Display-serif italic lines; a hand-drawn stroke
    in the accent crosses each out on cue and the word drops back."""
    F = _f(cx)
    size, gap = p.get("size", 96), p.get("gap", 1.25)
    rows, js = [], []
    for k, it in enumerate(p["items"]):
        top = p.get("y", 0.6) * cx.H + k * size * gap
        wpx = len(it["t"]) * size * 0.46 + 60
        rows.append(f'<div id="{cid}-r{k}" style="position:absolute;left:0;width:{cx.W}px;top:{top - size * 0.6:.0f}px;text-align:center">'
                    f'<span style="position:relative;display:inline-block;font:italic 400 {size}px/1.2 {F["serif"]};color:#fff;text-shadow:0 6px 28px rgba(0,0,0,0.45)">{esc(it["t"])}'
                    f'<svg style="position:absolute;left:-30px;top:{size * 0.18:.0f}px;overflow:visible" width="{wpx:.0f}" height="{size:.0f}" viewBox="0 0 100 20" preserveAspectRatio="none">'
                    f'<path id="{cid}-s{k}" d="M2 13 C 25 9, 45 12, 62 9 S 90 8, 98 6" pathLength="1" fill="none" stroke="{F["acc"]}" stroke-width="2.6" '
                    f'stroke-linecap="round" vector-effect="non-scaling-stroke" style="stroke-width:{max(6, size * 0.09):.0f}px;stroke-dasharray:1.1;stroke-dashoffset:1.1"/></svg></span></div>')
        js.append(f'tl.fromTo("#{cid}-r{k}", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "expo.out" }}, {cx.s(it["at"]):.3f});')
        if "strikeAt" in it:
            sa = cx.s(it["strikeAt"])
            js.append(f'tl.to("#{cid}-s{k}", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 0.32, ease: "power2.inOut" }}, {sa:.3f});')
            js.append(f'tl.to("#{cid}-r{k}", {{ opacity: 0.55, duration: 0.3 }}, {sa + 0.25:.3f});')
    js.extend(_exit(cid, dur, p.get("exit", "rise")))
    return scene_file(cx, cid, cx.H, "", f'<div id="{cid}-all" style="position:absolute;inset:0">{"".join(rows)}</div>', "\n".join(js), transparent=True)


# ---------------------------------------------------------------------------------------------- Web
def ov_web(cx: Ctx, cid: str, dur: float, p: dict) -> str:
    """{hub [x, y], n, box [x0, y0, x1, y1] (0-1), at, over (s for the web to grow), seed, exit}. Points
    are seeded; each links to its nearest earlier point, so the web grows outward from the hub."""
    F = _f(cx)
    rng = random.Random(p.get("seed", 7))
    x0, y0, x1, y1 = p.get("box", [0.04, 0.08, 0.96, 0.62])
    hub = p.get("hub", [0.5, 0.3])
    pts = [(hub[0] * cx.W, hub[1] * cx.H)]
    while len(pts) < p.get("n", 26):
        q = (rng.uniform(x0, x1) * cx.W, rng.uniform(y0, y1) * cx.H)
        if min(math.dist(q, o) for o in pts) > 110:
            pts.append(q)
    order = sorted(range(1, len(pts)), key=lambda i: math.dist(pts[i], pts[0]))
    seq = [0] + order
    lines, dots, js = [], [], []
    at, over = cx.s(p.get("at", 0)), p.get("over", 1.6)
    for rank, i in enumerate(seq):
        t = at + over * rank / len(seq)
        rr = 9 if i else 16
        dots.append(f'<circle id="{cid}-d{i}" cx="{pts[i][0]:.0f}" cy="{pts[i][1]:.0f}" r="{rr}" fill="{F["acc"] if i == 0 else "#fff"}" opacity="0"/>')
        js.append(f'tl.fromTo("#{cid}-d{i}", {{ opacity: 0, scale: 0, transformOrigin: "50% 50%" }}, {{ opacity: 0.95, scale: 1, duration: 0.35, ease: "expo.out" }}, {t:.3f});')
        if rank:
            prev = [seq[j] for j in range(rank)]
            links = sorted(prev, key=lambda j: math.dist(pts[i], pts[j]))[:2]
            for j in links:
                lid = f"{cid}-l{i}-{j}"
                lines.append(f'<line id="{lid}" x1="{pts[j][0]:.0f}" y1="{pts[j][1]:.0f}" x2="{pts[i][0]:.0f}" y2="{pts[i][1]:.0f}" pathLength="1" '
                             f'stroke="rgba(255,255,255,0.55)" stroke-width="3" stroke-dasharray="1.1" stroke-dashoffset="1.1"/>')
                js.append(f'tl.to("#{lid}", {{ attr: {{ "stroke-dashoffset": 0 }}, duration: 0.4, ease: "power2.out" }}, {t - 0.12:.3f});')
    svg = f'<svg width="{cx.W}" height="{cx.H}" style="position:absolute;left:0;top:0;filter:drop-shadow(0 0 10px rgba(255,255,255,0.35))">{"".join(lines)}{"".join(dots)}</svg>'
    js.append(f'tl.fromTo("#{cid}-all", {{ scale: 1 }}, {{ scale: 1.06, duration: {dur:.3f}, ease: "none", transformOrigin: "{hub[0] * 100:.0f}% {hub[1] * 100:.0f}%" }}, 0);')
    js.extend(_exit(cid, dur, p.get("exit", "rise")))
    return scene_file(cx, cid, cx.H, "", f'<div id="{cid}-all" style="position:absolute;inset:0">{svg}</div>', "\n".join(js), transparent=True)


# ----------------------------------------------------------------------------------------- captions
WHISPER_WORD_S = 0.32     # STARTING DEFAULT: each word's rise


def captions_whisper(cx: Ctx, caps: list[dict], ys: list[float], size: float, font: str | None = None, font_emph: str | None = None) -> str:
    """Small, light captions: each word rises 14 px and fades up as it is spoken (no blur, no colour
    flash); emphasis words switch to the italic display serif at 1.18x. One phrase on screen at a time."""
    f1, f2 = font or SANS, font_emph or SERIF
    groups, js = [], []
    for gi, (g, y) in enumerate(zip(caps, ys)):
        s_, e_ = cx.s(g["s"]), cx.s(g["e"])
        if gi + 1 < len(caps):
            e_ = min(e_, cx.s(caps[gi + 1]["s"]))
        spans = "".join(f'<span id="cw{gi}w{wi}" class="{"e" if w["emph"] else "w"}">{esc(w["w"])}</span> ' for wi, w in enumerate(g["words"]))
        groups.append(f'<div id="cw{gi}" class="cg" style="top:{y * cx.H:.0f}px">{spans}</div>')
        js.append(f'tl.set("#cw{gi}", {{ visibility: "visible" }}, {s_:.3f});')
        for wi, w in enumerate(g["words"]):
            t0 = max(s_, cx.s(w["s"]) - 1 / cx.fps)
            js.append(f'tl.fromTo("#cw{gi}w{wi}", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: {WHISPER_WORD_S}, ease: "power3.out" }}, {t0:.3f});')
        js.append(f'tl.set("#cw{gi}", {{ visibility: "hidden" }}, {e_:.3f});')
    css = f"""#capw {{ position: absolute; inset: 0; }}
#capw .cg {{ position: absolute; left: 80px; right: 80px; transform: translateY(-50%); text-align: center; visibility: hidden; line-height: 1.25; text-wrap: balance; }}
#capw span {{ display: inline-block; opacity: 0; font-synthesis: none; margin: 0 0.13em; }}
#capw .w {{ font-family: {f1}; font-weight: 300; font-size: {size}px; color: #fff; letter-spacing: 0.01em;
  text-shadow: 0 2px 4px rgba(0,0,0,0.35), 0 6px 26px rgba(0,0,0,0.4); }}
#capw .e {{ font-family: {f2}; font-style: italic; font-weight: 400; font-size: {size * 1.18:.1f}px; color: #fff;
  text-shadow: 0 2px 4px rgba(0,0,0,0.35), 0 6px 26px rgba(0,0,0,0.4); }}"""
    return scene_file(cx, "captions", cx.H, css, f'<div id="capw">{"".join(groups)}</div>', "\n".join(js), transparent=True)


OVERLAYS = {"Lockup": ov_lockup, "PhotoCard": ov_photocard, "Track": ov_track, "Fan": ov_fan, "Call": ov_call,
            "Orbit": ov_orbit, "Strikes": ov_strikes, "Web": ov_web}
