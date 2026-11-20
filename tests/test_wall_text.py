"""wall_text.py: planar tracking and the validity window (2026-11-20). Synthetic frames, no video files."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import wall_text as W  # noqa: E402


def _frames(n=12, w=320, h=240, dx=3):
    rng = np.random.default_rng(7)
    tex = (rng.random((h, w + n * dx + 10)) * 255).astype(np.uint8)
    import cv2
    tex = cv2.GaussianBlur(tex, (5, 5), 1.2)
    return np.stack([tex[:, i * dx:i * dx + w] for i in range(n)])          # the scene slides left dx px a frame


def test_track_follows_a_sliding_wall():
    g = _frames()
    quad = np.float32([[100, 80], [220, 80], [220, 160], [100, 160]])
    corners, st = W.track(g, None, 0, quad)
    shift = corners[-1] - corners[0]
    assert np.allclose(shift[:, 0], -3 * (len(g) - 1), atol=1.5) and np.allclose(shift[:, 1], 0, atol=1.5)
    assert st["fallback_share"] == 0 and st["median_points"] >= 10


def test_track_from_a_middle_ref_runs_both_ways():
    g = _frames()
    quad = np.float32([[100, 80], [220, 80], [220, 160], [100, 160]])
    corners, _ = W.track(g, None, 6, quad)
    assert np.allclose(corners[6], quad, atol=0.5)
    assert corners[0][0, 0] > corners[6][0, 0] > corners[-1][0, 0]


def test_valid_range_stops_where_the_quad_blows_up():
    q = np.float32([[10, 10], [60, 10], [60, 40], [10, 40]])
    good = [q + [i, 0] for i in range(6)]
    bad = np.float32([[10, 10], [60, 10], [10, 40], [60, 40]])            # self-crossing: not convex
    corners = np.stack(good[:3] + [bad] + good[3:])
    assert W.valid_range(corners, 1, 200, 200) == (0, 2)


def test_layout_fits_width_and_render_reveals_letters(tmp_path):
    item = {"s": 0, "e": 2, "lines": [{"t": "WALL", "font": "f.ttf", "h": 1.0}], "in": 0.0, "dur": 0.6}
    fonts = Path("C:/Windows/Fonts") if Path("C:/Windows/Fonts/arial.ttf").exists() else None
    if not fonts:
        import pytest
        pytest.skip("no system TTF to lay out with")
    item["lines"][0]["font"] = "arial.ttf"
    g = W.layout(item, fonts, 800, 200)
    assert len(g) == 4 and max(x for _, x, *_ in g) < 800
    early = np.array(W.render_text(g, 800, 200, 0.0, item))[..., 3].sum()
    late = np.array(W.render_text(g, 800, 200, 1.0, item))[..., 3].sum()
    assert late > early
