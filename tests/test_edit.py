"""Milestones 2-9 on synthetic media: plan -> render -> QC -> viral scores -> timeline -> package,
plus unit tests for the decisions those scripts make (zoom budget, pattern interrupts, privacy
blur, licence filter, disclosure, EDL diff, profile learning).

The talking-head stand-in is a generated clip with a tone that switches on and off like speech,
and a transcript injected into analysis.json (no Whisper in tests).
"""
from __future__ import annotations

import json
import shutil
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from conftest import SR, ff, run_script

FPS = 25
WORDS = ("Most people think there is a secret. That is not how it works. You learn from people "
         "who already do it. Then you start your own thing.").split()
SCRIPTS = ["detect_type.py", "plan_edit.py", "render.py", "qc.py", "fingerprint.py", "fetch_assets.py", "tag_assets.py",
           "retention_sim.py", "virality_score.py", "hook_variants.py", "export_timeline.py", "package.py", "profile.py"]


@pytest.mark.parametrize("script", SCRIPTS)
def test_every_script_has_help(script):
    r = run_script(script, "--help")
    assert r.returncode == 0 and "usage" in r.stdout.lower(), r.stderr


def word_times():
    """0.4 s words with 0.12 s gaps, a 0.6 s pause after each sentence."""
    out, t = [], 0.3
    for w in WORDS:
        s, e = t, t + 0.4
        out.append((w, s, e))
        t = e + (0.6 if w.endswith(".") else 0.12)
    return out, t + 0.5


