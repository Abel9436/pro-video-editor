#!/usr/bin/env python3
"""Stages 8-9 - Execute an EDL: picture, sound mix, colour, captions/graphics, encode.

Usage:
  python scripts/render.py --edl P/edl/v1.json --project P [--preview] [--out FILE]
                           [--graphics-engine auto|ass|remotion] [--dry-run]

--preview   rough cut from the 540p proxies at half resolution, fast encode (checkpoint 2)
--dry-run   validate the plan and list what would be rendered; renders nothing

The picture is built per event in Python (frame-exact decode, face-tracked reframing,
eased punch-ins, transitions, per-shot colour correction) and encoded as chunks under
P/render/<mode>/chunks/, keyed by a hash of everything that affects them: a re-render
after an EDL change only re-encodes the events that changed, and an interrupted render
resumes. Final encodes come from the original media (render_src), never from proxies.

Sound: dialogue stem (edge fades at every edit, voice chain, normalised), room tone in
any digital silence, music fitted on bar lines and ducked under speech, SFX at their
gain, then a two-pass loudness master. Stems are kept for QC.

Outputs: the video, P/render/<mode>/render.json (what was done, encoder, timings,
captions, stems), sidecar SRT/VTT, and new ledger lines in P/licenses.json.
"""
from __future__ import annotations

import argparse
import os
import hashlib
import json
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from lib.common import ToolError, fail, ffprobe_json, log, read_json, run, write_json  # noqa: E402
from lib.edl import event_len, fps_of, timeline_len, timeline_words, words_by_src  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
RENDER_VERSION = 1
FACE_STEP_S = Fraction(1, 6)     # face detection 6 times per second; interpolated between
FACE_SMOOTH_S = 0.6              # moving-average window for the tracked framing point
FACE_DEADZONE = 0.03             # tracked point moving less than 3 % of width = locked framing
HEADROOM_Y = 0.40                # face centre sits 40 % down the frame (eyes near the upper third)
CHUNK_CRF = {"final": 14, "preview": 28}
FINAL_QUALITY = {"libx264": ["-crf", "18", "-preset", "medium"],
                 "h264_qsv": ["-global_quality", "20", "-preset", "slower"],
                 "h264_nvenc": ["-cq", "19", "-preset", "p5", "-rc", "vbr"],
                 "h264_amf": ["-quality", "quality", "-rc", "cqp", "-qp_i", "18", "-qp_p", "20"]}
CODEC_TP_MARGIN_DB = 1.0
DEFAULT_TRANSITION_F = {"dissolve": 10, "fade": 8, "whip": 6, "zoom": 6}


# ----------------------------------------------------------------------------- helpers
def ease(kind: str, x: float) -> float:
    x = min(1.0, max(0.0, x))
    if kind == "linear":
        return x
    if kind == "in_cubic":
        return x ** 3
    if kind == "out_cubic":
        return 1 - (1 - x) ** 3
    if kind == "in_out_cubic":
        return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
    if kind == "out_back":
        c = 1.70158
        return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2
    return 0.5 - 0.5 * np.cos(np.pi * x)   # in_out_sine


def zoom_at(ev: dict, k: int) -> float:
    """Zoom factor k frames into the event: reframe zoom times every transform active at k."""
    z = float((ev.get("reframe") or {}).get("zoom", 1.0))
    for t in sorted(ev.get("transform", []), key=lambda t: t["at_f"]):
        if k < t["at_f"]:
            continue
        d = max(1, t.get("dur_f", 6))
        p = ease(t.get("ease", "out_cubic"), (k - t["at_f"]) / d)
        s = float(t.get("scale", 1.15))
        if t["type"] in ("punch_out", "pull_out"):
            s = 1 / s
        hold = t.get("hold_f")
        if hold is not None and k > t["at_f"] + d + hold:   # return to the base framing
            p = 1 - ease(t.get("ease", "out_cubic"), (k - t["at_f"] - d - hold) / d)
        z *= 1 + (s - 1) * p
    return z


def src_path(item: dict, preview: bool, project: Path) -> Path:
    p = item["proxy"] if preview and item.get("proxy") else item.get("render_src", item["path"])
    p = Path(p)
    return p if p.is_absolute() else project / p


_dims: dict = {}


def dims(path: Path) -> tuple[int, int]:
    if path not in _dims:
        pr = ffprobe_json(path)
        v = next(s for s in pr["streams"] if s["codec_type"] == "video")
        w, h = int(v["width"]), int(v["height"])
        rot = 0
        for sd in v.get("side_data_list", []):
            rot = int(sd.get("rotation", 0) or 0)
        rot = rot or int((v.get("tags") or {}).get("rotate", 0) or 0)
        _dims[path] = (h, w) if abs(rot) % 180 == 90 else (w, h)
    return _dims[path]


def in_matrix(item: dict) -> str:
    m = ((item.get("video") or {}).get("color") or {}).get("matrix")
    return "bt601" if m in ("smpte170m", "bt470bg") else "bt709"


def decode(path: Path, start_f: int, n: int, fps: Fraction, matrix: str):
    """Yield n BGR frames starting at timeline frame start_f of this source."""
    W, H = dims(path)
    t = max(0.0, float((Fraction(start_f) - Fraction(1, 2)) / fps))
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t:.6f}", "-i", str(path),
           "-vf", f"fps={fps},scale=in_color_matrix={matrix}:in_range=tv", "-frames:v", str(n),
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    sz = W * H * 3
    last = None
    got = 0
    try:
        while got < n:
            buf = p.stdout.read(sz)
            if len(buf) < sz:
                break
            last = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            got += 1
            yield last
    finally:
        p.stdout.close(); p.wait()
    while got < n and last is not None:   # source ended early: hold the last frame (reported by QC as frozen)
        got += 1
        yield last


class Encoder:
    def __init__(self, out: Path, W: int, H: int, fps: Fraction, mode: str):
        self.p = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps),
             "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
             "-c:v", "libx264", "-crf", str(CHUNK_CRF[mode]), "-preset", "veryfast" if mode == "final" else "ultrafast",
             "-g", str(int(round(fps)) * 2), "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-color_range", "tv", "-an", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, frame: np.ndarray):
        self.p.stdin.write(np.ascontiguousarray(frame).tobytes())

    def close(self):
        self.p.stdin.close()
        err = self.p.stderr.read().decode("utf-8", "replace")
        if self.p.wait() != 0:
            raise ToolError(f"chunk encode failed: {err[-500:]}")


