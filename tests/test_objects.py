"""3D object, light sweep and glint caption kit (lib/hf_objects.py). Offline and synthetic, 2026-11-19."""
from __future__ import annotations

import pytest

from lib import hf_design as H
from lib import hf_objects as O
from lib import hf_spec as S


def _cx():
    return H.Ctx(30.0, 1080, 1920, {"accent": "#E8C268", "brand": "#0E7A43"}, "")


def test_registered():
    assert {"Object3D", "Sweep"} <= H.OVERLAYS and "glint" in H.CAPTION_STYLES


def test_object_plays_its_clip_with_alpha_path_and_exits():
    h = O.ov_object3d(_cx(), "o1", 3.0, {"obj": "trophy", "at": 0, "enter": "fly", "exit": "push", "media_start": 1.0,
                                          "label": {"big": "0", "t": "x", "sub": "y"}})
    assert 'src="assets/objects/trophy.webm"' in h and 'data-media-start="1.000"' in h and "muted" in h
    assert "rotationY: -70" in h and "scale: 1.9, opacity: 0" in h and 'id="o1-lab"' in h


def test_object_rejects_unknown_moves():
    with pytest.raises(ValueError):
        O.ov_object3d(_cx(), "o1", 3.0, {"obj": "t", "enter": "spin"})
    with pytest.raises(ValueError):
        O.ov_object3d(_cx(), "o1", 3.0, {"obj": "t", "exit": "spin"})


def test_sweep_moves_wrappers_not_the_rotated_bands():
    h = O.ov_sweep(_cx(), "s1", 0.6, {"angle": -24})
    assert h.count("rotate(-24deg)") == 3 and h.count('tl.fromTo("#s1-w') == 3


def test_glint_captions_flip_words_and_glint_emphasis():
    caps = [{"s": 0, "e": 60, "words": [{"w": "a", "s": 0, "emph": False}, {"w": "b", "s": 15, "emph": True}]}]
    h = O.captions_glint(_cx(), caps, [0.7], 66)
    assert "rotationX: -85" in h and '"#cg0b1", { backgroundPosition' in h and '"#cg0u1", { scaleX: 0' in h
    assert '"#cg0w0", { opacity: 0.72' in h and '"#cg0w1", { opacity: 0.72' not in h


def test_meters_rows_carry_3d_icons_and_a_hero():
    h = S.sc_meters(_cx(), "m1", 1920, 6.0, {"under": True, "hero": {"obj": "gauge", "size": 240}, "rows": [
        {"label": "a", "icon": "drop", "at": 0, "maxAt": 30}]})
    assert "assets/objects/gauge.webm" in h and "assets/objects/drop.webm" in h
