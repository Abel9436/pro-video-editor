"""Before/after showcase video for a finished edit (2026-11-17).

Usage:
  python scripts/before_after.py --edl P/edl/v4.json --project P --after P/exports/v4.mp4 \
      --script-font PATH/TO/script.ttf [--out P/exports/v4_before_after.mp4] [--before-color bw|color]

Layout (vertical 1080x1920): a warm amber set; on the left a small "Before" card tilted in 3D holding
the raw source footage cut exactly like the edit (the EDL's video track replayed from the proxies:
same in points, speed and freezes, no grade, no reframe, no graphics), on the right a larger "After"
card with the finished video, neon handwritten "Before" / "After" labels, and below an editing
timeline in perspective drawn from the EDL itself (graphics lanes, captions, the picture track with
thumbnails, SFX, dialogue and music with the real waveform) with a playhead that runs with the video.
The sound is the finished video's.

--script-font: any handwritten font you are licensed to use (e.g. Mrs Saint Delafield, SIL OFL, from
github.com/google/fonts). Nothing is downloaded by this script and no font ships with the skill.

Prints JSON {"ok", "out", "duration_s", "events"}; exits 1 with {"ok": false, "error"} on failure.
Layout numbers are STARTING DEFAULTS measured by eye from a reference before/after reel.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
# boxes: x, y, w, h and the card's quad as fractions of its box (tl, tr, bl, br) -> 3D tilt
AFTER = dict(x=392, y=205, w=590, h=1048, r=34, q=[(0, 0), (1, 0.025), (0, 1), (1, 0.975)])
BEFORE = dict(x=70, y=455, w=336, h=672, r=26, q=[(0, 0), (1, 0.065), (0, 1), (1, 0.935)])
TL = dict(x=18, y=1318, w=1044, h=500, r=22, q=[(0.06, 0), (0.94, 0), (0, 1), (1, 1)])
FW, FH = 1600, 766          # flat timeline panel, scaled into TL then tilted
HDR, TOOL, RULER = 128, 46, 30
UI_FONT = ["C:/Windows/Fonts/segoeui.ttf", "/System/Library/Fonts/SFNS.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError(f"{cmd[0]} failed: {p.stderr[-1500:]}")


def ui_font(size: int) -> ImageFont.FreeTypeFont:
    for f in UI_FONT:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def quad(b: dict) -> list[tuple[float, float]]:
    return [(fx * b["w"], fy * b["h"]) for fx, fy in b["q"]]


def persp_coeffs(dst: list[tuple[float, float]], src: list[tuple[float, float]]) -> list[float]:
    """PIL PERSPECTIVE coefficients mapping output (dst quad) back to input (src rect)."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        B += [u, v]
    return list(np.linalg.solve(np.array(A, float), np.array(B, float)))


def card_mask(b: dict) -> Image.Image:
    w, h = b["w"], b["h"]
    m = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], radius=b["r"] * 2, fill=255)
    m = m.resize((w, h), Image.LANCZOS)
    src = [(0, 0), (w, 0), (0, h), (w, h)]
    return m.transform((w, h), Image.PERSPECTIVE, persp_coeffs(quad(b), src), Image.BICUBIC)


def persp_arg(b: dict) -> str:
    q = quad(b)
    return ":".join(f"{v:.1f}" for pt in q for v in pt) + ":sense=destination"


# ---------------------------------------------------------------------------------------- set + labels
def background(path: Path) -> None:
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W * 0.5) / W) ** 2 + ((yy - H * 0.2) / (H * 0.9)) ** 2)
    k = np.clip(1 - d / 0.95, 0, 1) ** 1.4
    top, edge = np.array([168, 112, 22], np.float32), np.array([30, 19, 6], np.float32)
    img = edge + (top - edge) * k[..., None]
    img *= (1 - 0.35 * np.clip((yy - H * 0.62) / (H * 0.38), 0, 1))[..., None]
    rng = np.random.default_rng(7)
    img += rng.normal(0, 2.2, img.shape[:2])[..., None]
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    sh = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(sh)
    for b, a, off in ((TL, 150, 26), (BEFORE, 190, 34), (AFTER, 210, 42)):
        pts = [(b["x"] + x, b["y"] + y + off) for x, y in quad(b)]
        dr.polygon([pts[0], pts[1], pts[3], pts[2]], fill=a)
    sh = sh.filter(ImageFilter.GaussianBlur(38))
    im.alpha_composite(Image.merge("RGBA", (Image.new("L", (W, H), 0),) * 3 + (sh,)))
    im.convert("RGB").save(path)


