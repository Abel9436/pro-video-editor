"""Sound-spacing restraint checks and the local SFX library search (scripts/find_sfx.py).
Offline and synthetic, 2026-11-19."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lib import restraint

ROOT = Path(__file__).resolve().parents[1]


def _edl(sfx_frames, assets=None):
    assets = assets or [f"file:sfx/s{i}.wav" for i in range(len(sfx_frames))]
    return {"project": {"fps": 30}, "tracks": {"video": [{"id": "v1", "in_f": 0, "out_f": 900, "at_f": 0}],
            "sfx": [{"asset": a, "at_f": f, "reason": "x"} for f, a in zip(sfx_frames, assets)]}, "design": {}}


def _got(edl):
    return {c["id"]: c for c in restraint.audit(edl)}


def test_near_miss_sounds_warn_but_a_same_frame_stack_passes():
    assert _got(_edl([30, 33]))["restraint_sfx_gap"]["status"] == "warn"        # 0.1 s apart: mud
    g = _got(_edl([30, 30, 31, 90]))["restraint_sfx_gap"]                       # low/mid/high stack, then a gap
    assert g["status"] == "pass" and "stack 3" in g["detail"]
    assert _got(_edl([30, 30, 30, 30]))["restraint_sfx_gap"]["status"] == "warn"  # a stack of 4 is a wall


def test_one_file_everywhere_warns():
    same = ["file:sfx/whoosh.wav"] * 4
    assert _got(_edl([0, 60, 120, 180], same))["restraint_sfx_repeat"]["status"] == "warn"
    assert _got(_edl([0, 60, 120], same[:3]))["restraint_sfx_repeat"]["status"] == "pass"


def _lib(tmp: Path) -> Path:
    kit = tmp / "sfx-kit"
    (kit / "sounds" / "impacts").mkdir(parents=True)
    (kit / "sounds" / "impacts" / "impact-metal.wav").write_bytes(b"RIFF0000WAVE")
    (kit / "sounds.json").write_text(json.dumps({"sounds": [{
        "id": "impact-metal", "name": "Metal clang", "category": "impacts", "file": "sounds/impacts/impact-metal.wav",
        "description": "A steel clang", "use_for": ["heavy landing"], "avoid_for": [], "tags": ["metal"],
        "duration": 1.2, "sync": {"at": 0.03, "meets": "instant"}}]}), encoding="utf-8")
    sc = tmp / "soundcn" / "assets"
    (sc / "kenney_impact-sounds").mkdir(parents=True)
    (sc / "kenney_impact-sounds" / "impactMetal_heavy_000.ogg").write_bytes(b"OggS")
    (sc / "wow").mkdir()
    (sc / "wow" / "metal_clang.ogg").write_bytes(b"OggS")                      # (c) Blizzard: must never be indexed
    return tmp


def _run(*a):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "find_sfx.py"), *a], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, json.loads(r.stdout)


def test_index_excludes_the_blizzard_pack_and_search_ranks_by_meaning(tmp_path):
    lib = _lib(tmp_path / "lib")
    code, out = _run("index", "--lib", str(lib))
    assert code == 0 and out["by_library"] == {"sfx-kit": 1, "soundcn": 1}
    rows = json.loads((lib / "INDEX.json").read_text(encoding="utf-8"))
    assert not any("wow" in r["file"] for r in rows)
    code, out = _run("search", "--lib", str(lib), "metal clang")
    assert out["results"][0]["id"] == "sfx-kit:impact-metal" and out["results"][0]["sync_s"] == 0.03


def test_get_copies_with_licence_and_sync(tmp_path):
    lib, proj = _lib(tmp_path / "lib"), tmp_path / "P"
    _run("index", "--lib", str(lib))
    code, out = _run("get", "--lib", str(lib), "--project", str(proj), "sfx-kit:impact-metal")
    assert code == 0 and out["edl"][0] == {"asset": "file:sfx/sfx-kit_impact-metal.wav", "sync_s": 0.03}
    assert (proj / "sfx" / "sfx-kit_impact-metal.wav").exists()
    lic = json.loads((proj / "licenses.json").read_text(encoding="utf-8"))
    assert lic["assets"][0]["license"] == "CC0-1.0"
    code, out = _run("get", "--lib", str(lib), "--project", str(proj), "sfx-kit:nope")
    assert code == 1 and out["ok"] is False
