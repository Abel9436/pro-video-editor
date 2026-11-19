"""Spec-sheet explainer kit (lib/hf_spec.py) and the backdrop exclusion in lib/restraint.py.
Offline and synthetic, 2026-11-19."""
from __future__ import annotations

from lib import hf_design as H
from lib import hf_spec as S
from lib import restraint


def _cx():
    return H.Ctx(30.0, 1080, 1920, {"accent": "#E8C268", "brand": "#0E7A43", "font_title": "'Tsega Elto', sans-serif"}, "")


def test_registered():
    assert set(S.OVERLAYS) <= H.OVERLAYS and set(S.SCENES) <= H.SCENES and "plate" in H.CAPTION_STYLES
    assert all(H.SCENE_FN[k] is v for k, v in S.SCENES.items())


def test_world_is_deterministic_and_never_tweens_its_css_transforms():
    a, b = S.ov_world(_cx(), "w1", 5.0, {"seed": 4}), S.ov_world(_cx(), "w1", 5.0, {"seed": 4})
    assert a == b and "rotateY(64deg)" in a and "rotateX(74deg)" in a
    # the walls and floor keep their CSS transform; GSAP only moves their inner backgrounds
    assert 'tl.fromTo("#w1-flg", { backgroundPosition' in a and 'tl.fromTo("#w1-fl",' not in a and "repeat: -1" not in a


def test_ring_draws_then_locks_and_runs_text_round_it():
    h = S.ov_ring(_cx(), "r1", 4.0, {"at": 0, "lockAt": 60, "text": "OPEN BODYBUILDING"})
    assert '"stroke-dashoffset": 0 }, duration: 2.000' in h and "<textPath" in h and "OPEN BODYBUILDING" in h


def test_stat_lands_on_value_after_the_roll():
    h = S.ov_stat(_cx(), "s1", 3.0, {"value": "0", "roll": "321", "at": 0, "land": 18, "label": "x"})
    assert h.count('line-height') >= 4 and "y: -" in h and "duration: 0.600" in h


def test_flipcard_has_two_faces_and_turns_180():
    h = S.ov_flipcard(_cx(), "f1", 3.0, {"front": {"title": "A"}, "back": {"title": "B"}, "flipAt": 30})
    assert h.count(";backface-visibility:hidden") == 2 and "rotateY(180deg)" in h and "rotationY: 180" in h


def test_meters_slam_to_max_and_count_the_value():
    h = S.sc_meters(_cx(), "m1", 1920, 6.0, {"under": True, "rows": [
        {"label": "a", "at": 0, "maxAt": 30, "value": {"from": 18, "to": 5, "at": 40, "final": "4–5"}}]})
    assert h.count('class="m1-s0"') == S.SEGMENTS and 'backgroundColor: "#E8C268"' in h
    assert 'count("#m1-v0", 18, 5,' in h and 'textContent: "4–5"' in h and "linear-gradient(180deg, #fff4d6" not in h


def test_divisions_runs_curve_strike_and_cards():
    h = S.sc_divisions(_cx(), "d1", 1920, 8.0, {"under": True, "curve": {"title": "t", "at": 0, "out": 60, "label": "here"},
                                                 "struck": {"t": "Open", "at": 60, "strikeAt": 90, "stamp": "no", "chipAt": 120},
                                                 "cards": [{"t": "A", "at": 130}, {"t": "B", "at": 140}], "spreadAt": 170})
    assert h.count('id="d1-k') == 2 and '"#d1-sl", { attr: { "stroke-dashoffset": 0 }' in h and "scale: 0.62" in h


def test_plate_captions_hand_the_plate_from_word_to_word():
    caps = [{"s": 0, "e": 60, "words": [{"w": "ኦፕን", "s": 0, "emph": False}, {"w": "ቦዲቢልዲንግ", "s": 15, "emph": True}]}]
    h = S.captions_plate(_cx(), caps, [0.7], 68)
    assert '"#cp0p0", { opacity: 0' in h and '"#cp0p1", { opacity: 0' not in h     # the last word keeps its plate
    assert "yPercent: 105" in h and "#E8C268" in h


def test_backdrop_is_not_counted_as_a_graphic():
    edl = {"project": {"fps": 30}, "tracks": {"video": [{"id": "v1", "in_f": 0, "out_f": 300, "at_f": 0}]},
           "design": {"overlays": [{"type": "World", "s": 0, "e": 300, "behind": True}, {"type": "Ring", "s": 0, "e": 60}],
                      "caption_style": "plate"}}
    got = {c["id"]: c for c in restraint.audit(edl)}
    assert got["restraint_persistent_overlay"]["status"] == "pass" and got["restraint_concurrent_layers"]["value"] == 2


def test_overlapping_behind_spans_keep_the_cutout_on():
    """Two behind graphics that overlap (a backdrop and a ring) are one stretch for the speaker cut-out:
    the ring's end must not hide him while the backdrop still covers the original background."""
    cx = _cx()
    ov = [{"cid": "a", "s": 0.0, "d": 12.0, "behind": True}, {"cid": "b", "s": 2.0, "d": 4.0, "behind": True}]
    html = H.root_file(cx, 20.0, [{"s": 0, "e": 600, "mode": "full"}], [], ov, [], [], 0.3, True, False, False, [], [])
    sets = [ln for ln in html.splitlines() if ln.startswith('tl.set("#camfg", { opacity')]
    assert sets == ['tl.set("#camfg", { opacity: 0 }, 0);', 'tl.set("#camfg", { opacity: 1 }, 0.000);', 'tl.set("#camfg", { opacity: 0 }, 12.000);']
