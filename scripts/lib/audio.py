"""Audio helpers: WAV loading, streaming level scan, cross-correlation sync."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .common import ToolError

ANALYSIS_SR = 16000          # analysis WAVs are mono 16 kHz (speech models expect this)
ENVELOPE_SR = 200            # coarse sync envelope rate: 5 ms resolution, cheap FFT on hour-long files
SYNC_REFINE_WINDOW_S = 0.1   # fine search radius around the coarse lag
SYNC_MIN_OVERLAP_S = 3.0     # shorter overlaps give unreliable correlation peaks
SYNC_MIN_PEAK_Z = 8.0        # peak must stand this many robust std-devs above the correlation floor
SYNC_MIN_PEARSON = 0.25      # envelope correlation over the overlap at the chosen lag

CLIP_LEVEL = 0.999           # |sample| at or above this counts as at full scale
CLIP_RUN = 3                 # 3+ consecutive flat full-scale samples = a flat-topped (clipped) wave
CLIP_FLAT_DELTA = 1e-4       # neighbouring samples within 1e-4 (-80 dB) count as flat
SILENCE_PEAK = 1e-4          # peak below -80 dBFS = digital silence / dead channel


def load_wav(path: str | Path) -> tuple[np.ndarray, int]:
    import soundfile as sf
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return data.mean(axis=1), sr


@dataclass
class LevelScan:
    peak: float
    clipped_samples: int
    clipped_runs: int
    total_samples: int
    overs: int = 0                # samples above 1.0 after decoding (lossy overshoot)

    @property
    def clipped_pct(self) -> float:
        return 100.0 * self.clipped_samples / max(1, self.total_samples)

    @property
    def peak_dbfs(self) -> float:
        return float(20 * np.log10(max(self.peak, 1e-12)))


def scan_levels(path: str | Path, stream: int = 0) -> LevelScan:
    """Stream the native-rate audio through FFmpeg and count flat-topped clipping.

    Resampled analysis WAVs smooth peaks away, so clipping is measured here on
    the original sample rate, in chunks, without holding the file in memory.
    """
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-map", f"0:a:{stream}", "-ac", "1",
           "-f", "f32le", "-acodec", "pcm_f32le", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    peak, clipped, runs, total, carry, overs = 0.0, 0, 0, 0, 0, 0
    chunk_bytes = 4 * 48000 * 10
    assert proc.stdout is not None
    while True:
        buf = proc.stdout.read(chunk_bytes)
        if not buf:
            break
        x = np.frombuffer(buf[: len(buf) // 4 * 4], dtype=np.float32)
        total += x.size
        a = np.abs(x)
        if a.size:
            peak = max(peak, float(a.max()))
            overs += int((a > 1.0).sum())
        # Clipping = flat tops: at full scale AND (nearly) the same value as the previous sample.
        # Lossy decoders overshoot past 1.0 with ringing, which is loud but not flat.
        flat = np.concatenate(([False], np.abs(np.diff(x)) < CLIP_FLAT_DELTA))
        hot = (a >= CLIP_LEVEL) & flat
        clipped += int(hot.sum())
        if hot.any():
            # run-length of consecutive hot samples, carrying a run across chunk edges
            padded = np.concatenate(([0], hot.astype(np.int8), [0]))
            d = np.diff(padded)
            starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
            lengths = ends - starts
            if carry and starts.size and starts[0] == 0:
                lengths[0] += carry
            runs += int((lengths >= CLIP_RUN).sum())
            carry = int(lengths[-1]) if ends.size and ends[-1] == x.size else 0
        else:
            carry = 0
    proc.wait()
    if proc.returncode != 0:
        err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        raise ToolError(f"ffmpeg could not decode audio of {Path(path).name}: {err.strip()[-300:]}")
    return LevelScan(peak, clipped, runs, total, overs)


def envelope(x: np.ndarray, sr: int, out_sr: int = ENVELOPE_SR) -> np.ndarray:
    """Log-compressed RMS envelope, mean-removed. Robust to gain differences between mics."""
    hop = max(1, sr // out_sr)
    n = x.size // hop
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    frames = x[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1) + 1e-12)
    env = np.log(rms + 1e-4)
    # first difference emphasises onsets (claps, plosives) which carry the sync information
    env = np.diff(env, prepend=env[0])
    env -= env.mean()
    std = env.std()
    return (env / std if std > 0 else env).astype(np.float32)


@dataclass
class SyncResult:
    offset_samples: int      # where sample 0 of `other` lands on the reference, at ANALYSIS_SR
    peak_z: float
    pearson: float
    overlap_s: float

    @property
    def accepted(self) -> bool:
        return (self.peak_z >= SYNC_MIN_PEAK_Z and self.pearson >= SYNC_MIN_PEARSON
                and self.overlap_s >= SYNC_MIN_OVERLAP_S)


def find_offset(ref: np.ndarray, other: np.ndarray, sr: int = ANALYSIS_SR) -> SyncResult:
    """Align `other` to `ref` by envelope cross-correlation, then refine on raw samples."""
    from scipy.signal import correlate

    er, eo = envelope(ref, sr), envelope(other, sr)
    if er.size < 10 or eo.size < 10:
        return SyncResult(0, 0.0, 0.0, 0.0)
    c = correlate(er, eo, mode="full", method="fft")
    k = int(np.argmax(c))
    lag_env = k - (eo.size - 1)
    med = float(np.median(c))
    mad = float(np.median(np.abs(c - med))) * 1.4826 + 1e-9
    peak_z = (float(c[k]) - med) / mad

    # Pearson over the overlapping region at the chosen lag
    a0, b0 = max(0, lag_env), max(0, -lag_env)
    n = min(er.size - a0, eo.size - b0)
    pearson = float(np.corrcoef(er[a0:a0 + n], eo[b0:b0 + n])[0, 1]) if n > 10 else 0.0
    overlap_s = n / ENVELOPE_SR

    hop = sr // ENVELOPE_SR
    coarse = lag_env * hop
    radius = int(SYNC_REFINE_WINDOW_S * sr)
    best = coarse
    # Refine on raw samples within +-radius of the coarse lag, using up to 20 s of overlap.
    seg = int(min(20 * sr, n * hop))
    o0 = max(0, -coarse) + radius
    if seg > 2 * radius and o0 + seg <= other.size:
        o_seg = other[o0:o0 + seg]
        r_start = o0 + coarse - radius
        r_end = r_start + seg + 2 * radius
        if r_start >= 0 and r_end <= ref.size:
            cc = correlate(ref[r_start:r_end], o_seg, mode="valid", method="fft")
            best = r_start + int(np.argmax(cc)) - o0
    return SyncResult(int(best), round(peak_z, 2), round(pearson, 3), round(overlap_s, 2))
