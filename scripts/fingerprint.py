#!/usr/bin/env python3
"""Measure the editing style of finished, pro-edited videos, and aggregate many into a rulebook.

Usage:
  python scripts/fingerprint.py measure VIDEO [--audio AUDIO] --out FP.json [--frames-dir DIR]
  python scripts/fingerprint.py batch REF_FOLDER --out-dir DIR      (one fingerprint per video)
  python scripts/fingerprint.py aggregate FP.json ... --type short_form --name NAME --out STYLE.json

measure: every frame is measured in code at the source frame rate (cuts, transitions,
punch-ins, zooms, speed-ramp candidates, colour per shot, B-roll ratio). On-screen text is
read with OCR at OCR_FPS. Audio: speech (Whisper), music presence, ducking depth, SFX onsets
and their alignment to cuts/text, loudness, beats. Structure: hook length, re-hook spacing,
ending type, loop similarity. A few frames per shot are saved for Claude's qualitative pass;
fields only a viewer can judge are left in `qualitative` for Claude to fill.

batch: pairs Pinterest/yt-dlp style downloads (`x.mp4` + `x-audio.mp4` + `x.info.json`) and
reads performance numbers (view_count, repost_count, like_count) from info.json when present.

aggregate: median, low (10th pct) and high (90th pct) per numeric field. When performance
numbers exist, the top half is compared with the bottom half and the most different fields
are written as `hypotheses` (not rules) until evals support them.

Reference videos are only measured. Nothing from them is copied into any output.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from lib.common import ToolError, fail, ffprobe_json, file_hash, log, read_json, run, write_json  # noqa: E402
from lib.timebase import parse_rate  # noqa: E402

FP_VERSION = 1
SMALL_W = 160                 # per-frame analysis width: enough for global motion and colour
OCR_FPS = 2                   # text cards last >= 0.5 s in every reference measured; 2 fps catches them
OCR_MIN_SCORE = 0.6
ANIM_PROBE_FRAMES = (2,)      # frames before a sampled card onset re-read to classify its entrance
SAME_FRAME_DIFF = 1.5         # mean abs pixel difference under which a frame is treated as unchanged
OCR_W = 480                   # OCR input width: caption text stays >= 12 px tall on 9:16 video
BEAT_TOL_F = 2                # a cut within 2 frames of a beat counts as on the beat
PUNCH_MIN_SCALE = 1.05        # scale jump across a cut that counts as a punch-in
ZOOM_EVENT_SCALE = 1.06       # cumulative in-shot zoom within ZOOM_EVENT_WINDOW frames
ZOOM_EVENT_WINDOW = 15
ZOOM_CONSISTENCY = 0.8        # 80 % of frame steps must scale the same way (noise flips sign)
WHIP_BLUR = 0.35              # sharpness next to the cut under 35 % of its neighbourhood = motion blur
RAMP_RATIO = 3.0              # in-shot motion speed changing >= 3x = speed-ramp candidate
WHIP_SHIFT_PCT = 6.0          # global shift > 6 % of width per frame next to a cut = whip
FADE_LUMA = 16                # mean luma under this at a cut = fade through black
SFX_ONSET_Z = 3.0             # percussive onsets this far above the median = SFX candidate
SFX_ALIGN_F = 2
LOOP_SIM_LOOP = 0.75          # last-vs-first frame similarity above this = loop ending
QUAL_FRAMES_MAX = 24
HOOK_MAX_S = 10               # a "first sentence" longer than this is a punctuation failure, not a hook
HOOK_PAUSE_S = 0.3


# ----------------------------------------------------------------------------- frames
def iter_small_frames(path: Path, w: int = SMALL_W):
    """Yield RGB frames at the source rate, scaled to width w."""
    import subprocess
    pr = ffprobe_json(path)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    W, H = int(v["width"]), int(v["height"])
    h = int(round(H * w / W / 2)) * 2
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h}:flags=area",
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


def per_frame_stats(path: Path) -> dict:
    import cv2
    luma, diff, shx, shy, resp, scale, sat, sharp = [], [], [], [], [], [], [], []
    prev = None
    hann = None
    for fr in iter_small_frames(path):
        g = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY)
        gf = g.astype(np.float32)
        luma.append(float(g.mean()))
        sat.append(float(cv2.cvtColor(fr, cv2.COLOR_RGB2HSV)[..., 1].mean()))
        sharp.append(float(cv2.Laplacian(g, cv2.CV_32F).var()))
        if prev is None:
            diff.append(0.0); shx.append(0.0); shy.append(0.0); resp.append(1.0); scale.append(1.0)
        else:
            diff.append(float(np.abs(gf - prev).mean()))
            if hann is None:
                hann = cv2.createHanningWindow(g.shape[::-1], cv2.CV_32F)
            (dx, dy), r = cv2.phaseCorrelate(prev, gf, hann)
            shx.append(dx / g.shape[1] * 100); shy.append(dy / g.shape[1] * 100); resp.append(float(r))
            scale.append(_scale_between(prev.astype(np.uint8), g))
        prev = gf
    return {k: np.array(v) for k, v in dict(luma=luma, diff=diff, shx=shx, shy=shy, resp=resp,
                                              scale=scale, sat=sat, sharp=sharp).items()}


def _scale_between(a: np.ndarray, b: np.ndarray) -> float:
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


def scale_across_cut(reader, f: int) -> float | None:
    """Scale between the last frame before a cut and the first after (ORB match). None = different shot."""
    import cv2
    a, b = reader.read(f - 1), reader.read(f)
    if a is None or b is None:
        return None
    orb = cv2.ORB_create(600)
    ga, gb = (cv2.cvtColor(cv2.resize(x, (360, int(360 * x.shape[0] / x.shape[1]))), cv2.COLOR_BGR2GRAY) for x in (a, b))
    ka, da = orb.detectAndCompute(ga, None)
    kb, db = orb.detectAndCompute(gb, None)
    if da is None or db is None or len(ka) < 20 or len(kb) < 20:
        return None
    m = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
    if len(m) < 20:
        return None
    pa = np.float32([ka[x.queryIdx].pt for x in m]); pb = np.float32([kb[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(pa, pb, ransacReprojThreshold=4)
    if M is None or inl is None or inl.sum() < 25 or inl.mean() < 0.35:
        return None
    return float(np.hypot(M[0, 0], M[1, 0]))


# ----------------------------------------------------------------------------- OCR
_ocr = None


def ocr(frame) -> list[dict]:
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    import cv2
    h, w = frame.shape[:2]
    if w > OCR_W:
        frame = cv2.resize(frame, (OCR_W, int(h * OCR_W / w)), interpolation=cv2.INTER_AREA)
        h, w = frame.shape[:2]
    res, _ = _ocr(frame, use_cls=False)
    out = []
    for box, text, score in res or []:
        if float(score) < OCR_MIN_SCORE or not re.search(r"\w", text):
            continue
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        out.append({"text": text.strip(), "x": (min(xs) + max(xs)) / 2 / w, "y": (min(ys) + max(ys)) / 2 / h,
                    "h": (max(ys) - min(ys)) / h, "w": (max(xs) - min(xs)) / w})
    return out


def _norm_text(lines: list[dict]) -> str:
    return " ".join(re.sub(r"[^\w]+", "", l["text"].lower()) for l in sorted(lines, key=lambda l: (l["y"], l["x"])))


def text_cards(video: Path, total_f: int, fps: Fraction) -> list[dict]:
    """OCR every step-th frame while decoding sequentially (seeking is the slow part)."""
    from collections import deque
    step = max(1, round(fps / OCR_FPS))
    recent = deque(maxlen=max(ANIM_PROBE_FRAMES) + 1)
    cards, cur, last_img, last_lines = [], None, None, []
    for f, rgb in enumerate(iter_small_frames(video, OCR_W)):
        img = rgb[..., ::-1]
        recent.append(img)
        if f % step:
            continue
        if last_img is not None and np.abs(img.astype(np.int16) - last_img).mean() < SAME_FRAME_DIFF:
            lines = last_lines               # picture unchanged: reuse the last read
        else:
            lines = ocr(img)
            last_img, last_lines = img.astype(np.int16), lines
        key = _norm_text(lines)
        if cur and key and _similar(key, cur["key"]):
            cur["e_f"] = f + step
            cur["samples"].append(lines)
            continue
        if cur:
            cards.append(cur)
        cur = None
        if key:
            probes = [ocr(recent[-1 - d]) for d in ANIM_PROBE_FRAMES if f > 0 and d < len(recent)]
            cur = {"s_f": f, "e_f": f + step, "key": key, "samples": [lines], "probes": probes}
    if cur:
        cards.append(cur)
    out = []
    for c in cards:
        lines = max(c["samples"], key=len)
        words = sum(len(l["text"].split()) for l in lines)
        y = float(np.median([l["y"] for l in lines])); hgt = float(np.median([l["h"] for l in lines]))
        out.append({"s_f": c["s_f"], "e_f": min(total_f, c["e_f"]), "text": " / ".join(l["text"] for l in lines),
                    "words": words, "lines": len(lines), "y": round(y, 3), "height": round(hgt, 4),
                    "region": _region(y), "animation": _entrance(c, lines)})
    return out


def is_caption(card: dict, words: list[dict]) -> bool:
    """A card is a caption when most of its words are being spoken around that time."""
    toks = [t for t in re.findall(r"\w+", card["text"].lower()) if len(t) > 1]
    if not toks or not words:
        return False
    near = {re.sub(r"\W", "", w["w"].lower()) for w in words
            if card["s_f"] - 45 <= w["s_f"] <= card["e_f"] + 45}
    return sum(t in near for t in toks) / len(toks) >= 0.5


def _similar(a: str, b: str) -> bool:
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def _region(y: float) -> str:
    return "top" if y < 0.25 else "center" if y < 0.6 else "center_low" if y < 0.8 else "bottom"


def _entrance(card, lines) -> str:
    """Compare the card with the frames just before its first sighting."""
    if card["s_f"] == 0:
        return "on_at_start"
    ref_h = float(np.median([l["h"] for l in lines])); ref_y = float(np.median([l["y"] for l in lines]))
    seen = [p for p in card.get("probes", []) if p]
    if not seen:
        return "cut_on"
    h0 = float(np.median([l["h"] for l in seen[0]])); y0 = float(np.median([l["y"] for l in seen[0]]))
    if h0 < 0.85 * ref_h or h0 > 1.15 * ref_h:
        return "pop"
    if abs(y0 - ref_y) > 0.03:
        return "slide"
    return "fade_or_type" if _norm_text(seen[0]) != _norm_text(lines) else "on_before_sample"


# ----------------------------------------------------------------------------- audio
def load_audio(path: Path, sr: int = 16000) -> np.ndarray:
    import soundfile as sf
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), str(wav)])
        x, _ = sf.read(str(wav), dtype="float32")
    return x


def audio_measures(x: np.ndarray, sr: int, fps: Fraction, words: list[dict], cuts_f: list[int],
                   text_on_f: list[int]) -> dict:
    import librosa
    from lib.music import analyze_music
    dur_f = int(len(x) / sr * fps)
    hop = int(sr / fps)
    speech = np.zeros(dur_f + 1, bool)
    for w in words:
        speech[max(0, w["s_f"]):min(dur_f, w["e_f"] + 1)] = True
    H, P = librosa.decompose.hpss(librosa.stft(x, n_fft=1024, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    n = min(H.shape[1], dur_f)
    harm_db = librosa.amplitude_to_db(np.sqrt((np.abs(H) ** 2).mean(0)) + 1e-9)[:n]
    # Music under speech: harmonic energy outside the voice formant band (below 120 Hz and above
    # 5 kHz) is mostly music. A band proxy, not source separation; marked as such.
    band = (freqs < 120) | (freqs > 5000)
    bg_db = librosa.amplitude_to_db(np.sqrt((np.abs(H[band]) ** 2).mean(0)) + 1e-9)[:n]
    sp = speech[:n]
    music_gap = float(np.median(harm_db[~sp])) if (~sp).sum() > fps else None
    music_present = bool(music_gap is not None and music_gap > -45) or (
        sp.mean() > 0.9 and float(np.median(bg_db[sp])) > -55)
    duck = None
    if (~sp).sum() > fps and sp.sum() > fps:
        duck = round(float(np.median(bg_db[sp]) - np.median(bg_db[~sp])), 1)
    # SFX candidates: strong percussive onsets
    pon = librosa.onset.onset_strength(S=np.abs(P), sr=sr)
    med = np.median(pon) + 1e-9
    mad = np.median(np.abs(pon - med)) + 1e-9
    peaks = librosa.util.peak_pick(pon, pre_max=3, post_max=3, pre_avg=5, post_avg=5, delta=0, wait=int(fps / 5))
    onsets = [int(p) for p in peaks if (pon[p] - med) / mad > SFX_ONSET_Z * 1.4826]
    events = np.array(sorted(cuts_f + text_on_f)) if (cuts_f or text_on_f) else np.array([-10**6])
    # Editors place SFX on cuts and text entrances; onsets elsewhere are mostly music hits.
    sfx = [o for o in onsets if np.abs(events - o).min() <= SFX_ALIGN_F]
    minutes = len(x) / sr / 60
    def aligned(evs, refs):
        if not evs or not refs:
            return None
        r = np.array(refs)
        return round(100 * float(np.mean([np.abs(r - e).min() <= SFX_ALIGN_F for e in evs])), 1)
    mus = analyze_music(x, sr, fps)
    beats = np.array(mus["beats_f"])
    on_beat = None
    if beats.size >= 4 and cuts_f:
        on_beat = round(100 * float(np.mean([np.abs(beats - c).min() <= BEAT_TOL_F for c in cuts_f])), 1)
    chance = None
    if beats.size >= 4:
        chance = round(100 * min(1.0, (2 * BEAT_TOL_F + 1) * beats.size / max(1, dur_f)), 1)
    lv = librosa.amplitude_to_db(librosa.feature.rms(y=x, hop_length=hop)[0] + 1e-9)
    silence_pct = round(100 * float((lv < -50).mean()), 1)
    return {"music_present": music_present, "music_level_gap_db": None if music_gap is None else round(music_gap, 1),
            "ducking_db": duck, "ducking_method": "harmonic energy outside 120 Hz-5 kHz, speech vs gaps",
            "sfx_per_min": round(len(sfx) / minutes, 1) if minutes else None,
            "onsets_per_min": round(len(onsets) / minutes, 1) if minutes else None,
            "cuts_with_sfx_pct": aligned(cuts_f, sfx), "titles_with_sfx_pct": aligned(text_on_f, sfx),
            "sfx_method": "strong percussive onsets within 2 frames of a cut or title entrance (music hits that "
                          "coincide are counted too: an upper bound)",
            "bpm": mus["bpm"], "cuts_on_beat_pct": on_beat, "cuts_on_beat_chance_pct": chance,
            "silence_pct": silence_pct}


# ----------------------------------------------------------------------------- measure
def measure(video: Path, audio: Path | None, frames_dir: Path | None, model: str = "base",
            cache_dir: Path | None = None) -> dict:
    import cv2
    from lib.shots import FaceDetector, FrameReader, detect_shots
    pr = ffprobe_json(video)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    fps = parse_rate(v.get("avg_frame_rate")) or parse_rate(v.get("r_frame_rate"))
    from lib.timebase import nearest_standard
    fps = nearest_standard(fps)
    W, H = int(v["width"]), int(v["height"])
    from lib.common import Cache
    cache = Cache(cache_dir or Path(tempfile.gettempdir()) / "pve_fp_cache")
    digest = file_hash(video)
    log(f"measure {video.name}: per-frame stats")
    raw = cache.get(digest, "fp_frames", {"v": 1, "w": SMALL_W})
    if raw is None:
        st = per_frame_stats(video)
        shots, _ = detect_shots(video, st["luma"].size)
        raw = cache.put(digest, "fp_frames", {"v": 1, "w": SMALL_W},
                        {"st": {k: v.round(4).tolist() for k, v in st.items()}, "shots": shots})
    st = {k: np.array(v) for k, v in raw["st"].items()}
    shots = raw["shots"]
    total_f = st["luma"].size
    dur_s = float(total_f / fps)
    cuts = [s["s_f"] for s in shots[1:]]
    reader = FrameReader(video)

    # transitions
    trans = {"cut": 0, "dissolve": 0, "fade": 0, "whip": 0, "zoom": 0}
    punch = []
    for c in cuts:
        # Frame pairs inside each shot next to the cut; the pair across the cut itself is excluded
        # (two unrelated pictures always look like a huge "shift" to phase correlation).
        side = [i for i in (c - 2, c - 1, c + 1, c + 2) if 1 <= i < total_f]
        shift = np.hypot(st["shx"][side], st["shy"][side])
        sh_med = np.median(st["sharp"][max(0, c - 15):min(total_f, c + 15)]) + 1e-9
        blur = st["sharp"][[i for i in (c - 1, c, c + 1) if 0 <= i < total_f]].min() / sh_med
        d = st["diff"][max(1, c - 8):c + 8]
        if st["luma"][max(0, c - 2):c + 2].min() < FADE_LUMA and st["luma"][max(0, c - 10)] > FADE_LUMA * 2:
            kind = "fade"
        elif shift.mean() > WHIP_SHIFT_PCT / 2 and blur < WHIP_BLUR:
            kind = "whip"
        elif np.abs(np.log(np.clip(st["scale"][side], 0.5, 2))).mean() > np.log(1.03) and blur < WHIP_BLUR * 1.5:
            kind = "zoom"
        elif d.size >= 8 and (d > 2 * np.median(st["diff"][1:]) + 1).sum() >= 5 and d.max() < 3 * np.sort(d)[-2]:
            kind = "dissolve"
        else:
            kind = "cut"
        trans[kind] += 1
        s = scale_across_cut(reader, c)
        if s is not None and (s >= PUNCH_MIN_SCALE or s <= 1 / PUNCH_MIN_SCALE):
            punch.append({"at_f": c, "scale": round(s, 3), "kind": "punch_in" if s > 1 else "punch_out"})

    # in-shot zooms and speed-ramp candidates
    zooms, ramps = [], []
    for sh in shots:
        a, b = sh["s_f"] + 1, sh["e_f"]
        sc = np.log(np.clip(st["scale"][a:b], 0.8, 1.25))
        k = 0
        while k + 2 < sc.size:
            win = sc[k:k + ZOOM_EVENT_WINDOW]
            cum = np.cumsum(win)
            j = int(np.argmax(np.abs(cum)))
            same_dir = np.mean(np.sign(win[:j + 1]) == np.sign(cum[j])) if j >= 3 else 0
            if abs(cum[j]) >= np.log(ZOOM_EVENT_SCALE) and same_dir >= ZOOM_CONSISTENCY:
                zooms.append({"at_f": a + k, "dur_f": j + 1, "scale": round(float(np.exp(cum[j])), 3)})
                k += j + 1
            else:
                k += ZOOM_EVENT_WINDOW // 2
        mv = np.hypot(st["shx"][a:b], st["shy"][a:b])
        if mv.size >= 20:
            sm = np.convolve(mv, np.ones(5) / 5, "valid")
            hi_, lo_ = sm.max(), max(np.percentile(sm, 10), 0.05)
            if hi_ > 1.0 and hi_ / lo_ >= RAMP_RATIO:
                ramps.append({"at_f": a + int(np.argmax(sm)), "ratio": round(float(hi_ / lo_), 1)})

    # colour per shot, faces (B-roll)
    faces = FaceDetector(Path(__file__).resolve().parent.parent / "assets" / "cache" / "models")
    shot_rows, qual = [], []
    for sh in shots:
        mid = (sh["s_f"] + sh["e_f"]) // 2
        fr = reader.read(mid)
        if fr is None:
            continue
        hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(fr, cv2.COLOR_BGR2LAB).astype(np.float32)
        fc = faces.faces(fr)
        shot_rows.append({"s_f": sh["s_f"], "e_f": sh["e_f"], "luma": round(float(lab[..., 0].mean() / 2.55), 1),
                          "contrast": round(float(lab[..., 0].std() / 2.55), 1),
                          "saturation": round(float(hsv[..., 1].mean() / 2.55), 1),
                          "warmth": round(float(lab[..., 2].mean() - 128), 2),
                          "tint": round(float(lab[..., 1].mean() - 128), 2),
                          "faces": len(fc), "face_size": fc[0]["size"] if fc else 0})
        if frames_dir is not None and len(qual) < QUAL_FRAMES_MAX:
            frames_dir.mkdir(parents=True, exist_ok=True)
            p = frames_dir / f"{video.stem[:40]}_shot{sh['n']:03d}.jpg"
            cv2.imwrite(str(p), cv2.resize(fr, (270, int(270 * fr.shape[0] / fr.shape[1]))))
            qual.append(p.as_posix())

    log("  on-screen text (OCR)")
    cards = cache.get(digest, "fp_ocr", {"v": 2, "fps": OCR_FPS})
    if cards is None:
        cards = cache.put(digest, "fp_ocr", {"v": 2, "fps": OCR_FPS}, text_cards(video, total_f, fps))
    # loop similarity: first vs last frame (downscaled, grey, correlation)
    first, last = reader.read(0), reader.read(total_f - 1)
    loop = None
    if first is not None and last is not None:
        a = cv2.resize(cv2.cvtColor(first, cv2.COLOR_BGR2GRAY), (36, 64)).astype(float).ravel()
        b = cv2.resize(cv2.cvtColor(last, cv2.COLOR_BGR2GRAY), (36, 64)).astype(float).ravel()
        loop = round(float(np.corrcoef(a, b)[0, 1]) if a.std() and b.std() else 0.0, 3)
    reader.close()

    # audio
    words, aud = [], {}
    src_audio = audio or (video if any(s["codec_type"] == "audio" for s in pr["streams"]) else None)
    if src_audio:
        log("  audio: transcript, music, SFX")
        x = load_audio(src_audio)
        adig = file_hash(src_audio)
        tr = cache.get(adig, "fp_transcript", {"v": 1, "model": model})
        if tr is None:
            try:
                from lib.transcribe import load_transcriber
                with tempfile.TemporaryDirectory() as td:
                    import soundfile as sf
                    wp = Path(td) / "a.wav"; sf.write(str(wp), x, 16000)
                    tr = cache.put(adig, "fp_transcript", {"v": 1, "model": model},
                                   load_transcriber("faster-whisper", model).transcribe(wp))
            except Exception as e:
                log(f"  transcript skipped: {e}")
        if tr:
            from analyze import words_to_frames
            words, _ = words_to_frames(tr, fps)
    for c in cards:
        c["caption"] = is_caption(c, words)
    if src_audio:
        aud = audio_measures(x, 16000, fps, words, cuts, [c["s_f"] for c in cards if not c.get("caption")])
        from lib.music import loudness_r128
        lo = loudness_r128(src_audio, fps)
        aud["lufs"] = lo.get("integrated_lufs"); aud["true_peak_db"] = lo.get("true_peak_dbtp")

    lens = np.array([s["dur_f"] for s in shots], float) / float(fps)
    mask = np.zeros(total_f + 1, bool)
    for w in words:
        mask[max(0, w["s_f"]):min(total_f, w["e_f"])] = True
    speech_f = int(mask.sum())
    cap_cards = [c for c in cards if c.get("caption")]
    covered = 0
    for w in words:
        mid = (w["s_f"] + w["e_f"]) // 2
        covered += any(c["s_f"] <= mid < c["e_f"] for c in cap_cards)
    face_shots = [r for r in shot_rows if r["faces"]]
    broll = None
    if words and face_shots:
        nf = sum(r["e_f"] - r["s_f"] for r in shot_rows if not r["faces"])
        broll = round(nf / total_f, 3)
    # structure
    hook_f = None
    if words:
        from lib.speech import sentences
        sents = sentences(words)
        hook_f = sents[0]["e_f"] if sents else None
        if hook_f is None or hook_f > HOOK_MAX_S * fps:
            # no sentence punctuation (some languages, run-on speech): the first real pause ends the hook
            hook_f = next((a["e_f"] for k, (a, b) in enumerate(zip(words, words[1:]))
                           if k >= 2 and b["s_f"] - a["e_f"] >= HOOK_PAUSE_S * fps), hook_f)
    if hook_f is None:
        hook_f = cuts[0] if cuts else total_f
    # Re-hooks: visible changes other than captions turning over (cuts, punch-ins, zooms, titles/graphics).
    titles = [c for c in cards if not c.get("caption")]
    # Title cards are reported separately (titles_per_min): OCR misreads make their onsets too noisy to count here.
    interrupts = sorted(set(cuts + [z["at_f"] for z in zooms] + [p["at_f"] for p in punch]))
    gaps = np.diff([0] + interrupts + [total_f]) / float(fps)
    end_luma = st["luma"][-max(1, int(fps / 2)):]
    if end_luma.min() < FADE_LUMA and st["luma"][max(0, total_f - int(fps * 2))] > FADE_LUMA * 2:
        ending = "fade_out"
    elif loop is not None and loop >= LOOP_SIM_LOOP:
        ending = "loop"
    elif cards and cards[-1]["e_f"] >= total_f - 2:
        ending = "text_card"
    else:
        ending = "hard_out"
    return {
        "version": FP_VERSION, "file": video.name, "hash": file_hash(video), "measured_on": str(_dt.date.today()),
        "fps": str(fps), "width": W, "height": H, "aspect": "9:16" if H > W * 1.5 else "16:9" if W > H * 1.5 else "other",
        "duration_s": round(dur_s, 2),
        "cuts": len(cuts), "cuts_per_min": round(len(cuts) / (dur_s / 60), 1),
        "shot_len_s": _stats(lens), "shot_len_cv": round(float(lens.std() / lens.mean()), 2) if lens.size else None,
        "transition_mix": {k: round(v / max(1, len(cuts)), 3) for k, v in trans.items()},
        "punch_ins": punch, "punch_in_every_s": round(dur_s / len(punch), 2) if punch else None,
        "punch_in_scale": round(float(np.median([p["scale"] for p in punch if p["scale"] > 1])), 3)
        if any(p["scale"] > 1 for p in punch) else None,
        "zoom_events": zooms, "zooms_per_min": round(len(zooms) / (dur_s / 60), 1),
        "speed_ramp_candidates": ramps,
        "text": {"cards": cards, "cards_per_min": round(len(cards) / (dur_s / 60), 1),
                 "caption_cards_per_min": round(len(cap_cards) / (dur_s / 60), 1),
                 "words_per_card": _stats([c["words"] for c in cap_cards]),
                 "position": _mode([c["region"] for c in cap_cards]),
                 "animation": _mode([c["animation"] for c in cap_cards]),
                 "titles_per_min": round(len(titles) / (dur_s / 60), 1),
                 "title_position": _mode([c["region"] for c in titles]),
                 "text_screen_pct": round(100 * sum(c["e_f"] - c["s_f"] for c in cards) / total_f, 1),
                 "caption_coverage_pct": round(100 * covered / len(words), 1) if words else None},
        "color": {"shots": shot_rows, "luma": _stats([r["luma"] for r in shot_rows]),
                  "contrast": _stats([r["contrast"] for r in shot_rows]),
                  "saturation": _stats([r["saturation"] for r in shot_rows]),
                  "warmth": _stats([r["warmth"] for r in shot_rows])},
        "broll_ratio": broll, "face_time_pct": round(100 * sum(r["e_f"] - r["s_f"] for r in face_shots) / total_f, 1),
        "speech_pct": round(100 * speech_f / total_f, 1) if words else 0.0,
        "words_per_min": round(len(words) / (dur_s / 60), 1) if words else 0.0,
        "audio": aud,
        "structure": {"hook_len_s": round(hook_f / float(fps), 2), "first_payoff_s": None,
                      "rehook_every_s": round(float(np.median(gaps)), 2) if gaps.size else None,
                      "max_no_change_s": round(float(gaps.max()), 2) if gaps.size else None,
                      "ending": ending, "loop_similarity": loop},
        "qualitative": {"frames": qual, "notes": [],
                        "todo": "Claude: view frames, fill framing, broll_subject, mood, why_cuts, first_payoff_s"},
        "transcript_excerpt": " ".join(w["w"] for w in words[:60]),
    }


def _stats(vals) -> dict:
    a = np.asarray([v for v in vals if v is not None], float)
    if not a.size:
        return {"med": None, "lo": None, "hi": None}
    return {"med": round(float(np.median(a)), 3), "lo": round(float(np.percentile(a, 10)), 3),
            "hi": round(float(np.percentile(a, 90)), 3)}


def _mode(vals):
    if not vals:
        return None
    u, c = np.unique(vals, return_counts=True)
    return str(u[np.argmax(c)])


# ----------------------------------------------------------------------------- aggregate
SCALAR_FIELDS = [
    "cuts_per_min", "shot_len_s.med", "shot_len_cv", "punch_in_every_s", "punch_in_scale", "zooms_per_min",
    "text.cards_per_min", "text.caption_cards_per_min", "text.titles_per_min", "text.words_per_card.med", "text.text_screen_pct", "text.caption_coverage_pct",
    "color.luma.med", "color.contrast.med", "color.saturation.med", "color.warmth.med", "broll_ratio",
    "face_time_pct", "speech_pct", "words_per_min", "audio.ducking_db", "audio.sfx_per_min",
    "audio.cuts_with_sfx_pct", "audio.cuts_on_beat_pct", "audio.cuts_on_beat_chance_pct", "audio.lufs", "audio.bpm", "audio.silence_pct",
    "structure.hook_len_s", "structure.rehook_every_s", "structure.max_no_change_s",
    "structure.loop_similarity", "duration_s",
]


def _get(d, path):
    for k in path.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def aggregate(fps_list: list[dict], typ: str, name: str) -> dict:
    out = {"name": name, "type": typ, "sources": len(fps_list), "measured_on": str(_dt.date.today()),
           "measured": True, "source_files": [f["file"] for f in fps_list], "fields": {}}
    for path in SCALAR_FIELDS:
        vals = [v for v in (_get(f, path) for f in fps_list) if isinstance(v, (int, float))]
        out["fields"][path] = {**_stats(vals), "n": len(vals)}
    mix = {}
    for f in fps_list:
        for k, v in f["transition_mix"].items():
            mix[k] = mix.get(k, 0) + v / len(fps_list)
    out["transition_mix"] = {k: round(v, 3) for k, v in mix.items()}
    for key in ("text.position", "text.animation", "structure.ending", "aspect"):
        out.setdefault("modes", {})[key] = _mode([_get(f, key) for f in fps_list if _get(f, key)])
    out["music_present_pct"] = round(100 * np.mean([bool(_get(f, "audio.music_present")) for f in fps_list]), 1)
    perf = [(f, f.get("meta", {}).get("performance")) for f in fps_list]
    perf = [(f, p) for f, p in perf if isinstance(p, (int, float))]
    if len(perf) >= 4:
        perf.sort(key=lambda t: t[1])
        half = len(perf) // 2
        low, high = [f for f, _ in perf[:half]], [f for f, _ in perf[-half:]]
        diffs = []
        for path in SCALAR_FIELDS:
            a = [v for v in (_get(f, path) for f in high) if isinstance(v, (int, float))]
            b = [v for v in (_get(f, path) for f in low) if isinstance(v, (int, float))]
            if len(a) >= 2 and len(b) >= 2:
                pooled = np.std(a + b) or 1e-9
                diffs.append((abs(np.median(a) - np.median(b)) / pooled, path, np.median(a), np.median(b)))
        diffs.sort(reverse=True)
        out["hypotheses"] = [{"field": p, "high_performers_med": round(float(a), 3),
                              "others_med": round(float(b), 3), "effect": round(float(e), 2),
                              "status": "hypothesis: not supported by evals yet"} for e, p, a, b in diffs[:6]]
        out["performance_metric"] = fps_list[0].get("meta", {}).get("performance_metric")
    out["qualitative"] = []
    return out


def pair_downloads(folder: Path) -> list[dict]:
    """Find videos (excluding *-audio* tracks) with their separate audio and info.json."""
    items = []
    for v in sorted(folder.rglob("*.mp4")):
        if re.search(r"-audio", v.stem):
            continue
        base = v.stem.rsplit("-", 1)[0]
        aud = sorted(a for a in v.parent.glob("*audio*.mp4") if a.stem.startswith(base))
        info = [i for i in v.parent.glob("*.info.json") if i.name.startswith(base.split(".")[0])]
        perf, metric = None, None
        if info:
            meta = read_json(info[0])
            for metric in ("view_count", "repost_count", "like_count"):
                if isinstance(meta.get(metric), (int, float)):
                    perf = meta[metric]
                    break
            else:
                metric = None
        items.append({"video": v, "audio": aud[0] if aud else None, "group": v.parent.name,
                      "performance": perf, "performance_metric": metric if perf is not None else None})
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure", help="fingerprint one finished video")
    m.add_argument("video"); m.add_argument("--audio"); m.add_argument("--out", required=True)
    m.add_argument("--frames-dir", help="save sampled frames for Claude's qualitative pass here")
    m.add_argument("--model", default="base", help="Whisper model for the speech measures (default base)")
    m.add_argument("--cache-dir", help="cache for the slow stages (frames, OCR, transcript)")
    b = sub.add_parser("batch", help="fingerprint every video under a reference folder")
    b.add_argument("folder"); b.add_argument("--out-dir", required=True); b.add_argument("--model", default="base")
    g = sub.add_parser("aggregate", help="combine fingerprints into a style rulebook")
    g.add_argument("fingerprints", nargs="+"); g.add_argument("--type", required=True)
    g.add_argument("--name", required=True); g.add_argument("--out", required=True)
    g.add_argument("--platform", default=None)
    a = ap.parse_args()
    try:
        if a.cmd == "measure":
            vid = Path(a.video)
            if not vid.exists():
                fail(f"{vid} does not exist")
            fp = measure(vid, Path(a.audio) if a.audio else None, Path(a.frames_dir) if a.frames_dir else None, a.model,
                         Path(a.cache_dir) if a.cache_dir else None)
            write_json(a.out, fp)
            log(f"wrote {a.out}")
        elif a.cmd == "batch":
            folder = Path(a.folder)
            if not folder.is_dir():
                fail(f"{folder} is not a folder")
            items = pair_downloads(folder)
            if not items:
                fail(f"no videos found under {folder}")
            out_dir = Path(a.out_dir)
            done = []
            for it in items:
                dst = out_dir / f"{it['group']}__{it['video'].stem[:60]}.json"
                fp = measure(it["video"], it["audio"], out_dir / "frames", a.model, out_dir / "cache")
                fp["meta"] = {"group": it["group"], "performance": it["performance"],
                              "performance_metric": it["performance_metric"]}
                write_json(dst, fp); done.append(str(dst))
            write_json(out_dir / "index.json", {"fingerprints": done})
            log(f"wrote {len(done)} fingerprints to {out_dir}")
        else:
            fps_list = [read_json(p) for p in a.fingerprints]
            style = aggregate(fps_list, a.type, a.name)
            style["platform"] = a.platform
            write_json(a.out, style)
            log(f"wrote {a.out} from {len(fps_list)} fingerprints")
    except (ToolError, FileNotFoundError, StopIteration) as e:
        fail(str(e) or "no video stream found")


if __name__ == "__main__":
    main()