def neon(text: str, font: ImageFont.FreeTypeFont, rot: float) -> Image.Image:
    bbox = font.getbbox(text)
    tw, th = bbox[2] - bbox[0] + 160, bbox[3] - bbox[1] + 160
    core = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(core).text((80 - bbox[0], 80 - bbox[1]), text, font=font, fill=255)
    out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    for rad, col, gain in ((24, (255, 214, 150), 0.7), (9, (255, 245, 225), 1.0), (2.5, (255, 255, 255), 1.0)):
        g = core.filter(ImageFilter.GaussianBlur(rad)).point(lambda v, k=gain: min(255, int(v * k * 2.2)))
        out.alpha_composite(Image.merge("RGBA", (*(Image.new("L", (tw, th), c) for c in col), g)))
    out.alpha_composite(Image.merge("RGBA", (*(Image.new("L", (tw, th), 255),) * 3, core)))
    return out.rotate(rot, resample=Image.BICUBIC, expand=True)


def labels(path: Path, font_path: str) -> None:
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for text, size, cx, cy, rot in (("Before", 118, 236, 440, 6), ("After", 158, 690, 160, 4)):
        n = neon(text, ImageFont.truetype(font_path, size), rot)
        im.alpha_composite(n, (int(cx - n.width / 2), int(cy - n.height / 2)))
    im.save(path)


# ---------------------------------------------------------------------------------------- timeline
def waveform(after: Path, cols: int) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(after), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
    a = np.abs(np.frombuffer(p.stdout, np.int16).astype(np.float32)) if p.stdout else np.zeros(cols)
    chunks = np.array_split(a, cols)
    env = np.array([c.max() if len(c) else 0 for c in chunks])
    return env / max(1.0, env.max())


def thumbs(after: Path, times: list[float], h: int, tmp: Path) -> list[Image.Image]:
    out = []
    for i, t in enumerate(times):
        f = tmp / f"th{i}.png"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(after), "-frames:v", "1", "-vf", f"scale=-2:{h}", str(f)])
        out.append(Image.open(f).convert("RGB"))
    return out


def lanes(items: list[tuple[float, float, str]]) -> list[list[tuple[float, float, str]]]:
    rows: list[list] = []
    for it in sorted(items):
        for r in rows:
            if r[-1][1] <= it[0]:
                r.append(it)
                break
        else:
            rows.append([it])
    return rows


