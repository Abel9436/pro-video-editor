"""Fast unit tests: time math, audio sync and clipping, speech features."""
from __future__ import annotations

from fractions import Fraction

import numpy as np
import soundfile as sf

from conftest import SR, SYNC_DELAY_S, click_audio
from lib.audio import ANALYSIS_SR, find_offset, scan_levels
from lib.speech import (find_emphasis, find_false_starts, find_fillers, find_gaps, find_retakes, sentences)
from lib.timebase import (convert_frames, nearest_standard, parse_rate, sec_to_frames, timecode)

FPS = Fraction(30)


# ---------------------------------------------------------------- timebase

def test_parse_rate_exact_ntsc():
    assert parse_rate("30000/1001") == Fraction(30000, 1001)
    assert parse_rate("0/0") is None
    assert parse_rate("25") == 25


def test_frames_do_not_drift_over_an_hour():
    ntsc = Fraction(30000, 1001)
    # one hour of 29.97: 107892.1 frames; float accumulation would drift, Fractions do not
    assert sec_to_frames(3600, ntsc) == 107892
    assert convert_frames(107892, ntsc, Fraction(60000, 1001)) == 215784


def test_nearest_standard_and_timecode():
    assert nearest_standard(Fraction(2997, 100)) == Fraction(30000, 1001)
    assert timecode(95, FPS) == "00:00:03.05"
    assert timecode(30 * 3661, FPS) == "01:01:01.00"


# ---------------------------------------------------------------- audio

def _resample16k(x):
    from scipy.signal import resample_poly
    return resample_poly(x, 1, 3).astype(np.float32)


def test_multicam_offset_recovered_to_the_sample_region():
    a = click_audio(8.0, seed=3)
    b = np.concatenate([np.zeros(int(SYNC_DELAY_S * SR), np.float32), a])[: a.size] * 0.4
    res = find_offset(_resample16k(a), _resample16k(b), ANALYSIS_SR)
    assert res.accepted, res
    # b holds the same sound 1.25 s later, so b started 1.25 s earlier: negative offset
    assert abs(res.offset_samples + SYNC_DELAY_S * ANALYSIS_SR) <= 2  # within 0.125 ms


def test_unrelated_recordings_are_not_synced():
    res = find_offset(_resample16k(click_audio(8.0, 1)), _resample16k(click_audio(8.0, 2)), ANALYSIS_SR)
    assert not res.accepted


def test_clipping_scan(tmp_path):
    t = np.arange(SR) / SR
    sf.write(tmp_path / "c.wav", np.clip(1.5 * np.sin(2 * np.pi * 200 * t), -1, 1), SR, subtype="PCM_16")
    sf.write(tmp_path / "ok.wav", 0.5 * np.sin(2 * np.pi * 200 * t), SR, subtype="PCM_16")
    clipped, clean = scan_levels(tmp_path / "c.wav"), scan_levels(tmp_path / "ok.wav")
    assert clipped.clipped_runs > 100 and clipped.clipped_pct > 10
    assert clean.clipped_runs == 0 and -7 < clean.peak_dbfs < -5


# ---------------------------------------------------------------- speech

def W(spec):
    """Build words from (text, start_frame, end_frame[, prob])."""
    return [{"i": k, "w": s[0], "s_f": s[1], "e_f": s[2], "p": s[3] if len(s) > 3 else 0.95, "speaker": "S1"}
            for k, s in enumerate(spec)]


def test_fillers_hard_and_soft():
    words = W([("So", 0, 5), ("um,", 6, 10), ("I", 12, 14), ("mean,", 14, 18), ("it", 19, 21), ("works.", 21, 30)])
    f = find_fillers(words, "en")
    assert [(x["text"], x["kind"]) for x in f] == [("um,", "hard"), ("I mean,", "soft")]


def test_false_starts_repeat_cutoff_restart():
    words = W([("I", 0, 3), ("I", 4, 7), ("think", 8, 14), ("we-", 15, 18), ("We", 30, 33), ("should", 34, 40),
               ("go", 41, 45), ("We", 50, 53), ("should", 54, 60), ("leave", 61, 70)])
    kinds = {x["kind"] for x in find_false_starts(words, FPS)}
    assert kinds == {"repeat", "cutoff", "restart"}


