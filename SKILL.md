---
name: pro-video-editor
description: Edits supplied raw footage into finished videos for any platform (YouTube Shorts, TikTok, Reels, YouTube long-form, podcasts, vlogs, documentaries, ads, gaming, explainers). It also analyses reference videos to learn an editing style. It plans the story from the transcript, cuts with a reason for every cut, mixes sound, colour-corrects, adds captions and graphics, self-checks with QC, and delivers the video, an editable timeline (Resolve, Premiere, Final Cut), captions, titles, thumbnails and credits. Use when the user gives footage or a video and asks to edit, cut, tighten, caption, reframe, grade, mix, repurpose into shorts, score for retention, export a timeline, or learn a style from reference videos. Not for generating video from nothing, and not for one-off conversions or compression.
---

# Pro video editor

## What it produces
From a folder of footage and a one-line brief:
1. **A finished video**: H.264 MP4 with faststart, Rec.709, -14 LUFS, captions burned in, plus SRT/VTT.
2. **An editable timeline**: `.otio`, `.fcpxml` and FCP7 `.xml`, with separate tracks, original media, a marker on every cut carrying its reason, and a captions/graphics alpha overlay.
3. **A package**: 5 titles, a description with chapters and credits, tags, 3-5 thumbnail candidates, `credits.txt`, platform presets, an AI-disclosure recommendation and the QC report.

Every cut has a reason. Every asset has a licence entry. Every QC check passes, or is reported with timestamps.

## Prerequisites
Run once per machine, and again when something fails:
```
python scripts/check_env.py
```
Required: FFmpeg with libass and libx264, Python 3.11+ with `requirements.txt` (faster-whisper, opencv, scenedetect, librosa, soundfile, numpy, jsonschema, rapidocr_onnxruntime, opentimelineio + otio-fcpx-xml-adapter + otio-fcp-adapter).
Optional: Node 18+. The design pass renders on **HyperFrames** (`npx hyperframes@0.9.53`, fetched on first use; override with `PVE_HYPERFRAMES`), and falls back to Remotion (`remotion/`, `npm install`) for scene types HyperFrames does not have yet; Remotion also draws the older graphics track and 3D titles. A GPU encoder; Blender (3D titles otherwise fall back to Three.js in Remotion).
Amharic transcription: `pip install -r requirements-amharic.txt` into the same environment (torch, transformers, uroman); `check_env` reports them. Run `npx --yes hyperframes@0.9.53 --version` once while online so the first render doesn't stall on the browser download.
Without the optional parts the skill degrades: libass draws captions and graphics, libx264 encodes, and 3D titles need Remotion.

All scripts: `--help`, JSON output, non-zero exit with one clear message on failure. Paths below use `P` for the project folder and assume the skill folder is the working directory.

## Workflow: eleven stages, in order
A stage starts only after the previous one has written its output.

| # | Stage | Command | Output |
|---|---|---|---|
| 1 | Brief | read the request and the profile (`profile.py show NAME`); infer platform, length, type and tone; ask only what cannot be inferred | |
| 2 | Ingest | `python scripts/ingest.py FOOTAGE --project P --platform shorts` | `P/media.json`, proxies (VFR->CFR, HDR->SDR, camera log -> Rec.709 detected automatically, multicam sync; references/craft-log.md) |
| 3 | Analyze | `python scripts/analyze.py --project P` | `P/analysis.json`, transcripts `P/analysis/transcript_<id>.md`, contact sheets |
| 4 | Type and style | `python scripts/detect_type.py --project P --target short` | `P/type.json`: type, evidence, chosen style and why |
| 5 | Selects and paper edit | Claude reads the transcript and contact sheets, then writes `P/edl/paper_v1.json` (beats as word ranges, each with a reason) | **Checkpoint 1: story** |
| 6 | Plan | `python scripts/plan_edit.py draft P/edl/paper_v1.json --project P --out P/edl/v1.json` | EDL + `v1.check.json` |
|   | Score and revise | `python scripts/hook_variants.py --paper P/edl/paper_v1.json --project P` / `python scripts/retention_sim.py --edl P/edl/v1.json --project P` / `python scripts/virality_score.py --edl P/edl/v1.json --project P --judged P/judged.json` | revise the paper edit until they pass (retention styles only) |
| 7 | Assets | `python scripts/tag_assets.py find "short bright whoosh"`; `python scripts/fetch_assets.py search --kind music --query "..." --commercial --out P/m.json`, then `get --from P/m.json --pick 0 --project P`; music beds: `python scripts/fetch_music.py get --project P --query workout --pick 0` (Mixkit, licence checked) | `cat:`/`kit:` ids, `P/licenses.json` |
| 8 | Rough render | `python scripts/render.py --edl P/edl/v1.json --project P --preview` (`--dry-run` validates without rendering) | `P/exports/v1_preview.mp4` — **Checkpoint 2: rough cut** |
| 9 | Finish | `python scripts/render.py --edl P/edl/vN.json --project P [--graphics-engine auto|hyperframes|remotion|ass|hybrid] [--design-project-only]` | `P/exports/vN.mp4` + .srt/.vtt; `P/render/final/hf/` (editable HyperFrames project) |
| 10 | QC | `python scripts/qc.py --video P/exports/vN.mp4 --edl P/edl/vN.json --project P --fix-loop` | `P/qc/qc_report.md`; up to 3 automatic fix loops write vN+1 |
| 11 | Export and package | `python scripts/export_timeline.py --edl P/edl/vN.json --project P` then `python scripts/package.py --edl P/edl/vN.json --project P --copy P/copy.json` | `P/timeline/`, `P/package/vN/` — **Checkpoint 3: delivery** |

