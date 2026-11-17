"""Audio: stems built in numpy at 48 kHz stereo, voice chain and master in FFmpeg.

Hierarchy (references/craft-audio.md): dialogue is the spine; music and SFX move around it.
Stems are normalised separately before mixing and written to render/stems/ so qc.py can
measure music-to-voice separation.
"""
from __future__ import annotations

import json
import re
from fractions import Fraction
from pathlib import Path

import numpy as np

from .common import run

SR = 48000
EDGE_FADE_S = 0.008              # raised-cosine fade at every edit point: removes clicks without audible dips
DIALOGUE_LUFS = -16.0            # STARTING DEFAULT: dialogue stem target (craft-audio.md: -16 to -18)
MUSIC_GAP_DB = -6.0              # STARTING DEFAULT: music level relative to dialogue when nobody speaks
SPEECH_PAD_S = 0.15              # duck starts this long before a word and ends this long after
ROOMTONE_WIN_S = 0.4             # room-tone loop length taken from the quietest stretch of the source
BED_LEVEL_DB = -40.0             # a steady level above this between words is a mixed bed (music/ambience), not noise
CUT_XFADE_S = 0.04               # equal-power crossfade at cuts when the source carries a bed: the bed must not jump
DIGITAL_SILENCE = 1e-5           # samples under this (-100 dBFS) are digital silence
SFX_PEAK_DEFAULT_DB = -18.0


def decode(path: Path, out: Path) -> Path:
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "2", "-ar", str(SR),
             "-c:a", "pcm_f32le", str(out)])
    return out


def load(path: Path) -> np.ndarray:
    import soundfile as sf
    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if sr != SR:
        raise ValueError(f"{path} is {sr} Hz, expected {SR}")
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2]


def save(path: Path, x: np.ndarray) -> Path:
    import soundfile as sf
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), x, SR, subtype="FLOAT")
    return path


def f2s(f: int | float, fps: Fraction) -> int:
    return int(round(Fraction(f) / fps * SR))


def _edge(n: int) -> np.ndarray:
    return (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))).astype(np.float32)[:, None]


