"""Camera log detection and conversion (lib/logcam.py, 2026-11-16). Synthetic media only, fast."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from lib import logcam as L

colour = pytest.importorskip("colour")
ROOT = Path(__file__).resolve().parents[1]

# Published 10-bit code values for 18 % grey (manufacturer tables): S-Log3 420, V-Log 433, LogC3 400.
SOURCED_GREY_CV = {"slog3": 420, "vlog": 433, "logc3": 400}


@pytest.mark.parametrize("prof,cv", SOURCED_GREY_CV.items())
def test_published_grey_code_value_decodes_to_18_percent(prof, cv):
    v = (cv - 64) / 876                                     # what ffmpeg hands us from a legal-range file
    lin = L.decode(np.array([[v, v, v]]), prof)
    assert abs(lin[0, 1] - 0.18) < 0.002


@pytest.mark.parametrize("prof", [k for k, p in L.PROFILES.items() if not p.get("lut") and k != "protune"])
def test_every_formula_profile_puts_grey_where_a_rec709_camera_does(prof):
    code = float(colour.log_encoding(0.18, L.PROFILES[prof]["curve"]))
    v = (code * 1023 - 64) / 876 if L.PROFILES[prof]["cv"] else code
    out = L.display_render(L.decode(np.array([[v, v, v]]), prof))
    assert np.allclose(out, 0.409, atol=0.003)


def test_display_render_is_monotonic_and_bounded():
    x = np.linspace(0, 20, 400)
    y = L.display_render(np.stack([x, x, x], -1))[:, 0]
    assert (np.diff(y) >= -1e-9).all() and y[0] == 0 and y.max() <= 1


def test_out_of_gamut_colour_is_pulled_in_not_clipped():
    out = L.display_render(np.array([[0.5, -0.1, 0.02]]))
    assert (out >= 0).all() and out[0, 0] > out[0, 1]


def test_sony_metadata_wins_and_rec709_metadata_means_not_log():
    blob = b'<Item name="CaptureGammaEquation" value="s-log3-cine"/><Item name="CaptureColorPrimaries" value="S-Gamut3.Cine"/>'
    assert L.metadata_profile(blob)[0] == "slog3"
    assert L.metadata_profile(blob.replace(b"S-Gamut3.Cine", b"S-Gamut3").replace(b"-cine", b""))[0] == "slog3_sg3"
    assert L.metadata_profile(b'<Item name="CaptureGammaEquation" value="rec709"/>') == (None, 'Sony CaptureGammaEquation="rec709"')
    assert L.metadata_profile(b"..V-Log..")[0] == "vlog" and L.metadata_profile(b"my vlog")[0] is None


def test_override_and_unknown_profile(tmp_path):
    f = tmp_path / "x.mp4"
    f.write_bytes(b"")
    assert L.detect(f, {}, override="vlog")["profile"] == "vlog"
    assert L.detect(f, {}, override="none")["profile"] is None
    with pytest.raises(ValueError):
        L.detect(f, {}, override="zlog")


def test_brand_needs_bt2020_for_apple():
    assert L.brand_of("com.apple.quicktime.make=Apple") == ("apple", "applelog")
    assert L.brand_of("encoder=Lavf") == (None, None)


def _clip(path: Path, lo: int, hi: int, sat: int) -> None:
    # a grey ramp between lo and hi with a little colour: flat when lo is high and hi is low
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "gradients=s=160x90:d=1:c0=0x%02x%02x%02x:c1=0x%02x%02x%02x"
                    % (lo, lo, lo + sat, hi, hi - sat, hi), "-frames:v", "12", "-pix_fmt", "yuv420p", str(path)], check=True)


def test_flat_picture_without_maker_is_reported_not_guessed(tmp_path):
    flat, normal = tmp_path / "flat.mp4", tmp_path / "normal.mp4"
    _clip(flat, 40, 170, 8)
    _clip(normal, 2, 250, 60)
    d = L.detect(flat, {"color": {}}, duration_s=0.4)
    assert d["profile"] is None and d["source"] == "flat_picture_unknown_maker"
    assert L.detect(normal, {"color": {}}, duration_s=0.4)["source"] is None


def test_cube_is_written_once_and_ffmpeg_accepts_it(tmp_path):
    cube = L.conversion_cube("slog3", False, tmp_path, size=17)
    assert cube.read_text().splitlines()[1] == "LUT_3D_SIZE 17" and L.conversion_cube("slog3", False, tmp_path, 17) == cube
    src = tmp_path / "in.mp4"
    _clip(src, 40, 170, 8)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", L.ffmpeg_filter(cube, "bt709", False),
                        "-frames:v", "1", str(tmp_path / "o.png")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_detect_log_cli_help_and_clear_failure(tmp_path):
    h = subprocess.run([sys.executable, str(ROOT / "scripts" / "detect_log.py"), "--help"], capture_output=True, text=True)
    assert h.returncode == 0 and "Rec.709" in h.stdout
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "detect_log.py"), "--media", str(tmp_path / "no.mp4")],
                       capture_output=True, text=True)
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["ok"] is False and "no such file" in out["error"]
