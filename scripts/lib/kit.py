"""Editor kit: asset id resolution, the synthesized fallback sound kit, and fonts.

Asset ids:
  kit:<role>         a sound from the editor kit (assets/kit/manifest.json). When no pack file
                     for the role is on disk, a synthesized sound is generated (license: made by
                     this skill, no third-party rights) so an edit never blocks on downloads.
  cat:<id>           an entry in assets/catalog.json (tag_assets.py / fetch_assets.py)
  file:<path>        a file inside the project folder
Fonts are downloaded once from the Google Fonts repository (SIL Open Font License) into
assets/fonts/, which is git-ignored: nothing third-party ships in the repo.
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import numpy as np

SKILL = Path(__file__).resolve().parent.parent.parent
SR = 48000
SYNTH_VERSION = "pve_synth_v2"

FONT_URLS = {
    "Poppins ExtraBold": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-ExtraBold.ttf",
    "Anton": "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
    "Noto Sans Ethiopic": "https://github.com/google/fonts/raw/main/ofl/notosansethiopic/NotoSansEthiopic%5Bwdth,wght%5D.ttf",
    "Noto Sans Arabic": "https://github.com/google/fonts/raw/main/ofl/notosansarabic/NotoSansArabic%5Bwdth,wght%5D.ttf",
}


def fonts_dir() -> Path:
    d = SKILL / "assets" / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_fonts(names: list[str]) -> tuple[Path, list[str]]:
    """Download missing fonts; returns the folder and the names that are unavailable."""
    d = fonts_dir()
    missing = []
    for n in names:
        url = FONT_URLS.get(n)
        if not url:
            continue
        dst = d / (n.replace(" ", "") + ".ttf")
        if dst.exists():
            continue
        if os.environ.get("PVE_OFFLINE"):
            missing.append(n); continue
        try:
            urllib.request.urlretrieve(url, dst)
        except Exception:
            missing.append(n)
    return d, missing


# ----------------------------------------------------------------------------- synth kit
def _env(n, a, d):
    a, d = max(1, int(a * SR)), max(1, n - int(a * SR))
    return np.concatenate([np.linspace(0, 1, a), np.exp(-np.linspace(0, 1, d) * 6)])[:n]


def _noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n).astype(np.float32)


def _bandsweep(x, f0, f1, q=4.0):
    """Time-varying band-pass by short-time FFT masking."""
    import scipy.signal as sg
    n = x.size
    x = np.pad(x, (0, max(0, 4096 - n)))      # very short sounds: pad so the STFT has whole frames
    f, t, Z = sg.stft(x, SR, nperseg=1024)
    fc = np.geomspace(f0, f1, Z.shape[1])
    mask = np.exp(-0.5 * (np.log(np.maximum(f[:, None], 1) / fc[None]) * q) ** 2)
    return sg.istft(Z * mask, SR, nperseg=1024)[1][:n].astype(np.float32)


def _arc_whoosh(d: float, lo: float, hi: float, seed: int) -> np.ndarray:
    """Pass-by whoosh: band-passed noise whose centre rises then falls (something flying past), sin^2 swell."""
    import scipy.signal as sg
    n = int(d * SR)
    x, y, hop = _noise(n + 512, seed), np.zeros(n + 512, np.float32), 256
    win = np.hanning(512).astype(np.float32)
    for i in range(0, n - 256, hop):
        fc = lo + (hi - lo) * np.sin(np.pi * min(1.0, (i + 256) / n))
        sos = sg.butter(2, [max(40.0, 0.6 * fc) / (SR / 2), min(20000.0, 1.4 * fc) / (SR / 2)], "band", output="sos")
        y[i:i + 512] += sg.sosfilt(sos, x[i:i + 512]).astype(np.float32) * win
    return y[:n] * np.sin(np.pi * np.arange(n) / n) ** 2


def synth(role: str) -> np.ndarray:
    t = lambda d: np.arange(int(d * SR)) / SR  # noqa: E731
    if role in ("whoosh_short", "transition_whoosh", "swipe"):
        x = _arc_whoosh(0.35 if role != "swipe" else 0.22, 500, 5000, 1)
    elif role == "whoosh_mid":
        x = _arc_whoosh(0.6, 300, 3500, 8)
    elif role == "whoosh_long":
        x = _arc_whoosh(1.0, 200, 2500, 2)
    elif role in ("tick", "ui_tick"):                       # tonal tick: bright noise snap + a short 1.8 kHz body
        tt = t(0.06)
        x = _bandsweep(_noise(tt.size, 9), 5000, 5000, 1.5) * np.exp(-tt / 0.006) + 0.5 * np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt / 0.010)
    elif role == "soft_hit":                                # felt more than heard: 120 -> 42 Hz, slow decay
        tt = t(0.9); f = np.geomspace(120, 42, tt.size)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(tt / 0.002, 1) * np.exp(-tt / 0.2)
    elif role == "air_bed":                                 # loopable airy texture under a design stage
        tt = t(4.0); x = _bandsweep(_noise(tt.size, 10), 3000, 3000, 0.8)
        edge = int(0.5 * SR); x[:edge] *= np.linspace(0, 1, edge); x[-edge:] *= np.linspace(1, 0, edge)
    elif role in ("pop_soft", "text_pop", "pop"):
        tt = t(0.09); f = 950 * np.exp(-tt * 30) + 280
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(tt.size, 0.002, 0)
    elif role in ("click_soft", "click"):
        tt = t(0.02); x = _bandsweep(_noise(tt.size, 3), 2500, 2500, 2) * _env(tt.size, 0.0005, 0)
    elif role in ("hit_low", "impact_hit", "hit"):
        tt = t(0.6); f = 110 * np.exp(-tt * 8) + 45
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(tt.size, 0.001, 0) + 0.3 * _noise(tt.size, 4) * np.exp(-tt * 60)
    elif role == "riser":
        tt = t(2.0); f = np.geomspace(150, 1600, tt.size)
        x = 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * _bandsweep(_noise(tt.size, 5), 300, 7000)
        x *= np.linspace(0.05, 1, tt.size) ** 2
    elif role == "sub_drop":
        tt = t(1.2); f = np.geomspace(90, 28, tt.size)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(tt.size, 0.005, 0)
    elif role in ("ding", "notification"):
        tt = t(1.2)
        x = sum(a * np.sin(2 * np.pi * fr * tt) * np.exp(-tt * k) for fr, a, k in
                ((1318.5, 1.0, 4), (2637, 0.35, 6), (3951, 0.15, 9)))
    elif role == "shutter":
        tt = t(0.12)
        x = _bandsweep(_noise(tt.size, 6), 3000, 3000, 2) * (_env(tt.size, 0.001, 0) + np.roll(_env(tt.size, 0.001, 0), int(0.06 * SR)) * 0.7)
    elif role == "glitch":
        tt = t(0.25); x = _noise(tt.size, 7)
        x = np.round(x * 3) / 3 * (np.sin(2 * np.pi * 37 * tt) > 0)
    else:
        raise KeyError(f"no synthesized sound for role '{role}'")
    x = np.asarray(x, np.float32)
    x /= (np.abs(x).max() + 1e-9)
    fade = min(int(0.005 * SR), x.size // 4)
    x[-fade:] *= np.linspace(1, 0, fade)
    if role in ("whoosh_short", "transition_whoosh", "swipe", "whoosh_mid", "whoosh_long", "air_bed"):
        # gentle width on airy sounds only: a little of a 0.25 ms delayed copy in the right channel.
        # Transients stay centred, because a phone speaker sums to mono and a full delay would cancel them.
        r = 0.8 * x + 0.2 * np.concatenate([np.zeros(12, np.float32), x[:-12]])
        return np.stack([x, r / (np.abs(r).max() + 1e-9)], 1)
    return np.stack([x, x], 1)


SYNTH_ROLES = ["whoosh_short", "whoosh_mid", "whoosh_long", "swipe", "pop_soft", "click_soft", "tick", "hit_low",
               "soft_hit", "riser", "sub_drop", "shutter", "glitch", "air_bed", "ding"]   # ding: kept for old EDLs; avoid


def kit_path(role: str) -> Path:
    """A pack file listed for the role in the kit manifest if present, else the synthesized sound."""
    man = SKILL / "assets" / "kit" / "manifest.json"
    if man.exists():
        import json
        data = json.loads(man.read_text(encoding="utf-8"))
        for s in data.get("sounds", []):
            if s.get("id") == f"kit:{role}" or s.get("role") == role:
                for cand in (SKILL / "assets" / "library" / s.get("pack", "") / s.get("file", ""),
                             SKILL / "assets" / "local" / s.get("pack", "") / s.get("file", "")):
                    if s.get("file") and cand.exists():
                        return cand
    dst = SKILL / "assets" / "cache" / SYNTH_VERSION / f"{role}.wav"
    if not dst.exists():
        import soundfile as sf
        dst.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(dst), synth(role), SR, subtype="FLOAT")
    return dst


def resolve(asset: str, project: Path) -> tuple[Path, dict]:
    """Asset id -> (file path, ledger entry)."""
    if asset.startswith("kit:"):
        role = asset[4:]
        p = kit_path(role)
        synthesized = SYNTH_VERSION in p.as_posix()
        return p, {"id": asset, "source": "pro-video-editor synthesized kit" if synthesized else "editor kit",
                   "license": "generated by the skill; no third-party rights" if synthesized else "see kit manifest",
                   "commercial": True, "attribution": None}
    if asset.startswith("cat:"):
        import json
        cat = SKILL / "assets" / "catalog.json"
        if not cat.exists():
            raise FileNotFoundError("assets/catalog.json missing; run tag_assets.py or fetch_assets.py")
        for e in json.loads(cat.read_text(encoding="utf-8")).get("assets", []):
            if e["id"] == asset:
                p = Path(e["path"])
                p = p if p.is_absolute() else SKILL / p
                if not p.exists():
                    raise FileNotFoundError(f"{asset}: file {p} missing")
                return p, {k: e.get(k) for k in ("id", "source", "license", "url", "commercial", "attribution",
                                                   "license_checked", "restrictions")}
        raise FileNotFoundError(f"{asset} not in assets/catalog.json")
    if asset.startswith("file:"):
        import json
        p = project / asset[5:]
        if not p.exists():
            raise FileNotFoundError(f"{asset}: {p} missing")
        keys = ("id", "source", "license", "url", "commercial", "attribution", "license_checked", "restrictions")
        # a downloaded file carries its licence: the project ledger first, then a catalog.json beside it
        led = project / "licenses.json"
        if led.exists():
            for e in json.loads(led.read_text(encoding="utf-8")).get("assets", []):
                if e.get("id") == asset:
                    return p, {k: e.get(k) for k in keys}
        cat = p.parent / "catalog.json"
        if cat.exists():
            data = json.loads(cat.read_text(encoding="utf-8"))
            for e in data.get("sounds", []) + data.get("assets", []):
                if e.get("file") == asset[5:]:
                    return p, {"id": asset, "source": f"{e.get('name', '')} by {e.get('author', '')}".strip(),
                               "license": e.get("license"), "url": e.get("source") or e.get("url"),
                               "commercial": e.get("commercial", True), "attribution": e.get("attribution"),
                               "license_checked": e.get("license_checked")}
        return p, {"id": asset, "source": "user project file", "license": "user's own", "commercial": True,
                   "attribution": None}
    raise ValueError(f"unknown asset id '{asset}' (use kit:, cat: or file:)")
