#!/usr/bin/env python3
"""Export an EDL as editable timelines for DaVinci Resolve, Premiere and Final Cut.

Usage:
  python scripts/export_timeline.py --edl P/edl/v2.json --project P [--formats otio,fcpxml,xml]
                                    [--out-dir P/timeline] [--no-overlay] [--proxies]

Writes, next to each other:
  <name>.otio      OpenTimelineIO (Resolve 18+, Premiere 25+ import it)
  <name>.fcpxml    Final Cut Pro X / Resolve
  <name>.xml       FCP7 XML (Premiere "Import", Resolve)
  <name>.srt       the caption track (editors import it as a subtitle track)
  <name>_overlay.mov  captions + titles rendered with alpha (QuickTime Animation), placed on
                   the graphics track, so the editor sees the same text the render burns in
  timeline.json    what was written, media paths, and the round-trip comparison

Tracks: V1 picture (dialogue edit), V2 B-roll, V3 graphics overlay; A1 dialogue, A2 music,
A3 SFX. Clips reference the ORIGINAL media (not proxies, unless --proxies) by absolute file
URL, so the timeline relinks on the machine that ran the edit. Split edits survive because
picture and dialogue are separate tracks with their own in/out points. Each picture clip
carries a marker with its role and reason; the reframe zoom and punch-ins are kept in clip
metadata (pve) because no interchange format carries an animated crop the same way.
Round-trip: every written file is read back and its clip positions and source ranges are
compared with the EDL to the frame. Mismatches are listed; the exit code is non-zero only if a
format could not be written or read at all.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.common import ToolError, fail, log, read_json, run, write_json  # noqa: E402
from lib.edl import event_len, fps_of, schema_errors, timeline_len  # noqa: E402

FORMATS = {"otio": ("otio_json", ".otio"), "fcpxml": ("fcpx_xml", ".fcpxml"), "xml": ("fcp_xml", ".xml")}
MARKER_COLOR = {"hook": "RED", "payoff": "GREEN", "ending": "PURPLE", "tension": "ORANGE", "setup": "BLUE"}


def _otio():
    try:
        import opentimelineio as otio
    except ImportError:
        fail("opentimelineio is not installed: pip install opentimelineio otio-fcpx-xml-adapter otio-fcp-adapter")
    return otio


def media_paths(project: Path, proxies: bool) -> dict:
    media = read_json(project / "media.json")
    out = {}
    for it in media["items"]:
        p = it["proxy"] if proxies and it.get("proxy") else it["path"]
        p = Path(p)
        out[it["id"]] = {"path": (p if p.is_absolute() else project / p).resolve(), "duration_f": it.get("duration_f")}
    return out


def ext_ref(otio, path: Path, dur_f: int | None, rate: float):
    ref = otio.schema.ExternalReference(target_url=path.as_uri())
    if dur_f:
        ref.available_range = otio.opentime.TimeRange(otio.opentime.RationalTime(0, rate),
                                                      otio.opentime.RationalTime(dur_f, rate))
    ref.name = path.name
    return ref


def place(otio, track, items: list[tuple[int, object]], rate: float) -> None:
    """items: (record start frame, clip) sorted; fills gaps; overlapping clips are moved to later
    tracks by the caller."""
    t = 0
    for at, clip in items:
        if at > t:
            track.append(otio.schema.Gap(source_range=otio.opentime.TimeRange(
                otio.opentime.RationalTime(0, rate), otio.opentime.RationalTime(at - t, rate))))
        track.append(clip)
        t = at + int(round(clip.source_range.duration.value))


def lanes(events: list[tuple[int, int, object]]) -> list[list[tuple[int, object]]]:
    """Greedy lane assignment so overlapping clips (stacked SFX) land on separate tracks."""
    out: list[list[tuple[int, int, object]]] = []
    for at, ln, clip in sorted(events, key=lambda e: e[0]):
        for lane in out:
            if lane[-1][0] + lane[-1][1] <= at:
                lane.append((at, ln, clip)); break
        else:
            out.append([(at, ln, clip)])
    return [[(a, c) for a, _, c in lane] for lane in out]


def audio_len_f(path: Path, fps: Fraction) -> int:
    import soundfile as sf
    try:
        info = sf.info(str(path))
        return int(info.frames / info.samplerate * fps)
    except RuntimeError:
        return 0


def media_len_f(path: Path, fps: Fraction) -> int | None:
    """Length of a video/image file in timeline frames (stills: None, the editor treats them as freely long)."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return int(float(out) * fps) if out and out != "N/A" else None
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return None


