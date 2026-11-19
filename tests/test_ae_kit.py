"""After Effects finishing kit (lib/hf_ae.py, 2026-11-16), the custom grade (lib/color.py) and the
Amharic transcriber's offline behaviour. Offline and fast: no render, no model download."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from lib import hf_ae as A
from lib import hf_design as H

ROOT = Path(__file__).resolve().parents[1]


def _cx():
    return H.Ctx(30.0, 1080, 1920, {"accent": "#C6FF3D", "ink": "#101114"}, "")


def _registered(html: str, cid: str) -> bool:
    return html.startswith("<template>") and f'window.__timelines["{cid}"]' in html


def test_textures_are_png_files_not_svg_noise(tmp_path):
    A.write_textures(tmp_path)
    assert (tmp_path / "grain.png").stat().st_size > 1000 and (tmp_path / "paper.png").stat().st_size > 1000
    el, js = A.grain_layer(2.0, 30.0, 0.1)
    assert "assets/grain.png" in el and "feTurbulence" not in el
    assert js == A.grain_layer(2.0, 30.0, 0.1)[1]            # seeded: identical every build
    assert len(js) == 30                                        # re-positioned every 2 frames


def test_ink_captions_build_characters_and_mark_ghosts():
    caps = [{"s": 0, "e": 30, "words": [{"w": "ቦርጭ", "s": 2, "emph": True}, {"w": "ነው", "s": 12, "emph": False}]}]
    html = A.captions_ink(_cx(), caps, [0.7], 96, "#C6FF3D")
    assert _registered(html, "captions")
    assert html.count("<span class=\"c\">") == 3 + 2                     # one span per Ethiopic syllable
    assert html.count("data-layout-ignore") == 2                        # the two Echo ghosts are decoration
    assert 'stroke-dashoffset="1"' in html and "back.out(" in html      # marker write-on, overshoot reveal


def test_scenes_and_overlays_register_their_timelines():
    cx = _cx()
    f = A.sc_formula(cx, "f1", 1920, 3.0, {"kicker": "01", "ring": 2, "terms": [{"t": "a", "at": 2}, {"t": "×", "at": 4}, {"t": "1.6", "at": 6}],
                                            "example": {"label": "ለምሳሌ", "a": 70, "b": 1.6, "res": 112, "unit": "g", "at": 30}})
    v = A.sc_versus(cx, "v1", 960, 4.0, {"left": {"t": "A"}, "right": {"t": "B"}, "wrong": [0.9, 0.3], "right_h": [0.3, 0.9],
                                          "tags": {"more": "more", "less": "less"}, "crossAt": 20, "swapAt": 60})
    c = A.sc_checklist(cx, "c1", 1920, 2.0, {"rows": [{"n": "1", "t": "x", "at": 3}, {"n": "2", "t": "y", "at": 9}]})
    a = A.ov_annotate(cx, "a1", 2.0, {"items": [{"kind": "ring", "x": 0.5, "y": 0.7, "w": 0.5, "h": 0.2, "at": 2},
                                                {"kind": "arrow", "x0": 0.9, "y0": 0.4, "x1": 0.7, "y1": 0.6, "at": 10}],
                                      "label": {"t": "እኔም", "x": 0.8, "y": 0.4, "at": 5}})
    k = A.ov_kinetic(cx, "k1", 2.0, {"items": [{"t": "01", "at": 1, "y": 0.2, "x": 0.78, "mode": "write"}, {"t": "ስብ", "at": 3, "y": 0.2}]})
    for html, cid in ((f, "f1"), (v, "v1"), (c, "c1"), (a, "a1"), (k, "k1")):
        assert _registered(html, cid), cid
        assert "feTurbulence" not in html and "letterSpacing" not in html, cid
    assert "assets/paper.png" in f and "count(" in f and "ለምሳሌ" in f
    assert 'id="a1-h1a"' in a and 'id="a1-h1b"' in a                      # arrow head strokes
    assert "left:302px" in k                                              # x 0.78 -> offset from centre


def test_band_wipe_sets_start_in_gsap_and_leaves():
    el, js = A.fx_bands(3, 2.0, 30.0, ["#000", "#fff"])
    assert "transform" not in el                                          # no CSS transform on a GSAP-animated element
    assert js[0].startswith('tl.set("#fx3b i", { xPercent: -101 }, 0)')
    assert "xPercent: 101" in js[2] and js[3].startswith('tl.set("#fx3b", { opacity: 0 }')


def test_shake_decays_and_resets():
    js = A.shake_js("#frame", 1.0, 1.4, 30.0, 16)
    assert js[-1] == 'tl.set("#frame", { x: 0, y: 0, rotation: 0 }, 1.400);'
    first, last = (abs(float(re.search(r"x: (-?[\d.]+)", j).group(1))) for j in (js[0], js[-2]))
    assert last <= 16 and len(js) == 7


def test_custom_grade_dict_writes_a_cube(tmp_path):
    from lib.color import look_path
    g = {"name": "t", "contrast": 1.1, "hues": [{"hue": 80, "width": 30, "sat": 0.6, "shift": 10}]}
    p = look_path(g, tmp_path)
    head = p.read_text(encoding="ascii").splitlines()[:2]
    assert head == ['TITLE "pve t"', "LUT_3D_SIZE 33"] and p == look_path(g, tmp_path)


def test_transcribe_am_help_and_clear_failure(tmp_path):
    h = subprocess.run([sys.executable, str(ROOT / "scripts" / "transcribe_am.py"), "--help"], capture_output=True, text=True, encoding="utf-8")
    assert h.returncode == 0 and "hohe-asr" in h.stdout
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "transcribe_am.py"), "draft", "--media", str(tmp_path / "none.wav")],
                       capture_output=True, text=True, encoding="utf-8")
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["ok"] is False and "no such file" in out["error"]