Revisions: write `paper_v2.json`, draft `v2.json`, then `python scripts/plan_edit.py diff P/edl/v1.json P/edl/v2.json --project P` and show the change list. After approval, `python scripts/profile.py learn NAME --from P/edl/v1.json --to P/edl/v2.json --note "<their words>"`.

Learning a style from reference videos:
```
python scripts/fingerprint.py batch REFS --out-dir work/fp/<type>
python scripts/fingerprint.py aggregate work/fp/<type>/*.json --type <type> --name <name> --out styles/<type>/<name>.json
```
Reference videos are measured, never copied.

## The three checkpoints
At each one, show what was decided and why, in plain words, using the reason fields.
1. **Story** (after the paper edit): the beat list with reasons, what was dropped and why, the chosen opening (deductive or inductive) and the style.
2. **Rough cut** (after the preview): the preview path, retention dips and the virality score with its fixes.
3. **Delivery**: the video, timeline and package paths, the QC summary, and every check that is not a pass, with its timestamp.

**Unattended mode** (batch or scheduled): skip the checkpoints, ask nothing, record every default in the paper edit's `assumptions` (copied to the EDL and the QC report), and keep all versions.

## Choosing the type and style
- Type comes from `detect_type.py` evidence (references/video-types.md). Mixed footage can map to several types; plan per section.
- Style order: the user's explicit request, then the profile's default for the platform, then the best-matching fingerprint (measured before starting defaults).
- State the choice in one line with the reason. Only `styles/short_form/pinterest_edit_refs.json` is measured; the `*_defaults.json` files are STARTING DEFAULTS, so say so when using one.
- A talking head is not finished with captions and zooms. Use the design pass (`design` block in the EDL, rendered by Remotion `Design`): rotate layouts (full / split / full-scene) so something changes every 0.5-1.2 s, put lines inside objects (phone notifications, notes, checkout, paywall), phrase captions with serif-italic emphasis, 3D icons with depth, zoom-blur whips. Lead with real B-roll cut on the spoken noun (with `push`, `grade` to match the main footage) and a ducked music bed; generated scenes are accents, or the edit reads as an AI template. Pull assets at zero cost with licences checked per item (Mixkit Free items, never Restricted; 3dicons CC0, Freesound CC0 via `scripts/fetch_sfx.py`, Kenney CC0, Commons). Read references/premium-design.md first.
- Effects come from references/effects-catalog.md (7 shorts watched at 30 fps, every frame). Pick ONE caption voice per edit: `caption_style` slam / neon / keyword / tier / phrase. Set `matte: true` (scripts/matte.py) to put halos, line icons and words `behind: true` the speaker, and `bg` spans to recolour only the background. Mark section changes with leakdip / smoke / overexpose / wash / burn (one every 6-13 s), plain cuts inside a section, B&W for the punchline. Give every visual move a sound placed peak-on-cut (`peak_s` in sfx/catalog.json): risers and whooshes run 20-60/min in the references. Study a new reference with `scripts/deep_watch.py --sheets full` before copying a technique, never from a 3 fps sample: transitions last 4-24 frames and vanish between samples.
- Design engine: HyperFrames by default (`design.engine`, or `--graphics-engine`). It writes `render/<mode>/hf/`, an editable project (one sub-composition per scene and overlay, captions on one track) the person can open with `hyperframes preview`; `--design-project-only` stops there. Footage grades and blurs are files, never CSS. Keep words between 168 and 1330 px on 9:16 (the platform UI covers the rest): `caption_y` 0.66, and `caption_y_at` spans (`{s, e, y, scrim}`) move captions off busy footage. `caption_text` fixes mis-heard names in captions only. Look at `hyperframes snapshot --at ...` frames before the full render. After Effects finish (`lib/hf_ae.py`): `caption_style: "ink"`, `Kinetic` / `Annotate` overlays, `Formula` / `Versus` / `Checklist` scenes, `bands` fx, camera `shake`, `finish: {grain}`, `color.halation`; colour stories use `lib/hf_grade.py` (`raw_video` + bg `raw` wipe, `Scopes` with real waveform/vectorscope, `LutCube`, `Hud`, `cine` captions); take the accent from the footage itself and grade per video (`color.look` as a dict with `hues` bands). No emoji or clip-art icons in this style. Amharic: `scripts/transcribe_am.py` (references/localization.md).
- Build to the style's numbers. Where the footage cannot support them (pre-edited source, 720p, no B-roll), adapt and say so. After the render, explain the `style_distance` gaps in the QC report.

