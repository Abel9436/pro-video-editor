"""Synthetic test media, generated once per test session with FFmpeg and NumPy.

Each fixture file exercises one ingest/analyze behaviour:
  cam_a.mp4    30 fps 720x1280 vertical, hard cut at frame 90, random-click audio track
  cam_b.wav    the same clicks 1.25 s later (cam_b started first), quieter -> multicam sync
  phone_vfr.mp4  frame intervals change from 33 ms to 53 ms half way      -> VFR conform
  hdr_pq.mp4   10-bit HEVC tagged BT.2020 / PQ                            -> HDR tone-map
  shaky.mp4    random per-frame crop offset                               -> shake flag
  dark.mp4     near-black picture, no audio                               -> low light + missing audio
  clipped.wav  sine driven past full scale                                -> clipping flag
  music.wav    120 BPM click track with accented downbeats                -> beat analysis
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.environ.setdefault("PVE_OFFLINE", "1")   # no model downloads during tests

SR = 48000
SYNC_DELAY_S = 1.25


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def click_audio(seconds: float, seed: int) -> np.ndarray:
    """Non-periodic clicks and noise bursts: one unambiguous cross-correlation peak."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 0.003, int(seconds * SR)).astype(np.float32)
    t = 0.2
    while t < seconds - 0.2:
        a = int(t * SR)
        n = int(rng.uniform(0.02, 0.12) * SR)
        x[a:a + n] += rng.normal(0, rng.uniform(0.1, 0.4), n).astype(np.float32) * np.hanning(n).astype(np.float32)
        t += rng.uniform(0.15, 0.6)
    return np.clip(x, -0.95, 0.95)


@pytest.fixture(scope="session")
def footage(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("footage")
    tmp = tmp_path_factory.mktemp("work")

    audio = click_audio(8.0, seed=7)
    sf.write(tmp / "a.wav", audio, SR)
    delayed = np.concatenate([np.zeros(int(SYNC_DELAY_S * SR), np.float32), audio])[: audio.size]
    delayed = 0.5 * delayed + np.random.default_rng(1).normal(0, 0.004, delayed.size).astype(np.float32)
    sf.write(d / "cam_b.wav", delayed, SR)

    # cam_a: two visually different shots, cut at exactly 3.000 s (frame 90 at 30 fps)
    ff("-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=30:duration=3",
       "-f", "lavfi", "-i", "smptebars=size=720x1280:rate=30",
       "-i", str(tmp / "a.wav"),
       "-filter_complex", "[1:v]trim=duration=5,setpts=PTS-STARTPTS,format=yuv420p[m];"
                          "[0:v]format=yuv420p[t];[t][m]concat=n=2:v=1:a=0[v]",
       "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest",
       str(d / "cam_a.mp4"))

    # VFR: 33.3 ms intervals for 45 frames, then 53.3 ms
    ff("-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=3",
       "-vf", "setpts='(N/30+if(gt(N,45),(N-45)*0.02,0))/TB'", "-fps_mode", "passthrough",
       "-c:v", "libx264", "-preset", "ultrafast", str(d / "phone_vfr.mp4"))

    # HDR PQ tagged 10-bit HEVC
    ff("-f", "lavfi", "-i", "smptehdbars=size=640x360:rate=25:duration=2",
       "-c:v", "libx265", "-preset", "ultrafast", "-pix_fmt", "yuv420p10le",
       "-x265-params", "log-level=error:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc",
       "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc",
       str(d / "hdr_pq.mp4"))

    # Shaky: a random 0-30 px crop offset every frame = handheld jitter (~3 % of width)
    ff("-f", "lavfi", "-i", "testsrc=size=720x420:rate=30:duration=4",
       "-vf", "crop=640:360:x='30*random(0)':y='30*random(1)'",
       "-c:v", "libx264", "-preset", "ultrafast", str(d / "shaky.mp4"))

    # Dark, with no audio stream at all
    ff("-f", "lavfi", "-i", "color=c=0x0c0c0c:size=640x360:rate=30:duration=2",
       "-c:v", "libx264", "-preset", "ultrafast", str(d / "dark.mp4"))

    # Clipped sine
    t = np.arange(int(2 * SR)) / SR
    sf.write(d / "clipped.wav", np.clip(1.6 * np.sin(2 * np.pi * 220 * t), -1, 1).astype(np.float32), SR,
             subtype="PCM_16")

    # 120 BPM click track, accented every 4th beat, 12 s
    m = np.zeros(int(12 * SR), np.float32)
    for k, bt in enumerate(np.arange(0.25, 12, 0.5)):
        a = int(bt * SR)
        n = int(0.03 * SR)
        amp = 0.9 if k % 4 == 0 else 0.35
        m[a:a + n] += amp * np.sin(2 * np.pi * (1500 if k % 4 == 0 else 900) * t[:n]) * np.hanning(n)
    sf.write(d / "music.wav", m, SR)
    return d


def run_script(name: str, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    e = {**os.environ, **(env or {})}
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True, env=e,
                          encoding="utf-8", errors="replace")


@pytest.fixture(scope="session")
def ingested(footage, tmp_path_factory) -> Path:
    project = tmp_path_factory.mktemp("project")
    r = run_script("ingest.py", str(footage), "--project", str(project), "--platform", "youtube_shorts")
    assert r.returncode == 0, r.stderr
    return project


@pytest.fixture(scope="session")
def broken_ts(tmp_path_factory) -> Path:
    """507-ish real 30 fps frames followed by packets bunched 0.1 ms apart (seen in the wild)."""
    d = tmp_path_factory.mktemp("broken")
    ff("-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=4",
       "-vf", "setpts='if(lt(N,60),N/30,2+(N-60)*0.0001)/TB'", "-fps_mode", "passthrough",
       "-c:v", "libx264", "-preset", "ultrafast", str(d / "broken.mp4"))
    return d / "broken.mp4"
