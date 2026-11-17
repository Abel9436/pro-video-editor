"""3D explainer stages (lib/hf_explainer.py): offline, synthetic, 2026-11-17."""
from __future__ import annotations

import pytest

from lib import hf_design as H
from lib import hf_explainer as X


def _cx():
    return H.Ctx(30.0, 1080, 1920, {"accent": "#0E7A43", "ink": "#06120B"}, "")


def test_registered():
    assert {"Stage3D", "Podium3D"} <= H.SCENES and "Title3D" in H.OVERLAYS and "flip3d" in H.FX


def test_card_folds_and_unfolds():
    js = X.card_js("#cam", 1.0, 5.0, {"scale": 0.5, "y": 0.2, "ry": -12}, 1080, 1920)
    assert "scale: 0.5" in js[0] and "rotationY: -12" in js[0]
    assert js[-1].startswith('tl.set("#cam", { scale: 1') and "5.000" in js[-1]


@pytest.mark.parametrize("card", [{"scale": 0.5, "y": 0.3}, {"scale": 0.9, "x": 0.2}, {"scale": 0.44, "y": -0.3}])
def test_card_outside_frame_is_rejected(card):
    with pytest.raises(ValueError, match="leaves the frame"):
        X.card_js("#cam", 0, 3, card, 1080, 1920)


def test_flip_turns_out_and_back():
    a, b = X.flip_js(2.0, "left")
    assert "rotationY: -88" in a and "rotationY: 88" in b and "rotationY: 0" in b


def test_stage_builds_claim_head_and_cards():
    html = X.sc_stage3d(_cx(), "s00", 1920, 8.0, {"under": True, "kicker": {"t": "K"},
                        "claim": {"t": "C", "icon": "thumb-down", "at": 0, "strikeAt": 30, "out": 40},
                        "head": {"n": "2", "t": "H", "at": 45, "out": 90},
                        "cards": [{"n": "01", "t": "A", "icon": "gym", "at": 100}, {"n": "02", "t": "B", "at": 160}]})
    for k in ("s00-cs", "s00-hn", "s00-c0", "s00-c1", "assets/icons3d/gym_color.png"):
        assert k in html
    assert 'tl.to("#s00-c0", { opacity: 0.42' in html          # the earlier card steps back when the next lands


def test_podium_hero_and_trophy():
    html = X.sc_podium3d(_cx(), "s01", 1920, 4.0, {"hero": 1, "pillars": [
        {"t": "a", "rank": 2, "slot": 0, "h": 200, "at": 0}, {"t": "b", "rank": 1, "slot": 1, "h": 380, "at": 30}],
        "trophy": {"icon": "trophy", "at": 40}})
    assert 'class="s01-p hero"' in html and "s01-tr" in html and "bounce.out" in html


def test_title3d_extrudes_and_tint_lightens():
    html = X.ov_title3d(_cx(), "o00", 2.0, {"items": [{"t": "ስሩ", "y": 0.2, "depth": 6, "enter": "spin"}]})
    assert html.count("px 0 #") == 6 and "rotationY: -180" in html
    assert X._tint("#0E7A43", 0.5) > "#0E7A43" and X._shade("#ffffff", 0.5) == "#7f7f7f"
