"""The worked example stays importable and portable (offline, 2026-11-17)."""
from __future__ import annotations

import ast
from pathlib import Path

EX = Path(__file__).resolve().parents[1] / "examples"


def test_examples_parse_and_carry_no_machine_paths():
    files = list(EX.rglob("*.py"))
    assert files
    for f in files:
        src = f.read_text(encoding="utf-8")
        ast.parse(src)
        assert "C:/Users" not in src and "C:\\Users" not in src and "/home/" not in src, f


def test_every_reference_frame_is_indexed():
    d = EX.parent / "references" / "frames"
    readme = (d / "README.md").read_text(encoding="utf-8")
    for jpg in d.glob("*.jpg"):
        n = jpg.name.split("-")[0]
        assert f"| {n}" in readme or f", {n} " in readme, jpg.name
        assert jpg.stat().st_size < 400_000, jpg.name


def test_example_falls_back_to_a_sound_of_the_same_role():
    src = (EX / "snap" / "make_edl.py").read_text(encoding="utf-8")
    assert "def snd(" in src and "f = snd(f)" in src     # named Freesound ids differ per fetch
