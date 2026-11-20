#!/usr/bin/env python3
"""Text on walls: track a flat surface in moving footage and render words that stay on it.

Usage:
  python scripts/wall_text.py SPEC.json [--only ID ...] [--preview] [--still ID:SEC]

SPEC (all times in SOURCE seconds; corners as fractions of the source frame, at the ref time):
  {"video": "footage/clip.mp4", "out_dir": "P/objects", "out_w": 1080, "out_h": 1920,
   "matte": "P/track/fg_src.webm",              # optional alpha matte of the person (scripts/matte.py)
   "fonts": "P/fonts",
   "items": [{"id": "master", "s": 44.0, "e": 47.5, "ref": 45.0,
              "quad": [[x, y], [x, y], [x, y], [x, y]],   # TL, TR, BR, BL of the wall area the text fills
              "lines": [{"t": "MASTER", "font": "BodoniModa-VF.ttf", "h": 0.55, "color": "#F3EBDD", "track": 0.12},
                        {"t": "ማስተር ቤድሩም", "font": "fontet-brana-0.ttf", "h": 0.3, "color": "#C9A25E"}],
              "align": "center"|"left", "reveal": "letters"|"wipe"|"fade", "in": 0.2, "dur": 0.7, "out": 0.3,
              "opacity": 0.94, "shadow": 0.35}]}

How it works: frames are decoded at source size; features (Shi-Tomasi) inside the wall area, never on the
person (the matte, dilated), are tracked frame to frame with pyramidal Lucas-Kanade, forward and backward
from `ref`. Each step is a RANSAC homography (similarity when fewer than 10 points survive); steps are
chained into ref->t, the four corners are smoothed over time (centred moving average, 5 frames, STARTING
DEFAULT), and the text, laid out in its own wall-space canvas, is warped onto the output frame. The person
is NOT cut out here: place the result as a `Plate` overlay with `behind: true` and the design pass's matte
puts the speaker in front of the wall.

Writes P/objects/wall_<id>.webm (VP9 yuva420p, 30 fps, one frame per source frame from s to e) and prints
JSON with per-item track quality: points kept, median forward-backward error (px) and the share of frames
that fell back to similarity. --preview also writes P/objects/wall_<id>_check.mp4 (text over the source with
the tracked quad drawn) for a person to judge the track. --still renders one frame to a PNG and stops.
Fails with {"ok": false, "error"} and exit 1.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

SMOOTH = 5          # frames, centred moving average on the corner tracks (STARTING DEFAULT)
MIN_PTS = 10        # below this, a step falls back to a similarity transform (STARTING DEFAULT)
CANVAS_W = 1600     # wall-space canvas width in px; height follows the quad's aspect


def fail(msg: str) -> None:
    print(json.dumps({"ok": False, "error": msg}))
    sys.exit(1)


def _ff() -> str:
    f = shutil.which("ffmpeg")
    if not f:
        fail("ffmpeg not found on PATH")
    return f


def probe(video: Path) -> tuple[int, int, float]:
    fp = shutil.which("ffprobe")
    r = subprocess.run([fp, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                        "-of", "json", str(video)], capture_output=True, text=True)
    s = json.loads(r.stdout)["streams"][0]
    a, b = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(a) / float(b)


def read_frames(video: Path, s: float, n: int, w: int, h: int, alpha: bool = False) -> np.ndarray:
    """n frames from time s, gray (or alpha of a VP9 alpha webm) at w x h."""
    args = [_ff(), "-v", "error"]
    if alpha:
        args += ["-c:v", "libvpx-vp9"]
    args += ["-ss", f"{s:.4f}", "-i", str(video), "-frames:v", str(n), "-vf", f"scale={w}:{h}",
             "-pix_fmt", "rgba" if alpha else "gray", "-f", "rawvideo", "-"]
    r = subprocess.run(args, capture_output=True)
    if r.returncode != 0:
        fail(f"decode failed for {video}: {r.stderr.decode()[-300:]}")
    ch = 4 if alpha else 1
    x = np.frombuffer(r.stdout, np.uint8)
    k = x.size // (w * h * ch)
    x = x[: k * w * h * ch].reshape(k, h, w, ch)
    return x[..., 3] if alpha else x[..., 0]


def _region(quad: np.ndarray, w: int, h: int, grow: float = 1.7) -> np.ndarray:
    import cv2
    c = quad.mean(0)
    q = (quad - c) * grow + c
    m = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(m, q.astype(np.int32), 255)
    return m


def track(gray: np.ndarray, person: np.ndarray | None, ref_i: int, quad0: np.ndarray) -> tuple[np.ndarray, dict]:
    """Corners of the quad in every frame (n x 4 x 2, source px) and quality stats."""
    import cv2
    n, h, w = gray.shape
    H = [None] * n
    H[ref_i] = np.eye(3)
    kept, fb_err, fallback = [], [], 0
    lk = dict(winSize=(21, 21), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))

    def mask_at(i, Hi):
        q = cv2.perspectiveTransform(quad0.reshape(-1, 1, 2), Hi).reshape(4, 2)
        m = _region(q, w, h)
        if person is not None:
            pm = cv2.dilate((person[i] > 60).astype(np.uint8) * 255, np.ones((25, 25), np.uint8))
            m[pm > 0] = 0
        return m

    for step in (1, -1):
        rng = range(ref_i + step, n if step == 1 else -1, step)
        prev_i = ref_i
        pts = cv2.goodFeaturesToTrack(gray[ref_i], 300, 0.005, 6, mask=mask_at(ref_i, H[ref_i]))
        for i in rng:
            Hp = H[prev_i]
            if pts is None or len(pts) < 30:
                pts = cv2.goodFeaturesToTrack(gray[prev_i], 300, 0.005, 6, mask=mask_at(prev_i, Hp))
            if pts is None or len(pts) < 4:
                H[i] = Hp
                fallback += 1
                prev_i = i
                continue
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(gray[prev_i], gray[i], pts, None, **lk)
            back, st2, _ = cv2.calcOpticalFlowPyrLK(gray[i], gray[prev_i], nxt, None, **lk)
            err = np.linalg.norm((back - pts).reshape(-1, 2), axis=1)
            good = (st.ravel() == 1) & (st2.ravel() == 1) & (err < 1.0)
            p0, p1 = pts[good].reshape(-1, 2), nxt[good].reshape(-1, 2)
            if len(p0):
                fb_err.append(float(np.median(err[good])))
            step_h = None
            if len(p0) >= MIN_PTS:
                step_h, inl = cv2.findHomography(p0, p1, cv2.RANSAC, 2.0)
                if step_h is not None and inl is not None and inl.sum() < MIN_PTS:
                    step_h = None
            if step_h is None and len(p0) >= 3:
                A, _ = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=2.0)
                if A is not None:
                    step_h = np.vstack([A, [0, 0, 1]])
                    fallback += 1
            if step_h is None:
                step_h = np.eye(3)
                fallback += 1
            H[i] = step_h @ Hp
            kept.append(len(p0))
            pts = p1.reshape(-1, 1, 2).astype(np.float32)
            prev_i = i
    corners = np.stack([cv2.perspectiveTransform(quad0.reshape(-1, 1, 2), Hi).reshape(4, 2) for Hi in H])
    if n >= SMOOTH:
        k = SMOOTH // 2
        # point-reflect the ends (2*c0 - c1..ck) so steady motion is not dragged back at the span's edges
        pad = np.concatenate([2 * corners[:1] - corners[1:k + 1][::-1], corners, 2 * corners[-1:] - corners[-k - 1:-1][::-1]])
        corners = np.stack([pad[i:i + SMOOTH].mean(0) for i in range(n)])
    stats = {"frames": n, "median_points": int(np.median(kept)) if kept else 0,
             "median_fb_error_px": round(float(np.median(fb_err)), 3) if fb_err else None,
             "fallback_share": round(fallback / max(1, n - 1), 3)}
    return corners, stats


def valid_range(corners: np.ndarray, ref_i: int, w: int, h: int) -> tuple[int, int]:
    """The contiguous frames around ref where the track is believable: the quad stays convex, its area within
    0.4-2.5x of the ref quad (STARTING DEFAULTS) and its centre within the frame grown by half on each side.
    Outside it the surface has left the shot or the homography has blown up, so the text must be gone."""
    import cv2

    def ok(q):
        if not cv2.isContourConvex(q.astype(np.float32).reshape(-1, 1, 2)):
            return False
        a = cv2.contourArea(q.astype(np.float32))
        c = q.mean(0)
        return 0.4 <= a / a0 <= 2.5 and -0.5 * w <= c[0] <= 1.5 * w and -0.5 * h <= c[1] <= 1.5 * h
    a0 = max(1.0, cv2.contourArea(corners[ref_i].astype(np.float32)))
    lo = hi = ref_i
    while lo - 1 >= 0 and ok(corners[lo - 1]):
        lo -= 1
    while hi + 1 < len(corners) and ok(corners[hi + 1]):
        hi += 1
    return lo, hi


def _hex(c: str, a: float = 1.0) -> tuple[int, int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(255 * a)


def layout(item: dict, fonts: Path, cw: int, ch: int):
    """Glyph runs for each line: list of (char, x, y, font, color, line_index). Lines fill the canvas height
    by their `h` share; each is scaled to fit the width."""
    from PIL import ImageFont
    out = []
    total_h = sum(l.get("h", 1 / len(item["lines"])) for l in item["lines"])
    y = 0.0
    for li, l in enumerate(item["lines"]):
        lh = ch * l.get("h", 1 / len(item["lines"])) / total_h
        size = int(lh * 0.86)
        font = ImageFont.truetype(str(fonts / l["font"]), size)
        tr = l.get("track", 0.0) * size
        widths = [font.getlength(c) for c in l["t"]]
        tw = sum(widths) + tr * (len(widths) - 1)
        if tw > cw * 0.98:
            size = int(size * cw * 0.98 / tw)
            font = ImageFont.truetype(str(fonts / l["font"]), size)
            tr = l.get("track", 0.0) * size
            widths = [font.getlength(c) for c in l["t"]]
            tw = sum(widths) + tr * (len(widths) - 1)
        x = (cw - tw) / 2 if item.get("align", "center") == "center" else 0
        for c, wd in zip(l["t"], widths):
            out.append((c, x, y + (lh - size) / 2, font, l.get("color", "#FFFFFF"), li))
            x += wd + tr
        y += lh
    return out


def render_text(glyphs, cw: int, ch: int, t: float, item: dict):
    """The wall-space RGBA canvas at time t (s since the item's start)."""
    from PIL import Image, ImageDraw, ImageFilter
    t_in, dur, t_out = item.get("in", 0.15), item.get("dur", 0.7), item.get("out", 0.3)
    span = item["e"] - item["s"]
    out_k = 1.0 if t < span - t_out else max(0.0, (span - t) / t_out)
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    n = max(1, len(glyphs))
    rev = item.get("reveal", "letters")
    for gi, (c, x, y, font, col, li) in enumerate(glyphs):
        if rev == "letters":
            st = t_in + dur * 0.6 * gi / n
            k = min(1.0, max(0.0, (t - st) / (dur * 0.4)))
        else:
            k = min(1.0, max(0.0, (t - t_in) / dur))
        k = 1 - (1 - k) ** 3                    # ease out cubic
        if k <= 0:
            continue
        dy = (1 - k) * font.size * 0.35
        d.text((x, y + dy), c, font=font, fill=_hex(col, k * out_k * item.get("opacity", 0.94)))
    if rev == "wipe":
        k = min(1.0, max(0.0, (t - t_in) / dur))
        a = np.array(img)
        a[:, int(cw * (1 - (1 - k) ** 3)):, 3] = 0
        img = Image.fromarray(a)
    sh = item.get("shadow", 0.35)
    if sh:
        al = np.array(img)[..., 3].astype(np.float32)
        sh_img = Image.fromarray((al * sh).astype(np.uint8)).filter(ImageFilter.GaussianBlur(ch * 0.012))
        base = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dark = Image.new("RGBA", (cw, ch), (20, 16, 10, 255))
        off = int(ch * 0.018)
        base.paste(dark, (off, off), sh_img)
        base.alpha_composite(img)
        img = base
    return img


def render_item(item: dict, spec: dict, base: Path, preview: bool, still: float | None = None) -> dict:
    import cv2
    video = base / spec["video"]
    sw, sh, fps = probe(video)
    ow, oh = spec.get("out_w", 1080), spec.get("out_h", 1920)
    n = int(round((item["e"] - item["s"]) * fps))
    gray = read_frames(video, item["s"], n, sw, sh)
    n = len(gray)
    person = read_frames(base / spec["matte"], item["s"], n, sw, sh, alpha=True) if spec.get("matte") else None
    if person is not None and len(person) < n:
        person = None
    ref_i = int(round((item["ref"] - item["s"]) * fps))
    ref_i = min(max(0, ref_i), n - 1)
    quad0 = np.array(item["quad"], np.float32) * [sw, sh]
    corners, stats = track(gray, person, ref_i, quad0)
    qw = np.linalg.norm(quad0[1] - quad0[0])
    qh = np.linalg.norm(quad0[3] - quad0[0])
    cw, ch = CANVAS_W, max(40, int(CANVAS_W * qh / max(qw, 1)))
    glyphs = layout(item, base / spec["fonts"], cw, ch)
    lo, hi = valid_range(corners, ref_i, sw, sh)
    stats["valid_s"] = [round(item["s"] + lo / fps, 3), round(item["s"] + hi / fps, 3)]
    shown = dict(item, e=item["s"] + (hi - lo) / fps)          # reveal and fade-out run inside the valid stretch
    src = np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]])
    k = np.float32([ow / sw, oh / sh])
    out_dir = base / spec["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = [int(round((still - item["s"]) * fps))] if still is not None else range(n)
    tmp = Path(tempfile.mkdtemp(prefix=f"wall_{item['id']}_"))
    for i in frames:
        if not lo <= i <= hi:
            cv2.imwrite(str(tmp / f"f_{i:05d}.png"), np.zeros((oh, ow, 4), np.uint8))
            continue
        txt = np.array(render_text(glyphs, cw, ch, (i - lo) / fps, shown))
        M = cv2.getPerspectiveTransform(src, (corners[i] * k).astype(np.float32))
        rgba = cv2.warpPerspective(txt, M, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        cv2.imwrite(str(tmp / f"f_{i:05d}.png"), cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    if still is not None:
        dst = out_dir / f"wall_{item['id']}_still.png"
        shutil.move(str(tmp / f"f_{frames[0]:05d}.png"), dst)
        shutil.rmtree(tmp, ignore_errors=True)
        return {"id": item["id"], "still": dst.as_posix(), **stats}
    webm = out_dir / f"wall_{item['id']}.webm"
    r = subprocess.run([_ff(), "-v", "error", "-y", "-framerate", f"{fps}", "-i", str(tmp / "f_%05d.png"), "-c:v", "libvpx-vp9",
                        "-pix_fmt", "yuva420p", "-crf", "28", "-b:v", "0", "-row-mt", "1", "-auto-alt-ref", "0", str(webm)], capture_output=True)
    if r.returncode != 0:
        fail(f"encode failed: {r.stderr.decode()[-300:]}")
    res = {"id": item["id"], "webm": webm.as_posix(), **stats}
    if preview:
        # text over the source with the tracked quad outlined, so a person can judge whether it sticks
        chk = out_dir / f"wall_{item['id']}_check.mp4"
        src_rgb = read_frames(video, item["s"], n, ow, oh, alpha=False)
        pngs = sorted(tmp.glob("f_*.png"))
        vw = cv2.VideoWriter(str(chk), cv2.VideoWriter_fourcc(*"mp4v"), fps, (ow, oh))
        for i, pth in enumerate(pngs):
            base_im = cv2.cvtColor(src_rgb[i], cv2.COLOR_GRAY2BGR).astype(np.float32)
            ov = cv2.imread(str(pth), cv2.IMREAD_UNCHANGED).astype(np.float32)
            a_ = ov[..., 3:4] / 255.0
            fr = (base_im * (1 - a_) + ov[..., :3] * a_).astype(np.uint8)
            cv2.polylines(fr, [(corners[i] * k).astype(np.int32)], True, (0, 0, 255), 2)
            vw.write(fr)
        vw.release()
        res["check"] = chk.as_posix()
    shutil.rmtree(tmp, ignore_errors=True)
    return res


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--still", help="ID:SEC (source seconds): render one frame of one item to a PNG")
    a = ap.parse_args(argv)
    if not a.spec.exists():
        fail(f"{a.spec} not found")
    try:
        import cv2  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as e:
        fail(f"needs opencv-python and Pillow: {e}")
    spec = json.loads(a.spec.read_text(encoding="utf-8"))
    base = a.spec.parent if not spec.get("base") else Path(spec["base"])
    items = spec["items"]
    for it in items:
        for k in ("id", "s", "e", "ref", "quad", "lines"):
            if k not in it:
                fail(f"item {it.get('id', '?')} lacks {k}")
        if not it["s"] <= it["ref"] <= it["e"]:
            fail(f"item {it['id']}: ref must lie between s and e")
    if a.still:
        iid, sec = a.still.split(":")
        it = next((i for i in items if i["id"] == iid), None)
        if not it:
            fail(f"no item {iid}")
        print(json.dumps({"ok": True, "items": [render_item(it, spec, base, False, float(sec))]}, ensure_ascii=False, indent=1))
        return
    done = [render_item(it, spec, base, a.preview) for it in items if not a.only or it["id"] in a.only]
    print(json.dumps({"ok": True, "items": done}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
