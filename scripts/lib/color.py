"""Colour: correct, then match, then grade (references/craft-color.md).

Correction and matching become one per-event 1D LUT per channel, applied to frames in
render.py. The look is a 3D LUT (.cube) generated here from parameters (no third-party
LUTs ship with the skill), applied once at the final encode at a set strength.

Skin is the anchor: exposure is judged on the face when there is one, and the look keeps
skin hues close to the original (SKIN_PROTECT).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

FACE_L_TARGET = (45.0, 70.0)    # STARTING DEFAULT: face L* range (Lab, 0-100) treated as well exposed
SCENE_L_TARGET = (35.0, 60.0)   # STARTING DEFAULT: median L* range for shots without faces
MAX_GAMMA_STEP = 0.25           # correction limited to gamma 0.75-1.25: correction, not a look
MAX_WB_GAIN = 0.08              # white-balance channel gains limited to +-8 %
NEUTRAL_CHROMA = 6.0            # Lab chroma under this = near-neutral pixel used for white balance
MATCH_STRENGTH = 0.6            # move each shot 60 % of the way to its scene's median
SKIN_HUE_DEG = (10.0, 50.0)     # skin hue band in Lab hue angle (red-yellow); the "skin line"
SKIN_PROTECT = 0.6              # how much of the look's change is removed inside the skin band
LUT_SIZE = 33


def frame_stats(frames_bgr: list[np.ndarray], face_boxes: list[list[float] | None]) -> dict:
    """Lab statistics of a few frames: global, face region and near-neutral pixels."""
    import cv2
    Ls, As, Bs, fL, fA, fB, nA, nB = [], [], [], [], [], [], [], []
    for fr, box in zip(frames_bgr, face_boxes):
        small = cv2.resize(fr, (192, int(192 * fr.shape[0] / fr.shape[1])))
        lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
        L = lab[..., 0] / 2.55; a = lab[..., 1] - 128; b = lab[..., 2] - 128
        Ls.append(np.median(L)); As.append(a.mean()); Bs.append(b.mean())
        chroma = np.hypot(a, b)
        neutral = (chroma < NEUTRAL_CHROMA) & (L > 15) & (L < 90)
        if neutral.sum() > 50:
            nA.append(a[neutral].mean()); nB.append(b[neutral].mean())
        if box:
            h, w = L.shape
            x0, y0 = int(box[0] * w), int(box[1] * h)
            x1, y1 = int((box[0] + box[2]) * w), int((box[1] + box[3]) * h)
            # inner face (skip hair/background at the box edges)
            ix, iy = (x1 - x0) // 5, (y1 - y0) // 5
            roi = (slice(y0 + iy, max(y0 + iy + 1, y1 - iy)), slice(x0 + ix, max(x0 + ix + 1, x1 - ix)))
            if L[roi].size > 20:
                fL.append(np.median(L[roi])); fA.append(a[roi].mean()); fB.append(b[roi].mean())
    out = {"L": float(np.median(Ls)), "a": float(np.mean(As)), "b": float(np.mean(Bs))}
    if fL:
        out.update(face_L=float(np.median(fL)), face_a=float(np.mean(fA)), face_b=float(np.mean(fB)),
                   face_hue=float(np.degrees(np.arctan2(np.mean(fB), np.mean(fA)))))
    if nA:
        out.update(neutral_a=float(np.mean(nA)), neutral_b=float(np.mean(nB)))
    return out


def correction(stats: dict) -> dict:
    """Gamma and per-channel gains that bring the shot into range. Small by design."""
    gamma, why = 1.0, []
    if "face_L" in stats:
        lo, hi = FACE_L_TARGET
        L = stats["face_L"]
        if L < lo or L > hi:
            tgt = lo if L < lo else hi
            gamma = float(np.clip(np.log(max(tgt, 1) / 100) / np.log(max(L, 1) / 100), 1 - MAX_GAMMA_STEP, 1 + MAX_GAMMA_STEP))
            why.append(f"face L* {L:.0f} outside {lo:.0f}-{hi:.0f}")
    else:
        lo, hi = SCENE_L_TARGET
        L = stats["L"]
        if L < lo or L > hi:
            tgt = lo if L < lo else hi
            gamma = float(np.clip(np.log(tgt / 100) / np.log(max(L, 1) / 100), 1 - MAX_GAMMA_STEP, 1 + MAX_GAMMA_STEP))
            why.append(f"median L* {L:.0f} outside {lo:.0f}-{hi:.0f}")
    gains = [1.0, 1.0, 1.0]  # B, G, R
    if "neutral_a" in stats:
        # a*>0 = magenta, b*>0 = yellow on near-neutral pixels: a colour cast
        da, db = stats["neutral_a"], stats["neutral_b"]
        if abs(da) > 2 or abs(db) > 2:
            gains[0] = 1 + float(np.clip(db / 100, -MAX_WB_GAIN, MAX_WB_GAIN))         # yellow cast -> more blue
            gains[2] = 1 - float(np.clip(db / 100, -MAX_WB_GAIN, MAX_WB_GAIN)) / 2
            gains[1] = 1 + float(np.clip(da / 100, -MAX_WB_GAIN, MAX_WB_GAIN))         # magenta cast -> more green
            why.append(f"neutral cast a*={da:+.1f} b*={db:+.1f}")
    return {"gamma": round(gamma, 3), "gains_bgr": [round(g, 3) for g in gains], "why": why}


def match_to(stats: dict, scene: dict) -> list[float]:
    """Extra per-channel gains moving this shot toward its scene's median (shot matching)."""
    key = "face_L" if "face_L" in stats and "face_L" in scene else "L"
    if scene.get(key) is None or stats.get(key) is None:
        return [1.0, 1.0, 1.0]
    g = (scene[key] / max(stats[key], 1)) ** MATCH_STRENGTH
    g = float(np.clip(g, 0.9, 1.1))
    return [g, g, g]