@pytest.fixture(scope="session")
def edit_project(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("edit")
    foot = root / "footage"; foot.mkdir()
    words, dur = word_times()
    t = np.arange(int(dur * SR)) / SR
    env = np.zeros_like(t)
    for _, s, e in words:
        env[(t >= s) & (t < e)] = 1.0
    voice = (0.25 * np.sin(2 * np.pi * 180 * t) + 0.08 * np.sin(2 * np.pi * 360 * t)) * env
    voice += np.random.default_rng(1).normal(0, 0.0005, len(t))
    sf.write(root / "voice.wav", np.stack([voice, voice], 1).astype(np.float32), SR)
    ff("-f", "lavfi", "-i", f"testsrc2=size=720x1280:rate={FPS}:duration={dur:.2f}", "-i", str(root / "voice.wav"),
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(foot / "talk.mp4"))
    project = root / "project"
    r = run_script("ingest.py", str(foot), "--project", str(project), "--platform", "shorts")
    assert r.returncode == 0, r.stderr
    r = run_script("analyze.py", "--project", str(project), "--transcriber", "none", "--max-images", "1")
    assert r.returncode == 0, r.stderr
    ana = json.loads((project / "analysis.json").read_text(encoding="utf-8"))
    rec = ana["files"]["talk"]
    rec["transcript"] = {"language": "en", "words": [
        {"i": i, "w": w, "s_f": round(s * FPS), "e_f": round(e * FPS), "p": 0.95, "speaker": "S1"}
        for i, (w, s, e) in enumerate(words)]}
    rec.setdefault("speech", {})["emphasis"] = [{"i": 7}]
    (project / "analysis.json").write_text(json.dumps(ana), encoding="utf-8")
    paper = {
        "platform": "shorts", "type": "short_form", "target_duration_s": 13, "commercial": True,
        "opening": "deductive", "pattern_interrupts": "auto",
        "beats": [
            {"src": "talk", "words": [6, 11], "role": "hook", "reason": "contrarian line first", "punch": [7],
             "rule_of_six": {"emotion": 7, "story": 8, "rhythm": 7}},
            {"src": "talk", "words": [0, 5], "role": "setup", "reason": "the belief being corrected"},
            {"src": "talk", "words": [12, 18], "role": "payoff", "reason": "the answer", "drop": [[16, 16]]},
            {"src": "talk", "words": [19, 24], "role": "ending", "reason": "the call to act"}],
        "captions": {"template": "pop_3word", "highlight": "keyword", "keywords": ["secret", "learn"]},
        "graphics": [{"component": "Title", "at_f": 0, "dur_s": 1.5, "props": {"text": "No secret", "y": 0.5},
                      "reason": "hook text layer"}],
        "sfx": [{"asset": "kit:hit_low", "at_f": 0, "gain_db": -20, "role": "impact_hit", "reason": "hook sound"}],
        "color": {"correction": "auto", "match_shots": True, "look": "clean_neutral", "strength": 0.4},
        "master": {"lufs": -14, "true_peak_db": -1}}
    (project / "edl").mkdir(exist_ok=True)
    (project / "edl" / "paper_v1.json").write_text(json.dumps(paper), encoding="utf-8")
    return project


@pytest.fixture(scope="session")
def planned(edit_project) -> Path:
    p = edit_project
    r = run_script("plan_edit.py", "draft", str(p / "edl" / "paper_v1.json"), "--project", str(p), "--out", str(p / "edl" / "v1.json"))
    assert r.returncode == 0, r.stderr
    return p / "edl" / "v1.json"


@pytest.fixture(scope="session")
def rendered(edit_project, planned) -> Path:
    r = run_script("render.py", "--edl", str(planned), "--project", str(edit_project), "--preview", "--graphics-engine", "ass")
    assert r.returncode == 0, r.stderr
    return edit_project / "exports" / "v1_preview.mp4"


def test_plan_reasons_order_and_notes(planned):
    edl = json.loads(planned.read_text(encoding="utf-8"))
    vids = edl["tracks"]["video"]
    assert vids[0]["role"] == "hook" and all(v.get("reason") for v in vids)
    assert [v["at_f"] for v in vids] == sorted(v["at_f"] for v in vids)
    assert any("Removed 'people'" in n for n in edl["notes"]), edl["notes"]
    spans = [(round(s * FPS), round(e * FPS)) for _, s, e in word_times()[0]]
    for d in edl["tracks"]["dialogue"]:          # every cut point sits outside a word
        for f in (d["in_f"], d["out_f"]):
            assert not any(a < f < b for a, b in spans), (d, f)


def test_zoom_budget_keeps_upscale_under_limit(planned):
    import plan_edit
    edl = json.loads(planned.read_text(encoding="utf-8"))
    for ev in edl["tracks"]["video"]:      # 720 wide source in a 1080 frame: base 1.5x, so zoom <= 1.32
        assert plan_edit.peak_zoom(ev) <= 2.0 * 720 / 1080 + 1e-6, ev


def test_render_preview_outputs(rendered, edit_project):
    from lib.common import ffprobe_json
    info = ffprobe_json(rendered)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (int(v["width"]), int(v["height"])) == (540, 960)
    assert rendered.with_suffix(".srt").exists() and rendered.with_suffix(".vtt").exists()
    rj = json.loads((edit_project / "render" / "preview" / "render.json").read_text(encoding="utf-8"))
    assert abs(rj["sound"]["master_input"]["input_i"] - (-16)) < 3


def test_rerender_reuses_chunks(rendered, edit_project, planned):
    r = run_script("render.py", "--edl", str(planned), "--project", str(edit_project), "--preview", "--graphics-engine", "ass")
    assert r.returncode == 0 and " 0 chunks rendered" in (r.stdout + r.stderr), r.stdout + r.stderr


def test_qc_report(rendered, edit_project, planned):
    r = run_script("qc.py", "--video", str(rendered), "--edl", str(planned), "--project", str(edit_project), "--preview",
                   "--no-retranscribe", "--no-style")
    rep = json.loads((edit_project / "qc" / "qc_report.json").read_text(encoding="utf-8"))
    ids = {c["id"]: c["status"] for c in rep["checks"]}
    for must in ("loudness", "true_peak", "cut_inside_word", "reasons", "licenses", "sidecar_captions", "format"):
        assert ids.get(must) == "pass", (must, ids.get(must), r.stdout[-800:])


def test_viral_scores(edit_project, planned):
    r = run_script("retention_sim.py", "--edl", str(planned), "--project", str(edit_project))
    assert r.returncode == 0, r.stderr
    ret = json.loads((edit_project / "retention.json").read_text(encoding="utf-8"))
    assert not any("no_visual_change" in w for d in ret["dips"] for w in d["why"]), ret["dips"]
    r = run_script("virality_score.py", "--edl", str(planned), "--project", str(edit_project))
    assert r.returncode == 0, r.stderr
    v = json.loads((edit_project / "virality.json").read_text(encoding="utf-8"))
    assert v["hook"]["text_in_first_s"] and v["hook"]["sound_in_first_s"]
    assert "guarantee" in v["disclaimer"]
    r = run_script("hook_variants.py", "--paper", str(edit_project / "edl" / "paper_v1.json"), "--project", str(edit_project))
    assert r.returncode == 0, r.stderr
    h = json.loads((edit_project / "hooks.json").read_text(encoding="utf-8"))
    assert h["candidates"] and h["candidates"][0]["score"] >= h["candidates"][-1]["score"]


def test_timeline_round_trip(rendered, edit_project, planned):
    r = run_script("export_timeline.py", "--edl", str(planned), "--project", str(edit_project))
    assert r.returncode == 0, r.stdout + r.stderr
    tj = json.loads((edit_project / "timeline" / "timeline.json").read_text(encoding="utf-8"))
    for f in ("otio", "fcpxml", "xml"):
        assert tj["files"][f]["ok"], (f, tj["files"][f])
    assert tj["overlay"] and Path(tj["overlay"]).exists()
    assert not tj["missing_media"]
    import opentimelineio as otio
    tl = otio.adapters.read_from_file(tj["files"]["otio"]["path"])
    names = [t.name for t in tl.tracks]
    assert names[:4] == ["V1 Picture", "V2 B-roll", "V3 Captions+Graphics (alpha)", "A1 Dialogue"] and "A3 SFX" in names
    clip = next(iter(tl.tracks[0].find_clips()))
    assert clip.markers and clip.markers[0].metadata["pve"]["reason"]


def test_package(rendered, edit_project, planned):
    r = run_script("package.py", "--edl", str(planned), "--project", str(edit_project))
    assert r.returncode == 0, r.stderr
    pk = json.loads((edit_project / "package" / "v1" / "package.json").read_text(encoding="utf-8"))
    assert len(pk["titles"]) == 5 and pk["titles_are_drafts"]
    assert pk["disclosure"]["label_needed"] is False
    assert pk["chapters"] == [] and "vertical" in pk["chapters_skipped"]
    out = edit_project / "package" / "v1"
    for f in ("video.mp4", "captions.srt", "captions.vtt", "credits.txt", "presets.json", "description.txt", "tags.txt"):
        assert (out / f).exists(), f
    assert "synthesized kit" in (out / "credits.txt").read_text(encoding="utf-8")


def test_plan_diff_and_profile_learning(edit_project, planned, tmp_path, monkeypatch):
    p = edit_project
    paper = json.loads((p / "edl" / "paper_v1.json").read_text(encoding="utf-8"))
    paper["beats"] = paper["beats"][:1] + paper["beats"][2:]          # "too long": drop the setup
    (p / "edl" / "paper_v2.json").write_text(json.dumps(paper), encoding="utf-8")
    r = run_script("plan_edit.py", "draft", str(p / "edl" / "paper_v2.json"), "--project", str(p), "--out", str(p / "edl" / "v2.json"))
    assert r.returncode == 0, r.stderr
    r = run_script("plan_edit.py", "diff", str(planned), str(p / "edl" / "v2.json"), "--project", str(p))
    assert r.returncode == 0, r.stderr
    ch = (p / "edl" / "v2.changes.md").read_text(encoding="utf-8")
    assert "length:" in ch and "removed shot" in ch
    import profile as prof_mod                      # scripts/profile.py (shadows the stdlib module on purpose)
    monkeypatch.setattr(prof_mod, "PROFILES", tmp_path)
    prof = json.loads(json.dumps(prof_mod.TEMPLATE))
    prof_mod.learn(prof, str(planned), str(p / "edl" / "v2.json"), "shorter")
    out = prof_mod.learn(prof, str(planned), str(p / "edl" / "v2.json"), "shorter again")
    assert prof["preferences"]["duration_s"]["value"] == "down" and out


# ------------------------------------------------------------------ unit tests

def _edl(events, W=1080, H=1920):
    return {"version": 1, "project": {"fps": "25", "width": W, "height": H, "platform": "shorts"},
            "tracks": {"video": events, "dialogue": [], "broll": [], "music": [], "sfx": [], "captions": None, "graphics": []},
            "notes": []}


def test_fit_zoom_budget_scales_stacked_punches():
    import plan_edit
    ev = {"id": "v1", "src": "a", "in_f": 0, "out_f": 100, "at_f": 0, "reason": "x", "reframe": {"zoom": 1.25},
          "transform": [{"at_f": 10, "type": "punch_in", "scale": 1.25, "dur_f": 4}]}
    edl = _edl([ev])
    media = {"items": [{"id": "a", "video": {"display_width": 720, "display_height": 1280}}]}
    notes = []
    assert plan_edit.peak_zoom(ev) > 1.5
    plan_edit.fit_zoom_budget(edl, media, notes)
    assert plan_edit.peak_zoom(ev) <= 0.99 * 2.0 * 720 / 1080 + 1e-3 and notes
    big = {"items": [{"id": "a", "video": {"display_width": 2160, "display_height": 3840}}]}
    ev2 = json.loads(json.dumps(ev)); ev2["reframe"]["zoom"] = 1.25; ev2["transform"][0]["scale"] = 1.25
    plan_edit.fit_zoom_budget(_edl([ev2]), big, [])
    assert ev2["transform"][0]["scale"] == 1.25          # 4K has room: untouched


def test_pattern_interrupts_fill_long_static_stretch():
    import plan_edit
    from lib.viral import static_gaps
    words = [{"i": i, "w": "w", "s_f": i * 10 + 2, "e_f": i * 10 + 8} for i in range(40)]
    edl = _edl([{"id": "v1", "src": "a", "in_f": 0, "out_f": 400, "at_f": 0, "reason": "x"}])
    notes = []
    plan_edit.add_interrupts(edl, {"files": {}}, {"a": words}, {}, Fraction(25), notes)
    assert max(b - a for a, b in static_gaps(edl)) <= 4 * 25
    kinds = [t["type"] for t in edl["tracks"]["video"][0]["transform"]]
    assert all(a != b for a, b in zip(kinds, kinds[1:])) and kinds[0] == "punch_in", kinds   # toggles; never creeps


def test_source_cuts_count_as_visual_change():
    from lib.viral import static_gaps
    edl = _edl([{"id": "v1", "src": "a", "in_f": 0, "out_f": 300, "at_f": 0, "reason": "x"}])
    ana = {"files": {"a": {"shots": [{"s_f": 0, "e_f": 100}, {"s_f": 100, "e_f": 200}, {"s_f": 200, "e_f": 300}]}}}
    assert max(b - a for a, b in static_gaps(edl)) == 300
    assert max(b - a for a, b in static_gaps(edl, ana)) == 100


def test_privacy_blurs_regions_only():
    import render
    fr = np.zeros((200, 100, 3), np.uint8)
    fr[::2, ::2] = 255                                        # high-frequency pattern: blur flattens it
    pv = render.Privacy({"regions": [{"t0_f": 0, "t1_f": 10, "box": [0.0, 0.0, 0.5, 0.5]}]}, faces=None)
    out = pv.apply(fr.copy(), 5)
    assert out[20:60, 10:40].std() < fr[20:60, 10:40].std() * 0.5
    assert (out[150:, 60:] == fr[150:, 60:]).all()            # outside the box untouched
    assert (pv.apply(fr.copy(), 20) == fr).all()              # outside the time range untouched


def test_license_filter():
    import fetch_assets as fa
    assert fa.license_ok("cc0", "music", True)[0]
    assert fa.license_ok("by", "music", True)[0]
    assert not fa.license_ok("by-nc", "music", True)[0]
    assert fa.license_ok("by-nc", "music", False)[0]
    assert not fa.license_ok("by-nd", "music", False)[0]
    assert not fa.license_ok("by-sa", "sfx", True)[0]


def test_disclosure_and_credits(tmp_path):
    import package
    edl = _edl([{"id": "v1", "src": "a", "in_f": 0, "out_f": 10, "at_f": 0, "reason": "x"}])
    edl["project"]["commercial"] = True
    assert package.disclosure(edl, [])["label_needed"] is False
    edl["tracks"]["dialogue"] = [{"id": "d1", "src": "a", "in_f": 0, "out_f": 10, "at_f": 0, "voice_clone": True}]
    assert package.disclosure(edl, [])["label_needed"] is True
    assert package.disclosure(_edl(edl["tracks"]["video"]), [{"id": "m", "ai_generated": True}])["label_needed"]
    edl["tracks"]["music"] = [{"asset": "cat:x:1", "at_f": 0}]
    (tmp_path / "licenses.json").write_text(json.dumps({"assets": [
        {"id": "cat:x:1", "license": "by-nc 4.0", "commercial": False, "attribution": '"Song" by A, CC BY-NC'}]}))
    text, warns, rows = package.credits(edl, tmp_path)
    assert '"Song" by A' in text and any("non-commercial" in w for w in warns)


def test_edl_diff_lists_changes():
    from lib.edl import edl_diff
    a = _edl([{"id": "v1", "src": "a", "in_f": 0, "out_f": 50, "at_f": 0, "reason": "x"},
              {"id": "v2", "src": "a", "in_f": 60, "out_f": 120, "at_f": 50, "reason": "y"}])
    b = json.loads(json.dumps(a)); b["tracks"]["video"] = b["tracks"]["video"][:1]; b["notes"] = ["dropped y"]
    ch = edl_diff(a, b)
    assert any(c.startswith("length:") for c in ch) and any("removed shot" in c for c in ch) and "note: dropped y" in ch


def test_phrase_groups_skip_hide_and_emphasis():
    from lib.captions import phrase_groups
    tw = [{"w": w, "t_s": i * 6, "t_e": i * 6 + 5} for i, w in enumerate(
        "you can never ever go wrong by being a teenager being an apprentice.".split())]
    g = phrase_groups(tw, 25, emphasis=["apprentice"], skip=[48, 54], hide=[(0, 5)], max_words=3)
    text = [" ".join(w["w"] for w in x["words"]) for x in g]
    assert "you can never" not in text                      # hidden: starts inside (0, 5)
    assert all("teenager" not in t and t != "a" for t in text)
    last = g[-1]["words"][-1]
    assert last["w"] == "apprentice." and last["emph"]
    assert all(x["e"] > x["s"] for x in g)
    assert all(a["e"] <= b["s"] for a, b in zip(g, g[1:]))    # phrases never overlap


def test_file_asset_licence_from_catalog(tmp_path):
    import json
    from lib.kit import resolve
    (tmp_path / "sfx").mkdir()
    (tmp_path / "sfx" / "whoosh_1.mp3").write_bytes(b"x")
    (tmp_path / "sfx" / "catalog.json").write_text(json.dumps({"sounds": [
        {"file": "sfx/whoosh_1.mp3", "name": "Woosh", "author": "someone", "source": "https://freesound.org/x",
         "license": "CC0 1.0", "license_checked": "2026-11-15", "commercial": True}]}))
    p, led = resolve("file:sfx/whoosh_1.mp3", tmp_path)
    assert led["license"] == "CC0 1.0" and led["url"] == "https://freesound.org/x"
    (tmp_path / "mine.mp4").write_bytes(b"x")
    assert resolve("file:mine.mp4", tmp_path)[1]["license"] == "user's own"