def place(dst: np.ndarray, seg: np.ndarray, at: int, fade_in: bool = True, fade_out: bool = True,
          n_in: int | None = None, n_out: int | None = None, power: bool = False) -> None:
    """Add seg at sample `at`. Fades: raised cosine (default) or equal-power (crossfades over a bed)."""
    if at < 0:
        seg = seg[-at:]; at = 0
    seg = seg[: max(0, dst.shape[0] - at)].copy()
    shape = (lambda n: np.sqrt(_edge(n))) if power else _edge
    for flag, n, head in ((fade_in, n_in, True), (fade_out, n_out, False)):
        n = min(n or int(EDGE_FADE_S * SR), seg.shape[0] // 2)
        if flag and n > 1:
            if head:
                seg[:n] *= shape(n)
            else:
                seg[-n:] *= shape(n)[::-1]
    dst[at:at + seg.shape[0]] += seg


def lufs(x: np.ndarray) -> float:
    import pyloudnorm as pyln
    if x.shape[0] < SR // 2 or np.abs(x).max() < DIGITAL_SILENCE:
        return -70.0
    return float(pyln.Meter(SR).integrated_loudness(x))


def gain_to(x: np.ndarray, target: float) -> tuple[np.ndarray, float]:
    cur = lufs(x)
    if cur <= -70:
        return x, 0.0
    g = target - cur
    return x * np.float32(10 ** (g / 20)), g


def voice_chain(src: Path, dst: Path, noise_floor_db: float | None) -> tuple[Path, str]:
    """HPF, adaptive noise reduction, EQ, de-esser, compression, limiter. Gentle by design."""
    nf = noise_floor_db if noise_floor_db is not None else -90
    parts = ["highpass=f=80"]
    if -60 < nf <= BED_LEVEL_DB:     # steady noise worth reducing; cleaner = leave it, louder = a mixed bed
        # (None = no measurable gaps, treated as clean)
        parts.append(f"afftdn=nr={8 if nf <= -45 else 12}:nf={max(-80, min(-20, round(nf)))}")
    parts += ["equalizer=f=300:t=q:w=1.2:g=-2", "equalizer=f=4000:t=q:w=1.0:g=1.5",
              "deesser=i=0.3", "acompressor=threshold=0.1:ratio=2.5:attack=10:release=160:makeup=1.5",
              "alimiter=limit=0.95:level=disabled"]
    chain = ",".join(parts)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", chain, "-ar", str(SR), "-c:a", "pcm_f32le", str(dst)])
    return dst, chain


def roomtone(x: np.ndarray, words_src_s: list[tuple[float, float]]) -> np.ndarray | None:
    """Quietest ROOMTONE_WIN_S window that sits between words (no speech)."""
    n = int(ROOMTONE_WIN_S * SR)
    if x.shape[0] < n * 2:
        return None
    mono = np.abs(x).mean(1)
    speech = np.zeros(x.shape[0], bool)
    for s, e in words_src_s:
        speech[max(0, int(s * SR) - SR // 10):int(e * SR) + SR // 10] = True
    best, best_v = None, np.inf
    for a in range(0, x.shape[0] - n, n // 2):
        if speech[a:a + n].any():
            continue
        v = float(np.sqrt((mono[a:a + n] ** 2).mean()))
        if DIGITAL_SILENCE < v < best_v:
            best, best_v = a, v
    return None if best is None else x[best:best + n].copy()


def gap_noise_floor(x: np.ndarray, words_src_s: list[tuple[float, float]]) -> float | None:
    """Noise floor (dBFS) measured only in the gaps between words; None when there are too few gaps.
    Continuous speech has no noise to measure, and treating speech as noise over-processes the voice."""
    spans = sorted(words_src_s)
    seg = []
    for (_, e), (s2, _) in zip(spans, spans[1:]):
        if s2 - e >= 0.15:
            a, b = int((e + 0.03) * SR), int((s2 - 0.03) * SR)
            seg.append(x[a:b])
    if not seg or sum(len(g) for g in seg) < 0.3 * SR:
        return None
    g = np.concatenate(seg).mean(1)
    win = SR // 20
    rms = [np.sqrt((g[k:k + win] ** 2).mean()) for k in range(0, g.size - win, win)] or [np.sqrt((g ** 2).mean())]
    return float(20 * np.log10(np.percentile(rms, 20) + 1e-9))


def fill_silence(dia: np.ndarray, tone: np.ndarray | None) -> int:
    """Fill digital-silence runs > 20 ms in the dialogue stem with looped room tone."""
    if tone is None:
        return 0
    quiet = np.abs(dia).max(1) < DIGITAL_SILENCE
    min_run = SR // 50
    filled, k = 0, 0
    N = quiet.size
    while k < N:
        if not quiet[k]:
            k += 1; continue
        j = k
        while j < N and quiet[j]:
            j += 1
        if j - k >= min_run:
            reps = int(np.ceil((j - k) / tone.shape[0]))
            bed = np.tile(tone, (reps, 1))[: j - k].copy()
            m = min(int(0.02 * SR), bed.shape[0] // 2)
            bed[:m] *= _edge(m); bed[-m:] *= _edge(m)[::-1]
            dia[k:j] += bed
            filled += j - k
        k = j
    return filled


def duck_envelope(n: int, speech_spans_s: list[tuple[float, float]], depth_db: float, attack_ms: float,
                  release_ms: float) -> np.ndarray:
    """Gain curve (linear) with exact attack/release: depth_db during speech, 0 dB elsewhere."""
    hop = SR // 200       # 5 ms control rate
    m = n // hop + 2
    tgt = np.zeros(m, np.float32)
    for s, e in speech_spans_s:
        a = max(0, int((s - SPEECH_PAD_S) * 200)); b = min(m, int((e + SPEECH_PAD_S) * 200) + 1)
        tgt[a:b] = depth_db
    env = np.zeros(m, np.float32)
    att = 1 - np.exp(-5.0 / attack_ms) if attack_ms > 0 else 1.0
    rel = 1 - np.exp(-5.0 / release_ms) if release_ms > 0 else 1.0
    cur = 0.0
    for i in range(m):
        k = att if tgt[i] < cur else rel
        cur += (tgt[i] - cur) * k
        env[i] = cur
    g = 10 ** (env / 20)
    return np.interp(np.arange(n), np.arange(m) * hop, g).astype(np.float32)[:, None]


def music_bed(x: np.ndarray, beats_s: list[float], downbeats_s: list[float], total: int, start_off: int,
              end_mode: str) -> np.ndarray:
    """Fit a music track to `total` samples. Prefer the real ending; else loop/cut on bar lines."""
    out = np.zeros((total, 2), np.float32)
    if end_mode == "natural" and x.shape[0] >= total:
        seg = x[x.shape[0] - total:]
        out[:] = seg
        return out
    bars = [int(t * SR) for t in downbeats_s] or [0]
    src = x[start_off:]
    if src.shape[0] >= total:
        out[:] = src[:total]
    else:
        # loop: repeat from the first bar line after the start, crossfading 30 ms at the join
        pos, k = 0, start_off
        loop_from = next((b for b in bars if b > start_off), start_off)
        while pos < total:
            seg = x[k:]
            take = min(seg.shape[0], total - pos)
            place(out, seg[:take], pos, fade_in=pos > 0, fade_out=False)
            pos += take; k = loop_from
            if take <= 0:
                break
    if end_mode in ("bar", "hit"):
        # end on the last bar line inside the timeline, with a short release
        cand = [b - start_off for b in bars if 0 < b - start_off <= total]
        if cand and total - cand[-1] < SR * 4:
            cut = cand[-1]
            fl = int(0.15 * SR) if end_mode == "bar" else int(0.03 * SR)
            out[cut:cut + fl] *= _edge(min(fl, out.shape[0] - cut))[::-1][: out[cut:cut + fl].shape[0]]
            out[cut + fl:] = 0
    elif end_mode == "fade":
        fl = min(int(1.5 * SR), total // 3)
        out[-fl:] *= _edge(fl)[::-1]
    return out


def loudnorm_master(src: Path, dst: Path, target: float, tp: float) -> dict:
    """Two-pass EBU R128 normalisation (linear mode) to the delivery target."""
    p1 = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af",
              f"loudnorm=I={target}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"])
    txt = p1.stderr.decode("utf-8", "replace")
    m = json.loads(re.findall(r"\{[^{}]*\}", txt)[-1])
    af = (f"loudnorm=I={target}:TP={tp}:LRA=11:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", af, "-ar", str(SR), "-c:a", "pcm_f32le", str(dst)])
    # loudnorm cannot hold TP when the gain it needs pushes short transients (SFX hits) over it, so a
    # look-ahead limiter on a 4x oversampled copy catches what is left (true peak, not sample peak).
    out_tp = true_peak(dst)
    limited = False
    if out_tp > tp:
        out_tp, limited = limit(dst, tp - 0.3), True
    return {"input_i": float(m["input_i"]), "input_tp": float(m["input_tp"]), "output_tp": out_tp, "limited": limited}


def limit(path: Path, ceiling_db: float) -> float:
    """Look-ahead limiter on a 4x oversampled copy (true peak, not sample peak); rewrites `path` in
    place and returns its new true peak in dBTP."""
    tmp = path.with_name(path.stem + "_pre_limit.wav")
    path.replace(tmp)
    lim = 10 ** (ceiling_db / 20)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af",
         f"aresample={SR * 4},alimiter=limit={lim:.5f}:attack=1:release=60:level=false,aresample={SR}",
         "-c:a", "pcm_f32le", str(path)])
    tmp.unlink()
    return true_peak(path)


def true_peak(path: Path) -> float:
    """True peak in dBTP (ebur128, 4x oversampled)."""
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    txt = p.stderr.decode("utf-8", "replace")
    m = re.findall(r"True peak:\s*Peak:\s*(-?[\d.]+|-inf)", txt)
    return float(m[-1]) if m and m[-1] != "-inf" else -120.0
