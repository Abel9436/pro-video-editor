"""Rational frame time. Every time value the skill stores is an integer frame
count at the timeline rate. Seconds exist only at the edges (decoder output,
human-readable timecode) and are converted here, with exact Fractions, so no
float drift accumulates across a long timeline.
"""
from __future__ import annotations

from fractions import Fraction

# Broadcast and camera rates the skill conforms to. NTSC rates are exact fractions.
STANDARD_RATES: tuple[Fraction, ...] = (
    Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001), Fraction(30),
    Fraction(48), Fraction(50), Fraction(60000, 1001), Fraction(60), Fraction(120),
)


def parse_rate(value: str | int | float | Fraction | None) -> Fraction | None:
    """Parse ffprobe-style '30000/1001', '30', 29.97 or a Fraction. 0/0 -> None."""
    if value is None:
        return None
    if isinstance(value, Fraction):
        return value if value > 0 else None
    if isinstance(value, (int, float)):
        return Fraction(value).limit_denominator(1001) if value > 0 else None
    s = str(value).strip()
    if "/" in s:
        num, den = s.split("/", 1)
        if int(den) == 0 or int(num) == 0:
            return None
        return Fraction(int(num), int(den))
    f = float(s)
    return Fraction(f).limit_denominator(1001) if f > 0 else None


def nearest_standard(rate: Fraction) -> Fraction:
    return min(STANDARD_RATES, key=lambda r: abs(float(r) - float(rate)))


def rate_str(rate: Fraction) -> str:
    return f"{rate.numerator}/{rate.denominator}" if rate.denominator != 1 else str(rate.numerator)


def sec_to_frames(seconds: float | Fraction, fps: Fraction) -> int:
    """Nearest frame (round half to even) for a time in seconds."""
    return round(Fraction(seconds).limit_denominator(10**9) * fps) if not isinstance(seconds, Fraction) \
        else round(seconds * fps)


def frames_to_sec(frames: int, fps: Fraction) -> Fraction:
    return Fraction(frames) / fps


def convert_frames(frames: int, src_fps: Fraction, dst_fps: Fraction) -> int:
    """Map a frame index from one rate to another exactly, then round once."""
    return round(Fraction(frames) * dst_fps / src_fps)


def timecode(frames: int, fps: Fraction) -> str:
    """Readable HH:MM:SS.ff for logs and reports (not drop-frame SMPTE)."""
    sign = "-" if frames < 0 else ""
    frames = abs(frames)
    nominal = round(fps)  # frame field counts 0..nominal-1
    total = Fraction(frames) / fps
    whole = int(total)
    ff = frames - round(Fraction(whole) * fps)
    ff = max(0, min(nominal - 1, ff))
    h, rem = divmod(whole, 3600)
    m, s = divmod(rem, 60)
    return f"{sign}{h:02d}:{m:02d}:{s:02d}.{ff:02d}"
