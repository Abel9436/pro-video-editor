"""Camera log footage: detect the profile, then convert it to Rec.709 before anything else.

Order (references/craft-log.md): colour space transform first (log decode -> scene linear ->
Rec.709 primaries -> display rendering), then the normal correction, skin protection and look
in lib/color.py. Grading log as if it were badly exposed Rec.709 is the mistake this avoids.

The decode curves and camera gamuts are the manufacturers' published formulas as implemented
by colour-science (BSD-3). Profiles with no published formula (DJI D-Log M, Samsung Log,
GoPro GP-Log, Insta360 I-Log) need the maker's own LUT (`--log-lut`); without one they get an
approximate conversion measured from the clip, and ingest flags it.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import numpy as np

# id: (name, colour-science curve, formula in 10-bit code values, gamut, needs maker LUT)
# "cv" curves are written in full-scale code values (S-Log3 black = 95/1023), so the file's
# code values go in directly; "signal" curves are a 0-1 signal the camera maps onto the
# container's range (legal range for tv-tagged files).
PROFILES: dict[str, dict] = {
    "slog3":      {"name": "Sony S-Log3 / S-Gamut3.Cine", "curve": "S-Log3", "cv": True, "gamut": "S-Gamut3.Cine"},
    "slog3_sg3":  {"name": "Sony S-Log3 / S-Gamut3", "curve": "S-Log3", "cv": True, "gamut": "S-Gamut3"},
    "slog2":      {"name": "Sony S-Log2 / S-Gamut", "curve": "S-Log2", "cv": True, "gamut": "S-Gamut"},
    "vlog":       {"name": "Panasonic V-Log / V-Gamut", "curve": "V-Log", "cv": True, "gamut": "V-Gamut"},
    "clog3":      {"name": "Canon Log 3 / Cinema Gamut", "curve": "Canon Log 3", "cv": True, "gamut": "Cinema Gamut"},
    "clog2":      {"name": "Canon Log 2 / Cinema Gamut", "curve": "Canon Log 2", "cv": True, "gamut": "Cinema Gamut"},
    "clog":       {"name": "Canon Log / Cinema Gamut", "curve": "Canon Log", "cv": True, "gamut": "Cinema Gamut"},
    "flog":       {"name": "Fujifilm F-Log / F-Gamut", "curve": "F-Log", "cv": True, "gamut": "F-Gamut"},
    "flog2":      {"name": "Fujifilm F-Log2 / F-Gamut", "curve": "F-Log2", "cv": True, "gamut": "F-Gamut"},
    "nlog":       {"name": "Nikon N-Log / N-Gamut", "curve": "N-Log", "cv": True, "gamut": "N-Gamut"},
    "llog":       {"name": "Leica L-Log / BT.2020", "curve": "L-Log", "cv": True, "gamut": "ITU-R BT.2020"},
    "logc3":      {"name": "ARRI LogC3 / AWG3", "curve": "ARRI LogC3", "cv": True, "gamut": "ARRI Wide Gamut 3"},
    "logc4":      {"name": "ARRI LogC4 / AWG4", "curve": "ARRI LogC4", "cv": True, "gamut": "ARRI Wide Gamut 4"},
    "dlog":       {"name": "DJI D-Log / D-Gamut", "curve": "D-Log", "cv": True, "gamut": "DJI D-Gamut"},
    "applelog":   {"name": "Apple Log / BT.2020", "curve": "Apple Log Profile", "cv": False, "gamut": "ITU-R BT.2020"},
    "protune":    {"name": "GoPro Protune Flat", "curve": "Protune", "cv": False, "gamut": "ITU-R BT.709"},
    "dlogm":      {"name": "DJI D-Log M", "lut": True},
    "samsunglog": {"name": "Samsung Log", "lut": True},
    "gplog":      {"name": "GoPro GP-Log", "lut": True},
    "ilog":       {"name": "Insta360 I-Log", "lut": True},
}

# Text markers cameras write into the file (Sony's NonRealTimeMeta XML, maker tags, QuickTime
# keys). Checked most specific first. A marker is evidence, not proof: detect() reports it.
SONY_GAMMA = re.compile(rb'CaptureGammaEquation"\s+value="([^"]+)"', re.I)
SONY_PRIMARIES = re.compile(rb'CaptureColorPrimaries"\s+value="([^"]+)"', re.I)
MARKERS: list[tuple[str, re.Pattern]] = [
    ("applelog", re.compile(rb"Apple ?Log", re.I)),
    ("dlogm", re.compile(rb"D-?Log[ -]?M\b", re.I)),
    ("dlog", re.compile(rb"\bD-Log\b")),
    ("clog3", re.compile(rb"Canon ?Log ?3|\bC-?Log ?3\b", re.I)),
    ("clog2", re.compile(rb"Canon ?Log ?2|\bC-?Log ?2\b", re.I)),
    ("flog2", re.compile(rb"\bF-Log ?2\b", re.I)),
    ("flog", re.compile(rb"\bF-Log\b", re.I)),
    ("nlog", re.compile(rb"\bN-Log\b", re.I)),
    ("vlog", re.compile(rb"\bV-Log\b")),
    ("llog", re.compile(rb"\bL-Log\b")),
    ("logc4", re.compile(rb"\bLog ?C4\b", re.I)),
    ("logc3", re.compile(rb"\bLog ?C3?\b")),
    ("samsunglog", re.compile(rb"Samsung ?Log", re.I)),
    ("gplog", re.compile(rb"\bGP-?Log\b", re.I)),
    ("ilog", re.compile(rb"\bI-Log\b", re.I)),
]
SCAN_BYTES = 8 << 20            # head and tail of the file: where MP4/MOV keep moov, udta and XML

# Maker -> the log that maker's cameras record, used only when the picture is also flat.
BRANDS: list[tuple[str, re.Pattern, str]] = [
    ("apple", re.compile(r"\bapple\b|iphone", re.I), "applelog"),
    ("sony", re.compile(r"\bsony\b|manufacturer=\"sony", re.I), "slog3"),
    ("panasonic", re.compile(r"panasonic|lumix", re.I), "vlog"),
    ("canon", re.compile(r"\bcanon\b", re.I), "clog3"),
    ("fujifilm", re.compile(r"fujifilm", re.I), "flog2"),
    ("nikon", re.compile(r"\bnikon\b", re.I), "nlog"),
    ("dji", re.compile(r"\bdji\b", re.I), "dlogm"),
    ("samsung", re.compile(r"samsung", re.I), "samsunglog"),
    ("gopro", re.compile(r"gopro", re.I), "gplog"),
    ("insta360", re.compile(r"insta360", re.I), "ilog"),
    ("leica", re.compile(r"\bleica\b", re.I), "llog"),
]

# Flat-picture test on the decoded (ffmpeg-normalised) luma of a few frames.
FLAT_BLACK = 0.04     # 0.5th-percentile luma above this = lifted blacks (real Samsung Log clip: 0.050)
FLAT_WHITE = 0.85     # 99.5th-percentile luma below this = no real whites (real Samsung Log clip with sky: 0.801)
FLAT_SAT = 0.12       # mean (max-min) chroma below this (Samsung Log 0.081; Rec.709 sources 0.157, 0.228)
SAMPLE_FRAMES = 6

# Display rendering: scene linear Rec.709 -> display Rec.709 (BT.1886, gamma 2.4).
GREY_SCENE = 0.18
GREY_DISPLAY = (0.18 ** 0.45 * 1.099 - 0.099) ** 2.4   # where a BT.709 camera puts 18 % grey on a BT.1886 display
CONTRAST = 1.35       # STARTING DEFAULT: tonescale exponent; puts diffuse white (1.0) near 0.80 code
PEAK_SCENE = 10.0     # STARTING DEFAULT: scene-linear value that reaches display white
PATH_TO_WHITE = 0.6   # STARTING DEFAULT: how far the brightest colours desaturate toward white
LUT_SIZE = 65         # 65-point cube: log spreads stops evenly, so this samples every stop finely

# Approximate conversion for LUT-only profiles without the maker's LUT.
APPROX_WHITE = 0.92   # STARTING DEFAULT: display value the clip's 99.5th percentile is lifted to
APPROX_SAT = 1.30     # STARTING DEFAULT: saturation restored after levels
APPROX_S = 0.30       # STARTING DEFAULT: S-curve strength


def _colour():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import colour
    return colour


# ---------------------------------------------------------------- conversion

def to_signal(v: np.ndarray, profile: str, full_range: bool) -> np.ndarray:
    """ffmpeg's normalised RGB (legal range already expanded for tv files) -> the curve's input."""
    if PROFILES[profile].get("cv") and not full_range:
        return (v * 876.0 + 64.0) / 1023.0
    return v


def decode(v: np.ndarray, profile: str, full_range: bool = False) -> np.ndarray:
    """Log RGB -> scene-linear Rec.709 RGB (18 % grey = 0.18)."""
    c, p = _colour(), PROFILES[profile]
    lin = np.asarray(c.log_decoding(to_signal(v, profile, full_range), p["curve"]), dtype=np.float64)
    if p["gamut"] != "ITU-R BT.709":
        lin = c.RGB_to_RGB(lin, c.RGB_COLOURSPACES[p["gamut"]], c.RGB_COLOURSPACES["ITU-R BT.709"],
                           chromatic_adaptation_transform=None)
    return lin


def tonescale(x: np.ndarray) -> np.ndarray:
    """Michaelis-Menten curve through (GREY_SCENE, GREY_DISPLAY) and (PEAK_SCENE, 1.0)."""
    a, b = GREY_SCENE ** CONTRAST, PEAK_SCENE ** CONTRAST
    k = a * b * (1 - GREY_DISPLAY) / (GREY_DISPLAY * b - a)
    xc = np.maximum(x, 0.0) ** CONTRAST
    return (b + k) / b * xc / (xc + k)


def display_render(lin: np.ndarray) -> np.ndarray:
    """Scene-linear Rec.709 -> Rec.709 code values. Hue-preserving tonescale on max(RGB), out-of-gamut
    colours pulled toward their own luminance instead of clipped, brightest colours eased to white."""
    lum = np.maximum(lin @ np.array([0.2126, 0.7152, 0.0722]), 0.0)[..., None]
    lo = lin.min(axis=-1, keepdims=True)
    k = np.where(lo < 0, lum / np.maximum(lum - lo, 1e-9), 1.0)       # bring the lowest channel to 0
    rgb = lum + (lin - lum) * k
    n = rgb.max(axis=-1, keepdims=True)
    y = tonescale(n)
    rgb = rgb * np.where(n > 1e-9, y / np.maximum(n, 1e-9), 0.0)
    w = PATH_TO_WHITE * np.clip((y - 0.7) / 0.3, 0, 1) ** 2
    rgb = rgb + (y - rgb) * w
    return np.clip(rgb, 0, 1) ** (1 / 2.4)


def grid(size: int = LUT_SIZE) -> np.ndarray:
    r = np.linspace(0, 1, size)
    b, g, rr = np.meshgrid(r, r, r, indexing="ij")          # .cube order: red changes fastest
    return np.stack([rr, g, b], axis=-1).reshape(-1, 3)


def _write_cube(path: Path, title: str, rgb: np.ndarray, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {size}"]
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in np.clip(rgb, 0, 1)]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def conversion_cube(profile: str, full_range: bool, out_dir: Path, size: int = LUT_SIZE) -> Path:
    """Bake decode + display rendering into one .cube applied to the log file's RGB."""
    key = f"{profile}|{full_range}|{size}|{CONTRAST}|{PEAK_SCENE}|{PATH_TO_WHITE}|v1"
    path = out_dir / f"log_{profile}_{'full' if full_range else 'tv'}_{hashlib.sha1(key.encode()).hexdigest()[:8]}.cube"
    if path.exists():
        return path
    return _write_cube(path, f"pve {profile} to Rec709", display_render(decode(grid(size), profile, full_range)), size)