def build(edl: dict, project: Path, proxies: bool, overlay: Path | None):
    otio = _otio()
    from lib import kit
    fps = fps_of(edl)
    rate = float(fps)
    RT, TR = otio.opentime.RationalTime, otio.opentime.TimeRange
    media = media_paths(project, proxies)
    tl = otio.schema.Timeline(name=f"{edl['project'].get('platform', 'edit')} {Path(edl.get('_path', 'edit')).stem}")
    tl.global_start_time = RT(0, rate)
    tl.metadata["pve"] = {"width": edl["project"]["width"], "height": edl["project"]["height"], "fps": str(fps),
                          "edl": edl.get("_path"), "notes": edl.get("notes", [])}
    missing = []

    def clip_for(src, in_f, out_f, name):
        m = media.get(src)
        if not m:
            missing.append(src)
            ref = otio.schema.MissingReference()
        else:
            ref = ext_ref(otio, m["path"], m["duration_f"], rate)
        return otio.schema.Clip(name=name, media_reference=ref,
                                source_range=TR(RT(in_f, rate), RT(out_f - in_f, rate)))

    v1 = otio.schema.Track(name="V1 Picture", kind=otio.schema.TrackKind.Video)
    items = []
    for ev in edl["tracks"]["video"]:
        c = clip_for(ev["src"], ev["in_f"], ev["out_f"], f"{ev['id']} {ev.get('role', '')}".strip())
        c.markers.append(otio.schema.Marker(name=ev.get("role", "cut"), color=MARKER_COLOR.get(ev.get("role"), "YELLOW"),
                                            marked_range=TR(RT(ev["in_f"], rate), RT(0, rate)),
                                            metadata={"pve": {"reason": ev.get("reason", "")}}))
        c.markers[-1].comment = ev.get("reason", "") if hasattr(c.markers[-1], "comment") else None
        c.metadata["pve"] = {k: ev[k] for k in ("reframe", "transform", "rule_of_six", "transition_in", "reason") if k in ev}
        if ev.get("speed") and ev["speed"] != 1:
            c.effects.append(otio.schema.LinearTimeWarp(time_scalar=float(ev["speed"])))
        items.append((ev["at_f"], c))
    place(otio, v1, items, rate)
    v2 = otio.schema.Track(name="V2 B-roll", kind=otio.schema.TrackKind.Video)
    b_items = []
    for b in edl["tracks"].get("broll") or []:
        if b.get("src") in media:
            c = clip_for(b["src"], b.get("in_f", 0), b.get("in_f", 0) + b["dur_f"], b.get("id", "broll"))
        else:
            try:
                p, _ = kit.resolve(b["asset"], project)
                c = otio.schema.Clip(name=b.get("id", "broll"), media_reference=ext_ref(otio, p.resolve(), max(media_len_f(p, fps) or 0, b.get("in_f", 0) + b["dur_f"]), rate),
                                     source_range=TR(RT(b.get("in_f", 0), rate), RT(b["dur_f"], rate)))
            except (FileNotFoundError, KeyError):
                missing.append(b.get("asset")); continue
        c.metadata["pve"] = {"reason": b.get("reason", "")}
        b_items.append((b["at_f"], c))
    place(otio, v2, b_items, rate)
    v3 = otio.schema.Track(name="V3 Captions+Graphics (alpha)", kind=otio.schema.TrackKind.Video)
    if overlay:
        c = otio.schema.Clip(name="captions and titles", media_reference=ext_ref(otio, overlay.resolve(), timeline_len(edl), rate),
                             source_range=TR(RT(0, rate), RT(timeline_len(edl), rate)))
        c.metadata["pve"] = {"graphics": edl["tracks"].get("graphics", []), "captions": edl["tracks"].get("captions")}
        place(otio, v3, [(0, c)], rate)
    a1 = otio.schema.Track(name="A1 Dialogue", kind=otio.schema.TrackKind.Audio)
    place(otio, a1, [(d["at_f"], clip_for(d["src"], d["in_f"], d["out_f"], d["id"])) for d in edl["tracks"]["dialogue"]], rate)
    tracks = [v1, v2, v3, a1]
    for label, key in (("A2 Music", "music"), ("A3 SFX", "sfx")):
        evs = []
        for k, s in enumerate(edl["tracks"].get(key) or []):
            try:
                p, _ = kit.resolve(s["asset"], project)
            except (FileNotFoundError, KeyError):
                missing.append(s.get("asset")); continue
            n = audio_len_f(p, fps)
            ln = s.get("dur_f") or n
            if key == "music":
                ln = min(ln, timeline_len(edl) - s["at_f"])
            if ln <= 0:
                continue
            c = otio.schema.Clip(name=f"{key} {k + 1} {s['asset']}", media_reference=ext_ref(otio, p.resolve(), n or None, rate),
                                 source_range=TR(RT(s.get("in_f", 0), rate), RT(ln, rate)))
            c.metadata["pve"] = {"gain_db": s.get("gain_db"), "duck": s.get("duck"), "reason": s.get("reason")}
            evs.append((s["at_f"], ln, c))
        for i, lane in enumerate(lanes(evs) or [[]]):
            tr = otio.schema.Track(name=label + (f" {i + 1}" if i else ""), kind=otio.schema.TrackKind.Audio)
            place(otio, tr, lane, rate)
            tracks.append(tr)
    for tr in tracks:
        tl.tracks.append(tr)
    return tl, sorted({m for m in missing if m})