def channel_luts(corr: dict, match_gains: list[float]) -> np.ndarray:
    """256x1x3 uint8 LUT for cv2.LUT on BGR frames."""
    x = np.arange(256, dtype=np.float32) / 255
    out = np.zeros((256, 1, 3), np.uint8)
    for c in range(3):
        y = np.power(np.clip(x * corr["gains_bgr"][c] * match_gains[c], 0, 1), corr["gamma"])
        out[:, 0, c] = np.clip(np.round(y * 255), 0, 255).astype(np.uint8)
    return out


# ----------------------------------------------------------------------------- looks
LOOKS = {
    # name: (contrast, saturation, warmth (+ = warmer), lift (black level), shadow tint (b*), highlight tint (b*))
    "clean_neutral": (1.06, 1.03, 0.0, 0.0, 0.0, 0.0),
    "clean_warm": (1.05, 1.05, 0.03, 0.01, 0.0, 0.02),
    "warm_soft": (0.96, 1.02, 0.05, 0.03, 0.0, 0.03),
    "muted_doc": (1.04, 0.82, 0.0, 0.02, -0.02, 0.01),
    "punchy": (1.14, 1.18, 0.01, 0.0, 0.0, 0.0),
    "teal_orange": (1.08, 1.08, 0.0, 0.0, -0.05, 0.05),
    "moody_night": (1.10, 0.95, -0.02, 0.0, -0.03, 0.02),
}


def _look_rgb(rgb: np.ndarray, p) -> np.ndarray:
    con, sat, warm, lift, sh_tint, hi_tint = p
    x = np.clip(rgb, 0, 1)
    luma = x @ np.array([0.2126, 0.7152, 0.0722])
    # S-curve contrast around mid grey
    y = 0.5 + (x - 0.5) * con
    y = lift + y * (1 - lift)
    l2 = y @ np.array([0.2126, 0.7152, 0.0722])
    y = l2[..., None] + (y - l2[..., None]) * sat
    y[..., 0] += warm; y[..., 2] -= warm
    sh = np.clip(1 - luma * 2, 0, 1)[..., None]; hi = np.clip(luma * 2 - 1, 0, 1)[..., None]
    y += sh * np.array([sh_tint, 0, -sh_tint])           # negative tint = teal (blue-green) shadows
    y += hi * np.array([hi_tint, hi_tint * 0.4, -hi_tint])
    return np.clip(y, 0, 1)