def approx_cube(stats: dict, out_dir: Path, size: int = 33) -> Path:
    """No formula and no maker LUT: levels from the clip's own black and white points, a soft S-curve
    and restored saturation. Approximate by design; ingest flags it."""
    lo, hi = stats["p_low"], stats["p_high"]
    key = f"approx|{lo:.4f}|{hi:.4f}|{APPROX_WHITE}|{APPROX_SAT}"
    path = out_dir / f"log_approx_{hashlib.sha1(key.encode()).hexdigest()[:8]}.cube"
    if path.exists():
        return path
    v = np.clip((grid(size) - lo) / max(hi - lo, 1e-3), 0, 1.2) * APPROX_WHITE
    v = np.clip(v, 0, 1)
    v = v * (1 - APPROX_S) + APPROX_S * (3 * v ** 2 - 2 * v ** 3)     # gentle S-curve (smoothstep blend)
    lum = (v @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
    return _write_cube(path, "pve approximate log", lum + (v - lum) * APPROX_SAT, size)


def ffmpeg_filter(cube: Path, matrix: str | None, full_range: bool) -> str:
    """yuv -> RGB float (no range or transfer change), the cube, then Rec.709 limited-range yuv."""
    m = {"bt2020nc": "2020_ncl", "bt2020c": "2020_cl", "bt470bg": "470bg", "smpte170m": "170m"}.get(matrix or "", "709")
    f = cube.resolve().as_posix().replace(":", r"\:")
    return (f"zscale=matrixin={m}:rangein={'full' if full_range else 'limited'}:range=full,format=gbrpf32le,"
            f"lut3d=file='{f}':interp=tetrahedral,"
            f"zscale=matrix=709:rangein=full:range=limited,format=yuv420p")


# ---------------------------------------------------------------- detection

def _read_ends(path: Path) -> bytes:
    size = path.stat().st_size
    with open(path, "rb") as fh:
        if size <= 2 * SCAN_BYTES:
            return fh.read()
        head = fh.read(SCAN_BYTES)
        fh.seek(size - SCAN_BYTES)
        return head + fh.read()


def metadata_profile(blob: bytes) -> tuple[str | None, str | None]:
    """(profile, evidence) from text the camera wrote into the file."""
    g = SONY_GAMMA.search(blob)
    if g:
        gamma = g.group(1).decode("latin-1").lower()
        prim = SONY_PRIMARIES.search(blob)
        prim_s = prim.group(1).decode("latin-1") if prim else ""
        ev = f'Sony CaptureGammaEquation="{gamma}"' + (f', CaptureColorPrimaries="{prim_s}"' if prim_s else "")
        if gamma.startswith("s-log3"):
            cine = "cine" in gamma or "cine" in prim_s.lower() or not prim_s
            return ("slog3" if cine else "slog3_sg3"), ev
        if gamma.startswith("s-log2"):
            return "slog2", ev
        return None, ev                                   # rec709, hlg, s-cinetone: not log
    for pid, rx in MARKERS:
        m = rx.search(blob)
        if m:
            return pid, f'marker "{m.group(0).decode("latin-1")}" in the file'
    return None, None


def brand_of(tags_text: str) -> tuple[str | None, str | None]:
    for name, rx, profile in BRANDS:
        if rx.search(tags_text):
            return name, profile
    return None, None


def pixel_stats(path: Path, duration_s: float) -> dict:
    """Luma percentiles and mean chroma of a few small frames, in ffmpeg's normalised RGB."""
    w, h, ys, sats = 96, 96, [], []
    for i in range(SAMPLE_FRAMES):
        t = duration_s * (i + 0.5) / SAMPLE_FRAMES if duration_s > 0 else 0
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                            "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True)
        if len(r.stdout) != w * h * 3:
            continue
        px = np.frombuffer(r.stdout, np.uint8).reshape(-1, 3).astype(np.float32) / 255
        ys.append(px @ np.array([0.2126, 0.7152, 0.0722], np.float32))
        sats.append(px.max(axis=1) - px.min(axis=1))
    if not ys:
        return {}
    y, s = np.concatenate(ys), np.concatenate(sats)
    st = {"p_low": float(np.percentile(y, 0.5)), "p_high": float(np.percentile(y, 99.5)), "sat": float(s.mean())}
    st["flat"] = st["p_low"] > FLAT_BLACK and st["p_high"] < FLAT_WHITE and st["sat"] < FLAT_SAT
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items()}


