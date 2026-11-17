"""Speaker diarization: who speaks when.

Methods, best first:
  pyannote     pyannote.audio pipeline (needs torch and a Hugging Face token in HF_TOKEN)
  loudest_mic  synced multicam / multi-lav recordings: the speaker is the mic that is
               loudest relative to its own baseline. Reliable for podcasts.
  mfcc_cluster single mic, no pyannote: MFCC statistics per segment, agglomerative
               clustering. Confidence is reported LOW; check before relying on it.
Each turn: {"speaker": "S1", "s_f": int, "e_f": int}.
"""
from __future__ import annotations

import os
from fractions import Fraction

import numpy as np

WINDOW_S = Fraction(3, 2)        # clustering window; long enough for a stable voice estimate
MAX_SPEAKERS = 6
SILHOUETTE_MIN = 0.25            # STARTING DEFAULT: below this, >1 cluster is not supported by the data
MIN_WINDOWS_PER_SPEAKER = 4      # a speaker needs >= 6 s of speech (4 x 1.5 s windows) to be counted
MIN_SPEAKER_SHARE = 0.08         # and at least 8 % of the speech windows
K_GAIN_MIN = 0.03                # a larger k must beat the smaller one's silhouette by this much


def diarize_pyannote(wav_path: str, fps: Fraction, n_speakers: int | None) -> list[dict] | None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        return None
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        return None
    pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
    ann = pipe(wav_path, num_speakers=n_speakers) if n_speakers else pipe(wav_path)
    labels: dict = {}
    turns = []
    for seg, _, spk in ann.itertracks(yield_label=True):
        labels.setdefault(spk, f"S{len(labels) + 1}")
        turns.append({"speaker": labels[spk], "s_f": round(Fraction(seg.start) * fps),
                      "e_f": round(Fraction(seg.end) * fps)})
    return turns


def _silhouette(X: np.ndarray, lab: np.ndarray) -> float:
    ks = np.unique(lab)
    if ks.size < 2:
        return -1.0
    from scipy.spatial.distance import cdist
    D = cdist(X, X)  # n x n only; an hour of speech is ~2400 windows, 46 MB
    s = []
    for i in range(len(X)):
        same = lab == lab[i]
        a = D[i, same].sum() / max(1, same.sum() - 1)
        b = min(D[i, lab == k].mean() for k in ks if k != lab[i])
        s.append((b - a) / max(a, b, 1e-9))
    return float(np.mean(s))


