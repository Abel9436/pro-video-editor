#!/usr/bin/env python3
"""Build the delivery package for a rendered EDL.

Usage:
  python scripts/package.py --edl P/edl/v2.json --project P [--copy P/copy.json] [--out-dir P/package]
                            [--repurpose 8] [--no-video]

Writes P/package/<edl name>/:
  video.mp4, captions .srt/.vtt   the render (final if present, else preview) and its caption files
  titles.txt                      5 title options
  description.txt                 description with chapters (long form) and credits
  tags.txt                        up to 15 tags
  thumbnails/thumb_N.jpg          3-5 frame candidates (clear face, sharp, expression), from the
                                  caption-free picture pass
  credits.txt                     from project/licenses.json, only assets the EDL uses, with the
                                  exact attribution each license asks for
  presets.json                    export presets for the target and sibling platforms
  disclosure.json                 whether a platform AI/synthetic-content label is needed, and why
  qc_report.md                    copied from the last QC run of this EDL
  package.json                    index of all of the above
--copy: titles and description lines written by Claude (JSON {"titles": [...], "description": "...",
  "tags": [...]}). Without it the script writes drafts from the transcript, marked as drafts:
  wording a title is a judgment call; the script only supplies material.
--repurpose N: for a source longer than 2 minutes, propose N self-contained shorts (each opening on
  its own hook sentence) as paper edits in P/edl/short_K_paper.json for approval; render approved
  ones with plan_edit.py + render.py.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.common import fail, log, read_json, write_json  # noqa: E402
from lib.edl import fps_of, timeline_len, timeline_words, words_by_src  # noqa: E402
from lib.speech import STOPWORDS, sentences  # noqa: E402
from lib.viral import hook_features  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
N_TITLES, N_TAGS, N_THUMBS = 5, 15, 5
THUMB_SPACING_S = 2.0          # candidates at least this far apart, so they differ
# YouTube chapters: first at 0:00, at least 3, each at least 10 s (YouTube Help, "Video chapters").
CHAPTER_MIN, CHAPTER_MIN_S = 3, 10
REPURPOSE_MIN_SOURCE_S = 120
SHORT_MIN_S, SHORT_MAX_S = 20, 55   # STARTING DEFAULT length of a repurposed short
# Export presets. Sizes and audio follow each platform's upload guidance; bitrates are STARTING
# DEFAULTS (high enough that the platform's own re-encode is the only lossy step that matters).
PRESETS = {
    "shorts":   {"size": [1080, 1920], "codec": "h264", "video_kbps": 16000, "audio": "aac 48k 320k", "lufs": -14, "max_s": 180},
    "tiktok":   {"size": [1080, 1920], "codec": "h264", "video_kbps": 16000, "audio": "aac 48k 320k", "lufs": -14},
    "reels":    {"size": [1080, 1920], "codec": "h264", "video_kbps": 16000, "audio": "aac 48k 320k", "lufs": -14},
    "youtube":  {"size": [1920, 1080], "codec": "h264", "video_kbps": 12000, "audio": "aac 48k 384k", "lufs": -14},
    "linkedin": {"size": [1080, 1350], "codec": "h264", "video_kbps": 10000, "audio": "aac 48k 256k", "lufs": -14},
    "podcast":  {"size": [1920, 1080], "codec": "h264", "video_kbps": 10000, "audio": "aac 48k 320k", "lufs": -16},
}
SIBLINGS = {"shorts": ["tiktok", "reels"], "tiktok": ["shorts", "reels"], "reels": ["shorts", "tiktok"],
            "youtube": ["linkedin"], "podcast": ["youtube"], "linkedin": ["youtube"]}
DISCLOSURE_CHECKED = "2026-11-15"
DISCLOSURE_RULE = ("YouTube: disclose realistic altered or synthetic content (a real person saying or doing something "
                   "they did not, altered footage of real events or places, realistic generated scenes); AI-generated "
                   "music and synthetic voices of real people count, and since May 2026 YouTube labels undisclosed "
                   "photorealistic AI itself. Not needed for scripts, captions, colour correction, beauty filters, "
                   "upscaling, background blur, audio repair or clearly unrealistic visuals. TikTok and Meta have "
                   "similar AI-content labels.")


def render_dir(project: Path, name: str) -> Path | None:
    for mode in ("final", "preview"):
        r = project / "render" / mode / "render.json"
        if r.exists() and Path(read_json(r).get("edl", "")).stem == name:
            return r.parent
    return None


def keywords(tw: list[dict], extra: list[str]) -> list[str]:
    c = Counter(re.sub(r"[^\w']", "", w["w"].lower()) for w in tw)
    c = Counter({k: v for k, v in c.items() if k and k not in STOPWORDS and len(k) > 3 and not k.endswith("'s")})
    out = [k for k in extra if k] + [k for k, _ in c.most_common(40)]
    seen, res = set(), []
    for k in out:
        if k.lower() not in seen:
            seen.add(k.lower()); res.append(k.lower())
    return res


def draft_titles(edl: dict, tw: list[dict], kws: list[str]) -> list[str]:
    ws = [{**w, "i": k} for k, w in enumerate(tw)]
    sents = sentences(ws)
    scored = []
    for s in sents:
        f = hook_features(s["text"])
        n = len(s["text"].split())
        sc = 3 * len(f["contrarian"]) + 2 * len(f["curiosity"]) + 2 * len(f["stakes"]) + (2 if f["question"] else 0) \
            - (3 if f["weak_opener"] else 0) - max(0, n - 12) * 0.5
        scored.append((sc, s["text"]))
    lines = [t for _, t in sorted(scored, key=lambda x: -x[0])]
    titles = []
    for g in edl["tracks"].get("graphics") or []:
        if g.get("component") == "Title" and (g.get("props") or {}).get("text"):
            titles.append(g["props"]["text"])
    for t in lines:
        t = re.sub(r"^(and|but|so|then)\s+", "", t.strip(), flags=re.I)
        t = t[0].upper() + t[1:] if t else t
        if 3 <= len(t.split()) <= 14:
            titles.append(t.rstrip(","))
        if len(titles) >= N_TITLES:
            break
    if len(titles) < N_TITLES and kws:
        titles.append(" ".join(k.title() for k in kws[:3]))
    return titles[:N_TITLES]


def chapters(edl: dict, analysis: dict, fps: Fraction) -> tuple[list[dict], str | None]:
    total_s = timeline_len(edl) / float(fps)
    if edl["project"]["height"] > edl["project"]["width"]:
        return [], "vertical short: platforms do not show chapters"
    tw = timeline_words(edl, analysis)
    marks = []
    for ev in edl["tracks"]["video"]:
        if ev.get("reason", "").startswith("jump cut inside"):
            continue
        t = ev["at_f"] / float(fps)
        if marks and t - marks[-1]["t"] < CHAPTER_MIN_S:
            continue
        words = [w["w"] for w in tw if ev["at_f"] <= w["t_s"] < ev["at_f"] + (ev["out_f"] - ev["in_f"])]
        kw = [re.sub(r"[^\w']", "", w) for w in words if re.sub(r"[^\w']", "", w.lower()) not in STOPWORDS and len(w) > 3][:4]
        marks.append({"t": 0.0 if not marks else round(t, 2), "title": " ".join(kw).capitalize() or ev.get("role", "Part").title()})
    marks = [m for k, m in enumerate(marks) if k == len(marks) - 1 or marks[k + 1]["t"] - m["t"] >= CHAPTER_MIN_S]
    if len(marks) < CHAPTER_MIN or total_s < CHAPTER_MIN * CHAPTER_MIN_S:
        return [], f"fewer than {CHAPTER_MIN} sections of {CHAPTER_MIN_S} s or more"
    marks[0]["t"] = 0.0
    return marks, None


def tc(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def thumbnails(picture: Path, out_dir: Path, fps: Fraction) -> list[dict]:
    import cv2
    from lib.shots import FaceDetector, FrameReader
    det = FaceDetector(SKILL / "assets" / "cache" / "models")
    rd = FrameReader(picture)
    n = int(rd.cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(float(fps) / 2))
    cands = []
    for f in range(0, n, step):
        fr = rd.read(f)
        if fr is None:
            break
        faces = [x for x in det.faces(fr) if x["score"] >= 0.85]
        if not faces:
            continue
        fc = faces[0]
        gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        x, y, w, h = [int(v * s) for v, s in zip(fc["box"], (fr.shape[1], fr.shape[0], fr.shape[1], fr.shape[0]))]
        roi = gray[max(0, y):y + h, max(0, x):x + w]
        sharp = float(cv2.Laplacian(roi, cv2.CV_64F).var()) if roi.size else 0.0
        lum = float(roi.mean()) if roi.size else 0.0
        sc = min(1.0, fc["size"] / 0.3) * 40 + min(1.0, sharp / 300) * 30 + (15 if fc.get("smile") else 0) + \
            (10 if fc.get("eyes_open") else 0) + (5 if 70 <= lum <= 200 else 0)
        cands.append({"f": f, "score": round(sc, 1), "face_size": fc["size"], "sharpness": round(sharp, 1),
                      "smile": fc.get("smile"), "eyes_open": fc.get("eyes_open"), "frame": fr})
    rd.close()
    picked = []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if all(abs(c["f"] - p["f"]) >= THUMB_SPACING_S * float(fps) for p in picked):
            picked.append(c)
        if len(picked) >= N_THUMBS:
            break
    out_dir.mkdir(parents=True, exist_ok=True)
    res = []
    for k, c in enumerate(sorted(picked, key=lambda c: c["f"])):
        p = out_dir / f"thumb_{k + 1}.jpg"
        cv2.imwrite(str(p), c.pop("frame"), [cv2.IMWRITE_JPEG_QUALITY, 92])
        res.append({**c, "t_s": round(c["f"] / float(fps), 2), "path": p.as_posix()})
    return res


def credits(edl: dict, project: Path) -> tuple[str, list[str], list[dict]]:
    used = {s.get("asset") for k in ("sfx", "music", "broll") for s in edl["tracks"].get(k) or []}
    lp = project / "licenses.json"
    ledger = read_json(lp).get("assets", []) if lp.exists() else []
    rows = [e for e in ledger if e["id"] in used]
    unknown = sorted(u for u in used if u and u not in {e["id"] for e in rows})
    warns = []
    if unknown:
        warns.append(f"assets in the EDL with no license entry: {', '.join(unknown)}")
    lines = ["CREDITS", ""]
    for e in rows:
        if edl["project"].get("commercial") and ("nc" in str(e.get("license", "")).lower().replace("non", "nc").split()
                                                 or e.get("commercial") is False):
            warns.append(f"{e['id']} is non-commercial but the project is commercial")
        if e.get("attribution"):
            lines.append(e["attribution"])
    gen = [e for e in rows if not e.get("attribution")]
    if gen:
        lines += ([""] if len(lines) > 2 else []) + ["No attribution required:"] + [f"  {e['id']} - {e.get('source')} ({e.get('license')})" for e in gen]
    if len(lines) == 2:
        lines.append("No third-party assets used.")
    return "\n".join(lines) + "\n", warns, rows


def disclosure(edl: dict, ledger_rows: list[dict]) -> dict:
    why, needed = [], False
    for k in ("video", "broll"):
        for ev in edl["tracks"].get(k) or []:
            if ev.get("synthetic") or ev.get("generated"):
                needed = True; why.append(f"{ev.get('id')}: generated or synthetic picture")
    for d in edl["tracks"].get("dialogue") or []:
        if d.get("voice_clone") or d.get("dub") or d.get("synthetic"):
            needed = True; why.append(f"{d.get('id')}: synthetic or cloned voice")
    for e in ledger_rows:
        if e.get("synthetic_realistic") or e.get("ai_generated"):
            needed = True; why.append(f"{e['id']}: AI-generated or realistic synthetic asset (music counts)")
    sponsor = any(re.search(r"\bsponsor|\bpaid partnership|\bbrought to you by", n, re.I) for n in edl.get("notes", []))
    if not needed:
        why.append("edit uses recorded footage of the speaker; cuts, captions, colour, zoom/upscaling and "
                   "synthesized sound effects do not show a real person or event that did not happen")
    return {"label_needed": needed, "reasons": why, "rule": DISCLOSURE_RULE, "rule_checked": DISCLOSURE_CHECKED,
            "paid_promotion_reminder": sponsor or None,
            "clearance_needed": [b.get("id") for b in edl["tracks"].get("broll") or [] if b.get("needs_clearance")]}


def repurpose(project: Path, analysis: dict, fps: Fraction, n: int, platform: str) -> list[dict]:
    wbs = words_by_src(analysis)
    props = []
    for src, words in wbs.items():
        if not words or (words[-1]["e_f"] - words[0]["s_f"]) / float(fps) < REPURPOSE_MIN_SOURCE_S:
            continue
        sents = sentences(words)
        for i, s in enumerate(sents):
            f = hook_features(s["text"])
            if f["weak_opener"] or not s["complete"]:
                continue
            sc = 3 * len(f["contrarian"]) + 2 * len(f["curiosity"]) + 2 * len(f["stakes"]) + (3 if f["question"] else 0)
            if sc <= 0:
                continue
            j = i
            while j + 1 < len(sents) and (sents[j + 1]["e_f"] - s["s_f"]) / float(fps) <= SHORT_MAX_S:
                j += 1
            dur = (sents[j]["e_f"] - s["s_f"]) / float(fps)
            if dur < SHORT_MIN_S:
                continue
            props.append({"src": src, "words": [s["i_from"], sents[j]["i_to"]], "hook": s["text"], "score": sc,
                          "dur_s": round(dur, 1)})
    picked = []
    for p in sorted(props, key=lambda p: -p["score"]):
        if all(p["src"] != q["src"] or p["words"][1] < q["words"][0] or p["words"][0] > q["words"][1] for q in picked):
            picked.append(p)
        if len(picked) >= n:
            break
    out = []
    for k, p in enumerate(picked):
        a, b = p["words"]
        paper = {"platform": platform if platform in ("shorts", "tiktok", "reels") else "shorts", "type": "short_form",
                 "beats": [{"src": p["src"], "words": [a, b], "role": "hook",
                            "reason": f"Repurposed short {k + 1}: opens on its own hook sentence ({p['hook'][:60]})"}],
                 "captions": {"template": "pop_3word", "highlight": "keyword"}, "pattern_interrupts": "auto",
                 "notes": ["Proposed by package.py --repurpose; split the beat into hook/body/payoff before approval"]}
        pp = project / "edl" / f"short_{k + 1}_paper.json"
        write_json(pp, paper)
        out.append({**p, "paper": pp.as_posix()})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", required=True); ap.add_argument("--project", required=True)
    ap.add_argument("--copy"); ap.add_argument("--out-dir"); ap.add_argument("--repurpose", type=int, default=0)
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    project = Path(a.project)
    try:
        edl = read_json(a.edl); analysis = read_json(project / "analysis.json")
        copy = read_json(a.copy) if a.copy else {}
    except FileNotFoundError as e:
        fail(str(e))
    name = Path(a.edl).stem
    fps = fps_of(edl)
    rdir = render_dir(project, name)
    if rdir is None:
        fail(f"no render of {name} found in {project / 'render'}; run render.py first")
    rj = read_json(rdir / "render.json")
    out = (Path(a.out_dir) if a.out_dir else project / "package") / name
    out.mkdir(parents=True, exist_ok=True)
    pkg = {"edl": Path(a.edl).as_posix(), "render_mode": rj["mode"], "files": {}}
    video = Path(rj["output"])
    if not video.exists():
        fail(f"render output {video} missing")
    if not a.no_video:
        shutil.copy2(video, out / "video.mp4"); pkg["files"]["video"] = (out / "video.mp4").as_posix()
    for tr in sorted((project / "captions").glob("*.srt")) if (project / "captions").exists() else []:
        shutil.copy2(tr, out / tr.name)                 # translated tracks, e.g. captions.am.srt
        pkg["files"][f"captions_{tr.stem}"] = (out / tr.name).as_posix()
    for ext in ("srt", "vtt"):
        p = video.with_suffix(f".{ext}")
        if not p.exists():
            p = rdir / f"captions.{ext}"
        if p.exists():
            shutil.copy2(p, out / f"captions.{ext}"); pkg["files"][ext] = (out / f"captions.{ext}").as_posix()
    tw = timeline_words(edl, analysis)
    kws = keywords(tw, list(copy.get("tags", [])) + list((edl["tracks"].get("captions") or {}).get("keywords", [])))
    titles = copy.get("titles") or draft_titles(edl, tw, kws)
    (out / "titles.txt").write_text(("" if copy.get("titles") else "# DRAFTS from the transcript - rewrite before publishing\n")
                                    + "\n".join(titles) + "\n", encoding="utf-8")
    tags = (copy.get("tags") or kws)[:N_TAGS]
    (out / "tags.txt").write_text(", ".join(tags) + "\n", encoding="utf-8")
    chs, ch_why = chapters(edl, analysis, fps)
    cred, warns, rows = credits(edl, project)
    (out / "credits.txt").write_text(cred, encoding="utf-8")
    desc = [copy.get("description") or (titles[0] if titles else "")]
    if chs:
        desc += ["", "Chapters:"] + [f"{tc(c['t'])} {c['title']}" for c in chs]
    attrib = [l for l in cred.splitlines()[2:] if l and not l.startswith(" ") and not l.startswith("No ")]
    if attrib:
        desc += ["", "Credits:"] + attrib
    if edl["project"].get("platform") == "shorts":
        desc += ["", "#shorts"]
    (out / "description.txt").write_text(("" if copy.get("description") else "# DRAFT - rewrite the first line\n")
                                         + "\n".join(desc) + "\n", encoding="utf-8")
    pic = rdir / "picture.mp4"
    thumbs = thumbnails(pic if pic.exists() else video, out / "thumbnails", fps)
    if len(thumbs) < 3:
        warns.append(f"only {len(thumbs)} thumbnail candidate(s) with a clear face")
    plat = edl["project"].get("platform", "shorts")
    presets = {p: PRESETS[p] for p in [plat] + SIBLINGS.get(plat, []) if p in PRESETS}
    write_json(out / "presets.json", {"master": plat, "presets": presets,
                                      "note": "one master, then variants; reframe between aspect ratios with face tracking "
                                              "(render.py with the target platform), never a centre crop"})
    disc = disclosure(edl, rows)
    said = " ".join(w["w"] for w in tw).lower()
    if re.search(r"sponsor|paid partnership|brought to you by", said):
        disc["paid_promotion_reminder"] = "the cut mentions a sponsor: turn on the platform's paid-promotion disclosure"
    write_json(out / "disclosure.json", disc)
    qc = project / "qc" / "qc_report.md"
    if qc.exists():
        shutil.copy2(qc, out / "qc_report.md"); pkg["files"]["qc_report"] = (out / "qc_report.md").as_posix()
    else:
        warns.append("no QC report: run qc.py before delivery")
    if rj["mode"] == "preview":
        warns.append("packaged from the PREVIEW render; render without --preview for delivery")
    shorts = repurpose(project, analysis, fps, a.repurpose, plat) if a.repurpose else []
    if a.repurpose and not shorts:
        warns.append(f"repurposing skipped: needs a source over {REPURPOSE_MIN_SOURCE_S} s with hook sentences")
    pkg.update(titles=titles, titles_are_drafts=not copy.get("titles"), tags=tags, chapters=chs, chapters_skipped=ch_why,
               thumbnails=[{k: v for k, v in t.items()} for t in thumbs], disclosure=disc, presets=list(presets),
               repurpose=shorts, warnings=warns,
               files={**pkg["files"], "titles": (out / "titles.txt").as_posix(), "description": (out / "description.txt").as_posix(),
                      "tags": (out / "tags.txt").as_posix(), "credits": (out / "credits.txt").as_posix(),
                      "presets": (out / "presets.json").as_posix(), "disclosure": (out / "disclosure.json").as_posix()})
    write_json(out / "package.json", pkg)
    log(f"package: {len(titles)} titles, {len(tags)} tags, {len(chs)} chapters, {len(thumbs)} thumbnails, "
        f"disclosure {'NEEDED' if disc['label_needed'] else 'not needed'}; wrote {out}")
    for w in warns:
        log(f"  warning: {w}")


if __name__ == "__main__":
    main()