def detect(path: Path, video: dict, tags_text: str = "", override: str | None = None,
           duration_s: float = 0.0) -> dict:
    """Which log profile, if any. Order: user override, the camera's own metadata, then maker + flat
    picture. A flat picture from an unknown maker is reported, not guessed."""
    out: dict = {"profile": None, "source": None, "evidence": None}
    if override and override != "auto":
        if override == "none":
            return {**out, "source": "override"}
        if override not in PROFILES:
            raise ValueError(f"unknown log profile '{override}' (known: {', '.join(PROFILES)})")
        return {**out, "profile": override, "source": "override", "evidence": "--log"}
    if (video or {}).get("hdr"):
        return {**out, "evidence": f"{video['hdr'].upper()} HDR, handled by tone mapping"}
    prof, ev = metadata_profile(_read_ends(path))
    if prof:
        return {**out, "profile": prof, "source": "metadata", "evidence": ev}
    if ev:                                                 # metadata says a non-log gamma
        return {**out, "source": "metadata", "evidence": ev}
    stats = pixel_stats(path, duration_s)
    out["stats"] = stats
    if not stats.get("flat"):
        return out
    brand, bprof = brand_of(tags_text)
    prim = ((video or {}).get("color") or {}).get("primaries")
    if brand == "apple" and prim != "bt2020":
        bprof = None                                       # iPhone SDR is bt709; Apple Log is tagged bt2020
    if bprof:
        return {**out, "profile": bprof, "source": "maker_and_flat_picture",
                "evidence": f"maker {brand}, flat picture (blacks {stats['p_low']}, whites {stats['p_high']}, "
                            f"saturation {stats['sat']})"}
    return {**out, "source": "flat_picture_unknown_maker",
            "evidence": f"flat picture but no maker in the metadata (blacks {stats['p_low']}, "
                        f"whites {stats['p_high']}); pass --log <profile>"}