def render_overlay(edl: dict, project: Path, out: Path) -> Path | None:
    """Captions + titles as a transparent QuickTime Animation clip, from the render's ASS file."""
    name = Path(edl.get("_path", "edit")).stem
    for mode in ("final", "preview"):
        r = project / "render" / mode / "render.json"
        if r.exists():
            rj = read_json(r)
            if Path(rj.get("edl", "")).stem == name and (rj.get("captions") or {}).get("ass"):
                rdir = r.parent
                break
    else:
        log("  no render of this EDL with captions found: overlay skipped (render it first)")
        return None
    W, H = edl["project"]["width"], edl["project"]["height"]
    if mode == "preview":
        W, H = rj["size"]
    fps = fps_of(edl)
    dur = float(Fraction(timeline_len(edl)) / fps)
    try:
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black@0.0:s={W}x{H}:r={fps}:d={dur:.3f},format=rgba",
             "-vf", "subtitles=captions.ass:fontsdir=fonts:alpha=1", "-c:v", "qtrle", "-pix_fmt", "argb",
             str(out.resolve())], cwd=rdir)
    except ToolError as e:
        log(f"  overlay render failed ({str(e)[-160:]}); graphics track left empty")
        return None
    return out


def compare(edl: dict, tl, rate: float) -> list[str]:
    """Clip-by-clip check of the picture and dialogue tracks against the EDL (to the frame)."""
    diffs = []
    want = {"V1": [(ev["at_f"], ev["in_f"], event_len(ev)) for ev in edl["tracks"]["video"]],
            "A1": [(d["at_f"], d["in_f"], d["out_f"] - d["in_f"]) for d in edl["tracks"]["dialogue"]]}
    for key, exp in want.items():
        tr = next((t for t in tl.tracks if t.name.startswith(key) or (key == "V1" and t.kind == "Video" and t is tl.tracks[0])), None)
        if tr is None:
            kind = "Video" if key == "V1" else "Audio"
            tr = next((t for t in tl.tracks if t.kind == kind), None)
        if tr is None:
            diffs.append(f"{key}: track missing"); continue
        got, t = [], 0
        for it in tr:
            d = int(round(it.source_range.duration.rescaled_to(rate).value)) if it.source_range else \
                int(round(it.duration().rescaled_to(rate).value))
            if type(it).__name__ == "Clip":
                got.append((t, int(round(it.source_range.start_time.rescaled_to(rate).value)), d))
            t += d
        if len(got) != len(exp):
            diffs.append(f"{key}: {len(got)} clips, expected {len(exp)}"); continue
        for (ga, gi, gd), (ea, ei, ed) in zip(got, exp):
            if abs(ga - ea) > 0 or abs(gd - ed) > 0 or abs(gi - ei) > 0:
                diffs.append(f"{key}: clip at {ea} expected in {ei} len {ed}, got at {ga} in {gi} len {gd}")
    return diffs


