"""Finish rules (2026-11-18): one light, one lens, no reversing moves, push-through exits, depth of field,
word reveals, sound aligned on its peak, a mono-safe synthesized kit. Offline and synthetic."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from lib import hf_design as H
from lib import hf_explainer as X
from lib import kit, mix


def _cx():
    return H.Ctx(30.0, 1080, 1920, {"accent": "#1F6F8B", "ink": "#0A1218"}, "")


STAGE = {"under": True, "claim": {"t": "Listed", "at": 0, "strikeAt": 20, "icon": "map-pin"},
         "head": {"n": "1", "t": "call", "at": 30},
         "cards": [{"n": "01", "t": "One", "icon": "gym", "at": 40}, {"n": "02", "t": "Two", "at": 60}]}


def _all():
    cx = _cx()
    return [X.sc_stage3d(cx, "s01", 1920, 4.0, STAGE),
            X.sc_podium3d(cx, "s02", 1920, 4.0, {"pillars": [{"t": "a", "rank": 1, "at": 0, "h": 500}], "trophy": {"icon": "trophy", "at": 20}}),
            X.ov_title3d(cx, "o01", 4.0, {"items": [{"t": "Just done.", "at": 0, "y": 0.3, "sheen": 30}, {"t": "Let's talk", "at": 60, "y": 0.5, "enter": "words", "still": True}]})]


def test_shadows_and_extrusions_fall_away_from_the_one_light():
    dx, dy = X.fall()
    lx, ly, _ = X.light_vec()
    assert dy == 1 and np.sign(dx) == -np.sign(lx) and ly < 0          # light above-left -> fall below-right
    first = X.extrude("#ffffff", 3).split(",")[0].split()
    assert float(first[0][:-2]) == pytest.approx(dx, abs=0.05) and float(first[1][:-2]) == pytest.approx(1.0)
    for html in _all():   # every drop shadow and box shadow uses the same direction
        for x, y in re.findall(r"drop-shadow\((-?\d+)px (\d+)px", html):
            if int(y):
                assert int(x) / int(y) == pytest.approx(dx, abs=0.1)


def test_one_lens_and_no_reversing_moves():
    for html in _all():
        assert set(re.findall(r"transformPerspective: (\d+)", html)) <= {str(X.PERSP)}
        assert "yoyo" not in html and "bounce" not in html and "elastic" not in html
    assert f"transformPerspective: {X.PERSP}" in X.card_js("#cam", 1, 4, {"scale": 0.5}, 1080, 1920)[0]


def test_title_drift_settles_and_still_items_hold():
    html = X.ov_title3d(_cx(), "o01", 4.0, {"items": [{"t": "A", "y": 0.3, "drift": 8}, {"t": "B", "y": 0.5, "still": True}]})
    assert "rotationY: -8" in html and "{ rotationY: 0, duration" in html      # -8 -> 0, never past it
    assert '"#o01-w1"' not in html                                           # the still item gets no drift tween


def test_stages_push_through_instead_of_dissolving():
    html = X.sc_stage3d(_cx(), "s01", 1920, 4.0, STAGE)
    assert 'scale: 1.22, filter: "blur(16px)"' in html
    cut = X.sc_stage3d(_cx(), "s01", 1920, 4.0, {**STAGE, "exit": "cut"})
    assert 'tl.set("#s01-stage", { opacity: 0 }' in cut
    with pytest.raises(ValueError):
        X.stage_exit("s01", 4.0, "fade")


def test_set_has_depth_of_field_and_safe_line_widths():
    html = X.sc_stage3d(_cx(), "s01", 1920, 4.0, STAGE)
    assert html.count('class="nr"') == 6 and "blur(7px)" in html                 # near motes out of focus
    assert "4px, transparent 4px" in html and "2px, transparent 2px" not in html
    assert 'filter: "blur(14px)"' in html                                          # headline racks into focus
    assert "-webkit-box-reflect" in html


def test_card_pushes_while_held_and_guard_counts_the_push():
    js = X.card_js("#cam", 1.0, 5.0, {"scale": 0.5, "y": 0.2}, 1080, 1920)
    assert "scale: 0.5200" in js[1]
    X.card_js("#cam", 1.0, 5.0, {"scale": 0.55, "y": 0.2}, 1080, 1920)         # 960 + 384 + 0.572 x 960 < 1920
    with pytest.raises(ValueError):                                             # the same card pushed to 0.66 leaves it
        X.card_js("#cam", 1.0, 5.0, {"scale": 0.55, "y": 0.2, "push": 1.2}, 1080, 1920)


def test_words_reveal_and_sheen():
    html = _all()[2]
    assert html.count('class="o01-wd1"') == 2 and "stagger: 0.075" in html and 'yPercent: 38' in html
    assert 'id="o01-sh0"' in html and 'backgroundPosition: "0% 0"' in html


# ---- sound ----------------------------------------------------------------------------------------
def _burst(n=4800, peak=3000):
    x = np.zeros((n, 2), np.float32)
    x[peak - 50:peak + 50] = 1.0
    x[200:260] = 0.2
    return x


def test_align_index_peak_start_end():
    x = _burst()
    assert abs(mix.align_index(x, "peak") - 3000) < 60
    assert mix.align_index(x, "start") <= 260                       # the quiet onset, not the peak
    assert 3050 <= mix.align_index(x, "end") <= 3050 + 480          # the tail, within the 10 ms smoothing
    with pytest.raises(ValueError):
        mix.align_index(x, "middle")


def test_repitch_and_pan():
    x = np.random.default_rng(0).standard_normal((4800, 2)).astype(np.float32)
    assert mix.repitch(x, 1.25).shape[0] == 3840 and mix.repitch(x, 1.0) is x
    y = mix.shape_sfx(np.ones((10, 2), np.float32), pan=1.0)
    assert y[0, 0] == pytest.approx(0, abs=1e-6) and y[0, 1] == pytest.approx(np.sqrt(2) * 1.0, rel=1e-3)
    z = mix.shape_sfx(x, lp=2000)
    assert np.abs(np.fft.rfft(z[:, 0]))[-500:].mean() < np.abs(np.fft.rfft(x[:, 0]))[-500:].mean() * 0.1


def test_sfx_schema_accepts_align_fields():
    from lib import edl as E
    props = E.SCHEMA["properties"]["tracks"]["properties"]["sfx"]["items"]["properties"]
    assert props["align"]["enum"] == ["peak", "start", "end"] and {"pitch", "lp", "hp", "pan"} <= set(props)


@pytest.mark.parametrize("role", kit.SYNTH_ROLES)
def test_synth_kit_is_mono_safe_and_clean(role):
    x = kit.synth(role)
    assert x.shape[1] == 2 and np.abs(x).max() <= 1.0001
    m = (x[:, 0] + x[:, 1]) / 2
    assert np.sqrt((m ** 2).mean()) >= 0.95 * np.sqrt((x[:, 0] ** 2).mean())   # no cancellation summed to mono
    assert np.abs(x[-1]).max() < 1e-3 and np.abs(x[-240:]).max() < np.abs(x).max()   # faded out, no click


def test_whooshes_pass_by():
    x = kit.synth("whoosh_mid")[:, 0]
    thirds = np.array_split(x, 3)
    rms = [float(np.sqrt((t ** 2).mean())) for t in thirds]
    assert rms[1] > rms[0] and rms[1] > rms[2]                                   # swells in the middle


def test_design_stills_collects_every_transition():
    import design_stills as D
    edl = {"fps": "30", "design": {"scenes": [{"s": 30, "e": 90, "type": "Stage3D"}], "overlays": [{"s": 90, "e": 120, "type": "Title3D"}],
                                   "camera": [{"s": 30, "e": 90, "card": {}}], "fx": [{"at": 30, "type": "flip3d"}]}}
    ev = D.events_of(edl)
    assert [round(t, 2) for t, _ in ev] == [1.0, 3.0, 4.0]                    # merged within 2 frames
    assert "Stage3D in" in ev[0][1] and "card in" in ev[0][1] and "flip3d" in ev[0][1]


def test_stage_kicker_position_claim_size_and_brand_fonts():
    cx = H.Ctx(30.0, 1080, 1920, {"accent": "#C9A46A", "ink": "#0F1C26", "font_title": "'DM Serif Display', serif"}, "")
    html = X.sc_stage3d(cx, "s01", 1920, 4.0, {"kicker": {"t": "BEFORE", "y": 0.478}, "claim": {"t": "On the market", "at": 0, "size": 120}})
    assert 'id="s01-k" style="top:918px"' in html and "font-size:120px" in html and "top:54px" in html   # strike at 0.45 x size
    assert "'DM Serif Display', serif" in html and "Zemach" not in html.split("s01-claim {")[1].split("}")[0]


def test_preview_lays_out_the_design_at_delivery_size():
    src = (Path(__file__).resolve().parents[1] / "scripts" / "render.py").read_text(encoding="utf-8")
    assert "LW, LH = (W * 2, H * 2) if preview else (W, H)" in src and 'scale={W}:{H}:flags=lanczos' in src