## Non-negotiable rules
1. **A reason for every cut**, written in the paper edit, and scored on emotion, story and rhythm (Rule of Six).
2. **Plan before render.** No render before the paper edit exists; no final render before the rough cut is approved (except in unattended mode).
3. **QC before delivery.** Never deliver a video without a QC report. Report failed checks with timestamps; never hide them.
4. **Licence ledger.** Every placed asset is in `P/licenses.json`. Commercial projects exclude NC, SA and Freesound-API assets. When nothing good enough is licensed, leave the slot empty and say so.
5. **No meaning-changing edits.** Never join words into a sentence the speaker did not say. Every removal inside a sentence is in the EDL notes; reread each changed sentence.
6. **Honest virality.** Hooks must be true and paid off. No rage bait by default. Never promise views: the score is a probability.
7. **Privacy.** No cloned voices or faces without permission. Blur bystanders on request (`privacy` in the EDL). Analysis runs locally; say when anything goes to an external API.

## Reference files: read only what the task needs
| File | Read when |
|---|---|
| references/craft-philosophy.md | before every paper edit |
| references/craft-story-structures.md | writing the paper edit (structure per type, openings) |
| references/craft-cut-vocabulary.md | choosing how shots meet (J/L cuts, transitions, continuity) |
| references/craft-pacing-rhythm.md | shot lengths, tightening speech, cutting to music |
| references/craft-audio.md | every project with sound (levels, voice chain, music bed rule) |
| references/craft-color.md | dark, mismatched or graded footage |
| references/craft-log.md | log footage (S-Log, V-Log, C-Log, F-Log, N-Log, Apple Log, D-Log...) or a `log_*` flag |
| references/craft-motion-type.md | captions, titles, zooms, the zoom budget |
| references/craft-anti-patterns.md | reviewing a rough cut |
| references/craft-motion-design.md | **every talking-head short**: the owner's house style (the footage moves: 3D card stages, Title3D, flip3d, one hero beat), what was rejected and why, where each font/icon comes from; worked example `examples/snap/make_edl.py` |
| references/frames/ | contact sheets of the owner's reference reels (12 frames each, indexed in its README): look before designing to calibrate the finish by eye |
| scripts/design_stills.py | after any render with a design pass: stills of every transition at -0.10/0/+0.15/+0.40 s on one sheet; look at it before showing anyone |
| scripts/fetch_fontet.py, scripts/fetch_3dicons.py | Amharic fonts from font.et (SIL OFL only) and 3D icons (3dicons, CC0) into a project, with licences |
| references/craft-human.md | before any graphics pass: one hero per moment, rationed SFX/emphasis/punch-ins, show the real thing; `scripts/slop_check.py --edl` audits it |
| scripts/before_after.py | a before/after showcase reel of a finished edit: raw footage (B&W, cut like the EDL) on a tilted card, the edit on a larger card, neon labels, an EDL-drawn timeline with a moving playhead; needs `--script-font` (a licensed handwritten font) |
| scripts/lib/hf_explainer.py | 3D explainer stages: camera `card` fold, `Stage3D` / `Podium3D` under-scenes, `Title3D` extruded type, `flip3d` transition |
| references/viral-algorithms.md, viral-psychology.md, viral-hooks.md, viral-retention.md, viral-formats.md | **retention-style projects only** (shorts, reels, TikTok, YouTube growth edits) |
| references/platforms.md | choosing the target, safe zones, export presets |
| references/video-types.md | stage 4, or measuring a new style |
| references/premium-design.md | any edit that must look premium: measured targets, design pass, free CC0 asset sources |
| references/effects-catalog.md | choosing effects: 30 fps measurements of 7 shorts, each effect with frames and timing, AE equivalents and expressions, SFX layering, free asset licences |
| references/assets-sources.md | any music, SFX, B-roll, icon, 3D or font need; credits |
| references/compliance.md | before delivery; generated media, music rights, sponsors, privacy |
| references/revisions.md | the user gives feedback on a cut |
| references/localization.md | non-English footage or captions, translated tracks |
| references/edl-schema.md | writing a paper edit or reading any project JSON |