def fix_fcpxml_offsets(edl: dict, path: Path, rate: float) -> int:
    """otio-fcpx-xml-adapter 0.18 rounds some connected-clip offsets to whole seconds (seen:
    251/25s written as 10s, one frame early). Recompute every connected clip's offset from the
    EDL (offset = parent start + (timeline position - parent offset)) and rewrite it in place,
    leaving the rest of the file byte-for-byte."""
    import re
    import xml.etree.ElementTree as ET
    fps = Fraction(rate).limit_denominator(1001)
    want = {d["id"]: d["at_f"] for d in edl["tracks"]["dialogue"]}
    for key in ("music", "sfx"):
        for k, s in enumerate(edl["tracks"].get(key) or []):
            want[f"{key} {k + 1} {s['asset']}"] = s["at_f"]
    want["captions and titles"] = 0

    def fr(s):
        return Fraction((s or "0s").rstrip("s")) * fps

    def fmt(frames):
        t = Fraction(frames) / fps
        return f"{t.numerator}s" if t.denominator == 1 else f"{t.numerator}/{t.denominator}s"

    spine = ET.parse(path).getroot().find(".//spine")
    fixes = {}
    for c in spine if spine is not None else []:
        if c.tag not in ("clip", "asset-clip", "gap"):
            continue
        off, start = fr(c.get("offset")), fr(c.get("start"))
        for k in c:
            n = k.get("name")
            if k.tag in ("clip", "asset-clip") and n in want and k.get("lane"):
                good = start + (want[n] - off)
                if fr(k.get("offset")) != good:
                    fixes[n] = fmt(good)
    if fixes:
        text = path.read_text(encoding="utf-8")
        for n, o in fixes.items():
            text = re.sub(r'(<(?:asset-)?clip name="%s" offset=")[^"]*(")' % re.escape(n.replace("&", "&amp;")),
                          lambda m: m.group(1) + o + m.group(2), text, count=1)
        path.write_text(text, encoding="utf-8")
    return len(fixes)


