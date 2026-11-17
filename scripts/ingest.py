#!/usr/bin/env python3
"""Stage 2 - Ingest. Probe, conform and proxy every file in a footage folder.

Usage:
  python scripts/ingest.py FOOTAGE_DIR --project PROJECT_DIR [options]

What it does, per file:
  * probes codec, resolution, rotation, frame rate, VFR, colour (HDR), audio layout
  * converts variable frame rate (phones, screen recordings) to constant, and
    tone-maps HLG/PQ HDR to Rec.709 SDR, into PROJECT/conformed/ (one pass)
  * picks the timeline frame rate (majority of source duration, or --fps)
  * writes a proxy at the timeline rate (short side 540 px) into PROJECT/proxies/
    so proxy frame N == timeline frame N for every analysis step
  * extracts a mono 16 kHz WAV into PROJECT/audio/
  * aligns cameras / external audio by audio cross-correlation (multicam)
  * flags problems: missing or silent audio, clipping, very low light, shake

Output: PROJECT/media.json (schema: references/edl-schema.md, "media.json").
Results are cached by file content hash; re-running only processes new files.
Exit code 1 with a message on any unrecoverable error.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.common import (Cache, ToolError, fail, ffprobe_json, file_hash, log, media_kind,  # noqa: E402
                        read_json, rel, run, write_json)
from lib.timebase import (convert_frames, nearest_standard, parse_rate, rate_str,  # noqa: E402
                          sec_to_frames)

INGEST_VERSION = 2

PROXY_SHORT_SIDE = 540        # the prompt's proxy spec: 540p
VFR_SAMPLE_S = 30             # read packet timestamps from the first 30 s to judge VFR
VFR_JITTER_TOL = 0.25         # a frame interval >25 % off the median counts as irregular
VFR_IRREGULAR_PCT = 1.0       # more than 1 % irregular intervals => variable frame rate
VFR_RATE_MISMATCH = 0.01      # r_frame_rate vs avg_frame_rate differing by >1 % => VFR
BUNCHED_INTERVAL_S = 0.002    # packets under 2 ms apart (500 fps) are broken timestamps, not frames

# Problem-flag thresholds. STARTING DEFAULTS, to be tuned on real footage in evals.
LOW_LIGHT_MEAN_LUMA = 50      # median frame mean luma (0-255) below this = very low light
SHAKE_PCT_OF_WIDTH = 0.6      # high-frequency jitter std above 0.6 % of frame width = shaky
CLIPPED_PCT_FLAG = 0.01       # >0.01 % of samples in flat-topped runs = audible clipping
PHASE_MIN_RESPONSE = 0.05     # phase-correlation peak below this = no reliable shift estimate

PLATFORM_DEFAULT_FPS = {      # used only when the footage gives no majority
    "youtube_shorts": Fraction(30), "tiktok": Fraction(30), "instagram_reels": Fraction(30),
    "youtube": Fraction(30), "instagram_feed": Fraction(30), "linkedin": Fraction(30),
    "podcast": Fraction(30),
}
PLATFORM_MAX_FPS = Fraction(60)

HDR_TRANSFERS = {"smpte2084": "pq", "arib-std-b67": "hlg"}


# ---------------------------------------------------------------- probing

def _stream(probe: dict, kind: str) -> dict | None:
    for s in probe.get("streams", []):
        if s.get("codec_type") == kind and not s.get("disposition", {}).get("attached_pic"):
            return s
    return None


def _rotation(vs: dict) -> int:
    for sd in vs.get("side_data_list", []) or []:
        if "rotation" in sd:
            return int(round(float(sd["rotation"]))) % 360
    tag = (vs.get("tags") or {}).get("rotate")
    return int(tag) % 360 if tag else 0


def detect_vfr(path: Path, vs: dict) -> dict:
    """VFR if r_frame_rate and avg_frame_rate disagree, or packet intervals are irregular."""
    r, avg = parse_rate(vs.get("r_frame_rate")), parse_rate(vs.get("avg_frame_rate"))
    evidence: dict = {"r_frame_rate": vs.get("r_frame_rate"), "avg_frame_rate": vs.get("avg_frame_rate")}
    mismatch = bool(r and avg and abs(float(r) - float(avg)) / float(avg) > VFR_RATE_MISMATCH)
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+{VFR_SAMPLE_S}",
               "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(path)]).stdout.decode()
    pts = sorted({float(x) for x in re.findall(r"-?\d+\.?\d*", out)})
    irregular_pct, measured = 0.0, None
    if len(pts) > 10:
        import numpy as np
        d = np.diff(np.array(pts))
        d = d[d > 0]
        # Packets closer than 2 ms are not frames of any real camera (that would be 500 fps):
        # they are bunched or duplicated timestamps from a broken mux or download.
        bunched = d < BUNCHED_INTERVAL_S
        normal = d[~bunched]
        if normal.size:
            # The most common interval is the camera's real rate, even when the median is
            # poisoned by a mix of normal and bunched packets.
            vals, counts = np.unique(np.round(normal, 4), return_counts=True)
            mode = float(vals[np.argmax(counts)])
            irregular_pct = 100.0 * float((np.abs(d - mode) > VFR_JITTER_TOL * mode).mean())
            # refine: mean of the real intervals in the mode's neighbourhood, then snap to a
            # standard rate when within 0.1 % (30.03 measured is 30, not 10000/333)
            mode = float(normal[np.abs(normal - mode) < 0.05 * mode].mean())
            measured = Fraction(1 / mode).limit_denominator(1001)
            std = nearest_standard(measured)
            if abs(float(measured / std) - 1) < 0.001:
                measured = std
            evidence.update({"mode_interval_ms": round(mode * 1000, 3), "measured_fps": round(1 / mode, 3)})
        evidence.update({"irregular_pct": round(irregular_pct, 2),
                         "bunched_packets_pct": round(100.0 * float(bunched.mean()), 2)})
    evidence["rate_mismatch"] = mismatch
    return {"vfr": mismatch or irregular_pct > VFR_IRREGULAR_PCT, "evidence": evidence,
            "measured_rate": rate_str(measured) if measured else None,
            "timestamp_anomaly": evidence.get("bunched_packets_pct", 0) > VFR_IRREGULAR_PCT}


def probe_file(path: Path) -> dict:
    probe = ffprobe_json(path)
    fmt = probe.get("format", {})
    kind = media_kind(path)
    vs, as_ = _stream(probe, "video"), _stream(probe, "audio")
    rec: dict = {
        "kind": kind if kind != "video" or vs else "audio",
        "container": fmt.get("format_name"),
        "duration_s_exact": fmt.get("duration"),   # string from ffprobe, kept only for provenance
        "video": None, "audio": None,
    }
    if vs and kind in ("video", "image"):
        rot = _rotation(vs)
        w, h = int(vs.get("width", 0)), int(vs.get("height", 0))
        dw, dh = (h, w) if rot in (90, 270) else (w, h)
        transfer = vs.get("color_transfer")
        pix = vs.get("pix_fmt", "")
        depth = 10 if ("10" in pix or "p010" in pix) else (12 if "12" in pix else 8)
        v = {
            "codec": vs.get("codec_name"), "width": w, "height": h, "rotation": rot,
            "display_width": dw, "display_height": dh,
            "pix_fmt": pix, "bit_depth": depth,
            "color": {"primaries": vs.get("color_primaries"), "transfer": transfer,
                      "matrix": vs.get("color_space"), "range": vs.get("color_range")},
            "hdr": HDR_TRANSFERS.get(transfer or ""),
        }
        if kind == "video":
            avg = parse_rate(vs.get("avg_frame_rate")) or parse_rate(vs.get("r_frame_rate"))
            v.update(detect_vfr(path, vs))
            # Prefer the measured packet cadence: avg_frame_rate is packets/duration and is
            # wrong whenever timestamps are broken or the file is VFR.
            native = parse_rate(v.pop("measured_rate")) or avg
            v["fps_native"] = rate_str(native) if native else None
            v["fps_nearest_standard"] = rate_str(nearest_standard(native)) if native else None
        rec["video"] = v
    if as_:
        rec["audio"] = {"codec": as_.get("codec_name"), "channels": as_.get("channels"),
                        "layout": as_.get("channel_layout"), "sample_rate": int(as_.get("sample_rate", 0))}
    return rec


# ---------------------------------------------------------------- timeline rate

def choose_timeline_fps(records: list[dict], platform: str | None, forced: str | None) -> tuple[Fraction, str]:
    if forced:
        fps = parse_rate(forced)
        if not fps:
            fail(f"--fps '{forced}' is not a valid frame rate (examples: 30, 25, 30000/1001)")
        return fps, "set by --fps"
    votes: Counter = Counter()
    for r in records:
        v = r["probe"].get("video")
        if r["probe"]["kind"] == "video" and v and v.get("fps_nearest_standard"):
            dur = float(r["probe"].get("duration_s_exact") or 0)
            votes[parse_rate(v["fps_nearest_standard"])] += max(dur, 0.001)
    if not votes:
        fps = PLATFORM_DEFAULT_FPS.get(platform or "", Fraction(30))
        return fps, f"no video sources; platform default {rate_str(fps)}"
    fps, weight = votes.most_common(1)[0]
    total = sum(votes.values())
    reason = f"{rate_str(fps)} fps carries {100 * weight / total:.0f}% of source duration"
    if fps > PLATFORM_MAX_FPS:
        # High-frame-rate footage is slow-motion material; deliver at half or quarter rate.
        while fps > PLATFORM_MAX_FPS:
            fps /= 2
        reason += f"; capped to {rate_str(fps)} (platform maximum 60, high-rate sources kept for slow motion)"
    return fps, reason


def conform_method(src: Fraction, tl: Fraction) -> str:
    """How a constant-rate source maps onto the timeline without stutter, if it can."""
    if src == tl:
        return "native"
    ratio = src / tl
    nearest_int = round(ratio)
    if ratio.denominator == 1:
        return "drop_frames"          # 60 -> 30: take every 2nd frame, no stutter
    if abs(float(ratio) - 1) < 0.002:
        return "retime"               # 29.97 <-> 30: 0.1 % speed change, inaudible
    if nearest_int >= 2 and abs(float(ratio) / nearest_int - 1) < 0.002:
        return "drop_frames_retime"   # 59.94 -> 30: every 2nd frame plus a 0.1 % retime
    if float(ratio) >= 2:
        return "slowmo_or_drop"       # 120 in a 30 timeline: usable as 4x slow motion
    return "frame_blend"              # 25 -> 30: needs blending; judder is likely, flag it


# ---------------------------------------------------------------- media operations

def _scale_short_side(n: int) -> str:
    return f"scale='if(gt(iw,ih),-2,{n})':'if(gt(iw,ih),{n},-2)':flags=bicubic"


def tonemap_filter(hdr: str) -> str:
    # zscale linearises (PQ or HLG), hable tone-maps highlights, then back to BT.709 limited range.
    return ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
            "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def conform(src: Path, dst: Path, rec: dict, tl_fps: Fraction, keep_hdr: bool,
            log_vf: str | None = None, log_name: str | None = None) -> list[str]:
    """One pass: log->Rec.709, VFR->CFR and HDR->SDR. Visually lossless intermediate (x264 CRF 12, PCM audio)."""
    v = rec["video"]
    applied, filters = [], []
    if log_vf:
        filters.append(log_vf)                 # colour space transform first, before anything else
        applied.append(f"log_{log_name}_to_rec709")
    if v.get("hdr") and not keep_hdr:
        filters.append(tonemap_filter(v["hdr"]))
        applied.append(f"tonemap_{v['hdr']}_to_rec709")
    target = tl_fps
    if v.get("vfr"):
        native = parse_rate(v.get("fps_nearest_standard")) or tl_fps
        # Conform to the timeline rate when the source is near it; otherwise keep its own standard rate.
        target = tl_fps if abs(float(native) - float(tl_fps)) / float(tl_fps) < 0.03 else native
        filters.append(f"fps={rate_str(target)}")
        applied.append(f"vfr_to_cfr_{rate_str(target)}")
    if not applied:
        return []
    if v.get("hdr") and keep_hdr:
        c = v["color"]  # HDR kept: 10-bit, carry the source colour tags through unchanged
        color = ["-pix_fmt", "yuv420p10le", "-color_primaries", c.get("primaries") or "bt2020",
                 "-color_trc", c.get("transfer") or "smpte2084", "-colorspace", c.get("matrix") or "bt2020nc"]
    else:
        color = ["-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-map", "0:v:0", "-map", "0:a?",
         "-vf", ",".join(filters), "-fps_mode", "cfr", "-c:v", "libx264", "-crf", "12", "-preset", "fast",
         *color, "-c:a", "pcm_s16le", "-af", "aresample=async=1:first_pts=0", str(dst)])
    return applied


def make_proxy(src: Path, dst: Path, tl_fps: Fraction, has_audio: bool) -> None:
    gop = max(1, round(tl_fps))  # one keyframe per second: fast random access for frame sampling
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-map", "0:v:0"]
    if has_audio:
        cmd += ["-map", "0:a:0"]
    cmd += ["-vf", f"{_scale_short_side(PROXY_SHORT_SIDE)},fps={rate_str(tl_fps)}", "-fps_mode", "cfr",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "fastdecode", "-crf", "26",
            "-g", str(gop), "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "96k"] if has_audio else []
    cmd.append(str(dst))
    run(cmd)


def extract_wav(src: Path, dst: Path) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-map", "0:a:0",
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)])


# ---------------------------------------------------------------- problem flags

def visual_flags(proxy: Path) -> tuple[list[dict], dict]:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(proxy))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    stats: dict = {}
    flags: list[dict] = []
    if n <= 0:
        cap.release()
        return flags, stats

    lumas = []
    for idx in np.linspace(0, n - 1, num=min(12, n)).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if ok:
            lumas.append(float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()))
    if lumas:
        med = float(np.median(lumas))
        stats["median_luma"] = round(med, 1)
        if med < LOW_LIGHT_MEAN_LUMA:
            flags.append({"type": "very_low_light", "severity": "warn",
                          "detail": f"median frame brightness {med:.0f}/255; expect noise when corrected"})

    # Shake: high-frequency part of frame-to-frame translation over up to 3 windows of 4 s.
    win = int(4 * fps)
    jitters = []
    for start in np.linspace(0, max(0, n - win - 1), num=3 if n > 3 * win else 1).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(start))
        prev, shifts = None, []
        for _ in range(min(win, n - start - 1)):
            ok, frame = cap.read()
            if not ok:
                break
            g = cv2.cvtColor(cv2.resize(frame, (160, int(160 * frame.shape[0] / frame.shape[1]))),
                             cv2.COLOR_BGR2GRAY).astype(np.float32)
            if prev is not None:
                (dx, dy), response = cv2.phaseCorrelate(prev, g)
                # A jump over 8 % of the width is a cut or whip, not shake; a weak
                # correlation peak means no reliable estimate. Neither counts as motion.
                if response < PHASE_MIN_RESPONSE or np.hypot(dx, dy) > 0.08 * 160:
                    dx = dy = 0.0
                shifts.append((dx, dy))
            prev = g
        if len(shifts) > 15:
            s = np.cumsum(np.array(shifts), axis=0)
            k = 15  # ~0.5 s smoothing: intentional camera moves are slower than this
            kernel = np.ones(k) / k
            smooth = np.stack([np.convolve(s[:, i], kernel, mode="same") for i in range(2)], axis=1)
            resid = (s - smooth)[k:-k] if len(s) > 2 * k + 2 else s - smooth
            mag = np.sqrt((resid ** 2).sum(axis=1))
            mad = float(np.median(np.abs(mag - np.median(mag)))) * 1.4826  # robust spread
            jitters.append(mad / 160 * 100)
    cap.release()
    if jitters:
        j = max(jitters)
        stats["shake_pct_width"] = round(j, 3)
        if j > SHAKE_PCT_OF_WIDTH:
            flags.append({"type": "shaky", "severity": "warn",
                          "detail": f"high-frequency jitter {j:.2f}% of frame width; consider stabilisation"})
    return flags, stats


def audio_flags(src: Path) -> tuple[list[dict], dict]:
    from lib.audio import SILENCE_PEAK, scan_levels
    scan = scan_levels(src)
    stats = {"peak_dbfs": round(scan.peak_dbfs, 2), "clipped_pct": round(scan.clipped_pct, 4),
             "clipped_runs": scan.clipped_runs}
    flags = []
    if scan.peak < SILENCE_PEAK:
        flags.append({"type": "silent_audio", "severity": "error",
                      "detail": "audio track is digitally silent (dead channel or muted recorder)"})
    elif scan.clipped_pct > CLIPPED_PCT_FLAG or scan.clipped_runs > 20:
        flags.append({"type": "clipped_audio", "severity": "warn",
                      "detail": f"{scan.clipped_runs} flat-topped runs ({scan.clipped_pct:.3f}% of samples); "
                                "distortion cannot be fully repaired"})
    elif scan.peak > 1.0:
        flags.append({"type": "hot_level", "severity": "info",
                      "detail": f"decoded peak {scan.peak_dbfs:+.1f} dBFS ({scan.overs} samples over full scale): "
                                "lossy audio mastered at 0 dBFS; leave headroom when mixing"})
    return flags, stats


# ---------------------------------------------------------------- multicam

def sync_groups(items: list[dict], project: Path, tl_fps: Fraction) -> list[dict]:
    """Greedy grouping: longest file anchors a group; others join the first group they correlate with."""
    from lib.audio import ANALYSIS_SR, find_offset, load_wav

    cands = [it for it in items if it.get("wav")]
    cands.sort(key=lambda it: -it["duration_f"])
    groups: list[dict] = []
    audio_cache: dict = {}

    def wav(it):
        if it["id"] not in audio_cache:
            audio_cache[it["id"]] = load_wav(project / it["wav"])[0]
        return audio_cache[it["id"]]

    for it in cands:
        placed = False
        for g in groups:
            res = find_offset(wav(g["anchor"]), wav(it), ANALYSIS_SR)
            if res.accepted:
                off_f = convert_frames(res.offset_samples, Fraction(ANALYSIS_SR), tl_fps)
                g["members"].append({"id": it["id"], "offset_f": off_f, "offset_samples_16k": res.offset_samples,
                                     "peak_z": res.peak_z, "pearson": res.pearson, "overlap_s": res.overlap_s})
                placed = True
                break
        if not placed:
            groups.append({"anchor": it, "members": [{"id": it["id"], "offset_f": 0, "offset_samples_16k": 0,
                                                      "anchor": True}]})
    out = []
    for i, g in enumerate(groups, 1):
        if len(g["members"]) > 1:
            out.append({"group": f"sync_{i}", "anchor": g["anchor"]["id"], "members": g["members"]})
    return out


# ---------------------------------------------------------------- camera log

def log_conversion(item: dict, p: Path, v: dict, args, project: Path, cache: Cache, digest: str,
                   dur_s: Fraction) -> tuple[str | None, str | None]:
    """Detect a log profile (lib/logcam.py) and return the conform filter that converts it, recording
    the detection and any doubt as flags on the item."""
    from lib import logcam
    key = {"v": 1, "override": args.log, "lut": args.log_lut}
    det = cache.get(digest, "logdetect", key)
    if det is None:
        try:
            tags = ffprobe_json(p)
            text = " ".join(f"{k}={val}" for sec in [tags.get("format", {})] + tags.get("streams", [])
                            for k, val in (sec.get("tags") or {}).items())
            det = logcam.detect(p, v, text, args.log, float(dur_s))
        except ValueError as e:
            fail(str(e))
        cache.put(digest, "logdetect", key, det)
    item["log"] = det
    prof = det.get("profile")
    if det.get("source") == "flat_picture_unknown_maker":
        item["flags"].append({"type": "log_suspected", "severity": "warn",
                              "detail": f"looks like log footage but the camera is unknown: {det['evidence']}"})
    if not prof:
        return None, None
    full = (v.get("color") or {}).get("range") == "pc"
    luts = project / "cache" / "luts"
    spec = logcam.PROFILES[prof]
    if args.log_lut:
        cube, how = Path(args.log_lut), "maker LUT " + Path(args.log_lut).name
        if not cube.is_file():
            fail(f"--log-lut not found: {cube}")
    elif spec.get("lut"):
        cube, how = logcam.approx_cube(det.get("stats") or logcam.pixel_stats(p, float(dur_s)), luts), "approximate"
        item["flags"].append({"type": "log_approximate", "severity": "warn",
                              "detail": f"{spec['name']} has no published formula; converted approximately from "
                                        "the clip's own levels. For exact colour pass the maker's free "
                                        "log-to-Rec.709 LUT with --log-lut"})
    else:
        cube, how = logcam.conversion_cube(prof, full, luts), "published curve and gamut"
    det["conversion"] = how
    item["flags"].append({"type": "log_converted", "severity": "info",
                          "detail": f"{spec['name']} ({det['source']}: {det['evidence']}) converted to Rec.709 "
                                    f"with the {how}"})
    log(f"log     {p.name}: {spec['name']} via {det['source']}")
    return logcam.ffmpeg_filter(cube, (v.get("color") or {}).get("matrix"), full), prof


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("footage", help="folder of raw footage (searched recursively)")
    ap.add_argument("--project", required=True, help="project folder; media.json is written here")
    ap.add_argument("--platform", help="target platform id from references/platforms.md, e.g. youtube_shorts")
    ap.add_argument("--fps", help="force the timeline frame rate, e.g. 30 or 30000/1001")
    ap.add_argument("--keep-hdr", action="store_true", help="do not tone-map HDR sources (HDR delivery)")
    ap.add_argument("--log", default="auto",
                    help="camera log profile: auto (detect), none, or one of lib/logcam.py PROFILES "
                         "(slog3, slog3_sg3, slog2, vlog, clog3, clog2, clog, flog, flog2, nlog, llog, logc3, "
                         "logc4, dlog, applelog, protune, dlogm, samsunglog, gplog, ilog)")
    ap.add_argument("--log-lut", help="the camera maker's own log-to-Rec.709 .cube; used instead of the "
                                      "built-in conversion (required for full accuracy on dlogm, samsunglog, gplog, ilog)")
    ap.add_argument("--no-sync", action="store_true", help="skip multicam audio alignment")
    ap.add_argument("--no-flags", action="store_true", help="skip shake / light / clipping checks (faster)")
    args = ap.parse_args()

    footage, project = Path(args.footage), Path(args.project)
    if not footage.is_dir():
        fail(f"footage folder not found: {footage}")
    for d in ("proxies", "audio", "conformed", "cache"):
        (project / d).mkdir(parents=True, exist_ok=True)
    cache = Cache(project / "cache")

    files = sorted(p for p in footage.rglob("*") if p.is_file() and media_kind(p) and not p.name.startswith("."))
    if not files:
        fail(f"no media files in {footage} (looked for video, audio and image extensions)")

    # Pass 1: probe (cached by content hash)
    records, used_ids = [], set()
    for p in files:
        digest = file_hash(p)
        probe = cache.get(digest, "probe", {"v": INGEST_VERSION})
        if probe is None:
            log(f"probe   {p.name}")
            try:
                probe = cache.put(digest, "probe", {"v": INGEST_VERSION}, probe_file(p))
            except ToolError as e:
                log(f"skip    {p.name}: {e}")
                continue
        base = re.sub(r"[^A-Za-z0-9_-]+", "_", p.stem).strip("_")[:40] or "clip"
        mid, k = base, 2
        while mid in used_ids:
            mid, k = f"{base}_{k}", k + 1
        used_ids.add(mid)
        records.append({"id": mid, "path": p, "hash": digest, "probe": probe})

    tl_fps, fps_reason = choose_timeline_fps(records, args.platform, args.fps)
    log(f"timeline fps {rate_str(tl_fps)} ({fps_reason})")

    # Pass 2: conform, proxy, wav, flags
    items = []
    for r in records:
        p, pr, digest = r["path"], r["probe"], r["hash"]
        item: dict = {"id": r["id"], "kind": pr["kind"], "path": p.resolve().as_posix(), "hash": digest,
                      "size_bytes": p.stat().st_size, "video": pr["video"], "audio": pr["audio"],
                      "conform": {"applied": []}, "flags": []}
        dur_s = Fraction(pr.get("duration_s_exact") or "0")
        item["duration_f"] = sec_to_frames(dur_s, tl_fps)
        render_src = p

        if pr["kind"] == "video" and pr["video"]:
            v = pr["video"]
            log_vf, log_name = log_conversion(item, p, v, args, project, cache, digest, dur_s)
            key = {"v": INGEST_VERSION, "fps": rate_str(tl_fps), "keep_hdr": args.keep_hdr, "log": log_vf}
            needs_conform = v.get("vfr") or (v.get("hdr") and not args.keep_hdr) or log_vf
            conf_path = project / "conformed" / f"{r['id']}_{digest[:8]}.mov"
            if needs_conform:
                done = cache.get(digest, "conform", key)
                if done is None or not conf_path.exists():
                    log(f"conform {p.name} ({'VFR' if v.get('vfr') else ''}{' HDR' if v.get('hdr') else ''}"
                        f"{' ' + log_name if log_vf else ''})")
                    try:
                        applied = conform(p, conf_path, pr, tl_fps, args.keep_hdr, log_vf, log_name)
                    except ToolError as e:
                        fail(f"conforming {p.name} failed: {e}")
                    done = cache.put(digest, "conform", key, {"applied": applied})
                item["conform"]["applied"] = done["applied"]
                render_src = conf_path
            if v.get("timestamp_anomaly"):
                item["flags"].append({"type": "broken_timestamps", "severity": "warn",
                                      "detail": f"{v['evidence']['bunched_packets_pct']}% of video packets have "
                                                "bunched timestamps (broken mux or download); conformed to "
                                                "constant frame rate, check the end of the clip"})
            if v.get("hdr") and args.keep_hdr:
                item["flags"].append({"type": "hdr_kept", "severity": "info",
                                      "detail": f"{v['hdr'].upper()} HDR kept by --keep-hdr"})
            src_rate = parse_rate(v.get("fps_nearest_standard")) or tl_fps
            if v.get("vfr"):
                src_rate = tl_fps if abs(float(src_rate) - float(tl_fps)) / float(tl_fps) < 0.03 else src_rate
            item["conform"]["fps_method"] = conform_method(src_rate, tl_fps)
            item["conform"]["source_fps"] = rate_str(src_rate)
            if item["conform"]["fps_method"] == "frame_blend":
                item["flags"].append({"type": "fps_mismatch", "severity": "warn",
                                      "detail": f"{rate_str(src_rate)} fps source in a {rate_str(tl_fps)} fps "
                                                "timeline needs frame blending; motion may judder"})

            proxy = project / "proxies" / f"{r['id']}.mp4"
            pkey = {"v": INGEST_VERSION, "fps": rate_str(tl_fps), "src": render_src.name}
            if cache.get(digest, "proxy", pkey) is None or not proxy.exists():
                log(f"proxy   {p.name}")
                make_proxy(render_src, proxy, tl_fps, bool(pr["audio"]))
                cache.put(digest, "proxy", pkey, {"ok": True})
            item["proxy"] = rel(proxy, project)
            if not args.no_flags:
                vf = cache.get(digest, "visual_flags", {"v": INGEST_VERSION})
                if vf is None:
                    flags, stats = visual_flags(proxy)
                    vf = cache.put(digest, "visual_flags", {"v": INGEST_VERSION}, {"flags": flags, "stats": stats})
                item["flags"] += vf["flags"]
                item.setdefault("stats", {}).update(vf["stats"])
            if not pr["audio"]:
                item["flags"].append({"type": "missing_audio", "severity": "warn",
                                      "detail": "no audio stream; needs external audio or music only"})

        if pr["audio"]:
            wav = project / "audio" / f"{r['id']}.wav"
            if cache.get(digest, "wav", {"v": INGEST_VERSION, "src": render_src.name}) is None or not wav.exists():
                extract_wav(render_src, wav)
                cache.put(digest, "wav", {"v": INGEST_VERSION, "src": render_src.name}, {"ok": True})
            item["wav"] = rel(wav, project)
            if not args.no_flags:
                af = cache.get(digest, "audio_flags", {"v": INGEST_VERSION})
                if af is None:
                    try:
                        flags, stats = audio_flags(p)
                    except ToolError as e:
                        flags, stats = [{"type": "audio_decode_error", "severity": "error", "detail": str(e)}], {}
                    af = cache.put(digest, "audio_flags", {"v": INGEST_VERSION}, {"flags": flags, "stats": stats})
                item["flags"] += af["flags"]
                item.setdefault("stats", {}).update(af["stats"])

        item["render_src"] = render_src.resolve().as_posix()
        items.append(item)

    sync = []
    if not args.no_sync and sum(1 for it in items if it.get("wav")) > 1:
        log("sync    aligning audio across files")
        sync = sync_groups(items, project, tl_fps)
        by_id = {it["id"]: it for it in items}
        for g in sync:
            for m in g["members"]:
                by_id[m["id"]]["sync"] = {"group": g["group"], "offset_f": m["offset_f"]}

    media = {
        "version": 1,
        "fps": rate_str(tl_fps),
        "fps_reason": fps_reason,
        "platform": args.platform,
        "footage_dir": footage.resolve().as_posix(),
        "items": items,
        "sync_groups": sync,
        "problems": [{"id": it["id"], **f} for it in items for f in it["flags"] if f["severity"] != "info"],
    }
    out = write_json(project / "media.json", media)
    log(f"wrote {out} ({len(items)} files, {len(media['problems'])} problems flagged)")
    for prob in media["problems"]:
        log(f"  [{prob['severity']}] {prob['id']}: {prob['type']} - {prob['detail']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ToolError as e:
        fail(str(e))
    except FileNotFoundError as e:
        fail(str(e))
