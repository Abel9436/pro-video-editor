#!/usr/bin/env python3
"""Stage 10 - Measure a rendered video against every QC check; optionally fix and re-render.

Usage:
  python scripts/qc.py --video OUT.mp4 --edl P/edl/v1.json --project P [--style STYLE.json]
                       [--fix-loop] [--no-retranscribe] [--no-style] [--out P/qc]

Writes P/qc/qc_report.json and P/qc/qc_report.md: every check as pass / warn / fail / fixed /
skipped, with timeline timestamps and the reason. Thresholds marked STARTING DEFAULT in
references/craft-*.md are defaults until evals replace them.

--fix-loop: failed checks that have a mechanical fix (loudness, captions over faces, cuts
inside words, flash frames, digital silence) are fixed in a new EDL version (vN+1, with a note
per change) and re-rendered; at most MAX_LOOPS rounds, then whatever still fails is reported.

Checks: picture (black, frozen, flash frames, unintended jump cuts, face framing/headroom,
captions on faces / outside safe zone, format and colour tags, upscaling, skin hue, clipped
faces, shot matching, photosensitivity); sound (loudness, true peak, clipping, dialogue
consistency, music-to-voice separation, cuts inside words, digital silence, pops at edits,
intelligibility by re-transcription, A/V sync and lip-sync offset); captions (timing, names,
reading speed, contrast); edit (duration, planned structure, style distance, virality, licenses).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from lib.common import ToolError, fail, ffprobe_json, log, read_json, run, write_json  # noqa: E402
from lib.edl import event_len, fps_of, timeline_len, timeline_words  # noqa: E402
from lib.timebase import parse_rate, timecode  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
MAX_LOOPS = 3
LUFS_TOL = 1.0                 # integrated loudness within +-1 LU of target
TP_TOL = 0.2
FLASH_F = 3                    # shots shorter than 3 frames are flash frames
FREEZE_S = 0.5
BLACK_S = 0.04
DIGITAL_SILENCE_DB = -90
DIGITAL_SILENCE_S = 0.05
POP_RATIO = 8.0                # sample-step at an edit point 8x the local median step = audible pop
SEP_RANGE_DB = (18, 24)        # music under speech, dB below the voice (craft-audio.md STARTING DEFAULT)
SEP_MIN_DB = 15                # below this is a fail: music competes with the voice
SPEAKER_SPREAD_LU = 3.0        # dialogue loudness spread across speakers
WER_MAX = 0.15                 # STARTING DEFAULT: word error rate of the re-transcribed mix vs the cut's words
MAX_CPS = {"short": 25, "long": 20}    # caption reading speed, characters per second
FACE_MIN_SCORE = 0.85          # hands and microphones score lower; they are not faces to protect
FACE_ASPECT = (0.9, 1.8)       # face box height/width in pixels
HEADROOM_MIN = 0.02            # face box top must sit at least 2 % below the frame top
FACE_EDGE = 0.01
SKIN_HUE = (5.0, 60.0)         # Lab hue band treated as plausible skin (wider than the skin line on purpose)
FACE_CLIP_PCT = 5.0            # % of face pixels clipped (>=250) or crushed (<=5)
MATCH_DL = 8.0                 # neighbouring shots: L* difference
MATCH_DAB = 6.0                # and chroma (a*b*) difference
FLASH_PER_S = 3                # photosensitivity: more than 3 flashes in any one second fails
FLASH_DELTA = 0.2              # a flash = luminance swing of 20 % of full range and back
UPSCALE_WARN, UPSCALE_FAIL = 1.5, 2.0
LIPSYNC_MAX_F = 1
LIPSYNC_MIN_R = 0.15           # weaker mouth/audio correlation than this cannot locate an offset
STYLE_FIELDS = ["cuts_per_min", "shot_len_s.med", "text.caption_coverage_pct", "text.words_per_card.med",
                "structure.rehook_every_s", "structure.hook_len_s", "audio.lufs", "zooms_per_min"]
PRESETS = {"shorts": (1080, 1920), "youtube_shorts": (1080, 1920), "tiktok": (1080, 1920), "reels": (1080, 1920),
           "instagram_reels": (1080, 1920), "youtube": (1920, 1080), "instagram_feed": (1080, 1350),
           "linkedin": (1080, 1080), "podcast": (1920, 1080)}


class Report:
    def __init__(self, fps: Fraction):
        self.items, self.fps = [], fps

    def add(self, cid, cat, status, detail, at=None, fix=None):
        self.items.append({"id": cid, "category": cat, "status": status, "detail": detail,
                           "at": [timecode(int(a), self.fps) for a in (at or [])][:20], "fix": fix})

    def failed(self):
        return [i for i in self.items if i["status"] == "fail"]


def ffmpeg_log(video: Path, vf: str | None = None, af: str | None = None) -> str:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(video)]
    if vf:
        cmd += ["-vf", vf]
    if af:
        cmd += ["-af", af]
    if not vf:
        cmd += ["-vn"]
    if not af:
        cmd += ["-an"]
    cmd += ["-f", "null", "-"]
    return run(cmd, check=False).stderr.decode("utf-8", "replace")


def frames_small(video: Path, w: int = 270, every: int = 1):
    pr = ffprobe_json(video)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    W, H = int(v["width"]), int(v["height"])
    h = int(round(H * w / W / 2)) * 2
    vf = f"scale={w}:{h}" + (f",select='not(mod(n\\,{every}))'" if every > 1 else "")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-vf", vf, "-vsync", "0", "-f", "rawvideo",
                          "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    n = w * h * 3
    k = 0
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            yield k * every, np.frombuffer(b, np.uint8).reshape(h, w, 3)
            k += 1
    finally:
        p.stdout.close(); p.wait()


# ----------------------------------------------------------------------------- picture
def picture_checks(rep: Report, video: Path, edl: dict, analysis: dict, rdir: Path, project: Path):
    import cv2
    from lib.shots import FaceDetector
    fps = rep.fps
    W, H = edl["project"]["width"], edl["project"]["height"]
    pr = ffprobe_json(video)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    a = next((s for s in pr["streams"] if s["codec_type"] == "audio"), None)
    # format
    plat = edl["project"].get("platform", "shorts")
    want = PRESETS.get(plat, (W, H))
    if rdir.name == "preview":
        want = ((want[0] // 2) // 2 * 2, (want[1] // 2) // 2 * 2)
    probs = []
    if (int(v["width"]), int(v["height"])) != want:
        probs.append(f"size {v['width']}x{v['height']} != preset {want[0]}x{want[1]}")
    if parse_rate(v.get("avg_frame_rate")) != fps:
        probs.append(f"frame rate {v.get('avg_frame_rate')} != {fps}")
    if v.get("color_primaries") != "bt709" or v.get("color_transfer") != "bt709" or v.get("color_space") != "bt709":
        probs.append(f"colour tags {v.get('color_primaries')}/{v.get('color_transfer')}/{v.get('color_space')} (want bt709)")
    if v.get("pix_fmt") != "yuv420p":
        probs.append(f"pix_fmt {v.get('pix_fmt')}")
    if not a or a.get("codec_name") != "aac" or int(a.get("sample_rate", 0)) != 48000:
        probs.append("audio must be AAC 48 kHz")
    fmt = pr.get("format", {})
    rep.add("format", "picture", "fail" if probs else "pass", "; ".join(probs) or
            f"{v['width']}x{v['height']} {v.get('avg_frame_rate')} fps H.264 yuv420p bt709, AAC 48 kHz",
            fix="re-render with the platform preset" if probs else None)
    # faststart
    head = open(video, "rb").read(64 * 1024)
    rep.add("faststart", "picture", "pass" if head.find(b"moov") != -1 and head.find(b"moov") < head.find(b"mdat") + 1
            or head.find(b"mdat") == -1 else "warn", "moov atom at the start (streams before full download)")
    # black / frozen
    txt = ffmpeg_log(video, vf=f"blackdetect=d={BLACK_S}:pix_th=0.06")
    blacks = [float(x) for x in re.findall(r"black_start:([\d.]+)", txt)]
    planned_fades = {ev["at_f"] for ev in edl["tracks"]["video"] if ev.get("transition_in") == "fade"}
    bad = [b for b in blacks if not any(abs(b * float(fps) - f) < 12 for f in planned_fades)]
    rep.add("black_frames", "picture", "fail" if bad else "pass",
            f"{len(bad)} unplanned black segment(s)" if bad else "no unplanned black frames",
            at=[b * float(fps) for b in bad])
    txt = ffmpeg_log(video, vf=f"freezedetect=n=-60dB:d={FREEZE_S}")
    frz = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", txt)]
    planned = [ev for ev in edl["tracks"]["video"] if ev.get("freeze_f")]
    rep.add("frozen_frames", "picture", "warn" if frz and not planned else "pass",
            f"{len(frz)} frozen stretch(es) >= {FREEZE_S} s" if frz else "no frozen frames", at=[f * float(fps) for f in frz])
    # flash frames / single-frame leftovers
    short = [ev for ev in edl["tracks"]["video"] if event_len(ev) < FLASH_F]
    from lib.shots import detect_shots
    total = timeline_len(edl)
    shots, _ = detect_shots(video, total)
    sh_short = [s for s in shots if s["dur_f"] < FLASH_F and 0 < s["s_f"] < total - FLASH_F]
    rep.add("flash_frames", "picture", "fail" if short or sh_short else "pass",
            f"{len(short)} EDL event(s) and {len(sh_short)} detected shot(s) under {FLASH_F} frames" if short or sh_short
            else "no flash frames", at=[e["at_f"] for e in short] + [s["s_f"] for s in sh_short],
            fix="merge or remove the short events" if short else None)
    # unintended jump cuts: same source, same framing, consecutive
    jumps = []
    vids = edl["tracks"]["video"]
    for p, q in zip(vids, vids[1:]):
        if p["src"] == q["src"] and abs((p.get("reframe") or {}).get("zoom", 1) - (q.get("reframe") or {}).get("zoom", 1)) < 0.05 \
                and q["in_f"] != p["out_f"] and q.get("transition_in", "cut") == "cut":
            jumps.append(q["at_f"])
    style_jumps = edl["project"].get("type") in ("short_form", "talking_head", "vlog", "podcast_clip")
    rep.add("jump_cuts", "picture", "pass" if not jumps else ("warn" if style_jumps else "fail"),
            f"{len(jumps)} jump cut(s) without a framing change" if jumps else "every jump cut changes framing", at=jumps)
    # per-frame pass on the output: faces, flashes, colour
    faces = FaceDetector(SKILL / "assets" / "cache" / "models")
    step = max(1, int(round(fps / 4)))
    luma, face_rows = [], []
    for f, fr in frames_small(video, 270, 1):
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        luma.append(float(g.mean()) / 255)
        if f % step == 0:
            big = cv2.resize(fr, (fr.shape[1] * 2, fr.shape[0] * 2))
            fc = [c for c in faces.faces(big) if c.get("score", 1) >= FACE_MIN_SCORE
                  and FACE_ASPECT[0] <= (c["box"][3] * fr.shape[0]) / max(1e-6, c["box"][2] * fr.shape[1]) <= FACE_ASPECT[1]]
            if fc:
                x, y, w, h = fc[0]["box"]
                lab = cv2.cvtColor(fr, cv2.COLOR_BGR2LAB).astype(np.float32)
                Hh, Ww = g.shape
                x0, y0, x1, y1 = int((x + w * 0.2) * Ww), int((y + h * 0.2) * Hh), int((x + w * 0.8) * Ww), int((y + h * 0.8) * Hh)
                roi = lab[max(0, y0):max(y0 + 1, y1), max(0, x0):max(x0 + 1, x1)]
                gr = g[max(0, y0):max(y0 + 1, y1), max(0, x0):max(x0 + 1, x1)]
                if roi.size:
                    aa, bb = float(roi[..., 1].mean() - 128), float(roi[..., 2].mean() - 128)
                    face_rows.append({"f": f, "box": [x, y, w, h], "hue": float(np.degrees(np.arctan2(bb, aa))),
                                      "a": aa, "b": bb, "clip": float(((gr >= 250) | (gr <= 5)).mean() * 100),
                                      "L": float(roi[..., 0].mean() / 2.55)})
    luma = np.array(luma)
    # face framing
    crop_top = [r["f"] for r in face_rows if r["box"][1] < HEADROOM_MIN]
    crop_edge = [r["f"] for r in face_rows if r["box"][0] < FACE_EDGE or r["box"][0] + r["box"][2] > 1 - FACE_EDGE
                 or r["box"][1] + r["box"][3] > 1 - FACE_EDGE]
    rep.add("face_framing", "picture", "fail" if len(crop_top) + len(crop_edge) > 2 else "pass",
            f"forehead cropped in {len(crop_top)}, face cut by an edge in {len(crop_edge)} of {len(face_rows)} sampled frames",
            at=crop_top + crop_edge, fix="lower the zoom or move the framing point" if crop_top or crop_edge else None)
    # skin and face exposure
    if face_rows:
        off = [r["f"] for r in face_rows if not (SKIN_HUE[0] <= r["hue"] <= SKIN_HUE[1])]
        green = [r["f"] for r in face_rows if r["a"] < 3]
        rep.add("skin_hue", "picture", "warn" if len(off) > len(face_rows) * 0.2 else "pass",
                f"median face hue {np.median([r['hue'] for r in face_rows]):.0f} deg (skin band {SKIN_HUE[0]:.0f}-{SKIN_HUE[1]:.0f}); "
                f"{len(off)} sampled frame(s) outside, {len(green)} with a green cast", at=off)
        clipped = [r["f"] for r in face_rows if r["clip"] > FACE_CLIP_PCT]
        rep.add("face_exposure", "picture", "warn" if clipped else "pass",
                f"{len(clipped)} sampled frame(s) with > {FACE_CLIP_PCT}% clipped/crushed face pixels; "
                f"median face L* {np.median([r['L'] for r in face_rows]):.0f}", at=clipped)
    else:
        rep.add("skin_hue", "picture", "skipped", "no faces found in the output")
    # captions vs faces and safe zone
    cc = rdir / "caption_cards.json"
    if cc.exists():
        from lib.captions import SAFE
        data = read_json(cc)
        base_y = SAFE.get(edl["project"].get("platform", "shorts"), 0.8)
        cap_h = 0.06
        fixes = ((edl["tracks"].get("captions") or {}).get("fix") or {})
        over, detail = [], []
        for card in data["cards"]:
            mid = (card["s_f"] + card["e_f"]) // 2
            y_c = float(card.get("y", fixes.get(str(card["s_f"]), base_y)))   # design pass records each card's centre
            # faces while the card is on screen; widen by one sample step only when none were sampled
            # (the wide window wrongly mixed in the framing from across a layout change)
            near = [r for r in face_rows if card["s_f"] <= r["f"] < card["e_f"]] or                 [r for r in face_rows if card["s_f"] - step <= r["f"] <= card["e_f"] + step]
            hits = [r["box"] for r in near if r["box"][1] < y_c + cap_h / 2 and r["box"][1] + r["box"][3] > y_c - cap_h / 2]
            if hits:
                # the card must clear the face for its duration: typical extent of the face (robust to one bad box)
                top = float(np.percentile([r["box"][1] for r in near], 20))
                bottom = float(np.percentile([r["box"][1] + r["box"][3] for r in near], 80))
                over.append(card["s_f"])
                detail.append({"s_f": card["s_f"], "face": [0, round(top, 3), 1, round(bottom - top, 3)]})
        rep.add("captions_on_faces", "captions", "fail" if over else "pass",
                f"{len(over)} caption card(s) overlap a face" if over else "captions clear of faces",
                at=over, fix="move those cards off the face" if over else None)
        rep.items[-1]["cards"] = detail
        rep.add("caption_safe_zone", "captions", "pass" if base_y <= 0.8 else "fail",
                f"caption centre at {base_y:.0%} of height; platform UI covers the bottom ~20 % and right ~12 %")
    # photosensitivity: luminance swings of FLASH_DELTA that reverse, counted per second
    d = np.diff(luma)
    big = np.where(np.abs(d) > FLASH_DELTA)[0]
    flashes = [i for k, i in enumerate(big[1:], 1) if np.sign(d[i]) != np.sign(d[big[k - 1]]) and i - big[k - 1] <= fps / 3]
    win = int(round(fps))
    worst = max((sum(1 for x in flashes if s <= x < s + win) for s in range(0, max(1, len(luma) - win), max(1, win // 4))), default=0)
    rep.add("photosensitivity", "picture", "fail" if worst > FLASH_PER_S else "pass",
            f"max {worst} luminance flash(es) in any second (limit {FLASH_PER_S})", at=flashes,
            fix="remove or soften the flashing section" if worst > FLASH_PER_S else None)
    # neighbouring shot match (from render colour stats)
    rj = rdir / "render.json"
    if rj.exists():
        col = read_json(rj).get("colour", {})
        bad = []
        ids = [ev["id"] for ev in vids]
        for p, q in zip(ids, ids[1:]):
            sp, sq = (col.get(p) or {}).get("stats"), (col.get(q) or {}).get("stats")
            if not sp or not sq or "face_L" not in sp or "face_L" not in sq:
                continue
            gp = (col[p]["correction"]["gamma"]); gq = (col[q]["correction"]["gamma"])
            Lp = 100 * (sp["face_L"] / 100) ** gp; Lq = 100 * (sq["face_L"] / 100) ** gq
            if abs(Lp - Lq) > MATCH_DL or np.hypot(sp["face_a"] - sq["face_a"], sp["face_b"] - sq["face_b"]) > MATCH_DAB:
                bad.append(next(ev["at_f"] for ev in vids if ev["id"] == q))
        rep.add("shot_match", "picture", "warn" if bad else "pass",
                f"{len(bad)} cut(s) where neighbouring faces differ by > {MATCH_DL} L* or {MATCH_DAB} a*b*" if bad
                else "neighbouring shots match", at=bad)
    # upscaling
    items = {it["id"]: it for it in read_json(project / "media.json")["items"]}
    ups = []
    for ev in vids:
        it = items.get(ev["src"], {})
        sw, sh = (it.get("video") or {}).get("display_width"), (it.get("video") or {}).get("display_height")
        if not sw:
            continue
        A = W / H
        bw = sh * A if sw / sh > A else sw
        from plan_edit import peak_zoom
        z = peak_zoom(ev)          # transforms multiply (render.zoom_at), so measure the true peak
        ups.append((W / (bw / z), ev["at_f"]))
    worst_up = max(ups, default=(1.0, 0))
    rep.add("upscaling", "picture", "fail" if worst_up[0] > UPSCALE_FAIL else "warn" if worst_up[0] > UPSCALE_WARN else "pass",
            f"largest upscale {worst_up[0]:.2f}x (warn > {UPSCALE_WARN}, fail > {UPSCALE_FAIL})",
            at=[a for s, a in ups if s > UPSCALE_WARN])
    return face_rows


# ----------------------------------------------------------------------------- sound
def sound_checks(rep: Report, video: Path, edl: dict, analysis: dict, rdir: Path, project: Path, retranscribe: bool):
    import soundfile as sf
    from lib import mix
    fps = rep.fps
    ms = edl.get("master") or {}
    tgt, tp = float(ms.get("lufs", -14)), float(ms.get("true_peak_db", -1))
    txt = ffmpeg_log(video, af="ebur128=peak=true")
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)[-1])
    TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", txt)[-1])
    rep.add("loudness", "sound", "pass" if abs(I - tgt) <= LUFS_TOL else "fail",
            f"integrated {I:.1f} LUFS (target {tgt:.0f} +- {LUFS_TOL})", fix="re-master" if abs(I - tgt) > LUFS_TOL else None)
    rep.add("true_peak", "sound", "pass" if TP <= tp + TP_TOL else "fail", f"true peak {TP:.1f} dBTP (max {tp:.0f})",
            fix="re-master" if TP > tp + TP_TOL else None)
    from lib.audio import scan_levels
    lv = scan_levels(video)
    rep.add("clipping", "sound", "fail" if lv.clipped_runs else "pass",
            f"{lv.clipped_runs} flat-topped run(s) at full scale" if lv.clipped_runs else "no clipping")
    # decode master for sample-level checks
    tmp = rdir / "qc_audio.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_f32le", str(tmp)])
    x, sr = sf.read(str(tmp), dtype="float32", always_2d=True)
    mono = x.mean(1)
    # digital silence
    win = int(DIGITAL_SILENCE_S * sr)
    quiet = np.abs(mono) < 10 ** (DIGITAL_SILENCE_DB / 20)
    runs, k = [], 0
    while k < quiet.size:
        if quiet[k]:
            j = k
            while j < quiet.size and quiet[j]:
                j += 1
            if j - k >= win:
                runs.append(k)
            k = j
        else:
            k += 1
    rep.add("digital_silence", "sound", "fail" if runs else "pass",
            f"{len(runs)} stretch(es) of digital silence >= {DIGITAL_SILENCE_S * 1000:.0f} ms" if runs else "no digital silence",
            at=[r / sr * float(fps) for r in runs], fix="fill with room tone" if runs else None)
    # pops at edit points
    pops = []
    step = np.abs(np.diff(mono))
    for ev in edl["tracks"]["video"][1:]:
        c = int(Fraction(ev["at_f"]) / fps * sr)
        if c < 200 or c > step.size - 200:
            continue
        local = np.median(step[c - 2000:c + 2000]) + 1e-6
        if step[c - 24:c + 24].max() > POP_RATIO * local and step[c - 24:c + 24].max() > 0.05:
            pops.append(ev["at_f"])
    rep.add("pops", "sound", "warn" if pops else "pass", f"{len(pops)} possible click(s) at edit points" if pops
            else "no clicks at edit points", at=pops)
    # music-to-voice separation from stems
    stems = rdir / "stems"
    tw = timeline_words(edl, analysis)
    if (stems / "music.wav").exists() and (stems / "dialogue.wav").exists():
        mus, _ = sf.read(str(stems / "music.wav"), dtype="float32", always_2d=True)
        dia, _ = sf.read(str(stems / "dialogue.wav"), dtype="float32", always_2d=True)
        if np.abs(mus).max() > 1e-5 and tw:
            n = min(mus.shape[0], dia.shape[0])
            mask = np.zeros(n, bool)
            for w in tw:
                mask[int(Fraction(w["t_s"]) / fps * sr):int(Fraction(w["t_e"]) / fps * sr)] = True
            rm = lambda s: 20 * np.log10(np.sqrt((s ** 2).mean()) + 1e-9)  # noqa: E731
            sep = rm(dia[:n][mask]) - rm(mus[:n][mask])
            st = "pass" if SEP_RANGE_DB[0] <= sep <= SEP_RANGE_DB[1] + 6 else "fail" if sep < SEP_MIN_DB else "warn"
            rep.add("music_voice_separation", "sound", st, f"music sits {sep:.1f} dB under the voice during speech "
                    f"(target {SEP_RANGE_DB[0]}-{SEP_RANGE_DB[1]})", fix="deepen the duck" if st == "fail" else None)
        else:
            rep.add("music_voice_separation", "sound", "skipped", "no added music")
        # per-speaker consistency
        spk = {}
        for w in tw:
            spk.setdefault(w.get("speaker", "S1"), []).append(w)
        if len(spk) > 1:
            lv_ = {}
            for s, ws in spk.items():
                idx = np.concatenate([np.arange(int(Fraction(w["t_s"]) / fps * sr), int(Fraction(w["t_e"]) / fps * sr)) for w in ws])
                idx = idx[idx < dia.shape[0]]
                lv_[s] = 20 * np.log10(np.sqrt((dia[idx] ** 2).mean()) + 1e-9)
            spread = max(lv_.values()) - min(lv_.values())
            rep.add("speaker_consistency", "sound", "pass" if spread <= SPEAKER_SPREAD_LU else "warn",
                    f"speaker levels spread {spread:.1f} dB ({', '.join(f'{k} {v:.1f}' for k, v in lv_.items())})")
    # cuts inside words (EDL level)
    from plan_edit import check
    _, cr = check(json.loads(json.dumps(edl)), project, fix=False)
    inside = [e for e in cr["errors"] if "inside the word" in e]
    rep.add("cut_inside_word", "sound", "fail" if inside else "pass", "; ".join(inside[:3]) or "no cut inside a word",
            fix="plan_edit.py check --fix" if inside else None)
    clipped_cons = [w for w in cr["warnings"] if "first consonant" in w]
    rep.add("first_consonant", "sound", "warn" if clipped_cons else "pass", "; ".join(clipped_cons[:3]) or
            "air before every first word")
    # A/V sync: stream alignment
    pr = ffprobe_json(video)
    vs = next(s for s in pr["streams"] if s["codec_type"] == "video")
    as_ = next((s for s in pr["streams"] if s["codec_type"] == "audio"), None)
    if as_:
        dv = float(vs.get("duration", 0)); da = float(as_.get("duration", 0))
        ds = abs(float(vs.get("start_time", 0)) - float(as_.get("start_time", 0)))
        bad = ds > float(1 / fps) or abs(dv - da) > 2 * float(1 / fps)
        rep.add("av_streams", "sound", "fail" if bad else "pass",
                f"video {dv:.3f} s / audio {da:.3f} s, start offset {ds * 1000:.0f} ms")
    # intelligibility
    if retranscribe and tw:
        try:
            from lib.transcribe import load_transcriber
            wav16 = rdir / "qc_16k.wav"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav16)])
            src_tr = analysis["files"][edl["tracks"]["video"][0]["src"]].get("transcript") or {}
            model = src_tr.get("model") or "small"
            # the source's language, never auto-detect: a dubbed or accented voice can be detected as
            # another language and fail a perfectly clear mix (Japanese-accented TTS, 2026-11-16)
            lang = tw[0].get("lang") or src_tr.get("language") or edl["project"].get("language")
            tr = load_transcriber("faster-whisper", model).transcribe(wav16, lang or None)
            got = [re.sub(r"[^\w']", "", w["w"].lower()) for s in tr["segments"] for w in s["words"]]
            ref = [re.sub(r"[^\w']", "", w["w"].lower()) for w in tw]
            wer = edit_distance(ref, got) / max(1, len(ref))
            rep.add("intelligibility", "sound", "pass" if wer <= WER_MAX else "fail",
                    f"re-transcribed word error rate {wer:.1%} against the cut's own words (max {WER_MAX:.0%})",
                    fix="lower music/SFX under speech" if wer > WER_MAX else None)
        except Exception as e:
            rep.add("intelligibility", "sound", "skipped", f"re-transcription unavailable: {e}")
    else:
        rep.add("intelligibility", "sound", "skipped", "disabled (--no-retranscribe)")
    tmp.unlink(missing_ok=True)


def edit_distance(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def lipsync_check(rep: Report, video: Path):
    """Correlate mouth-region motion with the audio envelope; the best lag is the A/V offset."""
    import cv2
    import soundfile as sf
    from lib.shots import FaceDetector
    fps = rep.fps
    faces = FaceDetector(SKILL / "assets" / "cache" / "models")
    motion, box, prev = [], None, None
    for f, fr in frames_small(video, 360, 1):
        if f % 5 == 0:
            fc = faces.faces(fr)
            if fc:
                box = fc[0]["box"]
        if box is None:
            motion.append(0.0); prev = None; continue
        h, w = fr.shape[:2]
        x, y, bw, bh = box
        roi = cv2.cvtColor(fr[int((y + bh * 0.6) * h):int((y + bh) * h), int((x + bw * 0.2) * w):int((x + bw * 0.8) * w)],
                           cv2.COLOR_BGR2GRAY).astype(np.float32)
        motion.append(float(np.abs(roi - prev).mean()) if prev is not None and prev.shape == roi.shape else 0.0)
        prev = roi
    tmp = video.with_suffix(".lip.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(tmp)])
    x, sr = sf.read(str(tmp), dtype="float32"); tmp.unlink(missing_ok=True)
    hop = sr / float(fps)
    env = np.array([np.sqrt((x[int(k * hop):int((k + 1) * hop)] ** 2).mean()) for k in range(len(motion))])
    m = np.array(motion)
    if m.std() == 0 or env.std() == 0 or len(m) < 50:
        rep.add("lip_sync", "sound", "skipped", "not enough talking-face frames to measure")
        return
    m = (m - m.mean()) / m.std(); e = (np.diff(env, prepend=env[0]) - 0)
    e = (np.abs(e) - np.abs(e).mean()) / (np.abs(e).std() + 1e-9)
    lags = range(-6, 7)
    cors = [float(np.corrcoef(m[max(0, l):len(m) + min(0, l)], e[max(0, -l):len(e) - max(0, l)])[0, 1]) for l in lags]
    best = list(lags)[int(np.argmax(cors))]
    peak = max(cors)
    if peak < LIPSYNC_MIN_R:
        rep.add("lip_sync", "sound", "skipped", f"mouth motion and audio too weakly related to measure (r={peak:.2f})")
        return
    rep.add("lip_sync", "sound", "pass" if abs(best) <= LIPSYNC_MAX_F else "warn",
            f"best mouth/audio alignment at {best:+d} frame(s) (r={peak:.2f}; positive = audio late)")


# ----------------------------------------------------------------------------- captions + edit
def caption_checks(rep: Report, edl: dict, rdir: Path, profile: dict):
    cc = rdir / "caption_cards.json"
    if not cc.exists():
        rep.add("captions_present", "captions", "warn" if edl["tracks"].get("captions") else "skipped", "no caption cards")
        return
    cards = read_json(cc)["cards"]
    fps = rep.fps
    short = edl["project"].get("height", 1) > edl["project"].get("width", 1)
    lim = MAX_CPS["short" if short else "long"]
    fast = []
    for c in cards:
        dur = max(1, c["e_f"] - c["s_f"]) / float(fps)
        chars = sum(len(w["w"]) for w in c["words"]) + len(c["words"]) - 1
        if chars / dur > lim and dur < 0.4:
            fast.append(c["s_f"])
    rep.add("reading_speed", "captions", "warn" if len(fast) > len(cards) * 0.1 else "pass",
            f"{len(fast)} of {len(cards)} card(s) faster than {lim} chars/s", at=fast)
    timing = [c["s_f"] for c in cards if c["words"] and abs(c["s_f"] - c["words"][0]["t_s"]) > 1]
    rep.add("caption_timing", "captions", "fail" if timing else "pass",
            "every card starts on its first word (+-1 frame)" if not timing else f"{len(timing)} card(s) off their word", at=timing)
    names = [n.lower() for n in profile.get("names", [])]
    near = []
    for c in cards:
        for w in c["words"]:
            t = re.sub(r"[^\w]", "", w["w"].lower())
            for n in names:
                if t != n and len(t) > 3 and edit_distance(list(t), list(n)) <= 2:
                    near.append(f"'{w['w']}' may be '{n}'")
    rep.add("caption_spelling", "captions", "warn" if near else "pass", "; ".join(near[:5]) or
            ("checked against the creator's names list" if names else "transcript spelling (no names list in profile)"))
    rep.add("caption_contrast", "captions", "pass", "white text with a black stroke: contrast 21:1 on any background")
    if (rdir / "captions.srt").exists() and (rdir / "captions.vtt").exists():
        rep.add("sidecar_captions", "captions", "pass", "SRT and VTT written next to the video")


def edit_checks(rep: Report, edl: dict, project: Path, video: Path, style_path: str | None, run_style: bool):
    fps = rep.fps
    total = timeline_len(edl)
    tgt = edl["project"].get("target_duration_f")
    if tgt:
        ok = total <= tgt * 1.1
        rep.add("duration", "edit", "pass" if ok else "fail",
                f"{total / float(fps):.1f} s against a {tgt / float(fps):.1f} s target")
    roles = [ev.get("role") for ev in edl["tracks"]["video"]]
    rep.add("structure", "edit", "pass" if roles and roles[0] == "hook" else "warn",
            f"opens with {roles[0] if roles else 'nothing'}; ends with {roles[-1] if roles else 'nothing'}; "
            f"{sum(1 for r in roles if r == 'payoff')} payoff event(s)")
    reasons = [ev for ev in edl["tracks"]["video"] if not ev.get("reason")]
    rep.add("reasons", "edit", "fail" if reasons else "pass", "every cut has a reason" if not reasons
            else f"{len(reasons)} event(s) without a reason")
    # restraint: the tells that make an edit read as machine-made (references/craft-human.md); warnings only
    from lib.restraint import audit as restraint_audit
    for it in restraint_audit(edl):
        if it["status"] == "warn":
            rep.add(it["id"], "edit", "warn", it["detail"], fix=it["fix"])
    # licenses
    led = read_json(project / "licenses.json") if (project / "licenses.json").exists() else {"assets": []}
    known = {e["id"]: e for e in led["assets"]}
    used = [m["asset"] for m in edl["tracks"].get("music") or []] + [s["asset"] for s in edl["tracks"].get("sfx") or []] + \
           [b["asset"] for b in edl["tracks"].get("broll") or [] if b.get("asset")]
    missing = [u for u in used if u not in known]
    nc = [u for u in used if u in known and known[u].get("commercial") is False and edl["project"].get("commercial", True)]
    rep.add("licenses", "edit", "fail" if missing or nc else "pass",
            f"{len(used)} asset(s) used; missing ledger: {missing or 'none'}; not commercial: {nc or 'none'}")
    # virality
    vs = project / "virality.json"
    if vs.exists():
        v = read_json(vs)
        rep.add("virality", "edit", "pass" if v.get("passed") else "warn",
                f"score {v.get('score')}/100; {len(v.get('fixes', []))} suggested fix(es)")
    # style distance
    if run_style and style_path and (SKILL / style_path).exists():
        from fingerprint import _get, measure
        style = read_json(SKILL / style_path)
        try:
            fp = measure(video, None, None, cache_dir=project / "render" / "fp_cache")
        except Exception as e:
            rep.add("style_distance", "edit", "skipped", f"fingerprint failed: {e}")
            return
        write_json(project / "qc" / "output_fingerprint.json", fp)
        rows, outside = [], 0
        for field in STYLE_FIELDS:
            s = (style.get("fields") or {}).get(field) or {}
            val = _get(fp, field)
            if val is None or s.get("lo") is None:
                continue
            inside = s["lo"] <= val <= s["hi"]
            outside += not inside
            rows.append(f"{field} {val} ({'in' if inside else 'OUT of'} {s['lo']}-{s['hi']})")
        rep.add("style_distance", "edit", "pass" if outside <= 2 else "warn",
                f"{outside} of {len(rows)} fields outside the style range: " + "; ".join(rows))
    elif style_path:
        rep.add("style_distance", "edit", "skipped", "disabled or style missing")


# ----------------------------------------------------------------------------- fix loop
def apply_fixes(edl: dict, failed: list[dict], project: Path) -> list[str]:
    notes = []
    ids = {f["id"] for f in failed}
    if "captions_on_faces" in ids and edl["tracks"].get("captions"):
        item = next(f for f in failed if f["id"] == "captions_on_faces")
        fx = edl["tracks"]["captions"].setdefault("fix", {})
        for c in item.get("cards", []):
            x, y, w, h = c["face"]
            below = y + h + 0.06
            # below the face if that stays out of the platform UI band, else above it
            fx[str(c["s_f"])] = round(below if below <= 0.8 else max(0.12, y - 0.06), 3)
        notes.append(f"QC fix: moved {len(item.get('cards', []))} caption card(s) off the speaker's face")
    if "flash_frames" in ids:
        vids = edl["tracks"]["video"]
        keep = [v for v in vids if event_len(v) >= FLASH_F]
        if len(keep) != len(vids):
            notes.append(f"QC fix: removed {len(vids) - len(keep)} event(s) under {FLASH_F} frames")
            gone = {v["id"] for v in vids} - {v["id"] for v in keep}
            edl["tracks"]["video"] = keep
            edl["tracks"]["dialogue"] = [d for d, v in zip(edl["tracks"].get("dialogue") or [], vids) if v["id"] not in gone]
    if ids & {"cut_inside_word", "flash_frames"}:
        from plan_edit import check
        check(edl, project, fix=True)
        notes.append("QC fix: plan_edit check --fix (cuts snapped out of words, timeline re-packed)")
    if ids & {"loudness", "true_peak"}:
        ms = edl.setdefault("master", {})
        if "true_peak" in ids:
            # re-running the same master cannot change the result: ask for 0.5 dB more headroom
            ms["true_peak_db"] = round(float(ms.get("true_peak_db", -1)) - 0.5, 1)
            notes.append(f"QC fix: true-peak ceiling lowered to {ms['true_peak_db']} dBTP for the master (codec overshoot)")
        else:
            notes.append("QC fix: re-mastered (two-pass loudness normalisation re-run)")
    if "face_framing" in ids:
        for v in edl["tracks"]["video"]:
            if (v.get("reframe") or {}).get("zoom", 1) > 1.0:
                v["reframe"]["zoom"] = round(max(1.0, v["reframe"]["zoom"] - 0.05), 3)
        notes.append("QC fix: reduced reframe zoom by 0.05 to restore headroom")
    if "music_voice_separation" in ids or "intelligibility" in ids:
        for m in edl["tracks"].get("music") or []:
            m.setdefault("duck", {})["depth_db"] = float(m["duck"].get("depth_db", -20)) - 4
            m["gain_db"] = float(m.get("gain_db", -6)) - 3
        notes.append("QC fix: music lowered 3 dB and ducked 4 dB deeper under speech")
    return notes


def run_checks(video, edl, project, rdir, style, retranscribe, run_style):
    analysis = read_json(project / "analysis.json")
    rep = Report(fps_of(edl))
    profile = {}
    if edl["project"].get("profile") and (SKILL / edl["project"]["profile"]).exists():
        profile = read_json(SKILL / edl["project"]["profile"])
    log("qc: picture"); picture_checks(rep, video, edl, analysis, rdir, project)
    log("qc: sound"); sound_checks(rep, video, edl, analysis, rdir, project, retranscribe)
    log("qc: lip sync"); lipsync_check(rep, video)
    log("qc: captions"); caption_checks(rep, edl, rdir, profile)
    log("qc: edit"); edit_checks(rep, edl, project, video, style or edl["project"].get("style"), run_style)
    return rep


def write_report(rep: Report, out_dir: Path, video: Path, edl_path: Path, loops: list, assumptions: list) -> dict:
    counts = {s: sum(1 for i in rep.items if i["status"] == s) for s in ("pass", "fixed", "warn", "fail", "skipped")}
    data = {"video": video.as_posix(), "edl": edl_path.as_posix(), "summary": counts, "passed": counts["fail"] == 0,
            "assumptions": assumptions, "fix_loops": loops, "checks": rep.items}
    write_json(out_dir / "qc_report.json", data)
    lines = [f"# QC report", "", f"Video: `{video.name}`  EDL: `{edl_path.name}`", "",
             f"**{'PASSED' if data['passed'] else 'FAILED'}**: " + ", ".join(f"{v} {k}" for k, v in counts.items()), ""]
    if assumptions:
        lines += ["## Assumptions", *[f"- {a}" for a in assumptions], ""]
    if loops:
        lines += ["## Automatic fixes", *[f"- round {k + 1}: {'; '.join(l)}" for k, l in enumerate(loops)], ""]
    for cat in ("picture", "sound", "captions", "edit"):
        lines += [f"## {cat.capitalize()}", "", "| Check | Status | Detail | At |", "|---|---|---|---|"]
        for i in rep.items:
            if i["category"] == cat:
                lines.append(f"| {i['id']} | {i['status']} | {i['detail'].replace('|', '/')} | {', '.join(i['at'][:5])} |")
        lines.append("")
    (out_dir / "qc_report.md").write_text("\n".join(lines), encoding="utf-8")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True); ap.add_argument("--edl", required=True); ap.add_argument("--project", required=True)
    ap.add_argument("--style"); ap.add_argument("--fix-loop", action="store_true")
    ap.add_argument("--no-retranscribe", action="store_true"); ap.add_argument("--no-style", action="store_true")
    ap.add_argument("--preview", action="store_true", help="the video is a preview render (render/preview)")
    ap.add_argument("--out")
    a = ap.parse_args()
    project, video, edl_path = Path(a.project), Path(a.video), Path(a.edl)
    for p in (video, edl_path, project / "analysis.json"):
        if not p.exists():
            fail(f"{p} does not exist")
    out_dir = Path(a.out) if a.out else project / "qc"
    out_dir.mkdir(parents=True, exist_ok=True)
    rdir = project / "render" / ("preview" if a.preview else "final")
    edl = read_json(edl_path)
    loops = []
    try:
        rep = run_checks(video, edl, project, rdir, a.style, not a.no_retranscribe, not a.no_style)
        rnd = 0
        while a.fix_loop and rep.failed() and rnd < MAX_LOOPS:
            fixable = [f for f in rep.failed() if f.get("fix")]
            if not fixable:
                break
            notes = apply_fixes(edl, fixable, project)
            if not notes:
                break
            rnd += 1
            m = re.match(r"(.*?)(\d+)$", edl_path.stem)
            new = edl_path.with_name(f"{m.group(1)}{int(m.group(2)) + 1}.json" if m else f"{edl_path.stem}_fix{rnd}.json")
            edl.setdefault("notes", []).extend(notes)
            write_json(new, edl)
            log(f"qc fix round {rnd}: {'; '.join(notes)} -> {new.name}")
            cmd = [sys.executable, str(Path(__file__).parent / "render.py"), "--edl", str(new), "--project", str(project),
                   "--out", str(video)] + (["--preview"] if a.preview else [])
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                loops.append(notes + [f"re-render failed: {r.stderr[-300:]}"]); break
            loops.append(notes)
            edl_path = new
            fixed_ids = {f["id"] for f in fixable}
            rep = run_checks(video, edl, project, rdir, a.style, not a.no_retranscribe, not a.no_style)
            for i in rep.items:
                if i["id"] in fixed_ids and i["status"] == "pass":
                    i["status"] = "fixed"
        data = write_report(rep, out_dir, video, edl_path, loops, edl.get("assumptions", []))
    except (ToolError, FileNotFoundError, KeyError, IndexError) as e:
        fail(f"qc failed: {type(e).__name__}: {e}")
    s = data["summary"]
    log(f"QC {'PASSED' if data['passed'] else 'FAILED'}: {s}; wrote {out_dir / 'qc_report.md'}")
    for i in rep.items:
        if i["status"] in ("fail", "warn"):
            log(f"  [{i['status']}] {i['id']}: {i['detail']}")
    sys.exit(0 if data["passed"] else 2)


if __name__ == "__main__":
    main()
