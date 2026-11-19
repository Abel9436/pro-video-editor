"""Editorial motion kit (lib/hf_editorial.py) and the cross-project grammar check (lib/grammar.py).
Offline and synthetic, 2026-11-19."""
from __future__ import annotations

import json

import pytest

from lib import grammar
from lib import hf_design as H
from lib import hf_editorial as E


def _cx():
    return H.Ctx(30.0, 1080, 1920, {"accent": "#B9825A", "ink": "#1C1A17", "font_title": "'Bodoni Moda', serif"}, "")


def test_registered():
    assert {"Lockup", "PhotoCard", "Track", "Fan", "Call", "Orbit", "Strikes", "Web"} <= H.OVERLAYS and "whisper" in H.CAPTION_STYLES
    assert all(H.OVERLAY_FN[k] is v for k, v in E.OVERLAYS.items())


def test_lockup_letters_turn_up_and_script_writes_on():
    html = E.ov_lockup(_cx(), "o1", 3.0, {"items": [{"t": "fast.", "role": "big", "y": 0.3}, {"t": "sold", "role": "lead", "y": 0.2},
                                                    {"t": "Just done.", "role": "script", "y": 0.6}]})
    assert html.count('class="o1-c0"') == 5 and "rotationX: -80" in html and "stagger: 0.035" in html
    assert 'clipPath: "inset(0% 100% 0% 0%)"' in html and "'Bodoni Moda', serif" in html
    with pytest.raises(ValueError):
        E.ov_lockup(_cx(), "o1", 3.0, {"items": [], "exit": "fade"})


def test_photocard_rolls_status_and_stamps_without_bounce():
    html = E.ov_photocard(_cx(), "o2", 3.0, {"img": "living.jpg", "statuses": [{"t": "COMING SOON", "at": 0}, {"t": "UNDER CONTRACT", "at": 30}],
                                             "stamp": {"t": "NEVER LISTED", "at": 45}})
    assert "assets/images/living.jpg" in html and 'tl.to("#o2-roll", { y: -56' in html and "white-space:nowrap" in html
    assert "bounce" not in html and "elastic" not in html


def test_track_call_fan_strikes_web_build():
    cx = _cx()
    t = E.ov_track(cx, "o3", 3.0, {"steps": [{"t": "Listed", "at": 0}, {"t": "Sold", "at": 40}]})
    assert 'tl.set("#o3-fill", { scaleX: 0 }, 0);' in t and "transform:scaleX(0)" not in t      # GSAP owns the transform
    c = E.ov_call(cx, "o4", 4.0, {"at": 0, "connect": 30})
    assert '"00:01"' in c and "calling…" in c
    f = E.ov_fan(cx, "o5", 2.0, {"cards": [{"t": "Offer", "at": 0}, {"t": "Offer", "at": 6}]})
    assert f.count('id="o5-k') == 2 and "data-layout-allow-overlap" in f
    s = E.ov_strikes(cx, "o6", 2.0, {"items": [{"t": "Showings", "at": 0, "strikeAt": 10}]})
    assert '"stroke-dashoffset": 0' in s
    w1 = E.ov_web(cx, "o7", 2.0, {"n": 12, "seed": 3})
    assert w1 == E.ov_web(cx, "o7", 2.0, {"n": 12, "seed": 3}) and w1.count("<circle") == 12   # seeded: same every build


def test_orbit_halves_share_the_ring_and_split_faces():
    p = {"images": ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], "spin": 120}
    front, back = E.ov_orbit(_cx(), "o8", 3.0, {**p, "half": "front"}), E.ov_orbit(_cx(), "o8", 3.0, {**p, "half": "back"})
    ring = 'tl.fromTo("#o8-ring", { rotationY: -40 }, { rotationY: 80'
    assert ring in front and ring in back                                  # identical motion, so the halves line up
    assert "rotateY(180deg)" in back and "rotateY(180deg)" not in front and "backface-visibility:hidden" in front
    with pytest.raises(ValueError):
        E.ov_orbit(_cx(), "o8", 3.0, {**p, "half": "middle"})


def test_whisper_captions_are_small_light_and_spaced():
    caps = [{"s": 0, "e": 30, "words": [{"w": "sold", "s": 0, "emph": False}, {"w": "fast", "s": 10, "emph": True}]}]
    html = E.captions_whisper(_cx(), caps, [0.76], 50)
    assert "font-weight: 300" in html and "margin: 0 0.13em" in html and "blur" not in html and "font-style: italic" in html


def test_grammar_flags_a_reused_edit(tmp_path, monkeypatch):
    monkeypatch.setenv("PVE_DESIGN_LOG", str(tmp_path / "log.jsonl"))
    old = {"design": {"scenes": [{"type": "Stage3D"}], "overlays": [{"type": "Title3D"}], "fx": [{"type": "flip3d"}],
                      "caption_style": "pop", "brand": {"font_title": "'DM Serif Display', serif"}, "camera": [{"card": {}}]}}
    grammar.record(old, "snap")
    assert grammar.compare(old, "house")["status"] == "warn"                # the same devices again
    new = {"design": {"overlays": [{"type": "PhotoCard"}, {"type": "Orbit"}], "fx": [{"type": "whip"}],
                      "caption_style": "whisper", "brand": {"font_title": "'Bodoni Moda', serif"}}}
    assert grammar.compare(new, "house")["status"] == "pass"
    grammar.record(new, "house")
    grammar.record(new, "house")                                            # latest wins, one line per project
    rows = [json.loads(x) for x in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["project"] for r in rows] == ["snap", "house"]