# ----------------------------------------------------------------------------- framing
def track_points(frames: list[np.ndarray], fps: Fraction, faces) -> list[tuple[float, float] | None]:
    """Face centre (normalised) per frame: detected every FACE_STEP_S, interpolated, smoothed."""
    import cv2
    step = max(1, int(round(FACE_STEP_S * fps)))
    keys = {}
    for k in range(0, len(frames), step):
        fr = frames[k]
        small = cv2.resize(fr, (320, int(320 * fr.shape[0] / fr.shape[1])))
        fc = faces.faces(small)
        if fc:
            x, y, w, h = fc[0]["box"]
            keys[k] = (x + w / 2, y + h / 2)
    if not keys:
        return [None] * len(frames)
    ks = sorted(keys)
    xs = np.interp(np.arange(len(frames)), ks, [keys[k][0] for k in ks])
    ys = np.interp(np.arange(len(frames)), ks, [keys[k][1] for k in ks])
    if np.ptp(xs) < FACE_DEADZONE and np.ptp(ys) < FACE_DEADZONE:
        return [(float(np.median(xs)), float(np.median(ys)))] * len(frames)   # lock the frame
    win = max(1, int(FACE_SMOOTH_S * float(fps)))
    ker = np.ones(win) / win
    pad = lambda a: np.convolve(np.pad(a, (win // 2, win - 1 - win // 2), mode="edge"), ker, "valid")  # noqa: E731
    return list(zip(pad(xs).tolist(), pad(ys).tolist()))


def crop_window(Sw: int, Sh: int, W: int, H: int, z: float, pt: tuple[float, float] | None,
                manual: dict | None) -> tuple[float, float, float, float]:
    A = W / H
    if Sw / Sh > A:
        bh, bw = Sh, Sh * A
    else:
        bw, bh = Sw, Sw / A
    cw, ch = bw / z, bh / z
    if manual and manual.get("mode") == "fixed":
        cx, cy = manual.get("x", 0.5) * Sw, manual.get("y", 0.5) * Sh
        y0 = cy - ch / 2
    elif pt is not None:
        cx, cy = pt[0] * Sw, pt[1] * Sh
        y0 = cy - HEADROOM_Y * ch
    else:
        cx, cy = Sw / 2, Sh / 2
        y0 = cy - ch / 2
    x0 = min(max(0.0, cx - cw / 2), Sw - cw)
    y0 = min(max(0.0, y0), Sh - ch)
    return x0, y0, cw, ch


def warp(frame: np.ndarray, win, W: int, H: int) -> np.ndarray:
    import cv2
    x0, y0, cw, ch = win
    sx, sy = W / cw, H / ch
    M = np.float32([[sx, 0, -x0 * sx], [0, sy, -y0 * sy]])
    interp = cv2.INTER_AREA if sx < 1 else cv2.INTER_LANCZOS4
    return cv2.warpAffine(frame, M, (W, H), flags=interp, borderMode=cv2.BORDER_REPLICATE)


def blend_transition(kind: str, k: int, d: int, cur: np.ndarray, prev_last: np.ndarray | None) -> np.ndarray:
    import cv2
    p = ease("in_out_sine", (k + 1) / (d + 1))
    if kind == "fade":
        return (cur.astype(np.float32) * p).astype(np.uint8)
    if prev_last is None:
        return cur
    if kind == "dissolve":
        return cv2.addWeighted(prev_last, 1 - p, cur, p, 0)
    H, W = cur.shape[:2]
    if kind == "whip":
        off = int((1 - p) * W)
        blur = max(1, int((1 - p) * W * 0.08)) | 1
        out = np.concatenate([prev_last[:, off:], cur[:, :off]], 1) if off else cur
        return cv2.blur(out, (blur, 1)) if blur > 1 else out
    if kind == "zoom":
        s = 1 + 0.25 * (1 - p)
        M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s)
        z = cv2.warpAffine(cur, M, (W, H), borderMode=cv2.BORDER_REPLICATE)
        return cv2.addWeighted(prev_last, max(0.0, 0.6 - p), z, min(1.0, 0.4 + p), 0)
    return cur


# ----------------------------------------------------------------------------- plan
def build_pieces(edl: dict) -> list[dict]:
    """Picture segments in timeline order; B-roll replaces the main picture over its range."""
    brs = sorted(edl["tracks"].get("broll") or [], key=lambda b: b["at_f"])
    pieces = []
    for ev in edl["tracks"]["video"]:
        a, b = ev["at_f"], ev["at_f"] + event_len(ev)
        cuts = [a, b]
        for br in brs:
            for x in (br["at_f"], br["at_f"] + br["dur_f"]):
                if a < x < b:
                    cuts.append(x)
        cuts = sorted(set(cuts))
        for s, e in zip(cuts, cuts[1:]):
            cover = next((br for br in brs if br["at_f"] <= s and e <= br["at_f"] + br["dur_f"]), None)
            if cover is None:
                pieces.append({"kind": "main", "ev": ev, "t0": s, "t1": e})
    for br in brs:
        pieces.append({"kind": "broll", "ev": br, "t0": br["at_f"], "t1": br["at_f"] + br["dur_f"]})
    pieces.sort(key=lambda p: p["t0"])
    return pieces


def piece_key(piece: dict, extra: dict) -> str:
    blob = json.dumps({"v": RENDER_VERSION, "p": {k: v for k, v in piece.items()}, "x": extra}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:20]


# ----------------------------------------------------------------------------- colour
def colour_plan(edl: dict, items: dict, project: Path, analysis: dict, fps: Fraction) -> dict:
    """Per-event correction + shot matching as channel LUTs. Measured on proxies."""
    from lib.color import channel_luts, correction, frame_stats, match_to
    col = edl.get("color") or {}
    out = {}
    if col.get("correction", "auto") == "none":
        return out
    stats = {}
    for ev in edl["tracks"]["video"]:
        it = items[ev["src"]]
        p = src_path(it, True, project)
        n = ev["out_f"] - ev["in_f"]
        picks = sorted({ev["in_f"] + n // 6, ev["in_f"] + n // 2, ev["in_f"] + 5 * n // 6})
        frames, boxes = [], []
        shots = (analysis["files"].get(ev["src"]) or {}).get("shots", [])
        for f in picks:
            fr = next(decode(p, f, 1, fps, in_matrix(it)), None)
            if fr is None:
                continue
            frames.append(fr)
            sh = next((s for s in shots if s["s_f"] <= f < s["e_f"]), None)
            boxes.append((((sh or {}).get("faces") or {}).get("main") or {}).get("box") if sh else None)
        if frames:
            stats[ev["id"]] = frame_stats(frames, boxes)
    scenes: dict = {}
    for ev in edl["tracks"]["video"]:
        if ev["id"] in stats:
            scenes.setdefault(ev["src"], []).append(stats[ev["id"]])
    scene_med = {}
    for src, rows in scenes.items():
        scene_med[src] = {k: float(np.median([r[k] for r in rows if k in r])) for k in ("L", "face_L")
                          if any(k in r for r in rows)}
    for ev in edl["tracks"]["video"]:
        st = stats.get(ev["id"])
        if not st:
            continue
        corr = correction(st)
        mg = match_to(st, scene_med.get(ev["src"], {})) if col.get("match_shots", True) else [1.0, 1.0, 1.0]
        out[ev["id"]] = {"stats": {k: round(v, 2) for k, v in st.items()}, "correction": corr,
                         "match_gains": [round(g, 3) for g in mg], "lut": channel_luts(corr, mg)}
    return out


# ----------------------------------------------------------------------------- picture
PRIVACY_DETECT_EVERY = 3      # re-detect faces to blur every 3 frames; boxes are held in between
PRIVACY_PAD = 0.25            # grow each blurred face box by 25 % so hair and chin edges are covered


class Privacy:
    """EDL privacy: {"blur_faces": "bystanders" | "all", "regions": [{"t0_f", "t1_f", "box": [x, y, w, h]}]}.
    Applied to the output frame, so boxes are in timeline (output) coordinates. "bystanders"
    blurs every face except the largest one in frame (the tracked speaker)."""

    def __init__(self, spec: dict | None, faces):
        self.spec = spec or {}
        self.faces = faces
        self.boxes: list = []
        self.last = -10**9

    def apply(self, fr: np.ndarray, t: int) -> np.ndarray:
        import cv2
        mode = self.spec.get("blur_faces")
        h, w = fr.shape[:2]
        regions = [r["box"] for r in self.spec.get("regions", []) if r.get("t0_f", 0) <= t < r.get("t1_f", 10**9)]
        if mode in ("bystanders", "all"):
            if t - self.last >= PRIVACY_DETECT_EVERY or t < self.last:
                found = sorted(self.faces.faces(fr), key=lambda f: -f["box"][2] * f["box"][3])
                self.boxes = [f["box"] for f in (found[1:] if mode == "bystanders" else found)]
                self.last = t
            regions += self.boxes
        for x, y, bw, bh in regions:
            x0, y0 = int(max(0, (x - bw * PRIVACY_PAD / 2) * w)), int(max(0, (y - bh * PRIVACY_PAD / 2) * h))
            x1, y1 = int(min(w, (x + bw * (1 + PRIVACY_PAD / 2)) * w)), int(min(h, (y + bh * (1 + PRIVACY_PAD / 2)) * h))
            if x1 - x0 > 2 and y1 - y0 > 2:
                k = max(3, (max(x1 - x0, y1 - y0) // 4) | 1)
                fr[y0:y1, x0:x1] = cv2.GaussianBlur(fr[y0:y1, x0:x1], (k, k), 0)
        return fr


def broll_stamp(ev: dict, project: Path) -> str:
    """Cache identity of a B-roll asset: its id plus the resolved file's size and mtime, so a
    re-rendered scene under the same name is not served from a stale chunk."""
    name = ev.get("asset") or ev.get("src")
    try:
        from lib.kit import resolve
        p, _ = resolve(ev["asset"], project) if ev.get("asset") else (project / ev["src"], {})
        st = p.stat()
        return f"{name}|{st.st_size}|{int(st.st_mtime)}"
    except (FileNotFoundError, KeyError, OSError):
        return str(name)


def render_picture(edl, items, project, analysis, fps, W, H, mode, rdir, colour) -> tuple[Path, dict]:
    import cv2
    from lib.shots import FaceDetector
    faces = FaceDetector(SKILL / "assets" / "cache" / "models")
    privacy = Privacy(edl.get("privacy"), faces) if edl.get("privacy") else None
    chunks_dir = rdir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    pieces = build_pieces(edl)
    files, reused, rendered = [], 0, 0
    prev_last = None
    for idx, pc in enumerate(pieces):
        ev = pc["ev"]
        lut = colour.get(ev.get("id"), {}).get("lut") if pc["kind"] == "main" else None
        extra = {"W": W, "H": H, "mode": mode, "fps": str(fps),
                 "lut": None if lut is None else hashlib.md5(lut.tobytes()).hexdigest(),
                 "src": items[ev["src"]].get("hash") if pc["kind"] == "main" else broll_stamp(ev, project),
                 "privacy": edl.get("privacy")}
        key = piece_key({k: v for k, v in pc.items()}, extra)
        out = chunks_dir / f"{idx:04d}_{key}.mp4"
        last_png = out.with_suffix(".last.png")
        n = pc["t1"] - pc["t0"]
        if out.exists() and last_png.exists():
            reused += 1
            files.append(out)
            prev_last = cv2.imread(str(last_png))
            continue
        enc = Encoder(out, W, H, fps, mode)
        if pc["kind"] == "main":
            it = items[ev["src"]]
            path = src_path(it, mode == "preview", project)
            Sw, Sh = dims(path)
            sp = float(ev.get("speed", 1.0) or 1.0)
            off = pc["t0"] - ev["at_f"]
            span_src = ev["out_f"] - ev["in_f"]
            first_src = ev["in_f"] + min(span_src - 1, int(off * sp))
            last_src = ev["in_f"] + min(span_src - 1, int((off + n - 1) * sp))
            raw = list(decode(path, first_src, last_src - first_src + 1, fps, in_matrix(it)))
            pts = track_points(raw, fps, faces) if (ev.get("reframe") or {}).get("mode", "face_track") == "face_track" \
                else [None] * len(raw)
            trans = ev.get("transition_in", "cut") if off == 0 else "cut"
            tdur = ev.get("transition_dur_f", DEFAULT_TRANSITION_F.get(trans, 0))
            for k in range(n):
                j = min(len(raw) - 1, int((off + k) * sp) - (first_src - ev["in_f"]))
                z = zoom_at(ev, off + k)
                win = crop_window(Sw, Sh, W, H, z, pts[j], ev.get("reframe"))
                fr = warp(raw[j], win, W, H)
                if lut is not None:
                    fr = cv2.LUT(fr, lut)
                if trans != "cut" and k < tdur:
                    fr = blend_transition(trans, k, tdur, fr, prev_last)
                if privacy:
                    fr = privacy.apply(fr, pc["t0"] + k)
                enc.write(fr)
                prev_last = fr
        else:
            from lib.kit import resolve
            ap, _ = resolve(ev["asset"], project) if ev.get("asset") else (project / ev["src"], {})
            from lib.common import media_kind
            if media_kind(ap) == "image":
                img = cv2.imread(str(ap))
                Sw, Sh = img.shape[1], img.shape[0]
                for k in range(n):
                    z = 1.0 + 0.06 * ease("in_out_sine", k / max(1, n - 1))   # slow push on stills
                    fr = warp(img, crop_window(Sw, Sh, W, H, z, None, None), W, H)
                    enc.write(fr); prev_last = fr
            else:
                # moving B-roll: optional `push` [z0, z1] (eased zoom across the clip), `speed` (<1 slow motion,
                # frames are repeated, never blended), `x`/`y` (crop centre as fractions of the source),
                # `transition_in` as on main events
                Sw, Sh = dims(ap)
                sp = float(ev.get("speed", 1.0) or 1.0)
                z0, z1 = (ev.get("push") or [1.0, 1.0])
                man = {"mode": "fixed", "x": ev["x"], "y": ev.get("y", 0.5)} if "x" in ev or "y" in ev else None
                if man and "x" not in ev:
                    man["x"] = 0.5
                raw = list(decode(ap, ev.get("in_f", 0), max(1, int(np.ceil(n * sp)) + 1), fps, "bt709"))
                g = ev.get("grade") or {}
                if g:      # match bright stock to the main footage: gain, saturation, vignette (0-1)
                    vig = None
                    if g.get("vignette"):
                        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
                        rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / np.sqrt(2)
                        vig = (1 - g["vignette"] * np.clip(rr, 0, 1) ** 2)[..., None].astype(np.float32)
                trans = ev.get("transition_in", "cut")
                tdur = ev.get("transition_dur_f", DEFAULT_TRANSITION_F.get(trans, 0))
                for k in range(n):
                    fr0 = raw[min(len(raw) - 1, int(k * sp))]
                    z = z0 + (z1 - z0) * ease("in_out_sine", k / max(1, n - 1))
                    fr = warp(fr0, crop_window(Sw, Sh, W, H, z, None, man), W, H)
                    if g:
                        f32 = fr.astype(np.float32) * g.get("gain", 1.0)
                        if g.get("sat", 1.0) != 1.0:
                            lum = f32 @ np.float32([0.114, 0.587, 0.299])
                            f32 = lum[..., None] + (f32 - lum[..., None]) * g["sat"]
                        if vig is not None:
                            f32 *= vig
                        fr = np.clip(f32, 0, 255).astype(np.uint8)
                    if trans != "cut" and k < tdur:
                        fr = blend_transition(trans, k, tdur, fr, prev_last)
                    enc.write(fr); prev_last = fr
        enc.close()
        cv2.imwrite(str(last_png), prev_last)
        rendered += 1
        files.append(out)
        log(f"  chunk {idx + 1}/{len(pieces)} ({n} f)")
    lst = rdir / "chunks.txt"
    lst.write_text("".join(f"file 'chunks/{f.name}'\n" for f in files), encoding="utf-8")
    pic = rdir / "picture.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "chunks.txt", "-c", "copy", "picture.mp4"], cwd=rdir)
    return pic, {"pieces": len(pieces), "rendered": rendered, "reused": reused}


# ----------------------------------------------------------------------------- sound
def render_sound(edl, items, project, analysis, fps, rdir) -> tuple[Path, dict, list]:
    from lib import mix
    total_f = timeline_len(edl)
    N = mix.f2s(total_f, fps)
    stems = rdir / "stems"
    adir = project / "render" / "audio"
    ledger = []
    srcs = {}
    def src_audio(sid):
        if sid not in srcs:
            it = items[sid]
            p = src_path(it, False, project)
            srcs[sid] = mix.load(mix.decode(p, adir / f"{it.get('hash', sid)}_48k.wav"))
        return srcs[sid]
    dia = np.zeros((N, 2), np.float32)
    dlg = sorted(edl["tracks"].get("dialogue") or [], key=lambda d: d["at_f"])
    wbs = words_by_src(analysis)
    beds = {}
    for sid in {d["src"] for d in dlg}:
        beds[sid] = mix.gap_noise_floor(src_audio(sid), [(float(Fraction(w["s_f"]) / fps), float(Fraction(w["e_f"]) / fps))
                                                         for w in wbs.get(sid, [])])
    xf = int(mix.CUT_XFADE_S * mix.SR)
    for i, d in enumerate(dlg):
        x = src_audio(d["src"])
        has_bed = (beds.get(d["src"]) or -99) > mix.BED_LEVEL_DB
        a0, a1 = mix.f2s(d["in_f"], fps), mix.f2s(d["out_f"], fps)
        seg = x[a0:a1 + (xf if has_bed else 0)]      # tail handle: the bed crossfades under the next clip
        sp = float(d.get("speed", 1.0) or 1.0)
        if sp != 1.0:
            import librosa
            seg = np.stack([librosa.effects.time_stretch(seg[:, c].copy(), rate=sp) for c in range(2)], 1)
        if d.get("gain_db"):
            seg = seg * np.float32(10 ** (d["gain_db"] / 20))
        prev = dlg[i - 1] if i else None
        nxt = dlg[i + 1] if i + 1 < len(dlg) else None
        joined_prev = prev and prev["src"] == d["src"] and prev["out_f"] == d["in_f"] and \
            prev["at_f"] + prev["out_f"] - prev["in_f"] == d["at_f"]
        joined_next = nxt and nxt["src"] == d["src"] and d["out_f"] == nxt["in_f"] and \
            d["at_f"] + d["out_f"] - d["in_f"] == nxt["at_f"]
        if has_bed and joined_next:
            seg = seg[: a1 - a0]
        mix.place(dia, seg, mix.f2s(d["at_f"], fps), fade_in=not joined_prev, fade_out=not joined_next,
                  n_in=xf if has_bed else None, n_out=xf if has_bed else None, power=has_bed)
    info = {"dialogue_events": len(dlg), "source_bed_db": {k: None if v is None else round(v, 1) for k, v in beds.items()}}
    if any((v or -99) > mix.BED_LEVEL_DB for v in beds.values()):
        info["source_bed_note"] = ("source audio already carries a steady bed (music or ambience) between words: "
                                   "no denoising, equal-power crossfades at cuts; a second music track would clash")
    if dlg:
        raw = mix.save(stems / "dialogue_raw.wav", dia)
        nf = max([v for v in beds.values() if v is not None], default=None)
        chained, chain = mix.voice_chain(raw, stems / "dialogue_chain.wav", nf)
        dia = mix.load(chained)[:N]
        if dia.shape[0] < N:
            dia = np.pad(dia, ((0, N - dia.shape[0]), (0, 0)))
        dia, g = mix.gain_to(dia, mix.DIALOGUE_LUFS)
        s0 = dlg[0]["src"]
        tone = None if (beds.get(s0) or -99) > mix.BED_LEVEL_DB else \
            mix.roomtone(src_audio(s0), [(float(Fraction(w["s_f"]) / fps), float(Fraction(w["e_f"]) / fps)) for w in wbs.get(s0, [])])
        filled = mix.fill_silence(dia, None if tone is None else tone * np.float32(10 ** (g / 20)))
        info.update(voice_chain=chain, dialogue_gain_db=round(g, 2), roomtone_filled_s=round(filled / mix.SR, 2),
                    noise_floor_db=nf)
    mix.save(stems / "dialogue.wav", dia)
    # speech activity on the timeline (for ducking and QC)
    tw = timeline_words(edl, analysis)
    spans = [(float(Fraction(w["t_s"]) / fps), float(Fraction(w["t_e"]) / fps)) for w in tw]
    mus = np.zeros((N, 2), np.float32)
    from lib.kit import resolve
    for m in edl["tracks"].get("music") or []:
        p, led = resolve(m["asset"], project)
        ledger.append({**led, "used_as": "music", "at_f": m["at_f"]})
        x = mix.load(mix.decode(p, adir / f"music_{hashlib.md5(str(p).encode()).hexdigest()[:10]}.wav"))
        from lib.music import analyze_music
        import librosa
        mono16 = librosa.resample(x.mean(1), orig_sr=mix.SR, target_sr=16000)
        ma = analyze_music(mono16, 16000, Fraction(100))
        beats = [b / 100 for b in ma["beats_f"]]; downs = [b / 100 for b in ma["downbeats_f"]]
        start = mix.f2s(m.get("in_f", 0), fps)
        dur = mix.f2s(m.get("dur_f", total_f - m["at_f"]), fps)
        align = m.get("align", "")
        if align.startswith("downbeat_to_cut:"):
            vid = align.split(":", 1)[1]
            ev = next((e for e in edl["tracks"]["video"] if e["id"] == vid), None)
            if ev and downs:
                want = Fraction(ev["at_f"] - m["at_f"]) / fps     # seconds into the bed where the cut is
                cand = [d - float(want) for d in downs if d - float(want) >= 0]
                if cand:
                    start = int(min(cand, key=lambda c: abs(c - start / mix.SR)) * mix.SR)
        end_mode = m.get("end") or ("natural" if x.shape[0] - start >= dur else "bar")
        bed = mix.music_bed(x, beats, downs, dur, start, end_mode)
        lvl = mix.DIALOGUE_LUFS + float(m.get("gain_db", mix.MUSIC_GAP_DB))
        bed, _ = mix.gain_to(bed, lvl)
        duck = m.get("duck") or {}
        if spans and duck:
            depth_rel = float(duck.get("depth_db", -20)) - float(m.get("gain_db", mix.MUSIC_GAP_DB))
            env = mix.duck_envelope(bed.shape[0], [(s - float(Fraction(m["at_f"]) / fps), e - float(Fraction(m["at_f"]) / fps))
                                                   for s, e in spans], min(0.0, depth_rel),
                                    float(duck.get("attack_ms", 80)), float(duck.get("release_ms", 400)))
            bed = bed * env
        mix.place(mus, bed, mix.f2s(m["at_f"], fps), fade_in=True, fade_out=end_mode != "natural")
        info.setdefault("music", []).append({"asset": m["asset"], "end": end_mode, "start_s": round(start / mix.SR, 2),
                                             "bpm": ma["bpm"], "level_lufs_gaps": lvl})
    mix.save(stems / "music.wav", mus)
    sfx = np.zeros((N, 2), np.float32)
    for s in edl["tracks"].get("sfx") or []:
        p, led = resolve(s["asset"], project)
        ledger.append({**led, "used_as": "sfx", "at_f": s["at_f"]})
        x = mix.load(mix.decode(p, adir / f"sfx_{hashlib.md5(str(p).encode()).hexdigest()[:10]}.wav"))
        x = x[int(float(s.get("in_s", 0)) * mix.SR):]
        if s.get("dur_f"):
            x = x[:mix.f2s(s["dur_f"], fps)]
        x = x / (np.abs(x).max() + 1e-9) * np.float32(10 ** (float(s.get("gain_db", mix.SFX_PEAK_DEFAULT_DB)) / 20))
        mix.place(sfx, x, mix.f2s(s["at_f"], fps), fade_in=False, fade_out=True)
    mix.save(stems / "sfx.wav", sfx)
    pre = mix.save(stems / "premaster.wav", dia + mus + sfx)
    ms = edl.get("master") or {}
    # AAC encoding overshoots true peak by up to ~0.6 dB: master below the ceiling by CODEC_TP_MARGIN_DB
    meas = mix.loudnorm_master(pre, rdir / "master.wav", float(ms.get("lufs", -14)),
                               float(ms.get("true_peak_db", -1)) - CODEC_TP_MARGIN_DB)
    info["master_input"] = meas
    info["speech_spans_s"] = len(spans)
    return rdir / "master.wav", info, ledger


# ----------------------------------------------------------------------------- captions / graphics
def caption_layer(edl, analysis, fps, W, H, rdir, items, project) -> tuple[Path | None, dict]:
    from lib import captions as C
    from lib.kit import ensure_fonts
    cap = edl["tracks"].get("captions")
    graphics = edl["tracks"].get("graphics") or []
    tw = timeline_words(edl, analysis)
    total = timeline_len(edl)
    info = {}
    # sidecar captions always (accessibility), from readable line cards
    lines = C.line_cards(tw, fps, total)
    srt, vtt = C.srt_vtt(lines, fps)
    (rdir / "captions.srt").write_text(srt, encoding="utf-8")
    (rdir / "captions.vtt").write_text(vtt, encoding="utf-8")
    info["srt"] = "captions.srt"; info["vtt"] = "captions.vtt"
    if not cap and not graphics:
        (rdir / "caption_cards.json").unlink(missing_ok=True)   # never leave an earlier render's cards for QC
        return None, info
    profile = {}
    if edl["project"].get("profile") and (SKILL / edl["project"]["profile"]).exists():
        profile = read_json(SKILL / edl["project"]["profile"])
    fonts = {"caption": "Poppins ExtraBold", "heading": "Anton", "ethiopic": "Noto Sans Ethiopic",
             **(profile.get("fonts") or {})}
    colors = {"primary": "#FFD400", "text": "#FFFFFF", "stroke": "#000000", **(profile.get("colors") or {})}
    fdir, missing = ensure_fonts(list(fonts.values()))
    if missing:
        info["font_warning"] = f"fonts unavailable (libass will substitute): {missing}"
    template = (cap or {}).get("template", "pop_3word")
    cards = C.make_cards(tw, fps, template, total) if cap else []
    # faces on the timeline, for caption placement
    avoid = []
    for ev in edl["tracks"]["video"]:
        shots = (analysis["files"].get(ev["src"]) or {}).get("shots", [])
        for sh in shots:
            if sh["e_f"] <= ev["in_f"] or sh["s_f"] >= ev["out_f"]:
                continue
            box = ((sh.get("faces") or {}).get("main") or {}).get("box")
            if not box:
                continue
            z = float((ev.get("reframe") or {}).get("zoom", 1.0))
            it = items[ev["src"]]
            Sw, Sh = it["video"]["display_width"], it["video"]["display_height"]
            cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
            x0, y0, cw, ch = crop_window(Sw, Sh, W, H, z, (cx, cy), ev.get("reframe"))
            nb = [(box[0] * Sw - x0) / cw, (box[1] * Sh - y0) / ch, box[2] * Sw / cw, box[3] * Sh / ch]
            a = ev["at_f"] + max(0, sh["s_f"] - ev["in_f"]); b = ev["at_f"] + min(ev["out_f"], sh["e_f"]) - ev["in_f"]
            avoid.append((a, b, nb))
    doc = C.ass_document(cards, fps, W, H, template, edl["project"].get("platform", "shorts"),
                         (cap or {}).get("keywords", []), fonts, colors, (cap or {}).get("highlight", "keyword"),
                         graphics, avoid, (cap or {}).get("position"), (cap or {}).get("fix"))
    (rdir / "captions.ass").write_text(doc, encoding="utf-8")
    fl = rdir / "fonts"
    fl.mkdir(exist_ok=True)
    for f in fdir.glob("*.ttf"):
        if not (fl / f.name).exists():
            shutil.copy2(f, fl / f.name)
    write_json(rdir / "caption_cards.json", {"template": template, "cards": cards, "face_boxes": avoid})
    info.update(cards=len(cards), template=template, ass="captions.ass", fonts=fonts)
    return rdir / "captions.ass", info


# Graphics only the Remotion engine can draw (libass has no equivalent). With any of these in the
# EDL, "auto" becomes "hybrid": libass draws captions and the simple graphics, Remotion draws these.
REMOTION_ONLY = {"XStamp", "WordSlam", "Title3D"}


def remotion_overlay(edl, cards_json: Path, fps, W, H, rdir, hybrid: bool = False) -> Path | None:
    rem = SKILL / "remotion"
    if not (rem / "node_modules" / "remotion").exists():
        return None
    gfx = edl["tracks"].get("graphics") or []
    if hybrid:
        gfx = [g for g in gfx if g["component"] in REMOTION_ONLY]
    props = {"fps": float(fps), "width": W, "height": H, "durationInFrames": timeline_len(edl),
             "cards": [] if hybrid or not cards_json.exists() else read_json(cards_json)["cards"],
             "graphics": gfx, "captions": None if hybrid else edl["tracks"].get("captions")}
    pj = rdir / "remotion_props.json"
    write_json(pj, props)
    out = rdir / "overlay.mov"
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    try:
        run([npx, "remotion", "render", "src/index.ts", "Overlay", str(out.resolve()), f"--props={pj.resolve()}", "--codec=prores",
             "--prores-profile=4444", "--pixel-format=yuva444p10le", "--image-format=png", "--log=error"], cwd=rem, timeout=3600)
    except ToolError as e:
        log(f"  remotion render failed, using libass: {e}")
        return None
    return out


DESIGN_CAP_Y = {"full": 0.7, "split": 0.45, "hidden": 0.86}   # mirrors CAP_Y in remotion/src/design/Design.tsx


def caption_text(tw: list[dict], fixes: dict) -> list[dict]:
    """Caption-only text corrections keyed by source word index ("55", or "src:55" with several
    sources): a string replaces the word, "" removes it (its time goes to the word before, so a name
    split by the transcriber, e.g. "Qur 'an Lee", reads as one word). The audio is not touched."""
    if not fixes:
        return tw
    out = []
    for w in tw:
        k = fixes.get(f"{w['src']}:{w['i']}", fixes.get(str(w["i"])))
        if k is None:
            out.append(w)
        elif k == "":
            if out:
                out[-1] = {**out[-1], "t_e": max(out[-1]["t_e"], w["t_e"])}
        else:
            out.append({**w, "w": k})
    return out


def design_pass(edl, analysis, pic: Path, fps, W, H, rdir: Path, project: Path, preview: bool, engine: str = "remotion") -> tuple[Path, dict]:
    """Premium design pass: the Remotion `Design` composition builds the finished picture around the
    clean speaker cut (layouts, explainer scenes, phrase captions, overlays, transitions). Assets are
    read from the project folder (Remotion public dir), so icons/footage/SFX stay out of the skill."""
    from lib import captions as C
    rem = SKILL / "remotion"
    if engine == "remotion" and not (rem / "node_modules" / "remotion").exists():
        raise ToolError("the design block needs Remotion: run npm install in remotion/ (or use --graphics-engine hyperframes)")
    d = edl["design"]
    total = timeline_len(edl)
    tw = caption_text(timeline_words(edl, analysis), d.get("caption_text") or {})
    hide = [tuple(x) for x in d.get("caption_hide", [])]
    caps = C.phrase_groups(tw, fps, d.get("emphasis", []), d.get("caption_skip", []), hide,
                           int(d.get("max_words", C.PHRASE_MAX_WORDS)), total)
    rel = pic.resolve().relative_to(project.resolve()).as_posix()
    matte_rel, minfo, fg = None, None, None
    if d.get("matte"):
        # person cut-out (alpha) so overlays marked behind:true and bg spans sit behind the speaker
        # cached on the picture's content (the chunk list carries a hash per chunk), not its mtime:
        # picture.mp4 is re-concatenated on every render even when every chunk is reused
        fg, keyf = rdir / "speaker_fg.webm", rdir / "speaker_fg.key"
        lst = rdir / "chunks.txt"
        key = hashlib.md5((lst.read_text(encoding="utf-8") if lst.exists() else f"{pic.stat().st_size}:{pic.stat().st_mtime}").encode()).hexdigest()
        if not fg.exists() or not keyf.exists() or keyf.read_text().strip() != key:
            log("  matte: cutting the speaker out (PP-HumanSeg)")
            run([sys.executable, str(SKILL / "scripts" / "matte.py"), str(pic), "--out", str(fg), "--report", str(rdir / "matte.json")], timeout=7200)
            keyf.write_text(key)
        matte_rel = fg.resolve().relative_to(project.resolve()).as_posix()
        minfo = read_json(rdir / "matte.json") if (rdir / "matte.json").exists() else None
    # LineIcon overlays may name a fetched icon (scripts/fetch_lineicons.py) instead of giving paths;
    # anywhere inside a scene or overlay, {"lineicon": "name"} gets the icon's "paths" added
    def icon_paths(name: str) -> list:
        jf = project / "lineicons" / f"{name}.json"
        if not jf.exists():
            raise ToolError(f"line icon {name} not fetched: run scripts/fetch_lineicons.py --project {project} {name}")
        return read_json(jf)["paths"]

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("lineicon"), str) and "paths" not in x:
                x["paths"] = icon_paths(x["lineicon"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for o in d.get("overlays", []):
        if o.get("type") == "LineIcon" and "paths" not in o.get("p", {}) and o.get("p", {}).get("icon"):
            o["p"] = {**o["p"], "paths": icon_paths(o["p"]["icon"])}
    walk(d.get("overlays", [])); walk(d.get("scenes", []))
    props = {"fps": float(fps), "width": edl["project"]["width"], "height": edl["project"]["height"], "durationInFrames": total,
             "base": rel, "faceY": float(d.get("face_y", 0.3)), "brand": d.get("brand") or {},
             "layout": d.get("layout", []), "scenes": d.get("scenes", []), "captions": caps,
             "overlays": d.get("overlays", []), "fx": d.get("fx", []),
             "capStyle": d.get("caption_style", "phrase"), "capSize": d.get("caption_size"), "capPalette": d.get("caption_palette") or [], "capY": d.get("caption_y"), "matte": matte_rel, "bg": d.get("bg", [])}
    pj = rdir / "design_props.json"
    write_json(pj, props)
    # caption cards with their real on-screen centre, so QC checks what is drawn (not a stale libass file)
    def mode_at(f):
        return next((L["mode"] for L in props["layout"] if L["s"] <= f < L["e"]), "full")

    def cap_y(c):
        mid = (c["s"] + c["e"]) // 2
        for sp in d.get("caption_y_at", []):            # per-span override, e.g. a screen recording with UI at the bottom
            if sp["s"] <= mid < sp["e"]:
                return float(sp["y"])
        return d["caption_y"] if d.get("caption_y") and mode_at(mid) == "full" else DESIGN_CAP_Y[mode_at(mid)]
    cap_ys = [cap_y(c) for c in caps]
    # a span may ask for a scrim behind its captions (bright footage, e.g. a white app screen)
    cap_scrims = [any(sp.get("scrim") and sp["s"] <= (c["s"] + c["e"]) // 2 < sp["e"] for sp in d.get("caption_y_at", [])) for c in caps]
    write_json(rdir / "caption_cards.json", {"template": "design_phrase", "cards": [
        {"s_f": c["s"], "e_f": c["e"], "y": y, "words": [{"w": w["w"], "t_s": w["s"], "emph": w["emph"]} for w in c["words"]]} for c, y in zip(caps, cap_ys)]})
    out = rdir / "design.mp4"
    info = {"captions": len(caps), "caption_style": props["capStyle"], "scenes": len(props["scenes"]), "overlays": len(props["overlays"]),
            "layout_spans": len(props["layout"]), "fx": len(props["fx"]), "matte": minfo}
    if engine == "hyperframes":
        hf_render(edl, d, caps, cap_ys, pic, fps, W, H, total, rdir, project, preview, fg if d.get("matte") else None, out, cap_scrims)
        return out, {**info, "engine": "hyperframes", "project": str((rdir / "hf").resolve())}
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    cmd = [npx, "remotion", "render", "src/index.ts", "Design", str(out.resolve()), f"--props={pj.resolve()}",
           f"--public-dir={project.resolve()}", "--codec=h264", "--crf=14", "--log=error"]
    if preview:
        cmd.append("--scale=0.5")
    run(cmd, cwd=rem, timeout=7200)
    return out, {**info, "engine": "remotion"}


HF_CLI = os.environ.get("PVE_HYPERFRAMES", "npx --yes hyperframes@0.9.53").split()   # pinned CLI; override with PVE_HYPERFRAMES
HF_PROJECT_ONLY = False
HF_WORKERS = int(os.environ.get("PVE_HF_WORKERS", "3"))    # STARTING DEFAULT: each worker is a Chrome (~256 MB+); 4 GB free machines were reaped above this


def hf_cmd(*args) -> list[str]:
    exe = shutil.which(HF_CLI[0]) or shutil.which(HF_CLI[0] + ".cmd") or HF_CLI[0]
    return [exe, *HF_CLI[1:], *args]


SCOPE_VF = {   # ffmpeg's own scopes, styled for the Scopes overlay (lib/hf_grade.py)
    "wave": "scale=540:960,format=gbrp,waveform=filter=lowpass:intensity=0.05:display=overlay:components=7:graticule=none,format=yuv420p,scale=640:320",
    "vec": "scale=540:960,format=yuv444p,vectorscope=mode=color4:graticule=none:intensity=0.2,crop=iw/2:ih/2,format=yuv420p,scale=480:480"}


def hf_media(pic: Path, rdir: Path, fps, need_bw: bool, need_soft: bool, raw: Path | None = None,
             scopes: set | None = None) -> dict:
    """Footage for the HyperFrames project, as files (grades and blurs are never CSS on footage):
    base.mp4 with a keyframe every second (seeking a long GOP freezes), base_bw.mp4, base_soft.mp4.
    Cached on the picture's chunk list."""
    md = rdir / "hf_media"
    md.mkdir(exist_ok=True)
    lst = rdir / "chunks.txt"
    key = hashlib.md5((lst.read_text(encoding="utf-8") if lst.exists() else str(pic.stat().st_mtime)).encode()).hexdigest()
    g = str(int(round(float(fps))))
    jobs = {"base": ("base.mp4", "null"), "bw": ("base_bw.mp4", "hue=s=0,eq=contrast=1.15") if need_bw else None,
            "soft": ("base_soft.mp4", "scale=iw/4:-2,boxblur=10:2,scale=1080:1920,eq=brightness=-0.22:saturation=1.2") if need_soft else None}
    if raw is not None:
        jobs["raw"] = ("base_raw.mp4", "null", raw)
        key += hashlib.md5(f"{raw}:{raw.stat().st_mtime}".encode()).hexdigest()
    for kind in scopes or ():
        jobs[kind] = (f"scope_{kind}.mp4", SCOPE_VF[kind])
        if raw is not None:
            jobs[kind + "_raw"] = (f"scope_{kind}_raw.mp4", SCOPE_VF[kind], raw)
    out = {}
    for k, job in jobs.items():
        if job is None:
            out[k] = None
            continue
        f, vf, *src = job
        src = src[0] if src else pic
        dst, kf = md / f, md / (f + ".key")
        if not dst.exists() or not kf.exists() or kf.read_text().strip() != key:
            log(f"  hyperframes media: {f}")
            run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-vf", vf, "-c:v", "libx264", "-crf", "16", "-preset", "fast",
                 "-g", g, "-keyint_min", g, "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)], timeout=3600)
            kf.write_text(key)
        out[k] = dst
    return out


def hf_render(edl, d, caps, cap_ys, pic, fps, W, H, total, rdir, project, preview, fg, out, cap_scrims=None) -> None:
    """Design pass on HyperFrames: write rdir/hf (an editable project), lint it, render design.mp4."""
    from lib import hf_design as HFD
    fonts = project / "fonts"
    if not (fonts / "fonts.css").exists():
        log("  fonts: fetching the design voices (Caveat, Instrument Serif, Anton, Amiri; OFL)")
        run([sys.executable, str(SKILL / "scripts" / "fetch_fonts.py"), "--project", str(project), "Caveat:700", "Instrument Serif:italic400", "Anton:400", "Amiri:700"], timeout=600)
    layout = d.get("layout", [])
    need_soft = any(L["mode"] == "split" for L in layout) or any(sc["p"].get("glass") for sc in d.get("scenes", []))
    need_bw = any(b.get("color") == "bw" for b in d.get("bg", []))
    raw = project / d["raw_video"] if d.get("raw_video") else None
    if raw is not None and not raw.exists():
        raise FileNotFoundError(f"design.raw_video not found: {raw}")
    scopes = {{"wave": "wave", "vector": "vec"}[o["p"].get("kind", "wave")] for o in d.get("overlays", []) if o["type"] == "Scopes"}
    media = hf_media(pic, rdir, fps, need_bw, need_soft, raw, scopes)
    hf = rdir / "hf"
    (hf / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    if (project / "icons3d").exists():          # 3D icon renders used by the motion-graphics scenes
        (hf / "assets" / "icons3d").mkdir(parents=True, exist_ok=True)
        for f in (project / "icons3d").glob("*_color.png"):
            if not (hf / "assets" / "icons3d" / f.name).exists():
                shutil.copy2(f, hf / "assets" / "icons3d" / f.name)
    for f in [p for ext in ("*.woff2", "*.ttf", "*.otf") for p in fonts.glob(ext)]:
        if not (hf / "assets" / "fonts" / f.name).exists():
            shutil.copy2(f, hf / "assets" / "fonts" / f.name)
    HFD.build(d, caps, cap_ys, float(fps), W, H, total, hf, {"base": media["base"], "fg": fg, "bw": media["bw"], "soft": media["soft"],
                                                             "master": rdir / "master.wav", **{k: media.get(k) for k in
                                                             ("raw", "wave", "wave_raw", "vec", "vec_raw")}}, HFD.fonts_inline(fonts), cap_scrims)
    chk = run(hf_cmd("check", "--json", str(hf.resolve())), cwd=hf, check=False, timeout=900)
    try:
        cj = json.loads(chk.stdout.decode("utf-8", "replace"))
    except ValueError:      # 0.9.5x also saves the report under .hyperframes/artifacts/checks; use it when stdout is not JSON
        saved = sorted((hf / ".hyperframes" / "artifacts" / "checks").glob("*.json"), key=lambda p: p.stat().st_mtime)
        try:
            cj = json.loads(saved[-1].read_text(encoding="utf-8")) if saved else {"raw": chk.stdout.decode("utf-8", "replace")[-2000:]}
        except ValueError:
            cj = {"raw": chk.stdout.decode("utf-8", "replace")[-2000:]}
    write_json(rdir / "hf_check.json", cj)
    errs = [{"section": k, **f} for k, v in cj.items() if isinstance(v, dict) for f in (v.get("findings") or [])
            if str(f.get("severity", "")).lower() == "error"]
    for f in errs[:8]:
        log(f"  [hyperframes check] {f['section']}: {f.get('code')} {f.get('selector', '')} at {f.get('time')}s - {str(f.get('message', ''))[:120]}")
    if errs:
        log(f"  [warn] hyperframes check: {len(errs)} error(s), see {rdir / 'hf_check.json'}")
    if HF_PROJECT_ONLY:
        print(json.dumps({"ok": True, "hyperframes_project": str(hf.resolve()), "check_errors": len(errs), "check": str(rdir / "hf_check.json"),
                          "next": f"{' '.join(HF_CLI)} preview {hf.resolve()}  (or render.py without --design-project-only)"}, indent=1))
        sys.exit(0)
    run(hf_cmd("render", str(hf.resolve()), "-o", str(out.resolve()), "--fps", str(fps), "--quality", "draft" if preview else "delivery",
               "--workers", str(HF_WORKERS), "--quiet"), cwd=hf, timeout=7200)


# ----------------------------------------------------------------------------- final
HALATION_THRESHOLD = 200   # STARTING DEFAULT: 8-bit level above which highlights bloom (about 78 %)
HALATION_SIGMA = 0.008     # STARTING DEFAULT: glow radius as a fraction of frame height


def halation_filter(label: str, amount: float, height: int) -> str:
    """Film halation: light scattering back through the emulsion leaves a red-orange glow around bright
    edges (references/craft-color.md). Highlights only, blurred, red-weighted, screened over the picture."""
    t, k = HALATION_THRESHOLD, 255.0 / (255 - HALATION_THRESHOLD)
    sig = max(1.0, HALATION_SIGMA * height)
    return (f"{label}format=gbrp,split[h0][h1];"
            f"[h1]lutrgb=r='clip((val-{t})*{k:.3f},0,255)':g='clip((val-{t})*{k:.3f},0,255)*0.35':b='0',"
            f"gblur=sigma={sig:.1f}[hg];"
            f"[h0][hg]blend=all_mode=screen:all_opacity={min(amount, 1.0):.3f},format=yuv420p[hal]")


def final_encode(pic, master, subs, overlay, edl, rdir, out, mode, look_lut, strength, hybrid=False, halation=0.0) -> str:
    from lib.env import best_h264_encoder
    enc = "libx264" if mode == "preview" else best_h264_encoder()
    chain, inputs = [], ["-i", pic.name, "-i", master.name]
    label = "[0:v]"
    if look_lut is not None and strength > 0:
        shutil.copy2(look_lut, rdir / "look.cube")
        chain.append(f"{label}split[a][b];[b]lut3d=file=look.cube[l];[a][l]blend=all_expr='A*(1-{strength:.3f})+B*{strength:.3f}'[g]")
        label = "[g]"
    if halation > 0:
        chain.append(halation_filter(label, halation, int(edl["project"]["height"])))
        label = "[hal]"
    if overlay is not None:
        inputs += ["-i", overlay.name]
        chain.append(f"{label}[2:v]overlay=0:0:format=auto[o]")
        label = "[o]"
    if subs is not None and (overlay is None or hybrid):
        chain.append(f"{label}subtitles={subs.name}:fontsdir=fonts[s]")
        label = "[s]"
    chain.append(f"{label}format=yuv420p[v]")
    q = ["-crf", "26", "-preset", "veryfast"] if mode == "preview" else FINAL_QUALITY.get(enc, FINAL_QUALITY["libx264"])
    fps = fps_of(edl)
    cmd = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chain), "-map", "[v]", "-map", "1:a",
           "-c:v", enc, *q, "-r", str(fps), "-g", str(int(round(fps)) * 2),
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(out.resolve())]
    try:
        run(cmd, cwd=rdir)
    except ToolError:
        if enc == "libx264":
            raise
        log(f"  {enc} failed; retrying with libx264")
        enc = "libx264"
        i = cmd.index("-c:v")
        cmd[i + 1:i + 2 + len(q)] = [enc] + FINAL_QUALITY["libx264"]
        run(cmd, cwd=rdir)
    hold_true_peak(out, rdir / master.name, float(edl.get("master", {}).get("true_peak_db", -1)))
    return enc


def hold_true_peak(out: Path, master: Path, ceiling: float, tries: int = 3) -> None:
    """AAC overshoot depends on the material: dense SFX transients measured +1.3 dB over the PCM master
    (skincare v2, 2026-11-15), more than CODEC_TP_MARGIN_DB. Measure the delivered file; while it is
    over the ceiling, limit the master by the excess and re-mux the audio only (video stream copied)."""
    from lib import mix
    for _ in range(tries):
        got = mix.true_peak(out)
        if got <= ceiling:
            return
        new_ceiling = mix.true_peak(master) - (got - ceiling) - 0.2
        mix.limit(master, new_ceiling)
        log(f"  true peak {got:.1f} dBTP after AAC > {ceiling:.1f}: master limited to {new_ceiling:.1f} and audio re-muxed")
        tmp = out.with_name(out.stem + "_remux" + out.suffix)
        run(["ffmpeg", "-v", "error", "-y", "-i", str(out.resolve()), "-i", str(master.resolve()), "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(tmp.resolve())])
        tmp.replace(out)


def update_ledger(project: Path, entries: list[dict], commercial: bool) -> list[str]:
    path = project / "licenses.json"
    data = read_json(path) if path.exists() else {"assets": []}
    known = {e["id"] for e in data["assets"]}
    warnings = []
    for e in entries:
        if e["id"] not in known:
            data["assets"].append({k: v for k, v in e.items() if k not in ("at_f",)})
            known.add(e["id"])
        if commercial and e.get("commercial") is False:
            warnings.append(f"{e['id']} is not cleared for commercial use but the project is commercial")
    write_json(path, data)
    return warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", required=True); ap.add_argument("--project", required=True)
    ap.add_argument("--preview", action="store_true"); ap.add_argument("--out")
    ap.add_argument("--design-project-only", action="store_true", help="hyperframes engine: write and lint the editable project (render/<mode>/hf), then stop")
    ap.add_argument("--graphics-engine", choices=["auto", "ass", "remotion", "hybrid", "hyperframes"], default="auto",
                    help="auto = hybrid when the EDL uses Remotion-only graphics (XStamp, WordSlam, Title3D), else remotion when installed")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    project = Path(a.project)
    t0 = time.time()
    try:
        edl = read_json(a.edl)
        media = read_json(project / "media.json")
        analysis = read_json(project / "analysis.json")
    except FileNotFoundError as e:
        fail(str(e))
    from plan_edit import check
    _, rep = check(json.loads(json.dumps(edl)), project, fix=False)
    if not rep["ok"]:
        for e in rep["errors"]:
            log(f"  [error] {e}")
        fail("the EDL has errors; run plan_edit.py check --fix and resolve the rest")
    fps = fps_of(edl)
    mode = "preview" if a.preview else "final"
    W, H = edl["project"]["width"], edl["project"]["height"]
    if a.preview:
        W, H = (W // 2) // 2 * 2, (H // 2) // 2 * 2
    items = {it["id"]: it for it in media["items"]}
    pieces = build_pieces(edl)
    if a.dry_run:
        plan = {"mode": mode, "size": [W, H], "fps": str(fps), "duration_f": timeline_len(edl),
                "pieces": [{"kind": p["kind"], "id": p["ev"].get("id"), "t0": p["t0"], "t1": p["t1"]} for p in pieces],
                "music": len(edl["tracks"].get("music") or []), "sfx": len(edl["tracks"].get("sfx") or []),
                "captions": bool(edl["tracks"].get("captions")), "warnings": rep["warnings"]}
        out = project / "render" / mode / "dry_run.json"
        write_json(out, plan)
        log(f"dry run ok: {len(pieces)} picture pieces, {plan['duration_f']} frames; wrote {out}")
        return
    rdir = project / "render" / mode
    rdir.mkdir(parents=True, exist_ok=True)
    out = Path(a.out) if a.out else project / "exports" / f"{Path(a.edl).stem}{'_preview' if a.preview else ''}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        log(f"render {mode} {W}x{H} @ {fps}: colour")
        colour = colour_plan(edl, items, project, analysis, fps)
        log("picture")
        pic, pinfo = render_picture(edl, items, project, analysis, fps, W, H, mode, rdir, colour)
        log("sound")
        master, sinfo, ledger = render_sound(edl, items, project, analysis, fps, rdir)
        log("captions and graphics")
        subs, cinfo = caption_layer(edl, analysis, fps, W, H, rdir, items, project)
        overlay = None
        dinfo = None
        if edl.get("design"):
            from lib.color import look_path
            col0 = edl.get("color") or {}
            lut0 = look_path(col0.get("look"), SKILL)
            st0 = float(col0.get("strength", 0.0))
            hal0 = float(col0.get("halation", 0.0))
            if (lut0 is not None and st0 > 0) or hal0 > 0:
                # grade the footage only; graphics keep their exact brand colours
                fc, lab = [], "[0:v]"
                if lut0 is not None and st0 > 0:
                    shutil.copy2(lut0, rdir / "look.cube")
                    fc.append(f"[0:v]split[a][b];[b]lut3d=file=look.cube[l];[a][l]blend=all_expr='A*(1-{st0:.3f})+B*{st0:.3f}'[g]")
                    lab = "[g]"
                if hal0 > 0:
                    fc.append(halation_filter(lab, hal0, H))
                    lab = "[hal]"
                fc.append(f"{lab}format=yuv420p[v]")
                run(["ffmpeg", "-v", "error", "-y", "-i", pic.name, "-filter_complex", ";".join(fc),
                     "-map", "[v]", "-c:v", "libx264", "-crf", "12", "-preset", "fast", "picture_graded.mp4"], cwd=rdir)
                pic = rdir / "picture_graded.mp4"
            log("design pass")
            from lib import hf_design
            global HF_PROJECT_ONLY
            HF_PROJECT_ONLY = a.design_project_only
            want = "remotion" if a.graphics_engine == "remotion" else edl["design"].get("engine", "hyperframes") if a.graphics_engine == "auto" else "hyperframes"
            gaps = hf_design.unsupported(edl["design"]) if want == "hyperframes" else []
            if gaps and a.graphics_engine == "hyperframes":
                fail(f"--graphics-engine hyperframes cannot draw: {', '.join(gaps)} (use remotion)")
            engine = "remotion" if gaps else want
            if gaps:
                log(f"  design engine: remotion (hyperframes has no {', '.join(gaps)})")
            log(f"  design engine: {engine}")
            pic, dinfo = design_pass(edl, analysis, pic, fps, W, H, rdir, project, a.preview, engine)
            subs = None   # captions and graphics are drawn by the design pass
        needs_rem = any(g["component"] in REMOTION_ONLY for g in edl["tracks"].get("graphics") or [])
        hybrid = a.graphics_engine == "hybrid" or (a.graphics_engine == "auto" and needs_rem)
        if needs_rem and a.graphics_engine == "ass":
            log("  [warn] XStamp/WordSlam/Title3D need Remotion; --graphics-engine ass drops them")
        if a.graphics_engine in ("auto", "remotion", "hybrid") and subs is not None and dinfo is None:
            overlay = remotion_overlay(edl, rdir / "caption_cards.json", fps, W, H, rdir, hybrid)
            if overlay is None and a.graphics_engine == "remotion":
                log("  remotion not installed (npm install in remotion/); captions drawn with libass")
        from lib.color import look_path
        col = edl.get("color") or {}
        lut = look_path(col.get("look"), SKILL)
        log("encode")
        enc = final_encode(pic, master, subs, overlay, edl, rdir, out, mode, lut, 0.0 if dinfo else float(col.get("strength", 0.0)),
                           hybrid and overlay is not None, 0.0 if dinfo else float(col.get("halation", 0.0)))
        for ext in ("srt", "vtt"):
            shutil.copy2(rdir / f"captions.{ext}", out.with_suffix(f".{ext}"))
        lw = update_ledger(project, ledger, bool(edl["project"].get("commercial", True)))
    except (ToolError, FileNotFoundError, ValueError, KeyError) as e:
        fail(f"render failed: {e}")
    report = {"version": RENDER_VERSION, "edl": Path(a.edl).as_posix(), "output": out.as_posix(), "mode": mode,
              "size": [W, H], "fps": str(fps), "duration_f": timeline_len(edl), "encoder": enc,
              "picture": pinfo, "sound": sinfo, "captions": cinfo,
              "graphics_engine": "design" if dinfo else ("hybrid" if hybrid else "remotion") if overlay is not None else "libass",
              "design": dinfo,
              "colour": {k: {kk: vv for kk, vv in v.items() if kk != "lut"} for k, v in colour.items()},
              "look": {"lut": None if lut is None else lut.name, "strength": col.get("strength", 0.0)},
              "ledger_warnings": lw, "seconds": round(time.time() - t0, 1)}
    write_json(rdir / "render.json", report)
    log(f"wrote {out} ({report['seconds']} s, {pinfo['rendered']} chunks rendered, {pinfo['reused']} reused, {enc})")


if __name__ == "__main__":
    main()