def diarize_mfcc(x: np.ndarray, sr: int, speech_spans: list[tuple[int, int]], fps: Fraction,
                 n_speakers: int | None) -> tuple[list[dict], dict]:
    import librosa
    from scipy.cluster.hierarchy import fcluster, linkage

    win_f = int(WINDOW_S * fps)
    windows = []
    for a, b in speech_spans:
        f = a
        while f < b:
            e = min(b, f + win_f)
            if e - f >= win_f // 2:
                windows.append((f, e))
            f = e
    if len(windows) < 4:
        return [{"speaker": "S1", "s_f": a, "e_f": b} for a, b in speech_spans], \
               {"method": "mfcc_cluster", "speakers": 1, "confidence": "low", "note": "too little speech to cluster"}
    feats, kept = [], []
    min_len = int(WINDOW_S * sr) // 2
    for a, b in windows:
        seg = x[int(Fraction(a) / fps * sr):int(Fraction(b) / fps * sr)]
        if seg.size < min_len:
            continue  # span runs past the audio (offset or rounding); no voice to measure
        m = librosa.feature.mfcc(y=seg, sr=sr, n_mfcc=20)[1:]  # drop c0 (loudness)
        feats.append(np.concatenate([m.mean(1), m.std(1)]))
        kept.append((a, b))
    windows = kept
    if len(windows) < 4:
        return [{"speaker": "S1", "s_f": a, "e_f": b} for a, b in speech_spans],                {"method": "mfcc_cluster", "speakers": 1, "confidence": "low", "note": "too little speech to cluster"}
    X = np.array(feats)
    X = (X - X.mean(0)) / (X.std(0) + 1e-6)
    Z = linkage(X, method="ward")
    if n_speakers:
        lab, k_best, sil = fcluster(Z, n_speakers, "maxclust"), n_speakers, None
    else:
        # Conservative: one speaker unless the data clearly says otherwise. Over-splitting one
        # voice into several "speakers" (music beds and mic moves do this) is worse for editing
        # than missing a speaker, because it creates false speaker switches.
        best = (SILHOUETTE_MIN, 1, np.ones(len(X), dtype=int))
        k_cap = min(MAX_SPEAKERS, len(X) // MIN_WINDOWS_PER_SPEAKER)
        for k in range(2, k_cap + 1):
            lab_k = fcluster(Z, k, "maxclust")
            sizes = np.bincount(lab_k)[1:]
            if sizes.min() < max(MIN_WINDOWS_PER_SPEAKER, MIN_SPEAKER_SHARE * len(X)):
                continue  # a speaker with almost no talk time is a noise cluster
            s = _silhouette(X, lab_k)
            if s > best[0] + (K_GAIN_MIN if best[1] > 1 else 0):
                best = (s, k, lab_k)
        sil, k_best, lab = best
    # relabel in order of first appearance
    order: dict = {}
    for l in lab:
        order.setdefault(int(l), f"S{len(order) + 1}")
    turns = []
    for (a, b), l in zip(windows, lab):
        spk = order[int(l)]
        if turns and turns[-1]["speaker"] == spk and a - turns[-1]["e_f"] <= win_f:
            turns[-1]["e_f"] = b
        else:
            turns.append({"speaker": spk, "s_f": a, "e_f": b})
    return turns, {"method": "mfcc_cluster", "speakers": int(k_best), "confidence": "low",
                   "silhouette": None if sil is None else round(float(sil), 3)}


def diarize_loudest_mic(levels: dict[str, np.ndarray], offsets: dict[str, int], fps: Fraction,
                        speech_spans: list[tuple[int, int]]) -> tuple[list[dict], dict]:
    """levels: per-member frame dB arrays on their own clocks; offsets: member start on the anchor clock."""
    ids = list(levels)
    hop = max(1, int(fps / 4))  # decide 4 times per second
    turns = []
    norm = {m: np.median(levels[m][levels[m] > -90]) if (levels[m] > -90).any() else -60 for m in ids}
    for a, b in speech_spans:
        for f in range(a, b, hop):
            vals = []
            for m in ids:
                k = f - offsets[m]
                arr = levels[m]
                vals.append(arr[k:k + hop].mean() - norm[m] if 0 <= k < arr.size else -99)
            spk = f"S{int(np.argmax(vals)) + 1}"
            e = min(b, f + hop)
            if turns and turns[-1]["speaker"] == spk and f - turns[-1]["e_f"] <= hop:
                turns[-1]["e_f"] = e
            else:
                turns.append({"speaker": spk, "s_f": f, "e_f": e})
    mapping = {f"S{k + 1}": m for k, m in enumerate(ids)}
    return turns, {"method": "loudest_mic", "speakers": len(ids), "confidence": "medium", "speaker_mic": mapping}


def assign_words(words: list[dict], turns: list[dict]) -> None:
    """Give each word the speaker whose turn overlaps its midpoint (nearest turn otherwise)."""
    if not turns:
        for w in words:
            w["speaker"] = "S1"
        return
    for w in words:
        mid = (w["s_f"] + w["e_f"]) // 2
        best, dist = turns[0]["speaker"], 10**12
        for t in turns:
            if t["s_f"] <= mid <= t["e_f"]:
                best, dist = t["speaker"], 0
                break
            d = min(abs(mid - t["s_f"]), abs(mid - t["e_f"]))
            if d < dist:
                best, dist = t["speaker"], d
        w["speaker"] = best
