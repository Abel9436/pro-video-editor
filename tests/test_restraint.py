"""Restraint audit (lib/restraint.py), pop captions (lib/hf_creator.py), cutaway check. Offline, 2026-11-17."""
from __future__ import annotations

from lib import hf_design as H
from lib.hf_creator import captions_pop
from lib.restraint import audit


def _edl(**design):
    v = [{"id": f"v{i}", "src": "a", "in_f": 0, "out_f": 90, "at_f": i * 90} for i in range(6)]    # 18 s
    return {"project": {"fps": 30}, "tracks": {"video": v, "sfx": [], "dialogue": []}, "design": design}


def _st(items, cid):
    return next(i for i in items if i["id"] == f"restraint_{cid}")["status"]


def test_quiet_edit_passes():
    items = audit(_edl(caption_style="pop", emphasis=["a", "b"], camera=[{"s": 0, "e": 60, "z0": 1, "z1": 1.05}]))
    assert all(i["status"] == "pass" for i in items)


def test_busy_edit_warns_on_each_tell():
    e = _edl(emphasis=list("abcdefghij"), fx=[{"at": i, "type": "flash"} for i in range(5)],
             overlays=[{"type": "Hud", "s": 0, "e": 540}, {"type": "Scopes", "s": 10, "e": 100}, {"type": "Kinetic", "s": 10, "e": 100}],
             camera=[{"s": 0, "e": 540, "z0": 1.0, "z1": 1.2, "shake": 8}] * 3,
             bg=[{"color": "raw", "s": 0, "e": 540, "labels": ["A", "B"], "wipe": [{}, {}, {}]}])
    e["tracks"]["sfx"] = [{}] * 12
    bad = {i["id"] for i in audit(e) if i["status"] == "warn"}
    for cid in ("sfx", "fx", "emphasis", "persistent_overlay", "concurrent_layers", "moving_camera", "punch_ins", "reveal_spent_once"):
        assert f"restraint_{cid}" in bad


def test_pop_captions_move_the_phrase_once_and_keep_accent_for_emphasis():
    cx = H.Ctx(30.0, 1080, 1920, {"accent": "#FF4438"}, "")
    caps = [{"s": 0, "e": 40, "words": [{"w": "ሰው", "s": 2, "emph": False}, {"w": "ስሩ", "s": 12, "emph": True}]}]
    html = captions_pop(cx, caps, [0.74], 88)
    assert "blur(" not in html and 'tl.fromTo("#cp0i"' in html
    assert html.count('tl.fromTo("#cp0w') == 0                          # no per-word entrance
    assert 'color: "#FF4438", scale: 1.08' in html                      # emphasis word lights in its accent
    assert "pop" in H.CAPTION_STYLES


def test_cutaway_and_freeze_are_schema_fields():
    from lib import edl as E
    src = open(E.__file__, encoding="utf-8").read()
    assert '"cutaway": {"type": "boolean"}' in src and '"freeze_f": NONNEG' in src
    import plan_edit
    assert 'v.get("cutaway")' in open(plan_edit.__file__, encoding="utf-8").read()


def test_distinct_plates_are_separate_shots_but_one_plate_held_long_warns():
    shots = [{"type": "Plate", "s": i * 120, "e": i * 120 + 110, "p": {"obj": f"t3_{i}"}} for i in range(4)]   # 4 x 3.7 s of 18 s
    assert _st(audit(_edl(overlays=shots)), "persistent_overlay") == "pass"
    held = [{"type": "Plate", "s": 0, "e": 450, "p": {"obj": "t3_0"}}]
    assert _st(audit(_edl(overlays=held)), "persistent_overlay") == "warn"
