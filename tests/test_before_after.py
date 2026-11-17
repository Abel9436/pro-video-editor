"""before_after.py geometry and timeline lanes (offline, synthetic, 2026-11-17)."""
from __future__ import annotations

import before_after as BA


def test_mask_is_tilted_quad():
    m = BA.card_mask(BA.BEFORE)
    w, h = m.size
    assert m.getpixel((w // 2, h // 2)) == 255
    assert m.getpixel((w - 2, 3)) == 0              # right edge is shorter: its top corner is outside the card


def test_lanes_never_overlap():
    rows = BA.lanes([(0, 10, "a"), (5, 15, "b"), (10, 20, "c"), (12, 13, "d")])
    for r in rows:
        assert all(a[1] <= b[0] for a, b in zip(r, r[1:]))
    assert sum(len(r) for r in rows) == 4


def test_perspective_arg_has_eight_numbers():
    arg = BA.persp_arg(BA.TL)
    assert arg.endswith("sense=destination") and len(arg.split(":")) == 9
