"""Colour-grading motion design (lib/hf_grade.py) and the raw wipe layer, 2026-11-16. Offline, no render."""
from __future__ import annotations

from lib import hf_design as H
from lib import hf_grade as G


def _cx():
    return H.Ctx(30.0, 1080, 1920, {"accent": "#FF9A2E", "ink": "#0B1220"}, "")


def _registered(html: str, cid: str) -> bool:
    return html.startswith("<template>") and f'window.__timelines["{cid}"]' in html


def test_components_are_registered_and_supported():
    d = {"scenes": [{"type": "LutCube"}], "overlays": [{"type": "Hud"}, {"type": "Scopes"}], "caption_style": "cine"}
    assert H.unsupported(d) == []


def test_hud_switches_profile_and_restores_the_right_pill_after_a_hide():
    html = G.ov_hud(_cx(), "h", 6.0, {"switchAt": 60, "hide_bottom": [[30, 45], [90, 120]]})
    assert _registered(html, "h") and "REC.709" in html and "00:00:00:00" in html
    assert 'tl.to("#h-prof1, #h-lut", { autoAlpha: 1' in html          # after the switch, REC.709 comes back
    assert 'tl.to("#h-prof, #h-lut", { autoAlpha: 1' in html           # before it, LOG does
    assert "textContent" not in html.split("onUpdate")[0]             # no tl.set on text


def test_scopes_play_the_right_videos_from_the_overlay_start():
    v = G.ov_scopes(_cx(), "s", 2.0, {"kind": "vector", "t0": 5.25})
    w = G.ov_scopes(_cx(), "w", 2.0, {"kind": "wave", "t0": 1.0})
    assert 'src="assets/scope_vec_raw.mp4"' in v and 'src="assets/scope_vec.mp4"' in v and 'data-media-start="5.2500"' in v
    assert "object-fit:cover" in v and "object-fit:fill" in w and "<text" in w


def test_lut_cube_moves_every_pixel_from_log_to_graded_colour():
    pts = [[0.4, 0.4, 0.4, 0.9, 0.5, 0.1], [0.45, 0.45, 0.5, 0.2, 0.5, 0.9]]
    html = G.sc_lutcube(_cx(), "c", 1920, 4.0, {"points": pts, "at": 30, "title": "LUT"})
    assert _registered(html, "c") and html.count('class="c-e"') == 12
    assert 'backgroundColor: "#e6801a"' in html and "Math.random" not in html


def test_cine_captions_reveal_words_and_underline_emphasis():
    caps = [{"s": 0, "e": 30, "words": [{"w": "log", "s": 2, "emph": True}, {"w": "video", "s": 10, "emph": False}]}]
    html = G.captions_cine(_cx(), caps, [0.72], 74)
    assert _registered(html, "captions") and 'id="cp0w0u"' in html and "blur(10px)" in html


def test_raw_wipe_layer_clips_and_hides_labels_until_the_line_moves():
    cx = _cx()
    bg = [{"s": 0, "e": 90, "color": "raw", "x0": 1.0, "wipe": [{"at": 30, "x": 0.5, "dur": 10}]}]
    html = H.root_file(cx, 3.0, [{"s": 0, "e": 90, "mode": "full"}], [], [], [], bg, 0.22, False, False, False, [], [], has_raw=True)
    assert 'src="assets/base_raw.mp4"' in html and 'clipPath: "inset(0% 50.00% 0% 0%)"' in html
    assert 'tl.set(".rlab0", { opacity: 0 }' in html and 'tl.to(".rlab0", { opacity: 1' in html
    assert "base_raw" not in H.root_file(cx, 3.0, [], [], [], [], bg, 0.22, False, False, False, [], [])
