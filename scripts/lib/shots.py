"""Shot boundaries, keyframes, contact sheets and per-shot visual measures.

Works on the proxy, whose frame N is timeline frame N (ingest makes proxies at
the timeline rate), so every number here is already in timeline frames.
"""
from __future__ import annotations

import os
import urllib.request
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from .common import rel
from .timebase import timecode

# PySceneDetect AdaptiveDetector defaults (adaptive_threshold 3.0) handle camera
# motion better than a fixed content threshold. Shots shorter than MIN_SHOT_F are merged.
MIN_SHOT_F = 4
HIST_CUT_THRESHOLD = 0.45      # fallback detector: Bhattacharyya distance between HSV histograms

SHEET_COLS, SHEET_ROWS = 4, 4  # 16 shots per contact sheet; one image covers many shots
TILE_W = 270                   # tile width in px; sheets stay under ~1100 px wide

YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
             "face_detection_yunet_2023mar.onnx")

# Camera-move classification thresholds per frame (proxy pixels normalised to width).
# STARTING DEFAULTS.
MOVE_STATIC_PCT = 0.08         # <0.08 % of width per frame = locked off
ZOOM_RATE = 0.0015             # >0.15 % scale change per frame = push in / pull out
JITTER_PCT = 0.25              # residual high-frequency motion above this = handheld


def detect_shots(proxy: Path, total_f: int) -> tuple[list[dict], str]:
    try:
        from scenedetect import AdaptiveDetector, detect
        scenes = detect(str(proxy), AdaptiveDetector(min_scene_len=MIN_SHOT_F))
        cuts = [(s.get_frames(), e.get_frames()) for s, e in scenes]
        method = "pyscenedetect_adaptive"
    except ImportError:
        cuts, method = _hist_detect(proxy), "opencv_hsv_histogram"
    if not cuts:
        cuts = [(0, total_f)]
    shots = [{"n": k, "s_f": a, "e_f": b, "dur_f": b - a} for k, (a, b) in enumerate(cuts)]
    return shots, method


def _hist_detect(proxy: Path) -> list[tuple[int, int]]:
    cap = cv2.VideoCapture(str(proxy))
    prev, cuts, f = None, [0], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        hsv = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2HSV)
        h = cv2.calcHist([hsv], [0, 1], None, [32, 16], [0, 180, 0, 256])
        cv2.normalize(h, h)
        if prev is not None and cv2.compareHist(prev, h, cv2.HISTCMP_BHATTACHARYYA) > HIST_CUT_THRESHOLD \
                and f - cuts[-1] >= MIN_SHOT_F:
            cuts.append(f)
        prev, f = h, f + 1
    cap.release()
    cuts.append(f)
    return [(cuts[k], cuts[k + 1]) for k in range(len(cuts) - 1)]


def keyframe_positions(s_f: int, e_f: int, fps: Fraction) -> list[int]:
    """1 to 3 keyframes per shot depending on length."""
    dur = e_f - s_f
    if dur < 2 * fps:
        rel = [0.5]
    elif dur < 6 * fps:
        rel = [0.25, 0.75]
    else:
        rel = [0.15, 0.5, 0.85]
    return [min(e_f - 1, s_f + int(dur * r)) for r in rel]


class FrameReader:
    def __init__(self, path: Path):
        self.cap = cv2.VideoCapture(str(path))
        self.pos = -1

    def read(self, f: int) -> np.ndarray | None:
        if f != self.pos + 1:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, frame = self.cap.read()
        self.pos = f if ok else -1
        return frame if ok else None

    def close(self):
        self.cap.release()


