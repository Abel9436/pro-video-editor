"""Music analysis (BPM, beats, downbeats, sections, energy) and EBU R128 loudness."""
from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

import numpy as np

from .common import run

HOP = 256                    # 16 ms at 16 kHz: beat times accurate to half a frame at 30 fps
ENERGY_STEP_S = Fraction(1, 2)
SECTION_SECONDS = 20         # one section per ~20 s, clamped to 2..10


def analyze_music(x: np.ndarray, sr: int, fps: Fraction) -> dict:
    import librosa

    onset = librosa.onset.onset_strength(y=x, sr=sr, hop_length=HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=HOP, units="frames")
    tempo = float(np.atleast_1d(tempo)[0])
    beat_t = librosa.frames_to_time(beats, sr=sr, hop_length=HOP)

    # Downbeats: assume 4/4 and pick the beat phase with the strongest accents.
    # A heuristic: madmom's downbeat tracker is better but does not install on Python 3.13.
    phase, conf = 0, 0.0
    if beats.size >= 8:
        strengths = [float(onset[beats[p::4]].mean()) for p in range(4)]
        phase = int(np.argmax(strengths))
        srt = sorted(strengths)
        conf = round((srt[-1] - srt[-2]) / (srt[-1] + 1e-9), 3)
    down_t = beat_t[phase::4]

    dur = x.size / sr
    k = int(min(10, max(2, dur // SECTION_SECONDS)))
    sections = []
    if beats.size > k * 2:
        chroma = librosa.feature.chroma_cqt(y=x, sr=sr, hop_length=HOP)
        mfcc = librosa.feature.mfcc(y=x, sr=sr, hop_length=HOP, n_mfcc=13)
        feat = librosa.util.sync(np.vstack([chroma, mfcc / (np.abs(mfcc).max() + 1e-9)]), beats)
        bounds = librosa.segment.agglomerative(feat, k)
        bound_t = librosa.frames_to_time(beats[np.clip(bounds, 0, beats.size - 1)], sr=sr, hop_length=HOP)
        bound_t = sorted(set([0.0] + [float(t) for t in bound_t]))
        sections = [{"s_f": round(Fraction(a).limit_denominator(10**6) * fps),
                     "e_f": round(Fraction(b).limit_denominator(10**6) * fps)}
                    for a, b in zip(bound_t, bound_t[1:] + [dur])]

    rms = librosa.feature.rms(y=x, hop_length=HOP)[0]
    step = int(ENERGY_STEP_S * sr / HOP)
    energy = [float(rms[i:i + step].mean()) for i in range(0, rms.size, step)]
    peak = max(energy) if energy else 1.0

    def to_f(t):
        return round(Fraction(float(t)).limit_denominator(10**6) * fps)

    return {
        "bpm": round(tempo, 2),
        "beats_f": [to_f(t) for t in beat_t],
        "downbeats_f": [to_f(t) for t in down_t],
        "downbeat_method": "accent_phase_4_4_heuristic",
        "downbeat_confidence": conf,
        "sections": sections,
        "energy": {"step_f": int(ENERGY_STEP_S * fps),
                   "values": [round(e / (peak + 1e-12), 3) for e in energy]},
    }


def loudness_r128(path: Path, fps: Fraction, stream: int = 0) -> dict:
    """Integrated, LRA and true peak from FFmpeg's ebur128 (EBU R128 / ITU-R BS.1770)."""
    proc = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", f"0:a:{stream}",
                "-af", "ebur128=peak=true", "-f", "null", "-"])
    err = proc.stderr.decode("utf-8", "replace")
    series = [(float(t), float(s)) for t, s in
              re.findall(r"t:\s*([\d.]+)\s+TARGET:.*?S:\s*(-?[\d.inf]+)", err) if s not in ("-inf", "inf")]
    summary = err[err.rfind("Summary:"):] if "Summary:" in err else ""

    def grab(pattern):
        m = re.search(pattern, summary, re.S)
        return float(m.group(1)) if m else None

    # short-term loudness every 0.5 s, as frames
    st, last = [], -1.0
    for t, s in series:
        if t - last >= 0.5:
            st.append([round(Fraction(t).limit_denominator(1000) * fps), s])
            last = t
    return {
        "integrated_lufs": grab(r"I:\s*(-?[\d.]+)\s*LUFS"),
        "lra_lu": grab(r"LRA:\s*(-?[\d.]+)\s*LU"),
        "true_peak_dbtp": grab(r"Peak:\s*(-?[\d.]+)\s*dBFS"),
        "short_term": {"step": "0.5s", "points_f_lufs": st},
    }


def noise_floor_db(x: np.ndarray, sr: int) -> float:
    """10th percentile of 50 ms RMS levels: the room/self noise between words."""
    hop = sr // 20
    n = x.size // hop
    if n < 5:
        return -90.0
    rms = np.sqrt((x[: n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(1) + 1e-12)
    return round(float(20 * np.log10(np.percentile(rms, 10) + 1e-12)), 1)
