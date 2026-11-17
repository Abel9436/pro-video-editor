"""Effects milestone (2026-11-15): frame-by-frame reference watcher, SFX peak measurement and the
VideoEditingSFX matcher, line-icon conversion, and the design-block schema for the new caption
styles, matte and background spans. Synthetic media only; no network."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from conftest import ff, run_script


@pytest.mark.parametrize("script", ["deep_watch.py", "matte.py", "fetch_lineicons.py", "fetch_sfx.py", "fetch_fonts.py"])
def test_new_scripts_have_help(script):
    r = run_script(script, "--help")
    assert r.returncode == 0 and "usage" in r.stdout.lower(), r.stderr


def test_deep_watch_finds_cut_flash_bw_and_a_riser(tmp_path):
    # 3 s at 30 fps: colour bars, a 3-frame white flash at 1.0 s, a 0.6 s grey (B&W) beat, colour again;
    # audio: a 0.8 s rising noise swell ending in a click at 2.0 s.
    v = tmp_path / "v.mp4"
    ff("-f", "lavfi", "-i", "smptehdbars=s=320x568:r=30:d=1", "-f", "lavfi", "-i", "color=white:s=320x568:r=30:d=0.1",
       "-f", "lavfi", "-i", "testsrc2=s=320x568:r=30:d=0.6", "-f", "lavfi", "-i", "smptehdbars=s=320x568:r=30:d=1.3", "-filter_complex",
       "[2]hue=s=0[g];[0][1][g][3]concat=n=4:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(tmp_path / "pic.mp4"))
    sr = 22050
    t = np.arange(int(3 * sr)) / sr
    x = np.random.default_rng(1).normal(0, 1, t.size) * 0.002
    sw = (t > 1.2) & (t < 2.0)
    x[sw] += np.random.default_rng(2).normal(0, 1, sw.sum()) * np.linspace(0.001, 0.5, sw.sum())
    x[int(2.0 * sr):int(2.0 * sr) + 200] += 0.9
    sf.write(tmp_path / "a.wav", x.astype(np.float32), sr)
    ff("-i", str(tmp_path / "pic.mp4"), "-i", str(tmp_path / "a.wav"), "-c:v", "copy", "-c:a", "aac", "-shortest", str(v))
    out = tmp_path / "dw"
    r = run_script("deep_watch.py", str(v), "--out-dir", str(out), "--sheets", "full")
    assert r.returncode == 0, r.stderr
    d = json.loads((out / "events.json").read_text(encoding="utf-8"))
    kinds = {(e["kind"], e["f"]) for e in d["events"]}
    assert any(k == "flash" and 28 <= f <= 32 for k, f in kinds), kinds
    assert any(k == "cut" and 29 <= f <= 34 for k, f in kinds), kinds
    assert any(k == "bw_beat" for k, _ in kinds), kinds
    hit = [h for h in d["audio_hits"] if 1.9 <= h["t_s"] <= 2.1]
    assert hit and hit[0]["pre_rise_db"] > 10, d["audio_hits"]
    assert d["summary"]["frames"] >= 88 and list(out.glob("sheet_*.png"))


def test_sfx_peak_measure(tmp_path):
    import fetch_sfx
    sr = 16000
    x = np.zeros(sr, np.float32)
    x[int(0.6 * sr):int(0.6 * sr) + 400] = 0.8          # transient at 0.6 s
    x[int(0.3 * sr):int(0.6 * sr)] += np.linspace(0, 0.2, int(0.3 * sr)).astype(np.float32)
    f = tmp_path / "s.wav"
    sf.write(f, x, sr)
    m = fetch_sfx.measure(f)
    assert abs(m["peak_s"] - 0.6) < 0.02 and m["onset_s"] < m["peak_s"]


def test_ves_search_matches_whole_slug_words(monkeypatch):
    import fetch_sfx
    page = ''.join(f'<a href="/sfx/{s}">' for s in ("dramatic-buildup-1", "ui-sound", "pop-sound", "riser-2", "swooshes"))
    monkeypatch.setattr(fetch_sfx, "get", lambda url: page.encode())
    ids = [h["id"] for h in fetch_sfx.ves_search("ui pop")]
    assert "ves-dramatic-buildup-1" not in ids               # "ui" inside "buildup" must not match
    assert set(ids) == {"ves-ui-sound", "ves-pop-sound"}
    assert [h["id"] for h in fetch_sfx.ves_search("swoosh")] == ["ves-swooshes"]


def test_lineicon_elements_become_paths():
    import fetch_lineicons as L
    svg = ('<svg><rect width="20" height="14" x="2" y="3" rx="2" /><line x1="8" x2="16" y1="21" y2="21" />'
           '<circle cx="12" cy="12" r="3" /><polyline points="1,2 3,4" /><path d="M1 1h2" /></svg>')
    ps = L.to_paths(svg)
    assert len(ps) == 5 and ps[1] == "M8.0 21.0L16.0 21.0" and ps[4] == "M1 1h2"
    assert ps[0].startswith("M4.0 3.0") and ps[0].endswith("Z") and "a3.0 3.0" in ps[2]
    assert L.to_paths('<polyline points="7 10 12 15 17 10" />') == ["M7 10L12 15L17 10"]   # space-separated (Lucide download)
    assert ps[3] == "M1 2L3 4"


def test_design_schema_accepts_new_effects():
    from lib.edl import SCHEMA
    import jsonschema
    d = {"caption_style": "neon", "caption_size": 78, "matte": True, "bg": [{"s": 0, "e": 10, "color": "bw"}],
         "fx": [{"at": 5, "type": "leakdip"}], "overlays": [{"s": 0, "e": 9, "type": "Halo", "behind": True, "p": {}}]}
    jsonschema.validate(d, SCHEMA["properties"]["design"])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"caption_style": "comic"}, SCHEMA["properties"]["design"])


def test_master_limits_true_peak_after_loudnorm(tmp_path):
    # quiet speech-like noise plus loud SFX hits: loudnorm alone lets the hits through the ceiling
    from lib import mix
    sr = mix.SR
    rng = np.random.default_rng(3)
    x = rng.normal(0, 0.03, sr * 6).astype(np.float32)
    for t in (1.0, 3.0, 5.0):
        i = int(t * sr)
        x[i:i + 300] += np.hanning(300).astype(np.float32) * 0.98
    src, dst = tmp_path / "pre.wav", tmp_path / "master.wav"
    sf.write(src, np.stack([x, x], 1), sr)
    meas = mix.loudnorm_master(src, dst, -14.0, -2.0)
    assert meas["output_tp"] <= -1.9, meas


def test_caption_text_fixes_split_names_without_touching_timing():
    import render
    tw = [{"i": 54, "src": "a", "w": "the", "t_s": 0, "t_e": 4}, {"i": 55, "src": "a", "w": "Qur", "t_s": 5, "t_e": 8},
          {"i": 56, "src": "a", "w": "'an", "t_s": 8, "t_e": 10}, {"i": 57, "src": "a", "w": "Lee", "t_s": 10, "t_e": 14},
          {"i": 58, "src": "a", "w": "app", "t_s": 15, "t_e": 20}]
    out = render.caption_text(tw, {"55": "Quranly", "56": "", "a:57": ""})
    assert [w["w"] for w in out] == ["the", "Quranly", "app"]
    assert out[1]["t_s"] == 5 and out[1]["t_e"] == 14          # the name spans the dropped pieces
    assert render.caption_text(tw, {}) is tw