## Worked example
**Brief:** "Edit this 60 s clip into a short, minimum cost." **Footage:** one pre-edited 720p talking head with a music bed.
**Type and style:** `short_form` (vertical target; one speaker, face on screen 100 %), style `styles/short_form/pinterest_edit_refs.json` (measured, 13 refs).
**Paper edit excerpt** (deductive opening):
```json
{"pattern_interrupts": "auto",
 "beats": [
  {"src": "romance_source", "words": [75, 105], "drop": [[81, 84]], "role": "hook", "punch": [90],
   "reason": "Hook: the false promise the viewer came for (a secret AI technology that guarantees you become a millionaire)"},
  {"src": "romance_source", "words": [106, 111], "role": "payoff", "punch": [107],
   "reason": "First payoff, ~7 s in: the hook's tease is answered - that's not the way it works"}]}
```
**EDL excerpt** (frames at 25 fps; the zoom was scaled down to stay within 2x of the 720p source):
```json
{"id": "v2", "src": "romance_source", "in_f": 503, "out_f": 659, "at_f": 18, "role": "hook",
 "reason": "jump cut inside beat 0: removes a pause or filler; framing alternates so the jump reads as intentional",
 "reframe": {"mode": "face_track", "zoom": 1.155},
 "transform": [{"at_f": 16, "type": "punch_in", "scale": 1.155, "ease": "out_cubic", "dur_f": 4}]}
```
Result: 36 s, retention risk 0, virality 90/100. No music was added because the source already has a bed.

## Troubleshooting
| Symptom | Cause and fix |
|---|---|
| `check_env` reports no libass | Captions cannot burn: install an FFmpeg build with libass (e.g. gyan.dev full on Windows). |
| Transcript empty or nonsense | Wrong language: `analyze.py --language xx`. Afaan Oromo is refused by Whisper: supply a transcript or plug in a model (localization.md). |
| `plan_edit` error "duration exceeds the target" | Drop the weakest beat or raise `target_duration_s`; do not speed up speech. |
| QC `captions_on_faces` fails | `--fix-loop` moves the cards; if it persists, set `captions.position` to `bottom`. |
| QC `upscaling` warn or fail | Low-resolution source: reduce `zoom`/`punch` (plan_edit already caps the total at 2x); warn the user that 720p in 1080p is soft. |
| QC `music_voice_separation` or `intelligibility` fails | Duck deeper (`depth_db` -24), lower music `gain_db`, or pick a track without vocals or mid-range energy. |
| QC `true_peak` slightly over | Re-render; the master already leaves 1 dB for the AAC overshoot. Check that no SFX peaks above -6 dBFS. |
| `pops` warn at cuts | Source with a music bed: the cut crossfades handle it; otherwise check edits that land on loud syllables. |
| Render slow | Use `--preview` for iterations; chunks are cached, so only changed events re-render. |
| Remotion render fails | render.py falls back to libass automatically; `--graphics-engine ass` forces it. |
| Openverse returns HTTP 401 | Rate limit: wait, or use the catalog and kit (local first). |
| Timeline media offline in Resolve/Premiere | Media paths are absolute on the editing machine: relink to the originals folder (`timeline.json` lists them). |
