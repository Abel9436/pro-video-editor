"""hf_design: the speaker cut-out plays only where something sits behind it; fonts.css URLs in either quote style (2026-11-20)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import hf_design as H  # noqa: E402


def test_spans_pad_merge_and_clip():
    assert H.fg_spans([(9, 12), (11.9, 13), (44, 46)], 139) == [(8.8, 13.2), (43.8, 46.2)]
    assert H.fg_spans([(0, 1), (138.9, 139)], 139) == [(0.0, 1.2), (138.7, 139)]
    assert H.fg_spans([], 10) == []


def test_fonts_inline_rewrites_both_quote_styles(tmp_path):
    (tmp_path / "fonts.css").write_text("""src: url('a.ttf'); src: url("b.ttf"); src: url(c.ttf);""", encoding="utf-8")
    css = H.fonts_inline(tmp_path)
    assert "url('assets/fonts/a.ttf')" in css and "url('assets/fonts/b.ttf')" in css and "url('assets/fonts/c.ttf')" in css


def test_look_extras_gain_and_green_shadows():
    import numpy as np
    from lib.color import _look_extras
    rgb = np.array([[0.1, 0.1, 0.1], [0.9, 0.9, 0.9]])
    out = _look_extras(rgb, rgb.copy(), {"gain": 0.9, "tint_shadows": [0, 0.05, 0]})
    assert out[0, 1] > out[0, 0] and abs(out[1, 0] - 0.81) < 1e-6          # dark pixel goes green, bright one only scales
    assert np.allclose(_look_extras(rgb, rgb.copy(), {}), rgb)
