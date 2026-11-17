#!/usr/bin/env python3
"""Watch a reference video frame by frame at 30 fps and list every editing event, so a viewer
(Claude) can study each one at full temporal resolution.

Usage:
  python scripts/deep_watch.py VIDEO --out-dir DIR [--fps 30] [--sheets events|full|none]

Every frame is measured in code (cuts, flashes, colour washes, black-and-white beats, blur
transitions, zoom pushes, whips, text appearing in the top / middle / bottom band) and every
audio hit is measured and given a sound class from its shape (whoosh, riser, impact, click/pop,
ding, swell). Classes from shape are guesses, labelled `class_guess`; a viewer confirms them.

Outputs in DIR:
  events.json        per-event list: frame, time, kind, measures; audio hits; per-second summary
  frames.json        the raw per-frame measures (for re-thresholding without re-decoding)
  strip_NNNN.png     (--sheets events) 30 fps strips: the 6 frames before to 17 after each event
  sheet_NNN.png      (--sheets full) every frame, 96 per sheet (12 x 8), labelled frame/second

The thresholds below are STARTING DEFAULTS tuned on the 2026-11-15 reference set (7 videos):
each flagged event in that set was checked on a strip; edit them if a new set looks different.
Reference videos are only measured. Nothing from them is copied into any output.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from lib.common import ToolError, fail, ffprobe_json, log, run, write_json  # noqa: E402

W_SMALL = 160
CUT_DIFF_Z = 6.0          # STARTING DEFAULT: frame difference this many MADs above the median = cut
FLASH_LUMA_JUMP = 45      # STARTING DEFAULT: mean luma rising this much within 3 frames = flash/overexpose
WHITE_FRAC = 0.45         # STARTING DEFAULT: share of near-white pixels in a flash frame
WASH_HUE_SAT = 110        # STARTING DEFAULT: mean saturation over this with one dominant hue = colour wash
BW_SAT = 14               # STARTING DEFAULT: mean saturation under this (between colourful frames) = B&W beat
BLUR_DROP = 0.35          # STARTING DEFAULT: sharpness under 35 % of the 1 s median = blur transition / defocus
ZOOM_STEP = 1.012         # STARTING DEFAULT: per-frame scale change over 1.2 % for 3+ frames = push
WHIP_SHIFT = 6.0          # same as fingerprint.WHIP_SHIFT_PCT
TEXT_EDGE_JUMP = 2.2      # STARTING DEFAULT: band edge density jumping 2.2x = text/graphic appearing
SFX_Z = 6.0               # STARTING DEFAULT: percussive onset strength this many MADs over the median = audio hit
STRIP_BEFORE, STRIP_AFTER = 6, 17
SHEET_COLS, SHEET_ROWS, TILE_W = 12, 8, 90


def frames(path: Path, fps: float, w: int):
    import subprocess
    pr = ffprobe_json(path)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    W, H = int(v["width"]), int(v["height"])
    h = int(round(H * w / W / 2)) * 2
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={fps},scale={w}:{h}:flags=area",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 3
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        p.stdout.close()
        p.wait()


def measure_frames(path: Path, fps: float) -> dict:
    import cv2
    keys = ["luma", "diff", "sat", "hue", "hue_conc", "white", "black", "sharp", "scale", "shx",
            "edge_top", "edge_mid", "edge_bot", "r", "g", "b"]
    m = {k: [] for k in keys}
    prev = None
    hann = None
    for fr in frames(path, fps, W_SMALL):
        g = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY)
        gf = g.astype(np.float32)
        hsv = cv2.cvtColor(fr, cv2.COLOR_RGB2HSV)
        m["luma"].append(float(g.mean()))
        m["sat"].append(float(hsv[..., 1].mean()))
        hh = hsv[..., 0][hsv[..., 1] > 60]
        if hh.size > 50:
            hist = np.bincount((hh // 15).astype(int), minlength=12)
            m["hue"].append(int(hist.argmax() * 15 * 2))          # OpenCV hue 0-180 -> degrees
            m["hue_conc"].append(float(hist.max() / hist.sum()))
        else:
            m["hue"].append(-1); m["hue_conc"].append(0.0)
        m["white"].append(float((g > 225).mean()))
        m["black"].append(float((g < 20).mean()))
        m["sharp"].append(float(cv2.Laplacian(g, cv2.CV_32F).var()))
        for c, k in zip(range(3), "rgb"):
            m[k].append(float(fr[..., c].mean()))
        ed = cv2.Canny(g, 80, 200) > 0
        t = ed.shape[0] // 3
        m["edge_top"].append(float(ed[:t].mean())); m["edge_mid"].append(float(ed[t:2 * t].mean()))
        m["edge_bot"].append(float(ed[2 * t:].mean()))
        if prev is None:
            m["diff"].append(0.0); m["scale"].append(1.0); m["shx"].append(0.0)
        else:
            m["diff"].append(float(np.abs(gf - prev).mean()))
            if hann is None:
                hann = cv2.createHanningWindow(g.shape[::-1], cv2.CV_32F)
            (dx, _), _ = cv2.phaseCorrelate(prev, gf, hann)
            m["shx"].append(dx / g.shape[1] * 100)
            m["scale"].append(_scale(prev.astype(np.uint8), g))
        prev = gf
    if not m["luma"]:
        raise ToolError(f"no frames decoded from {path}")
    return {k: np.array(v, dtype=float) for k, v in m.items()}


def _scale(a, b) -> float:
    import cv2
    pts = cv2.goodFeaturesToTrack(a, 80, 0.01, 6)
    if pts is None or len(pts) < 10:
        return 1.0
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(a, b, pts, None)
    ok = st.reshape(-1) == 1
    if ok.sum() < 8:
        return 1.0
    M, _ = cv2.estimateAffinePartial2D(pts[ok], nxt[ok])
    return 1.0 if M is None else float(np.hypot(M[0, 0], M[1, 0]))


def rolling_median(x: np.ndarray, k: int) -> np.ndarray:
    pad = np.pad(x, (k // 2, k // 2), mode="edge")
    return np.array([np.median(pad[i:i + k]) for i in range(len(x))])


def find_events(m: dict, fps: float) -> list[dict]:
    n = len(m["luma"])
    ev = []
    d = m["diff"]
    med = np.median(d); mad = np.median(np.abs(d - med)) + 1e-6
    for i in range(1, n):
        if (d[i] - med) / mad > CUT_DIFF_Z and d[i] >= max(d[max(0, i - 2):i + 3]):
            ev.append({"f": i, "kind": "cut", "diff": round(float(d[i]), 1)})
    L = m["luma"]
    for i in range(3, n):
        if L[i] - L[i - 3] > FLASH_LUMA_JUMP and m["white"][i] > WHITE_FRAC:
            if not ev or ev[-1]["kind"] != "flash" or i - ev[-1]["f"] > 6:
                ev.append({"f": i, "kind": "flash", "luma": round(float(L[i]), 1), "white": round(float(m["white"][i]), 2)})
    S = m["sat"]
    run_bw = None
    sat_med = np.median(S)
    for i in range(n):
        bw = S[i] < BW_SAT and sat_med > BW_SAT * 2.5 and m["luma"][i] > 25
        if bw and run_bw is None:
            run_bw = i
        if (not bw or i == n - 1) and run_bw is not None:
            if i - run_bw >= 4:
                ev.append({"f": run_bw, "kind": "bw_beat", "dur_f": i - run_bw})
            run_bw = None
    run_w = None
    for i in range(n):
        w = S[i] > WASH_HUE_SAT and m["hue_conc"][i] > 0.55
        if w and run_w is None:
            run_w = i
        if (not w or i == n - 1) and run_w is not None:
            if i - run_w >= 2:
                hue = int(np.median(m["hue"][run_w:i]))
                ev.append({"f": run_w, "kind": "colour_wash", "dur_f": i - run_w, "hue_deg": hue})
            run_w = None
    sh = m["sharp"]
    base = rolling_median(sh, int(fps) | 1)
    run_b = None
    for i in range(n):
        b = sh[i] < BLUR_DROP * base[i]
        if b and run_b is None:
            run_b = i
        if (not b or i == n - 1) and run_b is not None:
            if i - run_b >= 2:
                ev.append({"f": run_b, "kind": "blur", "dur_f": i - run_b,
                           "min_sharp_pct": round(float(min(sh[run_b:i] / np.maximum(base[run_b:i], 1e-6))) * 100)})
            run_b = None
    sc = m["scale"]
    i = 1
    while i < n:
        j = i
        while j < n and (sc[j] > ZOOM_STEP or sc[j] < 1 / ZOOM_STEP) and np.sign(sc[j] - 1) == np.sign(sc[i] - 1):
            j += 1
        if j - i >= 3:
            ev.append({"f": i, "kind": "zoom_in" if sc[i] > 1 else "zoom_out", "dur_f": j - i,
                       "total_scale": round(float(np.prod(sc[i:j])), 3)})
            i = j
        else:
            i += 1
    for i in range(1, n):
        if abs(m["shx"][i]) > WHIP_SHIFT and m["sharp"][i] < 0.6 * base[i]:
            ev.append({"f": i, "kind": "whip", "shift_pct": round(float(m["shx"][i]), 1)})
    for band in ("top", "mid", "bot"):
        e = m[f"edge_{band}"]
        for i in range(2, n):
            if e[i] > TEXT_EDGE_JUMP * max(e[i - 2], 0.004) and e[i] > 0.02 and d[i] < med + 6 * mad:
                if not any(x["kind"] == f"graphic_in_{band}" and i - x["f"] < 8 for x in ev):
                    ev.append({"f": i, "kind": f"graphic_in_{band}", "edge": round(float(e[i]), 3)})
    for x in ev:
        x["t_s"] = round(x["f"] / fps, 3)
    return sorted(ev, key=lambda x: (x["f"], x["kind"]))


def audio_hits(video: Path, fps: float) -> tuple[list[dict], dict]:
    """Audio hits from the percussive part of the mix (HPSS), so voiced speech is not counted.
    Each hit gets loudness rise before it (whoosh/riser build), decay after, spectral centroid,
    low-frequency share and flatness, and a class guessed from that shape."""
    import librosa
    import soundfile as sf
    sr = 22050
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        try:
            run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), str(wav)])
        except ToolError:
            return [], {"audio": False}
        x, _ = sf.read(str(wav), dtype="float32")
    if x.size < sr // 2:
        return [], {"audio": False}
    hop = 256
    S = librosa.stft(x, n_fft=1024, hop_length=hop)
    H, P = librosa.decompose.hpss(np.abs(S), margin=2.0)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    tps = sr / hop
    env = librosa.onset.onset_strength(S=librosa.amplitude_to_db(P, ref=np.max), sr=sr, hop_length=hop)
    full_db = librosa.amplitude_to_db(np.abs(S).sum(0) + 1e-6)
    noise_db = librosa.amplitude_to_db((P.sum(0) + 1e-6))
    flat = librosa.feature.spectral_flatness(S=np.abs(S))[0]
    cen = (P * freqs[:, None]).sum(0) / (P.sum(0) + 1e-9)
    low = P[freqs < 150].sum(0) / (P.sum(0) + 1e-9)
    hshare = H.sum(0) / (H.sum(0) + P.sum(0) + 1e-9)
    med = np.median(env); mad = np.median(np.abs(env - med)) + 1e-9
    peaks = librosa.util.peak_pick(env, pre_max=3, post_max=3, pre_avg=10, post_avg=10, delta=SFX_Z * mad, wait=int(tps * 0.1))
    hits = []
    for i in peaks:
        z = (env[i] - med) / mad
        if z < SFX_Z:
            continue
        pre = noise_db[max(0, i - int(tps * 1.2)):i + 1]
        post = noise_db[i:i + int(tps * 0.8)]
        rise = float(np.mean(pre[-4:]) - np.mean(pre[:8])) if pre.size > 16 else 0.0
        below = np.nonzero(post < post.max() - 12)[0] if post.size else []
        dur_s = (below[0] if len(below) else post.size) / tps
        c = float(np.median(cen[i:i + 6])); lo = float(np.median(low[i:i + 6])); fl = float(np.median(flat[i:i + 6]))
        hs = float(np.median(hshare[i:i + 6]))
        if rise > 10 and pre.size > tps * 0.6:
            cls = "riser" if rise > 20 else "whoosh"
        elif lo > 0.3 and dur_s > 0.12:
            cls = "impact/boom"
        elif hs > 0.6 and dur_s > 0.3 and c > 1500:
            cls = "ding/chime/shimmer"
        elif c > 3000 and dur_s < 0.15:
            cls = "click/pop/tick"
        elif fl > 0.05 and dur_s > 0.15:
            cls = "swoosh/noise"
        elif c < 1500 and dur_s < 0.25:
            cls = "thud/kick"
        else:
            cls = "transient (speech or sfx)"
        hits.append({"f": int(round(i / tps * fps)), "t_s": round(i / tps, 3), "strength_z": round(float(z), 1),
                     "level_db": round(float(full_db[i]), 1), "pre_rise_db": round(rise, 1), "decay_s": round(dur_s, 3),
                     "centroid_hz": int(c), "low_share": round(lo, 2), "flatness": round(fl, 3), "harmonic_share": round(hs, 2),
                     "class_guess": cls})
    return hits, {"audio": True, "duration_s": round(len(x) / sr, 2)}


def per_second(m: dict, ev: list[dict], hits: list[dict], fps: float) -> list[dict]:
    n = len(m["luma"])
    out = []
    for s in range(int(np.ceil(n / fps))):
        a, b = int(s * fps), min(n, int((s + 1) * fps))
        kinds = [x["kind"] for x in ev if a <= x["f"] < b]
        out.append({"s": s, "events": kinds, "sfx": [h["class_guess"] for h in hits if a <= h["f"] < b],
                    "luma": round(float(m["luma"][a:b].mean()), 1), "sat": round(float(m["sat"][a:b].mean()), 1),
                    "hue_deg": int(np.median(m["hue"][a:b]))})
    return out


def write_strips(video: Path, ev: list[dict], fps: float, out: Path) -> int:
    """One 30 fps strip per event (merged when events are close): STRIP_BEFORE..STRIP_AFTER frames."""
    from PIL import Image, ImageDraw
    windows = []
    for x in ev:
        a, b = x["f"] - STRIP_BEFORE, x["f"] + STRIP_AFTER
        if windows and a <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], b)
        else:
            windows.append([max(0, a), b])
    want = {}
    for wi, (a, b) in enumerate(windows):
        for f in range(a, b + 1):
            want.setdefault(f, []).append(wi)
    tiles = {wi: [] for wi in range(len(windows))}
    for f, fr in enumerate(frames(video, fps, TILE_W)):
        for wi in want.get(f, []):
            tiles[wi].append((f, Image.fromarray(fr)))
    count = 0
    for wi, ts in tiles.items():
        if not ts:
            continue
        th = ts[0][1].height
        for part in range(0, len(ts), SHEET_COLS * SHEET_ROWS):
            chunk = ts[part:part + SHEET_COLS * SHEET_ROWS]
            rows = (len(chunk) + SHEET_COLS - 1) // SHEET_COLS
            img = Image.new("RGB", (SHEET_COLS * TILE_W, rows * th), "black")
            dr = ImageDraw.Draw(img)
            for k, (f, im) in enumerate(chunk):
                x0, y0 = (k % SHEET_COLS) * TILE_W, (k // SHEET_COLS) * th
                img.paste(im, (x0, y0))
                dr.rectangle([x0, y0, x0 + 44, y0 + 11], fill="black")
                dr.text((x0 + 2, y0), f"{f} {f / fps:.1f}s", fill=(255, 255, 0))
            img.save(out / f"strip_{wi:04d}_{part // (SHEET_COLS * SHEET_ROWS)}.png")
            count += 1
    return count


def write_sheets(video: Path, fps: float, out: Path) -> int:
    from PIL import Image, ImageDraw
    per = SHEET_COLS * SHEET_ROWS
    buf, count = [], 0

    def flush():
        nonlocal buf, count
        if not buf:
            return
        th = buf[0][1].height
        rows = (len(buf) + SHEET_COLS - 1) // SHEET_COLS
        img = Image.new("RGB", (SHEET_COLS * TILE_W, rows * th), "black")
        dr = ImageDraw.Draw(img)
        for k, (f, im) in enumerate(buf):
            x0, y0 = (k % SHEET_COLS) * TILE_W, (k // SHEET_COLS) * th
            img.paste(im, (x0, y0))
            dr.rectangle([x0, y0, x0 + 44, y0 + 11], fill="black")
            dr.text((x0 + 2, y0), f"{f} {f / fps:.1f}s", fill=(255, 255, 0))
        img.save(out / f"sheet_{count:03d}.png")
        count += 1
        buf = []
    for f, fr in enumerate(frames(video, fps, TILE_W)):
        buf.append((f, Image.fromarray(fr)))
        if len(buf) == per:
            flush()
    flush()
    return count


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--fps", type=float, default=30.0, help="analysis rate (default 30: every frame of a 30 fps edit)")
    ap.add_argument("--sheets", choices=["events", "full", "none"], default="events")
    a = ap.parse_args()
    if not a.video.exists():
        fail(f"video not found: {a.video}")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        log(f"deep_watch {a.video.name}: measuring every frame at {a.fps:g} fps")
        m = measure_frames(a.video, a.fps)
        ev = find_events(m, a.fps)
        hits, ainfo = audio_hits(a.video, a.fps)
        n = len(m["luma"])
        dur = n / a.fps
        counts = {}
        for x in ev:
            counts[x["kind"]] = counts.get(x["kind"], 0) + 1
        summary = {"frames": n, "fps": a.fps, "duration_s": round(dur, 2),
                   "event_counts": counts, "events_per_min": {k: round(v / dur * 60, 1) for k, v in counts.items()},
                   "sfx_hits": len(hits), "sfx_per_min": round(len(hits) / dur * 60, 1),
                   "sfx_classes": {c: sum(1 for h in hits if h["class_guess"] == c) for c in sorted({h["class_guess"] for h in hits})},
                   "sfx_on_visual_event_pct": round(100 * sum(1 for h in hits if any(abs(h["f"] - x["f"]) <= 2 for x in ev)) / max(1, len(hits)), 1),
                   "mean_sat": round(float(m["sat"].mean()), 1), "mean_luma": round(float(m["luma"].mean()), 1), **ainfo}
        write_json(a.out_dir / "frames.json", {k: [round(float(v), 4) for v in arr] for k, arr in m.items()})
        nimg = 0
        if a.sheets == "events":
            nimg = write_strips(a.video, ev, a.fps, a.out_dir)
        elif a.sheets == "full":
            nimg = write_sheets(a.video, a.fps, a.out_dir)
        write_json(a.out_dir / "events.json", {"video": a.video.name, "summary": summary, "events": ev, "audio_hits": hits,
                                                "per_second": per_second(m, ev, hits, a.fps), "images": nimg,
                                                "note": "class_guess and graphic_in_* are measured from shape; confirm on the strips"})
        log(f"wrote {a.out_dir / 'events.json'}: {len(ev)} visual events, {len(hits)} audio hits, {nimg} images")
    except ToolError as e:
        fail(str(e))


if __name__ == "__main__":
    main()
