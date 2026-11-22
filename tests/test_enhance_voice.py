"""enhance_voice: the fitted mic EQ moves a dark, boomy voice-like signal toward the speech target, and the studio
chain uses it. Synthetic and fast: shaped noise stands in for a far phone mic; DeepFilterNet itself is not run."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import enhance_voice as ev  # noqa: E402
from lib import mix  # noqa: E402


def _dark_voice(path: Path):
    rng = np.random.default_rng(3)
    n = ev.SR * 6
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / ev.SR)
    shape = 1 / (1 + (f / 400) ** 2) + 0.6 * np.exp(-((f - 320) / 120) ** 2)   # boomy, steep top-end roll-off
    x = np.fft.irfft(X * shape, n)
    env = (np.sin(np.arange(n) / ev.SR * 2 * np.pi * 2.5) > -0.3).astype(float)   # syllable-like on/off
    x = x / np.abs(x).max() * 0.3 * env
    sf.write(path, np.stack([x, x], 1).astype(np.float32), ev.SR, subtype="FLOAT")


def test_fit_eq_cuts_boom_and_lifts_presence(tmp_path):
    w = tmp_path / "v.wav"
    _dark_voice(w)
    gains, err0, err1 = ev.fit_eq(w, tmp_path / "t.wav")
    g = dict(zip([e[0] for e in ev.EQ], gains))
    assert g[340] < 0 and g[5500] > 0 and g[8000] > 0
    assert all(lo <= x <= hi for x, (_, _, _, lo, hi) in zip(gains, ev.EQ))
    assert sum(abs(e) for e in err1) < sum(abs(e) for e in err0)


def test_studio_chain_uses_fitted_eq_and_no_second_denoise(tmp_path):
    w = tmp_path / "v.wav"
    _dark_voice(w)
    _, chain = mix.voice_chain(w, tmp_path / "o.wav", -50, studio=True, eq=["equalizer=f=340:t=q:w=1.6:g=-3.0"])
    assert "afftdn" not in chain and "f=340" in chain and (tmp_path / "o.wav").exists()
