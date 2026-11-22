"""Neural speech enhancement for a phone- or camera-mic recording: DeepFilterNet 3 removes room noise, hum
and some room echo, then render.py mixes the cleaned voice with the studio voice chain (mix.voice_chain).

  python scripts/enhance_voice.py --project P --item ID [--atten-db 100] [--bin PATH]

DeepFilterNet (Schroeter et al., MIT / Apache-2.0) runs locally from its release binary
(github.com/Rikorose/DeepFilterNet/releases, deep-filter-<ver>-x86_64-pc-windows-msvc.exe or the Linux/macOS
build). The binary is looked up in --bin, $PVE_DEEPFILTER, PATH ("deep-filter"), then ~/bin/deepfilter/.
It is run with -D (delay compensated: the output lines up with the picture to the sample) and --pf (post-filter).
--atten-db caps how far the noise is pulled down; 100 = no cap. A lower cap (e.g. 24) keeps a trace of the room
when the full reduction sounds too dry - STARTING DEFAULT 100, judged by ear per recording.

Then it fits a "mic" EQ for the studio chain: six bands (150, 340, 750, 2800, 5500 Hz peaks, 8 kHz shelf) are
moved, within limits, so the speech's long-term spectrum approaches the ANSI S3.5 average-speech spectrum
(converted to per-Hz density relative to 1-2 kHz; targets approximate). A far phone mic reads dark and boomy, so
this mostly cuts the room boom and lifts presence; the limits (cuts to -6 dB, lifts to +6, shelf to +8) stop it
pulling up hiss that is not voice. Limits are STARTING DEFAULTS set on the angt take (2026-11-22).

Writes P/audio/<id>_voice_clean.wav (48 kHz stereo), sets media.json item["voice_clean"] and item["voice_eq"],
and prints JSON with the noise floor before and after (10th percentile of 50 ms RMS windows, dBFS) and the
spectrum error before and after the EQ. Exits 1 when the binary is missing.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
from lib.common import run  # noqa: E402

SR = 48000


def find_bin(arg):
    for c in (arg, os.environ.get("PVE_DEEPFILTER"), shutil.which("deep-filter"),
              str(Path.home() / "bin/deepfilter/deep-filter.exe"), str(Path.home() / "bin/deepfilter/deep-filter")):
        if c and Path(c).is_file():
            return c
    return None


def floor_db(x):
    h = SR // 20
    n = len(x) // h
    e = 20 * np.log10(np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9)
    return round(float(np.percentile(e, 10)), 1), round(float(np.percentile(e, 95)), 1)


F = np.fft.rfftfreq(4096, 1 / SR)
BANDS = [(120, 250), (250, 500), (500, 1000), (2000, 4000), (4000, 8000), (8000, 12000)]
TARGET = [14, 16, 8, -6, -13, -19]                     # dB per-Hz density relative to 1-2 kHz (ANSI S3.5, approx.)
EQ = [(150, "peak", 1.0, -6, 3), (340, "peak", 1.6, -6, 2), (750, "peak", 1.2, -4, 3), (2800, "peak", 0.9, -3, 6),
      (5500, "peak", 0.9, -3, 6), (8000, "shelf", 0, -3, 8)]   # freq, kind, width, min dB, max dB


def eq_filters(gains):
    out = []
    for (fq, kind, w, _, _), g in zip(EQ, gains):
        if abs(g) < 0.25:
            continue
        out.append(f"highshelf=f={fq}:g={g:.1f}" if kind == "shelf" else f"equalizer=f={fq}:t=q:w={w}:g={g:.1f}")
    return out


def spectrum_err(x):
    h = SR // 20
    n = len(x) // h
    fr = x[:n * h].reshape(n, h)
    e = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    loud = fr[e > np.percentile(e, 60)].ravel()                 # speech frames only
    S = np.zeros(len(F))
    k = 0
    for i in range(0, len(loud) - 4096, 4096):
        S += np.abs(np.fft.rfft(loud[i:i + 4096] * np.hanning(4096))) ** 2
        k += 1
    ref = S[(F >= 1000) & (F < 2000)].mean()
    return [round(float(10 * np.log10(S[(F >= a) & (F < b)].mean() / ref)) - t, 1) for (a, b), t in zip(BANDS, TARGET)]


def fit_eq(wav: Path, tmp: Path):
    """Three passes: move each band against its error (80 %), clamp, re-measure through FFmpeg."""
    x, _ = sf.read(wav, dtype="float32")
    x = x.mean(1) if x.ndim > 1 else x
    err0 = spectrum_err(x)
    gains = [0.0] * len(EQ)
    err = err0
    for _ in range(3):
        gains = [float(np.clip(g - 0.8 * e, lo, hi)) for g, e, (_, _, _, lo, hi) in zip(gains, err, EQ)]
        run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", ",".join(eq_filters(gains) or ["anull"]), str(tmp)])
        y, _ = sf.read(tmp, dtype="float32")
        err = spectrum_err(y.mean(1) if y.ndim > 1 else y)
    return [round(g, 1) for g in gains], err0, err


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--item", required=True, help="media.json item id")
    ap.add_argument("--atten-db", type=float, default=100)
    ap.add_argument("--bin", default=None)
    a = ap.parse_args()
    P = Path(a.project)
    exe = find_bin(a.bin)
    if not exe:
        print(json.dumps({"ok": False, "error": "deep-filter binary not found; download it from "
                          "github.com/Rikorose/DeepFilterNet/releases and pass --bin or set PVE_DEEPFILTER"}))
        sys.exit(1)
    media = json.loads((P / "media.json").read_text(encoding="utf-8"))
    it = next((i for i in media["items"] if i["id"] == a.item), None)
    if not it:
        print(json.dumps({"ok": False, "error": f"no item {a.item} in media.json"}))
        sys.exit(1)
    src = it.get("render_src") or it["path"]
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "voice.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(raw)])
        out = Path(td) / "out"
        run([exe, "-D", "--pf", "-a", str(a.atten_db), "-o", str(out), str(raw)])
        x, _ = sf.read(raw, dtype="float32")
        y, _ = sf.read(out / "voice.wav", dtype="float32")
    y = np.pad(y, (0, max(0, len(x) - len(y))))[:len(x)]          # same length as the source, sample-aligned
    dst = P / "audio" / f"{a.item}_voice_clean.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(dst, np.stack([y, y], 1), SR, subtype="FLOAT")
    gains, err0, err1 = fit_eq(dst, P / "audio" / f"{a.item}_eqfit.wav")
    (P / "audio" / f"{a.item}_eqfit.wav").unlink(missing_ok=True)
    it["voice_clean"] = str(dst.relative_to(P)).replace("\\", "/")
    it["voice_eq"] = eq_filters(gains)
    it["voice_clean_how"] = f"DeepFilterNet ({Path(exe).name}) -D --pf -a {a.atten_db:g}"
    (P / "media.json").write_text(json.dumps(media, indent=1, ensure_ascii=False), encoding="utf-8")
    (f0, p0), (f1, p1) = floor_db(x), floor_db(y)
    print(json.dumps({"ok": True, "item": a.item, "out": it["voice_clean"], "noise_floor_db": {"before": f0, "after": f1},
                      "loud_p95_db": {"before": p0, "after": p1}, "reduction_db": round(f0 - f1, 1),
                      "eq": it["voice_eq"], "spectrum_err_db": {"bands_hz": BANDS, "before": err0, "after": err1}}))


if __name__ == "__main__":
    main()
