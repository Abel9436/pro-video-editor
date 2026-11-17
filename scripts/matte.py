#!/usr/bin/env python3
"""Cut the person out of a video: writes the speaker with an alpha channel (VP9 WebM, yuva420p),
so the design pass can put text, halos and recoloured backgrounds BEHIND the speaker.

Usage:
  python scripts/matte.py VIDEO --out FG.webm [--report R.json] [--threshold 0.5] [--feather 3]

Model: PP-HumanSeg (OpenCV Zoo `human_segmentation_pphumanseg_2023mar.onnx`, Apache-2.0,
https://github.com/opencv/opencv_zoo/tree/main/models/human_segmentation_pphumanseg). It is
downloaded on first use into assets/cache/models/ (never committed). Inference runs at 192x192;
the mask is upscaled, edge-refined against the full-resolution luma and smoothed over time.

The report gives the mean person coverage and how many frames had no person, so the plan can
avoid "behind" text where the matte is empty or the subject fills the frame.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from lib.common import ToolError, fail, ffprobe_json, log, write_json  # noqa: E402

MODEL_URL = ("https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
             "human_segmentation_pphumanseg/human_segmentation_pphumanseg_2023mar.onnx")
MODEL = Path(__file__).resolve().parents[1] / "assets" / "cache" / "models" / "human_segmentation_pphumanseg_2023mar.onnx"
IN = 192
TEMPORAL = 0.6          # STARTING DEFAULT: weight of the current frame in the running mask (kills edge flicker)
EDGE_RADIUS = 8         # STARTING DEFAULT: guided-filter radius (px at 1080 wide) for hair/shoulder edges


def model():
    import onnxruntime as ort
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        log(f"downloading PP-HumanSeg (Apache-2.0) to {MODEL}")
        try:
            r = subprocess.run(["curl", "-sSL", "-o", str(MODEL), MODEL_URL], timeout=900)
            if r.returncode != 0:
                urllib.request.urlretrieve(MODEL_URL, MODEL)
        except Exception as e:  # noqa: BLE001
            raise ToolError(f"could not download the segmentation model: {e}")
        if MODEL.stat().st_size < 100_000:
            MODEL.unlink()
            raise ToolError("segmentation model download is not an ONNX file (Git LFS pointer?)")
    return ort.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])


def guided(I: np.ndarray, p: np.ndarray, r: int, eps: float = 1e-3) -> np.ndarray:
    import cv2
    k = (2 * r + 1, 2 * r + 1)
    mI = cv2.blur(I, k); mp = cv2.blur(p, k)
    cov = cv2.blur(I * p, k) - mI * mp
    var = cv2.blur(I * I, k) - mI * mI
    a = cov / (var + eps); b = mp - a * mI
    return cv2.blur(a, k) * I + cv2.blur(b, k)


def run(video: Path, out: Path, threshold: float, feather: int) -> dict:
    import cv2
    pr = ffprobe_json(video)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    W, H = int(v["width"]), int(v["height"])
    rate = v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1"
    sess = model()
    iname = sess.get_inputs()[0].name
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", rate, "-i", "-",
                            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "30", "-row-mt", "1", "-deadline", "realtime",
                            "-cpu-used", "8", "-auto-alt-ref", "0", str(out)], stdin=subprocess.PIPE)
    n = W * H * 3
    prev = None
    cover, empty, frames = [], 0, 0
    r = max(2, int(EDGE_RADIUS * W / 1080))
    try:
        while True:
            buf = dec.stdout.read(n)
            if len(buf) < n:
                break
            fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            x = cv2.resize(fr, (IN, IN), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
            x = ((x - 0.5) / 0.5).transpose(2, 0, 1)[None]
            o = sess.run(None, {iname: x})[0][0]
            e = np.exp(o - o.max(0, keepdims=True))
            m = (e[1] / e.sum(0)).astype(np.float32)
            m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
            gray = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
            m = np.clip(guided(gray, m, r), 0, 1)
            m = prev * (1 - TEMPORAL) + m * TEMPORAL if prev is not None else m
            prev = m
            a = np.clip((m - threshold) * 6 + 0.5, 0, 1)
            if feather > 0:
                a = cv2.GaussianBlur(a, (0, 0), feather)
            cover.append(float(a.mean()))
            empty += a.max() < 0.5
            rgba = np.dstack([fr, (a * 255).astype(np.uint8)])
            enc.stdin.write(rgba.tobytes())
            frames += 1
    finally:
        dec.stdout.close(); dec.wait()
        enc.stdin.close(); enc.wait()
    if frames == 0 or enc.returncode != 0:
        raise ToolError(f"matte failed: {frames} frames, encoder exit {enc.returncode}")
    return {"out": str(out), "frames": frames, "width": W, "height": H, "model": "PP-HumanSeg 2023mar (Apache-2.0)",
            "mean_coverage": round(float(np.mean(cover)), 3), "frames_without_person": int(empty),
            "threshold": threshold, "feather_px": feather}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--feather", type=int, default=3)
    a = ap.parse_args()
    if not a.video.exists():
        fail(f"video not found: {a.video}")
    try:
        rep = run(a.video, a.out, a.threshold, a.feather)
    except ToolError as e:
        fail(str(e))
    if a.report:
        write_json(a.report, rep)
    log(f"wrote {a.out}: {rep['frames']} frames, mean coverage {rep['mean_coverage']}, {rep['frames_without_person']} frames without a person")
    print(__import__("json").dumps(rep))


if __name__ == "__main__":
    main()
