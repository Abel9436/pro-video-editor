#!/usr/bin/env python3
"""Stage 3 - Analyze. Everything Claude needs to make editorial decisions, measured in code.

Usage:
  python scripts/analyze.py --project PROJECT_DIR [options]

Reads PROJECT/media.json (from ingest.py). Writes:
  PROJECT/analysis.json                transcript, speakers, speech features, shots, audio, music
  PROJECT/analysis/transcript_<id>.md  readable transcript with word indices for the paper edit
  PROJECT/analysis/keyframes/          1-3 JPEGs per shot
  PROJECT/analysis/contact/            contact sheets (one image = up to 36 shots)

All times are integer frames at the timeline rate in media.json. Each part is
cached by file hash, so re-running after adding footage only analyses new files.

Perception budget: contact sheets are the images Claude is expected to view.
Their count is kept at or below --max-images by enlarging the grid, then by
sampling shots evenly; analysis.json reports exactly what was sampled.
"""
from __future__ import annotations

import argparse
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from lib.common import Cache, ToolError, fail, log, read_json, rel, write_json  # noqa: E402
from lib.timebase import parse_rate, rate_str, timecode  # noqa: E402

ANALYZE_VERSION = 2
DEFAULT_MAX_IMAGES = 24      # STARTING DEFAULT perception budget per analysis run
SPEECH_MERGE_S = Fraction(3, 10)   # words closer than 0.3 s form one speech span
MUSIC_SPEECH_RATIO = 0.25    # files with less speech than this get music/beat analysis
EMPHASIS_KEEP = 60           # emphasis peaks reported per file, strongest first


def words_to_frames(tr: dict, fps: Fraction) -> tuple[list[dict], list[dict]]:
    words, segs = [], []
    for s in tr.get("segments", []):
        i0 = len(words)
        for w in s["words"]:
            sf = round(Fraction(w["start"]).limit_denominator(10**6) * fps)
            ef = max(sf + 1, round(Fraction(w["end"]).limit_denominator(10**6) * fps))
            words.append({"i": len(words), "w": w["w"], "s_f": sf, "e_f": ef, "p": w["p"]})
        if len(words) > i0:
            segs.append({"i_from": i0, "i_to": len(words) - 1, "s_f": words[i0]["s_f"], "e_f": words[-1]["e_f"],
                         "text": s["text"]})
    return words, segs


def speech_spans(words: list[dict], fps: Fraction) -> list[tuple[int, int]]:
    gap = int(SPEECH_MERGE_S * fps)
    spans: list[list[int]] = []
    for w in words:
        if spans and w["s_f"] - spans[-1][1] <= gap:
            spans[-1][1] = max(spans[-1][1], w["e_f"])
        else:
            spans.append([w["s_f"], w["e_f"]])
    return [(a, b) for a, b in spans]


def pitch_per_frame(x: np.ndarray, sr: int, fps: Fraction, n_frames: int) -> np.ndarray | None:
    try:
        import librosa
        f0 = librosa.yin(x, fmin=70, fmax=400, sr=sr, frame_length=1024, hop_length=160)
    except Exception:
        return None
    # yin returns a value for unvoiced frames too; gate by energy so silence reads 0
    rms = librosa.feature.rms(y=x, frame_length=1024, hop_length=160)[0][: f0.size]
    f0 = np.where(rms > np.percentile(rms, 40), f0, 0)
    idx = np.clip((np.arange(n_frames) / float(fps) * sr / 160).astype(int), 0, f0.size - 1)
    return f0[idx]