def compare_fcpxml(edl: dict, path: Path, rate: float) -> list[str]:
    """Check the written FCPXML itself. The otio fcpx reader splits some clips into N-1 frames plus
    a one-frame gap on re-import (seen with 0.18.1), so reading it back would blame the file for
    a reader bug. Spine clips are the picture; connected clips on lane -1 are the dialogue (A1)."""
    import xml.etree.ElementTree as ET

    def fr(s):
        s = (s or "0s").rstrip("s")
        return Fraction(s) * Fraction(rate).limit_denominator(1001)

    spine = ET.parse(path).getroot().find(".//spine")
    if spine is None:
        return ["no spine in the FCPXML"]
    pic, dia = [], []
    for c in spine:
        if c.tag not in ("clip", "asset-clip"):
            continue
        off, start = fr(c.get("offset")), fr(c.get("start"))
        pic.append((int(off), int(start), int(round(fr(c.get("duration"))))))
        for k in c:
            if k.tag in ("clip", "asset-clip") and k.get("lane") == "-1":     # A1; music is -2, SFX -3
                at = off + fr(k.get("offset")) - start
                dia.append((int(round(at)), int(round(fr(k.get("start")))), int(round(fr(k.get("duration"))))))
    exp_v = [(ev["at_f"], ev["in_f"], event_len(ev)) for ev in edl["tracks"]["video"]]
    exp_a = sorted((d["at_f"], d["in_f"], d["out_f"] - d["in_f"]) for d in edl["tracks"]["dialogue"])
    diffs = []
    for key, got, exp in (("V1", pic, exp_v), ("A1", sorted(dia), exp_a)):
        if len(got) != len(exp):
            diffs.append(f"{key}: {len(got)} clips, expected {len(exp)}"); continue
        diffs += [f"{key}: expected {e}, got {g}" for g, e in zip(got, exp) if g != e]
    return diffs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", required=True); ap.add_argument("--project", required=True)
    ap.add_argument("--formats", default="otio,fcpxml,xml"); ap.add_argument("--out-dir")
    ap.add_argument("--no-overlay", action="store_true"); ap.add_argument("--proxies", action="store_true")
    a = ap.parse_args()
    project = Path(a.project)
    try:
        edl = read_json(a.edl)
    except FileNotFoundError as e:
        fail(str(e))
    errs = schema_errors(edl)
    if errs:
        fail("EDL does not validate: " + "; ".join(errs[:3]))
    edl["_path"] = Path(a.edl).as_posix()
    name = Path(a.edl).stem
    out_dir = Path(a.out_dir) if a.out_dir else project / "timeline"
    out_dir.mkdir(parents=True, exist_ok=True)
    otio = _otio()
    overlay = None if a.no_overlay else render_overlay(edl, project, out_dir / f"{name}_overlay.mov")
    tl, missing = build(edl, project, a.proxies, overlay)
    rate = float(fps_of(edl))
    res = {"edl": edl["_path"], "files": {}, "missing_media": missing, "overlay": overlay.as_posix() if overlay else None,
           "media": {k: v["path"].as_posix() for k, v in media_paths(project, a.proxies).items()}}
    hard_fail = False
    for f in [x.strip() for x in a.formats.split(",") if x.strip()]:
        if f not in FORMATS:
            fail(f"unknown format {f}; choose from {', '.join(FORMATS)}")
        adapter, ext = FORMATS[f]
        path = out_dir / f"{name}{ext}"
        entry = {"path": path.as_posix()}
        try:
            otio.adapters.write_to_file(tl, str(path), adapter_name=adapter)
            if f == "fcpxml":
                entry["offsets_corrected"] = fix_fcpxml_offsets(edl, path, rate)
            back = otio.adapters.read_from_file(str(path), adapter_name=adapter)   # must at least re-import
            if isinstance(back, otio.schema.SerializableCollection):
                back = next(iter(back))
            entry["round_trip_diffs"] = compare_fcpxml(edl, path, rate) if f == "fcpxml" else compare(edl, back, rate)
            entry["ok"] = not entry["round_trip_diffs"]
        except Exception as e:  # noqa: BLE001 - adapters raise many types; report and continue
            entry.update(ok=False, error=f"{type(e).__name__}: {e}"[:300])
            hard_fail = True
        res["files"][f] = entry
        log(f"  {f:<7} {'ok' if entry.get('ok') else 'MISMATCH' if 'round_trip_diffs' in entry else 'FAILED'}  {path}")
        for d in entry.get("round_trip_diffs", [])[:5]:
            log(f"          {d}")
    srt = None
    for mode in ("final", "preview"):
        p = project / "render" / mode / "captions.srt"
        if p.exists() and Path(read_json(p.parent / "render.json").get("edl", "")).stem == name:
            srt = p; break
    if srt:
        (out_dir / f"{name}.srt").write_bytes(srt.read_bytes())
        res["captions_srt"] = (out_dir / f"{name}.srt").as_posix()
    write_json(out_dir / "timeline.json", res)
    if missing:
        log(f"  missing media: {', '.join(missing)}")
    log(f"wrote timelines to {out_dir}")
    if hard_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