def panel(e: dict, after: Path, total_f: int, path: Path, tmp: Path) -> tuple[float, float]:
    """Draw the flat timeline; returns (x0, x1) of the time axis in panel pixels."""
    im = Image.new("RGB", (FW, FH), (21, 23, 28))
    d = ImageDraw.Draw(im)
    f11, f13 = ui_font(13), ui_font(15)
    fps = int(round(float(e["project"]["fps"])))
    x0, x1 = HDR + 8, FW - 18
    X = lambda f: x0 + (x1 - x0) * f / max(1, total_f)  # noqa: E731
    # toolbar
    d.rectangle([0, 0, FW, TOOL], fill=(28, 31, 37))
    for i in range(9):
        d.rounded_rectangle([18 + i * 34, 14, 36 + i * 34, 32], 4, outline=(120, 126, 138), width=2)
    for i in range(3):
        d.ellipse([FW // 2 - 50 + i * 36, 13, FW // 2 - 30 + i * 36, 33], outline=(90, 200, 220), width=2)
    for i in range(6):
        d.rounded_rectangle([FW - 230 + i * 34, 15, FW - 212 + i * 34, 31], 4, fill=(58, 190, 210) if i < 2 else (70, 74, 84))
    # ruler
    d.rectangle([0, TOOL, FW, TOOL + RULER], fill=(25, 27, 33))
    step = max(1, round(total_f / fps / 10))
    for s in range(0, int(total_f / fps) + 1):
        x = X(s * fps)
        big = s % step == 0
        d.line([x, TOOL + RULER - (14 if big else 6), x, TOOL + RULER], fill=(110, 116, 128), width=1)
        if big:
            d.text((x + 4, TOOL + 3), f"00:00:{s:02d}:00", font=f11, fill=(140, 146, 158))
    T = e["tracks"]
    des = e.get("design") or {}
    gfx = [(o["s"], o["e"], o["type"]) for o in des.get("overlays", [])] + [(s["s"], s["e"], s["type"]) for s in des.get("scenes", [])]
    gfx += [(g["at_f"], g["at_f"] + g["dur_f"], g.get("component", "Title")) for g in T.get("graphics") or []]
    gfx += [(b["at_f"], b["at_f"] + b["dur_f"], "B-roll") for b in T.get("broll") or []]
    gfx += [(x["at"] - 6, x["at"] + 8, x["type"]) for x in des.get("fx", [])]
    sfx = [(s["at_f"], s["at_f"] + s.get("dur_f", 14), Path(s["asset"]).stem[:14]) for s in T.get("sfx") or []]
    rows: list[tuple[str, list, tuple]] = []
    pal = [(140, 92, 230), (230, 120, 60), (60, 170, 150), (210, 70, 110), (90, 130, 230)]
    for i, ln in enumerate(lanes(gfx)[:5][::-1]):
        rows.append(("gfx", ln, pal[i % len(pal)]))
    rows.append(("cap", [], (232, 196, 40)))
    rows.append(("vid", [], (40, 150, 170)))
    for ln in lanes(sfx)[:2]:
        rows.append(("sfx", ln, (60, 150, 235)))
    rows += [("dia", [], (52, 110, 200)), ("mus", [], (40, 160, 95))]
    top, bot = TOOL + RULER + 10, FH - 12
    heights = {"gfx": 34, "cap": 26, "vid": 70, "sfx": 26, "dia": 54, "mus": 46}
    scale = (bot - top - 4 * len(rows)) / sum(heights[k] for k, _, _ in rows)
    y = top
    wf = waveform(after, int(x1 - x0))
    V = sorted(T["video"], key=lambda v: v["at_f"])
    for kind, items, col in rows:
        h = max(14, int(heights[kind] * scale))
        d.rectangle([0, y, HDR, y + h], fill=(28, 30, 36))
        d.rounded_rectangle([12, y + h / 2 - 6, 24, y + h / 2 + 6], 3, outline=(120, 126, 138), width=2)
        d.rectangle([HDR, y + h + 1, FW, y + h + 2], fill=(30, 33, 39))
        if kind in ("gfx", "sfx"):
            for s, en, name in items:
                d.rounded_rectangle([X(s), y + 2, max(X(s) + 6, X(en) - 1), y + h - 2], 4, fill=tuple(int(c * 0.55) for c in col), outline=col, width=2)
                d.text((X(s) + 6, y + 3), name, font=f11, fill=(235, 238, 245))
        elif kind == "cap":
            spans = []                                     # caption cards: dialogue cut into ~1 s phrases
            for v in T.get("dialogue") or []:
                s0, s1 = v["at_f"], v["at_f"] + v["out_f"] - v["in_f"]
                for s in range(s0, s1, fps):
                    spans.append((s, min(s1, s + fps - 3)))
            for s, en in spans:
                d.rounded_rectangle([X(s), y + 3, max(X(s) + 4, X(en) - 2), y + h - 3], 3, fill=(120, 100, 20), outline=col, width=1)
        elif kind == "vid":
            ends = [v["at_f"] for v in V[1:]] + [total_f]
            ths = thumbs(after, [((v["at_f"] + en) / 2) / fps for v, en in zip(V, ends)], h - 4, tmp)
            for v, en, th in zip(V, ends, ths):
                a, b = int(X(v["at_f"])), int(X(en))
                clip = Image.new("RGB", (max(4, b - a - 2), h - 4), (20, 60, 70))
                for k in range(0, clip.width, th.width):
                    clip.paste(th, (k, 0))
                im.paste(clip, (a + 1, y + 2))
                d.rectangle([a + 1, y + 2, b - 1, y + h - 2], outline=col, width=2)
                d.rectangle([a + 1, y + 2, min(b - 1, a + 110), y + 18], fill=(15, 70, 80))
                d.text((a + 5, y + 2), f"{v['src'][:12]}.mp4", font=f11, fill=(225, 240, 245))
        else:
            spans = [(v["at_f"], v["at_f"] + v["out_f"] - v["in_f"]) for v in T.get("dialogue") or []] if kind == "dia" else \
                    [(m["at_f"], m["at_f"] + m["dur_f"]) for m in T.get("music") or []]
            for s, en in spans:
                a, b = int(X(s)), int(X(min(en, total_f)))
                d.rounded_rectangle([a, y + 2, max(a + 4, b - 1), y + h - 2], 4, fill=tuple(int(c * 0.5) for c in col), outline=col, width=2)
                mid, amp = y + h / 2, (h - 10) / 2
                for xx in range(a + 2, b - 2, 2):
                    v_ = wf[min(len(wf) - 1, xx - int(x0))] * (0.55 if kind == "mus" else 1.0)
                    d.line([xx, mid - amp * v_, xx, mid + amp * v_], fill=(170, 210, 255) if kind == "dia" else (150, 235, 180))
            d.text((6 + 30, y + 2), "A1" if kind == "dia" else "A2", font=f13, fill=(150, 156, 168))
        y += h + 4
    im.save(path)
    return x0, x1


# ---------------------------------------------------------------------------------------- before footage
def before_video(e: dict, project: Path, total_f: int, out: Path, color: str) -> int:
    fps = int(round(float(e["project"]["fps"])))
    media = json.loads((project / "media.json").read_text(encoding="utf-8"))
    paths = {it["id"]: it["path"] for it in media.get("items", [])}
    V = sorted(e["tracks"]["video"], key=lambda v: v["at_f"])
    ins, fl, segs = [], [], []
    for i, v in enumerate(V):
        end = V[i + 1]["at_f"] if i + 1 < len(V) else total_f
        n = max(1, end - v["at_f"])
        src = project / "proxies" / f"{v['src']}.mp4"
        src = src if src.exists() else Path(paths[v["src"]])
        ins += ["-ss", f"{v['in_f'] / fps:.4f}", "-i", str(src)]
        sp = float(v.get("speed") or 1.0)
        fl.append(f"[{i}:v]fps={fps},setpts=(PTS-STARTPTS)/{sp},tpad=stop_mode=clone:stop_duration=60,trim=end_frame={n},setpts=PTS-STARTPTS,"
                  f"scale=540:960:force_original_aspect_ratio=increase,crop=540:960,setsar=1[s{i}]")
        segs.append(f"[s{i}]")
    look = "hue=s=0,eq=contrast=0.92:brightness=-0.02" if color == "bw" else "eq=saturation=1"
    fl.append(f"{''.join(segs)}concat=n={len(segs)}:v=1:a=0,{look},format=yuv420p[v]")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fl), "-map", "[v]", "-r", str(fps),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    return len(V)


# ---------------------------------------------------------------------------------------- compose
def compose(after: Path, tmp: Path, out: Path, fps: int, dur: float, x0: float, x1: float) -> None:
    sx = TL["w"] / FW
    ph_top, ph_h = int(TOOL * TL["h"] / FH), int(TL["h"] * (1 - TOOL / FH)) - 4
    px0, pw = x0 * sx, (x1 - x0) * sx
    loop = lambda p: ["-framerate", str(fps), "-loop", "1", "-i", str(p)]  # noqa: E731
    ins = [*loop(tmp / "bg.png"), "-i", str(tmp / "before.mp4"), "-i", str(after), *loop(tmp / "panel.png"),
           *loop(tmp / "mA.png"), *loop(tmp / "mB.png"), *loop(tmp / "mT.png"), *loop(tmp / "fg.png"), *loop(tmp / "ph.png")]
    A, B = AFTER, BEFORE
    fc = [
        f"[1:v]scale={B['w']}:{B['h']}:force_original_aspect_ratio=increase,crop={B['w']}:{B['h']},perspective={persp_arg(B)},format=rgba[b0]",
        "[5:v]format=gray[mb]", "[b0][mb]alphamerge[b]",
        f"[2:v]scale={A['w']}:{A['h']}:force_original_aspect_ratio=increase,crop={A['w']}:{A['h']},perspective={persp_arg(A)},format=rgba[a0]",
        "[4:v]format=gray[ma]", "[a0][ma]alphamerge[a]",
        f"[3:v]scale={TL['w']}:{TL['h']},format=rgba[tp]",
        f"[tp][8:v]overlay=x='{px0 - 7:.1f}+{pw:.1f}*min(1,t/{dur:.3f})':y={ph_top}:eval=frame,perspective={persp_arg(TL)},format=rgba[t0]",
        "[6:v]format=gray[mt]", "[t0][mt]alphamerge[t]",
        f"[0:v][t]overlay={TL['x']}:{TL['y']}[c1]", f"[c1][b]overlay={B['x']}:{B['y']}[c2]", f"[c2][a]overlay={A['x']}:{A['y']}[c3]",
        f"[c3][7:v]overlay=0:0,fade=in:st=0:d=0.45,format=yuv420p[v]",
    ]
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "2:a?", "-t", f"{dur:.3f}",
         "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--after", required=True, help="the finished video")
    ap.add_argument("--script-font", required=True, help="handwritten font for the neon labels (a licensed .ttf/.otf)")
    ap.add_argument("--out")
    ap.add_argument("--before-color", choices=["bw", "color"], default="bw")
    a = ap.parse_args()
    try:
        project, after = Path(a.project), Path(a.after)
        e = json.loads(Path(a.edl).read_text(encoding="utf-8"))
        fps = int(round(float(e["project"]["fps"])))
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(after)],
                                   capture_output=True, text=True).stdout.strip())
        total_f = round(dur * fps)
        out = Path(a.out) if a.out else after.with_name(after.stem + "_before_after.mp4")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            n = before_video(e, project, total_f, tmp / "before.mp4", a.before_color)
            background(tmp / "bg.png")
            labels(tmp / "fg.png", a.script_font)
            for b, name in ((AFTER, "mA"), (BEFORE, "mB"), (TL, "mT")):
                card_mask(b).save(tmp / f"{name}.png")
            x0, x1 = panel(e, after, total_f, tmp / "panel.png", tmp)
            ph_h = int(TL["h"] * (1 - TOOL / FH)) - 4
            ph = Image.new("RGBA", (15, ph_h), (0, 0, 0, 0))
            dph = ImageDraw.Draw(ph)
            dph.rectangle([6, 0, 8, ph_h], fill=(255, 255, 255, 240))
            dph.polygon([(0, 0), (14, 0), (14, 8), (7, 14), (0, 8)], fill=(255, 255, 255, 245))
            ph.save(tmp / "ph.png")
            compose(after, tmp, out, fps, dur, x0, x1)
        print(json.dumps({"ok": True, "out": str(out), "duration_s": round(dur, 2), "events": n}, ensure_ascii=False))
        return 0
    except Exception as ex:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(ex)[-2000:]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