def write_readable_transcript(path: Path, fid: str, words: list[dict], sents: list[dict], fillers: list[dict],
                              fps: Fraction) -> None:
    filler_idx = {f["i"] for f in fillers if f["kind"] == "hard"}
    lines = [f"# Transcript: {fid}", "",
             "Format: `[#first-word-index timecode speaker]` sentence. {braces} mark hard fillers.", ""]
    for s in sents:
        toks = [("{" + w["w"] + "}") if w["i"] in filler_idx else w["w"]
                for w in words[s["i_from"]:s["i_to"] + 1]]
        lines.append(f"[#{s['i_from']} {timecode(s['s_f'], fps)} {s.get('speaker') or 'S?'}] {' '.join(toks)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="project folder containing media.json")
    ap.add_argument("--transcriber", default="faster-whisper",
                    help="faster-whisper | none | package.module:ClassName (default faster-whisper)")
    ap.add_argument("--model", default="small", help="Whisper model size: tiny, base, small, medium, large-v3")
    ap.add_argument("--device", default="auto", help="auto | cpu | cuda")
    ap.add_argument("--language", help="ISO 639-1 code (en, am, om...). Omit to auto-detect")
    ap.add_argument("--vocab", help="text file, one name or term per line, to bias spelling")
    ap.add_argument("--speakers", type=int, help="known number of speakers (improves diarization)")
    ap.add_argument("--max-images", type=int, default=DEFAULT_MAX_IMAGES,
                    help=f"perception budget: contact sheets Claude will view (default {DEFAULT_MAX_IMAGES})")
    ap.add_argument("--only", nargs="*", help="analyse only these media ids")
    args = ap.parse_args()

    project = Path(args.project)
    media = read_json(project / "media.json")
    fps = parse_rate(media["fps"])
    cache = Cache(project / "cache")
    out_root = project / "analysis"
    out_root.mkdir(parents=True, exist_ok=True)
    vocab = [l.strip() for l in Path(args.vocab).read_text(encoding="utf-8").splitlines() if l.strip()] \
        if args.vocab else []

    from lib.audio import ANALYSIS_SR, load_wav
    from lib.diarize import assign_words, diarize_loudest_mic, diarize_mfcc, diarize_pyannote
    from lib.music import analyze_music, loudness_r128, noise_floor_db
    from lib.shots import FaceDetector, detect_shots, measure_shots
    from lib.speech import (find_emphasis, find_false_starts, find_fillers, find_gaps, find_laughter_tokens,
                            find_retakes, frame_rms_db, sentences)

    items = [it for it in media["items"] if not args.only or it["id"] in args.only]
    by_id = {it["id"]: it for it in media["items"]}
    # In a sync group, transcribe only the anchor; members point at it with their offset.
    member_of = {m["id"]: g for g in media.get("sync_groups", []) for m in g["members"]}

    transcriber = None
    warnings: list[str] = []
    faces = None
    files: dict = {}
    levels_cache: dict = {}

    def levels(it):
        if it["id"] not in levels_cache:
            x, sr = load_wav(project / it["wav"])
            levels_cache[it["id"]] = (x, frame_rms_db(x, sr, fps))
        return levels_cache[it["id"]]

    for it in items:
        fid, digest = it["id"], it["hash"]
        rec: dict = {"kind": it["kind"], "duration_f": it["duration_f"]}
        log(f"analyse {fid}")

        # ---------------- audio-side analysis
        if it.get("wav"):
            x, lv = levels(it)
            rec["audio"] = {"noise_floor_db": noise_floor_db(x, ANALYSIS_SR),
                            **{k: v for k, v in (it.get("stats") or {}).items() if k in ("peak_dbfs", "clipped_pct")}}
            lk = {"v": ANALYZE_VERSION, "fps": media["fps"]}
            loud = cache.get(digest, "loudness", lk)
            if loud is None:
                try:
                    loud = cache.put(digest, "loudness", lk, loudness_r128(Path(it["render_src"]), fps))
                except ToolError as e:
                    loud = {"error": str(e)}
            rec["audio"]["loudness"] = loud

            g = member_of.get(fid)
            if g and g["anchor"] != fid:
                off = next(m["offset_f"] for m in g["members"] if m["id"] == fid)
                rec["transcript"] = {"ref": g["anchor"], "offset_f": off,
                                     "note": "same recording as the anchor; use its transcript shifted by offset_f"}
                words = []
            else:
                tk = {"v": ANALYZE_VERSION, "engine": args.transcriber, "model": args.model,
                      "lang": args.language, "vocab": vocab}
                tr = cache.get(digest, "transcript", tk)
                if tr is None:
                    if transcriber is None:
                        from lib.transcribe import TranscriberUnavailable, load_transcriber
                        try:
                            transcriber = load_transcriber(args.transcriber, args.model, args.device)
                        except TranscriberUnavailable as e:
                            fail(str(e))
                    log(f"  transcribe ({args.transcriber} {args.model})")
                    try:
                        tr = cache.put(digest, "transcript", tk,
                                       transcriber.transcribe(project / it["wav"], args.language, vocab))
                    except Exception as e:  # plugin errors must not be swallowed silently
                        fail(f"transcription of {fid} failed: {e}")
                if tr.get("warning"):
                    warnings.append(f"{fid}: {tr['warning']}")
                words, segs = words_to_frames(tr, fps)
                spans = speech_spans(words, fps)

                # ---------------- diarization
                turns, dmeta = None, None
                if args.transcriber != "none" and words:
                    pt = diarize_pyannote(str(project / it["wav"]), fps, args.speakers)
                    if pt is not None:
                        turns, dmeta = pt, {"method": "pyannote", "confidence": "high"}
                    elif g and len(g["members"]) > 1:
                        mem = [by_id[m["id"]] for m in g["members"] if by_id[m["id"]].get("wav")]
                        lvls = {m["id"]: levels(m)[1] for m in mem}
                        offs = {m["id"]: next(x["offset_f"] for x in g["members"] if x["id"] == m["id"]) for m in mem}
                        turns, dmeta = diarize_loudest_mic(lvls, offs, fps, spans)
                    else:
                        turns, dmeta = diarize_mfcc(x, ANALYSIS_SR, spans, fps, args.speakers)
                    assign_words(words, turns)
                    for s in segs:
                        s["speaker"] = words[s["i_from"]]["speaker"]

                lang = (tr.get("language") or "en")[:2]
                fillers = find_fillers(words, lang)
                fstarts = find_false_starts(words, fps)
                sents = sentences(words)
                retakes = find_retakes(sents, fillers, fstarts, fps)
                silences, breaths, nonspeech = find_gaps(words, lv, rec["audio"]["noise_floor_db"], fps,
                                                         it["duration_f"])
                pitch = pitch_per_frame(x, ANALYSIS_SR, fps, lv.size) if words else None
                emphasis = find_emphasis(words, lv, pitch)[:EMPHASIS_KEEP]
                speech_f = sum(b - a for a, b in spans)
                rec["transcript"] = {k: tr.get(k) for k in ("engine", "model", "language", "language_prob")}
                rec["transcript"].update({"words": words, "segments": segs, "sentences": sents})
                rec["speakers"] = {**(dmeta or {"method": "none"}), "turns": turns or []}
                rec["speech"] = {
                    "speech_ratio": round(speech_f / max(1, it["duration_f"]), 3),
                    "words_per_min": round(len(words) / max(1e-9, float(Fraction(speech_f) / fps) / 60), 1)
                    if speech_f else 0,
                    "fillers": fillers, "false_starts": fstarts, "retakes": retakes,
                    "silences": silences, "breaths": breaths,
                    "laughter": {"transcript_tokens": find_laughter_tokens(words),
                                 "nonspeech_candidates": nonspeech,
                                 "method": "transcript tokens + loud non-speech gaps (no laughter model)"},
                    "emphasis": emphasis,
                }
                if words:
                    write_readable_transcript(out_root / f"transcript_{fid}.md", fid, words, sents, fillers, fps)
                    rec["transcript"]["readable"] = rel(out_root / f"transcript_{fid}.md", project)

            # ---------------- music
            speech_ratio = rec.get("speech", {}).get("speech_ratio", 0)
            if it["kind"] == "audio" or (speech_ratio < MUSIC_SPEECH_RATIO and float(np.median(lv)) > -50):
                mk = {"v": ANALYZE_VERSION, "fps": media["fps"]}
                mus = cache.get(digest, "music", mk)
                if mus is None:
                    log("  music: beats, sections, energy")
                    mus = cache.put(digest, "music", mk, analyze_music(x, ANALYSIS_SR, fps))
                rec["music"] = mus

        # ---------------- picture-side analysis
        if it["kind"] == "video" and it.get("proxy"):
            sk = {"v": ANALYZE_VERSION, "fps": media["fps"]}
            shots = cache.get(digest, "shots", sk)
            kdir = out_root / "keyframes"
            if shots is None or any(not (project / k["path"]).exists()
                                    for s in shots["shots"] for k in s["keyframes"]):
                log("  shots, keyframes, faces, motion")
                if faces is None:
                    faces = FaceDetector(Path(__file__).resolve().parents[1] / "assets" / "cache" / "models")
                sh, method = detect_shots(project / it["proxy"], it["duration_f"])
                measure_shots(project / it["proxy"], sh, fps, kdir, fid, faces)
                for s_ in sh:  # cache and output hold project-relative paths, never cwd-relative
                    for k in s_["keyframes"]:
                        k["path"] = rel(k["path"], project)
                shots = cache.put(digest, "shots", sk, {"method": method, "shots": sh})
            rec["shot_method"] = shots["method"]
            rec["shots"] = shots["shots"]
        files[fid] = rec

    # --only re-analyses some files: keep the other files' results from the previous run
    prev_path = project / "analysis.json"
    if args.only and prev_path.exists():
        prev = read_json(prev_path)
        if prev.get("fps") == media["fps"]:
            current = {it["id"] for it in media["items"]}
            files = {**{k: v for k, v in prev["files"].items() if k in current and k not in files}, **files}

    # ---------------- perception budget: contact sheets
    from lib.shots import contact_sheets
    shots_by_file = {fid: r["shots"] for fid, r in files.items() if r.get("shots")}
    perception = contact_sheets(shots_by_file, fps, project, out_root / "contact", args.max_images) \
        if shots_by_file else {"limit": args.max_images, "images": [], "count": 0}

    analysis = {"version": 1, "fps": rate_str(fps), "files": files, "perception": perception,
                "warnings": warnings}
    out = write_json(project / "analysis.json", analysis)
    n_words = sum(len(r.get("transcript", {}).get("words", [])) for r in files.values())
    n_shots = sum(len(r.get("shots", [])) for r in files.values())
    log(f"wrote {out}: {len(files)} files, {n_words} words, {n_shots} shots, "
        f"{perception['count']} contact sheet(s) for Claude to view"
        f"{' (sampled)' if perception.get('sampled') else ''}")
    for w in warnings:
        log(f"  warning: {w}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ToolError as e:
        fail(str(e))
    except FileNotFoundError as e:
        fail(str(e))