def _skin_weight(rgb: np.ndarray) -> np.ndarray:
    """1 inside the skin hue band (moderate chroma, mid luma), 0 outside, soft edges."""
    import cv2
    lab = cv2.cvtColor((rgb.reshape(-1, 1, 3) * 255).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(rgb.shape).astype(np.float32)
    a = lab[..., 1] - 128; b = lab[..., 2] - 128; L = lab[..., 0] / 2.55
    hue = np.degrees(np.arctan2(b, a)); chroma = np.hypot(a, b)
    lo, hi = SKIN_HUE_DEG
    w_h = np.clip(1 - np.maximum(lo - hue, hue - hi) / 10, 0, 1)
    w_c = np.clip((chroma - 5) / 10, 0, 1) * np.clip((60 - chroma) / 20, 0, 1)
    w_l = np.clip((L - 20) / 15, 0, 1) * np.clip((95 - L) / 15, 0, 1)
    return w_h * w_c * w_l


KEYS = ("contrast", "saturation", "warmth", "lift", "shadow_tint", "highlight_tint")


def _hue_bands(rgb: np.ndarray, out: np.ndarray, bands: list[dict]) -> np.ndarray:
    """Per-hue saturation / hue shift (Lumetri's Hue vs Sat / Hue vs Hue), measured on the INPUT hue.
    band: {"hue": centre deg (HSV: 0 red, 60 yellow, 120 green, 240 blue), "width": deg, "sat": x, "shift": deg}."""
    import cv2
    hsv_in = cv2.cvtColor(rgb.reshape(-1, 1, 3).astype(np.float32), cv2.COLOR_RGB2HSV).reshape(rgb.shape)
    hsv = cv2.cvtColor(out.reshape(-1, 1, 3).astype(np.float32), cv2.COLOR_RGB2HSV).reshape(out.shape)
    for b in bands:
        d = np.abs((hsv_in[..., 0] - b["hue"] + 180) % 360 - 180)
        w = np.clip(1 - d / max(1.0, b.get("width", 30)), 0, 1) * np.clip(hsv_in[..., 1] * 4, 0, 1)
        hsv[..., 1] = np.clip(hsv[..., 1] * (1 + (b.get("sat", 1.0) - 1) * w), 0, 1)
        hsv[..., 0] = (hsv[..., 0] + b.get("shift", 0.0) * w) % 360
    return np.clip(cv2.cvtColor(hsv.reshape(-1, 1, 3), cv2.COLOR_HSV2RGB).reshape(out.shape), 0, 1)


def write_cube(name, path: Path) -> Path:
    """name: a LOOKS key, or a custom grade dict {contrast, saturation, warmth, lift, shadow_tint,
    highlight_tint, hues: [{hue, width, sat, shift}], skin_protect} built for one video."""
    if isinstance(name, dict):
        base = LOOKS[name.get("base", "clean_neutral")]
        params = tuple(name.get(k, base[i]) for i, k in enumerate(KEYS))
        hues, protect, title = name.get("hues", []), name.get("skin_protect", SKIN_PROTECT), name.get("name", "custom")
    else:
        if name not in LOOKS:
            raise ValueError(f"unknown look '{name}' (have: {', '.join(LOOKS)})")
        params, hues, protect, title = LOOKS[name], [], SKIN_PROTECT, name
    n = LUT_SIZE
    g = np.linspace(0, 1, n)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")        # .cube order: red changes fastest
    rgb = np.stack([r, gg, b], -1).reshape(-1, 3)
    out = _look_rgb(rgb, params)
    if hues:
        out = _hue_bands(rgb, out, hues)
    w = _skin_weight(rgb)[..., None] * protect
    out = out * (1 - w) + rgb * w
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="ascii") as f:
        f.write(f'TITLE "pve {title}"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        for row in out:
            f.write(f"{row[0]:.5f} {row[1]:.5f} {row[2]:.5f}\n")
    return path


def look_path(look: str | None, skill_root: Path) -> Path | None:
    """A look is a generated name ('clean_warm'), a custom grade dict (see write_cube), or a .cube path."""
    if not look:
        return None
    if isinstance(look, dict):
        import hashlib
        import json as _json
        h = hashlib.sha1(_json.dumps(look, sort_keys=True).encode()).hexdigest()[:10]
        dst = skill_root / "assets" / "luts" / "generated" / f"custom_{h}.cube"
        if not dst.exists():
            write_cube(look, dst)
        return dst
    p = Path(look)
    if p.suffix == ".cube":
        cand = p if p.is_absolute() else skill_root / "assets" / p if not (skill_root / p).exists() else skill_root / p
        if not cand.exists():
            raise FileNotFoundError(f"LUT {look} not found")
        return cand
    dst = skill_root / "assets" / "luts" / "generated" / f"{look}.cube"
    if not dst.exists():
        write_cube(look, dst)
    return dst