def test_retakes_pick_clean_complete_take():
    words = W([("The", 0, 3, .9), ("trick", 4, 9, .9), ("is,", 10, 14, .9), ("um,", 15, 20, .9), ("to", 21, 23, .9),
               ("start", 24, 30, .5), ("early", 31, 40, .6),
               ("The", 100, 103), ("trick", 104, 109), ("is", 110, 113), ("to", 114, 116), ("start", 117, 122),
               ("early.", 123, 135)])
    sents = sentences(words)
    fillers = find_fillers(words, "en")
    rt = find_retakes(sents, fillers, find_false_starts(words, FPS), FPS)
    assert len(rt) == 1
    best = sents[rt[0]["recommended"]]
    assert best["s_f"] == 100 and best["complete"]


def test_gaps_silence_breath_and_nonspeech():
    words = W([("one", 0, 30), ("two", 120, 150)])
    lv = np.full(200, -70.0)
    lv[0:30] = lv[120:150] = -20       # speech
    lv[40:50] = -45                    # breath: quiet, 0.33 s
    lv[70:90] = -22                    # loud non-speech, 0.67 s (laugh-like)
    sil, br, ns = find_gaps(words, lv, noise_floor_db=-70, fps=FPS, total_f=200)
    assert any(s["s_f"] == 30 and s["e_f"] == 120 for s in sil)
    assert br == [{"s_f": 40, "e_f": 50}]
    assert len(ns) == 1 and ns[0]["s_f"] == 70


def test_emphasis_finds_the_loud_word():
    spec = [(f"word{k}", k * 10, k * 10 + 8) for k in range(20)]
    words = W(spec)
    lv = np.full(220, -30.0) + np.random.default_rng(0).normal(0, 0.5, 220)
    lv[120:128] = -12   # word12 shouted
    em = find_emphasis(words, lv, None)
    assert em and em[0]["w"] == "word12"


def test_lossy_overshoot_is_not_clipping(tmp_path):
    # a smooth wave that peaks above full scale (as AAC decodes of 0 dBFS masters do) is hot, not flat
    t = np.arange(SR) / SR
    sf.write(tmp_path / "hot.wav", (1.05 * np.sin(2 * np.pi * 200 * t)).astype(np.float32), SR, subtype="FLOAT")
    s = scan_levels(tmp_path / "hot.wav")
    assert s.clipped_runs == 0 and s.overs > 0


# ---------------------------------------------------------------- ingest helpers

def test_conform_method_for_rate_pairs():
    from ingest import conform_method
    assert conform_method(Fraction(30), Fraction(30)) == "native"
    assert conform_method(Fraction(60), Fraction(30)) == "drop_frames"
    assert conform_method(Fraction(60000, 1001), Fraction(30)) == "drop_frames_retime"
    assert conform_method(Fraction(30000, 1001), Fraction(30)) == "retime"
    assert conform_method(Fraction(120), Fraction(30)) == "drop_frames"
    assert conform_method(Fraction(25), Fraction(30)) == "frame_blend"


def test_rhetorical_repetition_is_not_a_false_start():
    # "I don't want to be the guy. I don't want to be chasing likes. posting on YouTube or posting on Instagram"
    text = ("I don't want to be the guy. I don't want to be chasing likes. "
            "posting on YouTube or posting on Instagram").split()
    words = W([(t, k * 8, k * 8 + 7) for k, t in enumerate(text)])
    assert find_false_starts(words, FPS) == []


# ---------------------------------------------------------------- diarization

def _voice(f0, formant, seconds, seed):
    """Glottal-pulse-like harmonic source shaped by one formant, with syllable-rate amplitude."""
    from scipy.signal import butter, lfilter
    sr = 16000
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    f = f0 * (1 + 0.04 * np.sin(2 * np.pi * 0.7 * t))            # intonation
    src = np.sign(np.sin(2 * np.pi * np.cumsum(f) / sr)) + rng.normal(0, 0.05, t.size)
    b, a = butter(2, [formant * 0.7 / (sr / 2), formant * 1.3 / (sr / 2)], btype="band")
    y = lfilter(b, a, src) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 3 * t)))  # ~6 syllables/s
    return (0.3 * y / np.abs(y).max()).astype(np.float32)


def test_diarization_counts_one_and_two_voices():
    from lib.diarize import diarize_mfcc
    sr = 16000
    a, b = _voice(110, 700, 24, 1), _voice(210, 1800, 24, 2)
    # alternate 6 s turns: A B A B
    two = np.concatenate([a[:6 * sr], b[:6 * sr], a[6 * sr:12 * sr], b[6 * sr:12 * sr]])
    span = [(0, 24 * 30)]
    _, meta2 = diarize_mfcc(two, sr, span, FPS, None)
    _, meta1 = diarize_mfcc(a, sr, [(0, 24 * 30)], FPS, None)
    assert meta2["speakers"] == 2
    assert meta1["speakers"] == 1
