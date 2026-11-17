"""Integration tests: check_env, ingest.py and analyze.py on synthetic footage."""
from __future__ import annotations

import json
import time

import pytest

from conftest import SYNC_DELAY_S, run_script
from lib.common import ffprobe_json

SCRIPTS = ["check_env.py", "ingest.py", "analyze.py"]


@pytest.mark.parametrize("script", SCRIPTS)
def test_every_script_has_help(script):
    r = run_script(script, "--help")
    assert r.returncode == 0 and "usage" in r.stdout.lower()


def test_check_env_reports_ffmpeg():
    r = run_script("check_env.py", "--no-gpu-test")
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    assert rep["tools"]["ffmpeg"]["available"] and not rep["fatal"]


def test_ingest_fails_clearly_on_missing_folder(tmp_path):
    r = run_script("ingest.py", str(tmp_path / "nope"), "--project", str(tmp_path / "p"))
    assert r.returncode != 0 and "not found" in r.stderr


def _media(project):
    return json.loads((project / "media.json").read_text(encoding="utf-8"))


def test_ingest_timeline_rate_and_proxies(ingested):
    m = _media(ingested)
    assert m["fps"] == "30"
    for it in m["items"]:
        if it["kind"] == "video":
            s = next(x for x in ffprobe_json(ingested / it["proxy"])["streams"] if x["codec_type"] == "video")
            assert min(s["width"], s["height"]) == 540
            assert s["avg_frame_rate"] == "30/1"
        if it.get("wav"):
            a = ffprobe_json(ingested / it["wav"])["streams"][0]
            assert a["sample_rate"] == "16000" and a["channels"] == 1


def test_ingest_vfr_detected_and_conformed(ingested):
    it = next(i for i in _media(ingested)["items"] if i["id"] == "phone_vfr")
    assert it["video"]["vfr"] is True
    assert any(a.startswith("vfr_to_cfr") for a in it["conform"]["applied"])
    v = next(s for s in ffprobe_json(it["render_src"])["streams"] if s["codec_type"] == "video")
    assert v["r_frame_rate"] == v["avg_frame_rate"]


def test_ingest_hdr_tonemapped(ingested):
    it = next(i for i in _media(ingested)["items"] if i["id"] == "hdr_pq")
    assert it["video"]["hdr"] == "pq"
    v = next(s for s in ffprobe_json(it["render_src"])["streams"] if s["codec_type"] == "video")
    assert v.get("color_transfer") == "bt709" and v["pix_fmt"] == "yuv420p"


def test_ingest_multicam_offset(ingested):
    m = _media(ingested)
    assert len(m["sync_groups"]) == 1
    g = m["sync_groups"][0]
    assert {x["id"] for x in g["members"]} == {"cam_a", "cam_b"}
    b = next(x for x in g["members"] if x["id"] == "cam_b")
    # cam_b's audio is delayed, i.e. cam_b started recording 1.25 s (37.5 frames) BEFORE cam_a:
    # its frame 0 sits at -37.5 on cam_a's clock (rounded once, half to even -> -38)
    assert b["offset_f"] in (-37, -38)
    assert abs(b["offset_samples_16k"] + SYNC_DELAY_S * 16000) <= 3


def test_ingest_problem_flags(ingested):
    probs = {(p["id"], p["type"]) for p in _media(ingested)["problems"]}
    assert ("dark", "very_low_light") in probs
    assert ("dark", "missing_audio") in probs
    assert ("clipped", "clipped_audio") in probs
    assert ("shaky", "shaky") in probs
    assert not any(i == "cam_a" for i, _ in probs)


def test_ingest_is_cached(footage, ingested):
    t = time.time()
    r = run_script("ingest.py", str(footage), "--project", str(ingested), "--platform", "youtube_shorts")
    assert r.returncode == 0
    assert "probe " not in r.stderr and "proxy " not in r.stderr and "conform " not in r.stderr
    assert time.time() - t < 20


@pytest.fixture(scope="module")
def analysed(ingested):
    r = run_script("analyze.py", "--project", str(ingested), "--transcriber", "none", "--max-images", "2")
    assert r.returncode == 0, r.stderr
    return json.loads((ingested / "analysis.json").read_text(encoding="utf-8"))


def test_analyze_shot_boundary_on_the_frame(analysed):
    shots = analysed["files"]["cam_a"]["shots"]
    assert len(shots) == 2
    assert abs(shots[1]["s_f"] - 90) <= 1
    for s in shots:
        assert 1 <= len(s["keyframes"]) <= 3
        assert s["sharpness"] is not None and s["camera"]["type"]


def test_analyze_loudness_and_noise_floor(analysed):
    a = analysed["files"]["cam_a"]["audio"]
    assert a["loudness"]["integrated_lufs"] is not None
    assert a["loudness"]["true_peak_dbtp"] is not None
    assert a["noise_floor_db"] < -30


def test_analyze_music_beats(analysed):
    mus = analysed["files"]["music"]["music"]
    assert 115 <= mus["bpm"] <= 125 or 58 <= mus["bpm"] <= 62
    assert len(mus["beats_f"]) >= 10
    # beats every 0.5 s = every 15 frames at 30 fps
    gaps = [b - a for a, b in zip(mus["beats_f"], mus["beats_f"][1:])]
    assert sorted(gaps)[len(gaps) // 2] in (14, 15, 16, 30)


def test_analyze_perception_budget(analysed):
    p = analysed["perception"]
    assert p["count"] <= 2 and p["count"] >= 1
    assert p["shots_total"] >= 5


def test_analyze_member_points_at_anchor(analysed):
    t = analysed["files"]["cam_b"]["transcript"]
    assert t["ref"] == "cam_a" and t["offset_f"] in (-37, -38)


def test_broken_timestamps_use_real_cadence(broken_ts):
    from ingest import probe_file
    v = probe_file(broken_ts)["video"]
    assert v["vfr"] and v["timestamp_anomaly"]
    assert v["fps_native"] == "30"           # not the packets/duration average


def test_analyze_only_merges_and_is_cwd_independent(analysed, ingested, tmp_path, monkeypatch):
    import subprocess, sys, os
    from conftest import SCRIPTS
    before = set(analysed["files"])
    # run from a different working directory, re-analysing one file
    r = subprocess.run([sys.executable, str(SCRIPTS / "analyze.py"), "--project", str(ingested),
                        "--transcriber", "none", "--max-images", "2", "--only", "cam_a"],
                       cwd=tmp_path, capture_output=True, text=True, env={**os.environ})
    assert r.returncode == 0, r.stderr
    after = json.loads((ingested / "analysis.json").read_text(encoding="utf-8"))
    assert set(after["files"]) == before
    assert after["perception"]["count"] >= 1
    for img in after["perception"]["images"]:
        assert (ingested / img["path"]).exists()