class FaceDetector:
    """YuNet (accurate, gives landmarks) when the model can be fetched; Haar otherwise."""

    def __init__(self, model_dir: Path):
        self.method = "haar"
        self.yunet = None
        path = model_dir / "face_detection_yunet_2023mar.onnx"
        try:
            if not path.exists():
                if os.environ.get("PVE_OFFLINE"):
                    raise RuntimeError("offline: YuNet model not cached")
                model_dir.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(YUNET_URL, path)
            self.yunet = cv2.FaceDetectorYN.create(str(path), "", (320, 320), 0.7)
            self.method = "yunet"
        except Exception:
            self.yunet = None
        # Haar cascades were removed in OpenCV 5; without them eyes/smile are reported as null.
        cc = getattr(cv2, "CascadeClassifier", None)
        base = getattr(getattr(cv2, "data", None), "haarcascades", "")
        self.haar = cc(base + "haarcascade_frontalface_default.xml") if cc else None
        self.eyes = cc(base + "haarcascade_eye_tree_eyeglasses.xml") if cc else None
        self.smile = cc(base + "haarcascade_smile.xml") if cc else None
        if self.yunet is None and self.haar is None:
            self.method = "none"

    def faces(self, frame: np.ndarray) -> list[dict]:
        h, w = frame.shape[:2]
        boxes = []
        if self.yunet is not None:
            self.yunet.setInputSize((w, h))
            _, det = self.yunet.detect(frame)
            for d in det if det is not None else []:
                boxes.append((int(d[0]), int(d[1]), int(d[2]), int(d[3]), float(d[14])))
        elif self.haar is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            for (x, y, bw, bh) in self.haar.detectMultiScale(gray, 1.1, 5, minSize=(max(24, w // 20),) * 2):
                boxes.append((int(x), int(y), int(bw), int(bh), 1.0))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        out = []
        for x, y, bw, bh, score in sorted(boxes, key=lambda b: -b[2] * b[3]):
            x, y = max(0, x), max(0, y)
            roi = gray[y:y + bh, x:x + bw]
            eyes_open = smile = None
            if roi.size and bw >= 48 and self.eyes is not None:
                upper, lower = roi[: bh // 2], roi[bh // 2:]
                eyes_open = len(self.eyes.detectMultiScale(upper, 1.1, 6)) >= 2
                smile = len(self.smile.detectMultiScale(lower, 1.7, 22)) > 0
            cx = (x + bw / 2) / w
            out.append({"box": [round(x / w, 3), round(y / h, 3), round(bw / w, 3), round(bh / h, 3)],
                        "size": round(bh / h, 3),
                        "position": "left" if cx < 1 / 3 else ("right" if cx > 2 / 3 else "center"),
                        "score": round(score, 2), "eyes_open": eyes_open, "smile": smile})
        return out


def _camera_move(frames: list[np.ndarray]) -> dict:
    """Similarity transform between consecutive frames from tracked corners."""
    txs, tys, scales, rots = [], [], [], []
    for a, b in zip(frames, frames[1:]):
        ga, gb = (cv2.cvtColor(cv2.resize(f, (320, int(320 * f.shape[0] / f.shape[1]))), cv2.COLOR_BGR2GRAY)
                  for f in (a, b))
        pts = cv2.goodFeaturesToTrack(ga, 200, 0.01, 8)
        if pts is None or len(pts) < 12:
            continue
        nxt, st, _ = cv2.calcOpticalFlowPyrLK(ga, gb, pts, None)
        good = st.reshape(-1) == 1
        if good.sum() < 10:
            continue
        M, _ = cv2.estimateAffinePartial2D(pts[good], nxt[good])
        if M is None:
            continue
        s = float(np.hypot(M[0, 0], M[1, 0]))
        txs.append(M[0, 2] / 320 * 100)
        tys.append(M[1, 2] / 320 * 100)
        scales.append(s)
        rots.append(float(np.degrees(np.arctan2(M[1, 0], M[0, 0]))))
    if not txs:
        return {"type": "unknown"}
    tx, ty, sc = float(np.median(txs)), float(np.median(tys)), float(np.median(scales))
    jitter = float(np.std(txs) + np.std(tys))
    if abs(sc - 1) > ZOOM_RATE:
        kind = "push_in" if sc > 1 else "pull_out"
    elif max(abs(tx), abs(ty)) > MOVE_STATIC_PCT:
        kind = ("pan_left" if tx > 0 else "pan_right") if abs(tx) >= abs(ty) else ("tilt_up" if ty > 0 else "tilt_down")
    else:
        kind = "static"
    if jitter > JITTER_PCT and kind != "static":
        kind += "_handheld"
    elif jitter > JITTER_PCT:
        kind = "handheld"
    return {"type": kind, "pan_pct_per_f": round(tx, 3), "tilt_pct_per_f": round(ty, 3),
            "scale_per_f": round(sc, 5), "jitter": round(jitter, 3)}


def measure_shots(proxy: Path, shots: list[dict], fps: Fraction, out_dir: Path, file_id: str,
                  faces: FaceDetector) -> None:
    """Fill each shot with keyframes, sharpness, exposure, motion, camera move and faces."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rd = FrameReader(proxy)
    for sh in shots:
        kfs = []
        sharp, lum, hi, lo, mags, face_rows = [], [], [], [], [], []
        for f in keyframe_positions(sh["s_f"], sh["e_f"], fps):
            frame = rd.read(f)
            if frame is None:
                continue
            p = out_dir / f"{file_id}_s{sh['n']:03d}_{f}.jpg"
            cv2.imwrite(str(p), frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            kfs.append({"f": f, "path": p.as_posix()})
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharp.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            lum.append(float(gray.mean()))
            hi.append(float((gray >= 250).mean() * 100))
            lo.append(float((gray <= 5).mean() * 100))
            face_rows.append(faces.faces(frame))
            nxt = rd.read(f + 1) if f + 1 < sh["e_f"] else None
            if nxt is not None:
                g2 = cv2.cvtColor(nxt, cv2.COLOR_BGR2GRAY)
                small = (160, int(160 * gray.shape[0] / gray.shape[1]))
                flow = cv2.calcOpticalFlowFarneback(cv2.resize(gray, small), cv2.resize(g2, small), None,
                                                    0.5, 3, 15, 3, 5, 1.2, 0)
                mags.append(float(np.linalg.norm(flow, axis=2).mean()) / 160 * 100)
        # camera move from 5 frames spread over the middle of the shot
        span = sh["e_f"] - sh["s_f"]
        move_frames = []
        if span >= 6:
            start = sh["s_f"] + span // 4
            step = max(1, min(3, span // 10))
            for k in range(5):
                fr = rd.read(min(sh["e_f"] - 1, start + k * step))
                if fr is not None:
                    move_frames.append(fr)
        counts = [len(r) for r in face_rows]
        main = max((r[0] for r in face_rows if r), key=lambda d: d["size"], default=None)
        sh.update({
            "keyframes": kfs,
            "sharpness": round(float(np.median(sharp)), 1) if sharp else None,
            "exposure": {"mean_luma": round(float(np.mean(lum)), 1) if lum else None,
                         "clipped_high_pct": round(float(np.mean(hi)), 2) if hi else None,
                         "crushed_low_pct": round(float(np.mean(lo)), 2) if lo else None},
            "motion_pct_per_f": round(float(np.mean(mags)), 3) if mags else None,
            "camera": _camera_move(move_frames) if len(move_frames) >= 3 else {"type": "too_short"},
            "faces": {"count": int(max(counts)) if counts else 0, "main": main, "method": faces.method},
        })
    rd.close()


def contact_sheets(shots_by_file: dict[str, list[dict]], fps: Fraction, root: Path, out_dir: Path,
                   max_images: int) -> dict:
    """Grid images of one keyframe per shot. Samples shots evenly when the budget is exceeded.

    Keyframe paths are relative to `root` (the project); sheet paths are returned the same way.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = [(fid, sh) for fid, shots in shots_by_file.items() for sh in shots if sh.get("keyframes")]
    per_sheet = SHEET_COLS * SHEET_ROWS
    cols, rows = SHEET_COLS, SHEET_ROWS
    total = len(entries)
    # grow the grid to 6x6 before dropping shots
    while -(-total // (cols * rows)) > max_images and cols < 6:
        cols, rows = cols + 1, rows + 1
    per_sheet = cols * rows
    sampled = False
    if -(-total // per_sheet) > max_images:
        keep = max_images * per_sheet
        idx = np.unique(np.linspace(0, total - 1, keep).astype(int))
        entries = [entries[i] for i in idx]
        sampled = True
    for old in out_dir.glob("sheet_*.jpg"):
        old.unlink()
    sheets = []
    tile_w = TILE_W if cols <= 4 else 200
    for k in range(0, len(entries), per_sheet):
        chunk = entries[k:k + per_sheet]
        tiles = []
        for fid, sh in chunk:
            kf = sh["keyframes"][len(sh["keyframes"]) // 2]
            img = cv2.imread(str(Path(root) / kf["path"]))
            if img is None:
                continue
            th = int(tile_w * img.shape[0] / img.shape[1])
            img = cv2.resize(img, (tile_w, th))
            label = f"{fid[:14]} #{sh['n']} {timecode(sh['s_f'], fps)}"
            cv2.rectangle(img, (0, th - 22), (tile_w, th), (0, 0, 0), -1)
            cv2.putText(img, label, (4, th - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(img)
        if not tiles:
            continue
        th = max(t.shape[0] for t in tiles)
        tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
        blank = np.zeros_like(tiles[0])
        while len(tiles) % cols:
            tiles.append(blank)
        grid = np.vstack([np.hstack(tiles[r * cols:(r + 1) * cols]) for r in range(len(tiles) // cols)])
        p = out_dir / f"sheet_{len(sheets) + 1:02d}.jpg"
        cv2.imwrite(str(p), grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
        sheets.append({"path": rel(p, root), "shots": [[fid, sh["n"]] for fid, sh in chunk]})
    return {"limit": max_images, "images": sheets, "count": len(sheets), "grid": f"{cols}x{rows}",
            "shots_total": total, "shots_shown": len(entries), "sampled": sampled}
