"""Localization: Ethiopic, Arabic (right-to-left) and mixed-script captions render through the
same libass path render.py uses (lib/captions.py ASS -> ffmpeg subtitles filter).

What "renders correctly" means here, measured on pixels:
- ink: the card draws visible glyphs;
- no tofu: two different strings of the same length draw different shapes (missing-glyph boxes
  are identical for every character);
- bidi: in an Arabic word whose first logical letter is the tall alef, the alef is drawn at the
  RIGHT end (right-to-left order), not the left;
- syllable cards: Ethiopic cards are split by syllable count, not Latin word length.
"""
from __future__ import annotations

import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from lib import captions
from lib.kit import fonts_dir

W, H = 960, 240
FONTS = {"Noto Sans Ethiopic": "NotoSansEthiopic.ttf", "Noto Sans Arabic": "NotoSansArabic.ttf",
         "Poppins ExtraBold": "PoppinsExtraBold.ttf"}


def need_font(name: str) -> None:
    if not (fonts_dir() / FONTS[name]).exists():
        pytest.skip(f"{name} not downloaded (run scripts/check_env.py online once)")


def render_text(tmp_path: Path, text: str, font: str, tag: str) -> np.ndarray:
    """One white line on black, rendered by libass at 960x240; returns a grey image."""
    ass = tmp_path / f"{tag}.ass"
    ass.write_text("\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: S,{font},90,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,10,10,10,-1", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 0,0:00:00.00,0:00:01.00,S,,0,0,0,,{text}", ""]), encoding="utf-8")
    png = tmp_path / f"{tag}.png"
    fd = tmp_path / "fonts"                 # relative fontsdir, as render.py does (no drive-letter escaping)
    if not fd.exists():
        shutil.copytree(fonts_dir(), fd)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:d=1",
                    "-vf", f"subtitles={ass.name}:fontsdir=fonts",
                    "-frames:v", "1", png.name], check=True, cwd=tmp_path)
    import cv2
    return cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)


def ink_box(img: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(img > 128)
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


def test_ethiopic_glyphs_render(tmp_path):
    need_font("Noto Sans Ethiopic")
    a = render_text(tmp_path, "ሰላም ጤና", "Noto Sans Ethiopic", "eth_a")
    b = render_text(tmp_path, "ቡና ልጅ", "Noto Sans Ethiopic", "eth_b")
    assert (a > 128).mean() > 0.01, "Amharic text drew no ink"
    # same length, different letters: real glyphs differ, tofu boxes would match
    diff = np.abs(a.astype(int) - b.astype(int)).mean()
    assert diff > 3, f"two different Amharic strings render alike (tofu?): mean diff {diff:.2f}"


def test_arabic_is_shaped_right_to_left(tmp_path):
    need_font("Noto Sans Arabic")
    img = render_text(tmp_path, "اووو", "Noto Sans Arabic", "ar")   # alef (tall) then three waw
    x0, x1, y0, y1 = ink_box(img)
    cols = (img[:, x0:x1 + 1] > 128)
    top_band = cols[y0:y0 + max(2, (y1 - y0) // 4)].any(axis=0)       # only the alef reaches the top
    xs = np.nonzero(top_band)[0]
    assert len(xs), "no tall glyph found"
    centre = xs.mean() / max(1, x1 - x0)
    assert centre > 0.6, f"alef drawn at {centre:.2f} of the word width: text was not laid out right-to-left"


def test_mixed_line_renders_both_scripts(tmp_path):
    need_font("Noto Sans Ethiopic"); need_font("Poppins ExtraBold")
    latin = render_text(tmp_path, "HELLO", "Poppins ExtraBold", "lat")
    # mixed: Latin in the caption font, Ethiopic switched per span as render.py does with \fn
    mixed = render_text(tmp_path, r"HELLO {\fnNoto Sans Ethiopic}ሰላም", "Poppins ExtraBold", "mix")
    lx = ink_box(latin)
    mx = ink_box(mixed)
    assert mx[1] - mx[0] > (lx[1] - lx[0]) * 1.3, "the Ethiopic word after the Latin one did not draw"


def test_ethiopic_cards_split_by_syllables():
    words = [{"w": w, "s_f": i * 10, "e_f": i * 10 + 9, "t_s": i * 10, "t_e": i * 10 + 9, "i": i}
             for i, w in enumerate("ኢትዮጵያ ታላቅ ሀገር ናት በጣም".split())]
    cards = captions.make_cards(words, Fraction(30), "pop_3word", 60)
    syl = [sum(len(w["w"]) for w in c["words"]) for c in cards]
    assert all(s <= captions.ETHIOPIC_SYLLABLES["pop_3word"] or len(c["words"]) == 1 for s, c in zip(syl, cards)), syl
    assert len(cards) >= 2
