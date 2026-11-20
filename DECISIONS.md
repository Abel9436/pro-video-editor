# Decisions

Each entry: the choice, the alternative rejected, and why. Newest last.

## Milestone 1: foundation (2026-11-14)

**Layout kept exactly as the build prompt specifies, including `tests/`, `evals/` and this file inside the skill folder.**
Rejected: moving dev-only files beside the skill. The prompt fixes the layout; packaging can exclude them later.

**Time is integer frames at one timeline rate, chosen at ingest; `Fraction` for every conversion.**
Rejected: storing seconds as floats. Float seconds drift (29.97 fps over an hour is off by frames). Seconds appear only at decoder edges (ffprobe, Whisper) and are converted immediately.

**Proxies are rendered at the timeline frame rate, so proxy frame N is timeline frame N.**
Rejected: proxies at the source rate with per-file conversion. Every analysis step would need a rate conversion, and any slip misplaces a cut.

**VFR is judged from the most common packet interval, not ffprobe's `avg_frame_rate`.**
Found on reference footage: a Pinterest download had 50 % of packets bunched 0.1 ms apart, so `avg_frame_rate` read 59.88 for a 30 fps clip. Packets under 2 ms apart are treated as broken timestamps and flagged `broken_timestamps`.

**Clipping = runs of 3+ flat samples at full scale, on the native-rate audio.**
Rejected: counting samples at or above 0 dBFS. AAC decodes of loud masters overshoot past 1.0 without being flat; that over-flagged all three reference clips. Overshoot is reported separately as `hot_level` (info).

**Transcriber: faster-whisper by default, behind a plugin interface (`module:Class`).**
Rejected: WhisperX (needs torch; the same word timestamps come from faster-whisper's built-in alignment). Whisper has no Afaan Oromo and weak Amharic; the plugin interface is how a better model gets in. The skill refuses `om` with Whisper instead of producing a fake transcript. Audio is passed as samples because faster-whisper's PyAV path broke with the installed PyAV.

**Diarization: pyannote when available, else loudest-mic for synced multicam, else MFCC clustering labelled low confidence.**
The MFCC fallback is deliberately conservative (one speaker unless silhouette >= 0.25, every speaker >= 6 s and 8 % of speech). The first version split one voice into 6 "speakers" on music-backed reels. On the 26 s two-person podcast reference it reports 1 speaker; with `--speakers 2` it gets roughly half the lines right. **Real podcast speaker switching needs pyannote (torch + HF token) or separate mics.**

**False starts require an abandoned attempt.**
A restart is flagged only when the first attempt has no sentence end, is not joined by a conjunction, and differs from the retry by at most one word after their shared prefix. The first version flagged rhetorical repetition ("I don't want to be X. I don't want to be Y.") 10 times on the podcast reference; cutting that would change what the speaker meant.

**Shot detection: PySceneDetect AdaptiveDetector; OpenCV HSV-histogram fallback.**
Rejected: TransNetV2 (needs TensorFlow or torch). Revisit if evals show missed dissolves.

**Faces: OpenCV YuNet (downloaded once to `assets/cache/models/`), Haar fallback; eyes/smile by Haar cascades.**
Rejected: MediaPipe (no Python 3.13 wheels at build time). OpenCV pinned `<5` because 5.0 removed the Haar cascades. Eyes-open and smile are rough; they rank thumbnail candidates, not edit decisions.

**Downbeats: 4/4 accent-phase heuristic over librosa beats, reported with a confidence.**
Rejected: madmom (does not install on Python 3.13). Marked heuristic in the output.

**Perception budget: contact sheets grow from 4x4 to 6x6 tiles before shots are sampled.**
Default limit 24 images per analysis run (starting default). analysis.json states whether sampling happened.

**Cache key = sha256 of size + three 4 MiB windows; cached values hold project-relative paths.**
Rejected: full-file hash (seconds per GB) and cwd-relative paths (an early version broke when run from another folder).

**Blender:** not on PATH. A Blender MCP connection exists in the build session, but the skill needs headless `blender -b`; until it is installed, 3D falls back to Three.js in Remotion (milestone 5).

## Milestone 2: style learning (2026-11-15)

**Fingerprints measure every frame on a 160 px-wide decode; Claude sees only sampled frames.**
Per-frame luma, frame difference, phase-correlation shift and response, Lucas-Kanade scale, saturation and sharpness. Rejected: full-resolution analysis (minutes per video for no gain in cut or motion detection).

**Transition classification excludes the frame pair across the cut; a whip needs shift plus blur (sharpness < 0.35 of the shot median).**
The first version called 50-89 % of cuts whips, because the pair across a hard cut always shows a huge "shift". **Zoom events need 80 % direction consistency** over 15 frames; without it, handheld wobble counted as zooms.

**On-screen text: RapidOCR (ONNX) at 2 fps, 480 px wide, sequential decode, unchanged frames skipped, cached.**
Rejected: Tesseract (weak on stylised caption fonts) and seeking per sample (210 s per video; now ~2 min on the first run and seconds when cached). Captions are told apart from titles by overlap with the transcript.

**SFX are counted only as onsets aligned (+-2 frames) to cuts or text entrances.** Music hits otherwise inflated SFX/min. The value is still an upper bound and is labelled so.

**Re-hooks count cuts, zooms and punch-ins, not text churn.** Captions change every second; counting them made every video "re-hook" constantly.

**High vs low performers use repost_count**, the only metric the Pinterest downloads carry. With 13 sources the differences are recorded as hypotheses, never as rules.

**First rulebook: styles/short_form/pinterest_edit_refs.json, measured on the 13 reference videos.** Medians: 19.8 cuts/min, 2.0 s shots, 3 words per card, 4.5 s max without a visible change, -14.4 LUFS. Caveat stored in the file: several refs are editing tutorials, so text density and zooms run higher than a plain talking head should reach.

## Milestone 3: plan and render (2026-11-15)

**Claude writes a paper edit in word indices; plan_edit.py turns it into frames.** Rejected: Claude writing frame numbers (error-prone, and it hides the reasons). Cuts land in word gaps with 0.1 s of air. When Whisper spans touch, `out_f = max(out_f, last word end)`, so no cut lands inside a word.

**Python frame pipeline (decode -> face-tracked crop -> eased zoom -> LUT -> libx264 chunk), not one giant FFmpeg filtergraph.** Face tracking and per-frame zoom are easy in NumPy and hard in filtergraphs. Chunks are keyed by a hash of everything that affects their pixels, so a re-render reuses unchanged chunks (measured: 3 of 9 re-rendered after one beat changed).

**Captions and graphics via libass by default; Remotion when installed.** libass ships with the FFmpeg build, renders Ge'ez correctly and needs no Node. Remotion (remotion/) is the richer engine for 3D titles and complex motion; `--graphics-engine` picks. Remotion overlays need `--image-format=png` for alpha (found on the first sample render).

## Milestone 4: sound and colour (2026-11-15)

**Noise floor is measured only in gaps between words** (20th percentile of 50 ms RMS in gaps >= 0.15 s). Measured in continuous speech, it read -28 dB on clean speech.

**A steady level above -40 dBFS between words means the source already carries a music bed.** Then: no denoising (it smears music), equal-power 40 ms crossfades at every cut (a hard cut in a bed clicks), no room-tone fill, no second music track. Found on the user's test clip (-31 dBFS bed).

**Ducking: `depth_db` is music relative to voice during speech, and `gain_db` is music relative to voice in gaps**, with exact attack/release ramps. Rejected: FFmpeg sidechaincompress (the level depends on the music's own loudness, so depth is not controllable in dB).

**Master 1 dB under the true-peak ceiling (`CODEC_TP_MARGIN_DB`)**: AAC encoding overshot -1 dBTP to -0.4 dBTP on the first render.

**Looks are generated .cube files with skin protection (hue band 10-50 degrees).** Rejected: shipping third-party LUT packs (licence) and grading without skin protection (orange-teal looks turned faces green).

## Milestone 5: assets (2026-11-15)

**Synthesized kit (`pve_synth_v1`): 11 SFX roles made by the skill.** An edit never blocks on downloads, and nothing third-party ships. Pack sounds take priority once `tag_assets.py kit` fills the manifest from the user's downloads. The manifest ships with 300 role slots and no invented pack file names.

**Licence filter: CC0/PD/BY accepted; ND rejected for music, video and SFX; NC and SA rejected on commercial projects; Freesound API excluded on commercial projects** (its API terms make commercial use case by case; checked 2026-11-15).

**No CLAP embeddings** (they need torch, which is absent). Search ranks by tags, role and measured features, and says so.

## Milestone 6: QC loop (2026-11-15)

**Captions-on-faces uses robust faces only: YuNet score >= 0.85, box aspect 0.9-1.8, 20th-80th percentile box per card.** The first fix loop chased hands detected as faces and moved captions onto the speaker's hair; three loops failed. The fix moves only the offending cards (`captions.fix`), not the whole track.

**Lip sync is reported only when the mouth-motion/audio correlation is r >= 0.15**; below that the offset estimate is noise (measured r = 0.08 on the test clip), so the check is skipped, not passed.

**Intelligibility = WER of the re-transcribed mix against the cut's own words** (fail > 15 %, STARTING DEFAULT). The test clip scores 1.9 %.

## Milestone 7: viral brain (2026-11-15)

**Cuts inside pre-edited source footage count as visual changes.** Without them, retention_sim flagged 7.5 s "static" stretches that actually contain source cuts.

**`pattern_interrupts: auto` adds punch-ins on word starts that toggle in and out**, re-toggled in timeline order after every insert. A test caught the first version stacking two punch-ins, which made the framing creep tighter.

**Zoom budget: plan_edit scales each event's framing so the total upscale stays under 2x the source** (99 % of qc.py's fail limit, since scales are rounded). A 720p source in a 1080p frame is already 1.5x before any zoom; the draft had stacked a 1.25 reframe and a 1.25 punch, which is 2.35x. QC now measures the true peak zoom through render's `zoom_at`; it used to take only the largest single transform.

**Virality score weights are STARTING DEFAULTS (hook 25, retention 25, payoff 15, captions 10, loop 10, judged 15; pass at 70).** The score is labelled a probability, never a prediction.

## Milestone 8: hand-off and packaging (2026-11-15)

**Timelines go through OpenTimelineIO 0.18.1 with otio-fcpx-xml-adapter and otio-fcp-adapter.** Rejected: hand-writing FCPXML/XML (OTIO is what Resolve and Premiere import natively).

**FCPXML offsets are corrected after writing.** The fcpx adapter rounded a connected clip's offset of 251/25 s to 10 s, one frame early. Its reader also splits some clips into N-1 frames plus a one-frame gap. So the FCPXML round trip checks the written XML directly, and `fix_fcpxml_offsets` rewrites connected-clip offsets from the EDL.

**Captions and graphics go to the editor as a QuickTime Animation (qtrle, ARGB) clip rendered from the same ASS file**, plus the SRT. Rejected: ProRes 4444 via FFmpeg (heavier, and no better for a hand-off overlay).

**Titles and descriptions from the script are drafts and say so.** Wording is Claude's job (`--copy`); the script supplies material and structure.

**`profile.py` keeps the spec's name although it shadows Python's stdlib `profile` module when scripts/ is on sys.path.** Checked: no module in the pipeline imports `cProfile`/`profile`. Do not add one.

**Preferences are learned only after 2 revisions move the same field the same way.** One revision is a note, not a taste.

## Milestone 9: more types (2026-11-15)

**Nine `*_defaults.json` styles, with every field `"basis": "STARTING DEFAULT"` and `measured: false`.** No raw or reference footage of those types was supplied, so nothing is presented as measured and no eval project exists for them yet (evals/projects.json, `needed`).

## Milestone 10: localization, compliance, performance (2026-11-15)

**Localization is tested on pixels, not assumed:** two different Amharic strings render differently (no tofu), the Arabic alef lands at the right end (bidi works through libass/FriBidi), and a mixed Latin+Ethiopic line draws both scripts. Noto Sans Arabic was added to the font list.

**Privacy blur is applied to the output frame** (`privacy.blur_faces` bystanders/all, `privacy.regions`), with faces re-detected every 3 frames. Rejected: blurring in source coordinates (it would need re-mapping through every crop and zoom).

**Disclosure follows YouTube's rule as checked 2026-11-15**, including AI-generated music and synthetic voices; synthesized SFX do not trigger it.

**A real bug the new tests caught:** render crashed when a shot had no detected face (`faces.main` was null). Fixed.

## Explainer B-roll and the hybrid graphics engine (2026-11-15)

**Captions and punch-ins alone were rejected by the user as not a real edit.** The skill now ships 3D/motion explainer scenes (`remotion/src/broll/`: AIScam, Millionaire, BrickWall, PayToPlay, Ranks, Apprentice, YearsLater) rendered as opaque MP4 B-roll, plus `XStamp` and `WordSlam` overlay graphics. They are own work, so they need no third-party licence; real footage comes from public-domain or keyed stock sources.

**`hybrid` graphics engine:** libass draws captions and the simple graphics, and Remotion draws only what libass cannot (XStamp, WordSlam, Title3D). `auto` picks hybrid when those appear. Rejected: drawing everything in Remotion, which makes a caption change re-render a full-length ProRes overlay.

**Bugs found while doing it:**
- The Remotion props path was relative to the wrong working directory, so the overlay silently fell back to libass.
- B-roll chunks were cached by asset name only, so a re-rendered scene was ignored.
- FCPXML and XML export crashed on B-roll with no media length.

All three are fixed.

## Premium design pass (2026-11-15)

**Captions plus B-roll inserts were still judged generic.** Three premium references were measured frame by frame at 30 fps (references/premium-design.md):
- text is on screen in 90-97% of frames;
- a designed text event arrives about once a second;
- something changes every 0.5 to 1.2 s;
- layouts rotate, text lives inside UI objects, and the type uses two voices.

**The design pass replaces caption and overlay layers with one Remotion `Design` composition** built around the clean speaker cut. Rejected: adding more libass styles. libass cannot do blur-in, 3D planes, depth of field or UI scenes.

**Assets come only from sources whose licence is readable on the item**: 3dicons (CC0), Freesound filtered to CC0 and re-checked per sound page, Kenney (CC0), Commons. Mixkit was rejected because its licence text could not be read.

**`file:` assets now carry their real licence** from the project ledger or a `catalog.json` beside them, instead of being logged as "user's own".

**Smaller decisions:**
- SFX are timed by their measured peak, not their start.
- The colour look is applied to the footage before the design pass, so brand colours stay exact.

## Effects catalogue from a 30 fps study (2026-11-15)

- The first pass on the second reference set sampled at 3 fps. The user rejected that, and rightly: flashes, washes and whips last 2–12 frames and fall between 3 fps samples. `scripts/deep_watch.py` now measures every frame (cuts, flashes, colour washes, B&W beats, blur, zooms, whips, graphics appearing) and every audio hit (from HPSS percussive onsets, with pre-rise, decay and centroid giving a class guess). `--sheets full` writes every frame for viewing. All 7 videos were viewed in full; the findings are in references/effects-catalog.md.
- **Person matte.** PP-HumanSeg (OpenCV Zoo, Apache-2.0) runs at 192x192, followed by a full-resolution guided filter and temporal smoothing. It outputs a VP9 WebM with alpha, which Remotion draws over the "behind" layer. It was chosen over MediaPipe (not installed) and rembg (not installed, and large) because onnxruntime is already a dependency. On the user's footage it covered 72.7 % of frames' area with no empty frames. Hair edges were clean at frame 45.
- Text behind the head was tried on the hook and rejected. The user's framing puts the head across the top of the frame, so "the secret" became unreadable. The rule is that behind-text needs space around the head; halos and icons work behind in any framing.
- **SFX source.** VideoEditingSFX was added because every page carries a schema.org CC0 licence a script can verify, and its catalogue is edit-specific (risers, reverse hits, shutters). Sources not used:
  - Sonniss: its 2026 licence prohibits AI usage.
  - Pixabay: its terms prohibit automated collection.
  - Lots of Sounds: needs a paid API key.
  - Mixkit: licence unreadable.
- **SFX timing.** `peak_s` and `onset_s` are measured for every catalogue sound, so placement is computed rather than guessed.
- **Density.** The references run 20–60 whooshes and risers per minute; v4 had 5 strong SFX per minute. v5 runs at 124 audio events per minute in total, with a pop on every overlay, a transition stack (riser → whoosh → impact) on the four section changes, and soft ticks on the neon key words.
- **Caption styles** are one per edit, never mixed. Every reference keeps a single caption voice for the whole video.
- **Bugs found by the new tests:**
  - Lucide `<line x1=…>` attributes were not parsed, because the regex had no digits.
  - The VideoEditingSFX matcher let "ui" match inside "buildup".

  Both are fixed and covered by tests.

## True peak is checked on the delivered file, not only the master (2026-11-15)
The skincare v2 master measured -2.0 dBTP as PCM but -0.7 dBTP after the AAC encode: dense SFX
transients overshot by 1.3 dB, more than CODEC_TP_MARGIN_DB (1.0). A fixed margin cannot cover every
mix, so `render.py hold_true_peak` measures the encoded file and, while it is over the ceiling, limits
the master by the measured excess (+0.2 dB) and re-muxes the audio with the video stream copied.
The QC true_peak fix now lowers the master ceiling instead of only adding a note.

## The design pass renders on HyperFrames (2026-11-15)
Requested by the user ("change remotion with hyperframes"). `scripts/lib/hf_design.py` turns the EDL design block
into a HyperFrames project: root = clean speaker cut + layout camera + transitions, one sub-composition per scene
and overlay, all captions in one captions composition, the mix as an audio track. Why: the result is an editable
project (Studio / desktop app) instead of a closed render, the linter catches overlaps, unread lines, sub-28 px
type and hidden SVG dashes before rendering (it caught 2 overlaps and a broken icon path on the first build), and
type and fonts render sharper (Amiri for Arabic glyphs). Remotion stays as the fallback for the scene types not
yet ported (`hf_design.unsupported()` decides per EDL). Rules learned on the first build: footage grades/blurs are
pre-rendered files (base_bw, base_soft); base.mp4 gets a keyframe every second for seeking; the person matte is
shown only while something sits behind the speaker (it also cuts out hands, which then float over scenes);
caption text stays between 168 and 1330 px on 9:16, with a scrim over bright screen recordings. Line icons:
fetch_lineicons.py paired polyline numbers wrongly for space-separated `points` (fixed, tested).

## HyperFrames pin moved to 0.9.53 (2026-11-15)

The pinned CLI went from 0.9.4 to 0.9.53. Verified on the Quranly promo project: `check` 0 errors (2 warnings: one composition file over the line guideline, a closing line held 1.62 s against the 2 s craft rule), `snapshot` frames identical to the 0.9.4 render, test suite 83 passed. A passing check means the compositions still validate; it does not prove a render is frame-identical across versions. 0.9.5x also saves the check report under `.hyperframes/artifacts/checks/`; render.py reads that file when stdout is not JSON (the first npx download can leave stdout empty). Roll back with `PVE_HYPERFRAMES="npx --yes hyperframes@0.9.4"`.

## Mixkit is an allowed source; real B-roll leads talking-head edits (2026-11-15)

Supersedes the earlier rejection of Mixkit. Its licence texts are readable at `https://mixkit.co/license/modal/<videoFree|videoRestricted|musicFree|sfxFree>/`, and each item page names its licence. Free video, music and SFX allow commercial social use with no attribution. Restricted items are personal-use only and are never used. Free music is not for TV or radio broadcast and must not be registered with Content ID.

A user rejected the Quranly edit (generated star-field scenes, line icons, no music) as "robotic AI-like". Talking-head shorts now lead with real footage cut on the spoken noun, a ducked music bed and a few SFX on real moves; generated scenes are an accent, not the base. To support that, B-roll events gained `push`, `speed`, `x`/`y`, `grade` and `transition_in`. The design pass gained `BigWord`: large type behind the speaker through the matte, with an optional strike-through.

## Motion-graphics scenes and one caption voice (2026-11-16)

The user rejected B-roll for this style and asked for motion graphics like the reference shorts, with bigger, consistent captions. Re-watching the references (Alimarel, EarnEdits, Edits By Ahmed, John Ogwum) gave the language: one accent colour, white UI cards and 3D icon renders on a dark stage, type behind the speaker, and a single caption style for the whole video.

Added to the HyperFrames engine: scenes `CalendarBlocks`, `ChoiceCards`, `PileUp` (motion modelled on the registry's notification-pileup); overlay `FloatIcons` (3dicons renders, CC0, copied from `P/icons3d/`); `caption_style: "box"` (Montserrat 800, keyword in an accent box, never hidden, same y everywhere). Caption size 96 px on 1080 wide is a STARTING DEFAULT chosen from the user's "too small" note on 62-66 px; it is not measured from the references.

Registry components are sub-compositions with their own ids and variables; mounting them unchanged inside the generated project is not wired yet, so the three scenes are written in the skill's own scene format.

## Amharic transcription lives in the skill; an After Effects finishing kit; custom grades (2026-11-16)

**Transcriber.** `scripts/transcribe_am.py` (draft with `snapwre/hohe-asr-amharic`, align corrected text with the MMS forced aligner) and the `lib.amharic_asr:HoheAsr` plug-in replace the dependency on the user's clipper project. The code is ported from that project's `pipeline/transcribe.py` and `pipeline/align.py`. torch, transformers and uroman are optional (`requirements-amharic.txt`) and imported lazily. `scripts/profile.py` shadows the stdlib `profile` module that torch imports, so the module drops the scripts folder from `sys.path` before importing torch. Verified 2026-11-16 on a 35.4 s clip: 98-word draft, 102 aligned words, re-listening two unclear stretches as clips returned the same text.

**AE kit (`lib/hf_ae.py`).** The user rejected two edits as generic, same-coloured and "AI component" looking, and asked for an After Effects finish: text animators, soft shadows, write-ons, grain, textures, grading, sound on keyframes. Added: `caption_style: "ink"` (per-character reveal with overshoot, Echo ghosts and a written-on marker stroke on the keyword, soft ~20 % shadows, alternating tilt); overlays `Kinetic` (character build or outline write-on, optional `x`) and `Annotate` (marker rings and arrows drawn on the footage, with a label); scenes `Formula` (paper card, ringed multiplier, worked example that counts up), `Versus` (bars grow wrong, a cross writes on, bars swap) and `Checklist` (recap rows ticked); fx `bands`; camera `shake`; `finish.grain`. No icons or emoji in any of them. Feature shapes come from AE tutorials (School of Motion and Noble Desktop text animators, light-wrap and grain-matching compositing guides); every timing not measured on a reference is a STARTING DEFAULT.

**Textures are PNG files.** The HyperFrames renderer drew SVG `feTurbulence` backgrounds as solid black (paper cards rendered black), so grain and paper fibre are seeded PNG tiles written by `write_textures()` into `hf/assets/`.

**Custom grade.** `color.look` may be a dict: contrast, saturation, warmth, lift, shadow/highlight tint, plus `hues` bands (Hue vs Sat / Hue vs Hue, measured on the input hue) and `skin_protect`. It is written to a hashed `.cube`. First use: the gym video, where the lime walls were pulled back (sat 0.62, +10 deg) under teal shadows and warm highlights, with skin protected.

**Palette from the location.** Each video's accent now comes from its own footage (lime from the gym walls here; yellow and blue from the lamp and set in the previous one), not a house colour.

## Camera log is converted at ingest, from the makers' published curves (2026-11-16)
- **Decision:** ingest detects log (override, then camera metadata, then maker + flat picture) and converts it to Rec.709 in the conform pass, before analysis, correction and the look. `lib/logcam.py`, `scripts/detect_log.py`, `references/craft-log.md`.
- **Why first:** colourists put the colour space transform at the head of the node tree; correcting log as if it were Rec.709 lifts the wrong things. Converting at ingest also means analysis, face exposure and QC see a normal picture.
- **Curves and gamuts** come from colour-science 0.4.7 (BSD-3), which implements the makers' white papers. Checked against published 10-bit grey code values: S-Log3 420, V-Log 433, LogC3 400 all decode to 0.18.
- **Display rendering** is our own small transform: Michaelis-Menten tonescale through 18 % grey -> 0.409 code (where a BT.709 camera puts grey on a BT.1886 display), hue kept by scaling on max(RGB), out-of-gamut pulled to luminance, highlights eased to white. Contrast 1.35, peak 10 and path-to-white 0.6 are STARTING DEFAULTS (diffuse white lands near 0.80 code), not measured against maker LUTs.
- **No formula, no guess:** D-Log M, Samsung Log, GP-Log and I-Log need the maker's LUT (`--log-lut`); the fallback is a labelled approximation. A flat clip from an unknown maker is flagged, never assigned a profile.
- **Unverified until a real clip arrives:** marker strings other than Sony's XML items, Apple Log's signal range (treated as a 0-1 signal over the container range), D-Log as code-value based, and the flatness thresholds (FLAT_BLACK 0.05, FLAT_WHITE 0.80, FLAT_SAT 0.12, STARTING DEFAULTS that separate a synthetic S-Log3 clip from the two real Rec.709 sources on hand).
- **Halation** (`color.halation`) joins the finish: a 3D LUT cannot carry spatial effects, so it is a separate highlight-blur-screen step on the footage only.

## Colour-grading motion design; the first real log clip (2026-11-16)
- **Show the grade with the clip's own data** (`lib/hf_grade.py`): the untouched footage wiped against the grade (`design.raw_video` + bg `color: "raw"`), ffmpeg's real `waveform` / `vectorscope` of both (`Scopes`), the shot's pixels moving through an RGB cube (`LutCube`), a camera HUD (`Hud`), and `cine` captions. Real scopes beat drawn imitations: they cannot lie about the grade.
- **First real log clip** (Samsung Log, S25 Ultra, a 480x854 re-upload with metadata stripped) measured blacks 0.050, whites 0.801, saturation 0.081, right on the starting flatness thresholds, so detection missed it. Thresholds moved to 0.04 / 0.85 / 0.12; the two Rec.709 clips on hand (saturation 0.157, 0.228) stay clear.
- **Samsung's official LUT needs a Samsung-account login**, so it cannot be fetched by the skill; the approximate conversion is used and flagged. It looked right on this clip after the grade.
- **TTS voice-overs break word timing**: Whisper's word times bunched, and whole-clip MMS alignment drifted on "S25" (digits). Aligning sentence by sentence inside the measured pauses, with numbers spelled out, fixed it.

## 2026-11-17 - Restraint is enforced, not hoped for (slop_check, pop captions, cutaways)

The user called the s25 and amh2 edits "AI slop". Measured, they were: 46-60 SFX per minute, 10+ emphasised caption words, a HUD on screen for 79 % of the video, 4-5 graphic layers at once, an animated zoom 79 % of the time, a before/after wipe moved four times. Added `lib/restraint.py` + `scripts/slop_check.py` (also run inside qc.py as warnings) with the limits and sources in references/craft-human.md (research: LottieFiles motion-design-skill, MIT; digicurator, reap.video, inizioengage, Maximov). Limits are STARTING DEFAULTS except punch-ins (Maximov: once every 3-4 cuts). Both old edits fail 7-10 of 10 checks; the snap edit built to the page passes 10/10.

Also: caption_style "pop" (lib/hf_creator.py) - the phrase enters once, the spoken word comes up from dim to white, accent only for rationed emphasis, hard cut out; `cutaway: true` on a video event (picture only under continuing dialogue, skipped by the cut-inside-word check) with `freeze_f` + `speed` for slow-motion-into-freeze explainers; `finish.vignette`; per-item `font` on Kinetic type.

## 2026-11-17 - Restraint is not plainness: broadcast motion design (lib/hf_sport.py)

The first restraint edit of the snap video passed slop_check 10/10 and the user asked "where is the motion design?". Restraint limits excess per moment; it does not remove motion design. Added purpose-built, content-driven components: `Telestrate` (freeze-frame analysis: spotlight, joint dots with ripples, skeleton draw-on, joint-angle wedge, force line with arrow and ground ring, leader-line tags), `ReasonPanel` (a claim struck through, then an odometer index 01 -> 02 with text swaps and a sheen), `Standings` (rows named in turn, the hero row overtakes to #1, demoted ranks roll). Gotchas found on the rendered file: GSAP `fromTo` renders its start state at t=0 (use `immediateRender: false` for elements that should not show yet), and a round-capped zero-length dash still draws a dot (hide strokes until their draw-on starts).

## 2026-11-17 - Explainer stages in 3D (lib/hf_explainer.py)

"You're just playing with the captions": overlays on the footage don't read as motion design. Added stages where the footage itself moves: a camera `card` move folds #cam into a tilted, rounded 3D card while an `under: true` scene builds a studio set behind it (`Stage3D`: claim struck through, headline, cards that flip in with 3dicons; `Podium3D`: pillars rise, the hero rises highest, a 3D trophy lands). Also `Title3D` (extruded type via a text-shadow stack, rises from the floor or spins in) and the `flip3d` transition. Amharic display fonts now come from font.et (its data is at font.et/data/fonts.json with licence per font; only OFL entries are used: Menbere, Zemach, Bela Bereka). Fixes found on renders: caption phrases now cut each other off (two phrases were briefly on screen when positions changed between spans), and a stage must end when the next sentence starts.

## 2026-11-17 - Before/after showcase (scripts/before_after.py)

The user asked for before/after reels in the style of a reference (amber set, tilted Before card in black and white, After card, neon handwritten labels, an editing timeline in perspective). Built with ffmpeg + PIL rather than HyperFrames: three static layers and two video cards need no browser, and the result renders in about a minute. The Before card replays the EDL's video track from the proxies (same in points, speed, freezes), so it is the real raw footage cut like the edit; the timeline is drawn from the EDL (graphics lanes, captions, picture track with thumbnails, SFX, dialogue and music with the real waveform). The script font is a required argument so no font ships with the skill. Gotcha: in drawbox, `t` is thickness, not time; a moving playhead needs overlay with eval=frame.

## 2026-11-17 - Camera cards must stay in frame; music depth at the edge of the target

A suspected "card lands in the wrong place" bug turned out to be a misread contact sheet: measured on full frames, a card's centre is exactly (0.5 + x, 0.5 + y) of the frame. The real flaw was the snap reasons card at y 0.3 running off the bottom edge, so `card_js` now raises a clear error for any card that leaves the frame (tests/test_explainer.py). The repeated "music 17.7 dB under the voice" warning came from a hand-written EDL that ducked to -18 dB, the very edge of the 18-24 target; the drafted default (-20) was already right. Hand-written EDLs should use -20 too.

## 2026-11-17 - The skill carries its own taste and assets

A fresh machine could run the pipeline but not reproduce the accepted look: the owner's taste lived in one machine's assistant memory, and the 3D icons and font.et fonts had been downloaded by hand. Now: references/craft-motion-design.md holds the house style and the rejection history; examples/snap/make_edl.py is the accepted design as a worked example (verified: it rebuilds the delivered EDL exactly, apart from a generic music file name); fetch_fontet.py (font.et catalogue at /data/fonts.json, SIL OFL only, refuses the rest) and fetch_3dicons.py (CC0; metadata through the jsDelivr mirror because GitHub's API allows 60 unauthenticated requests an hour, and some file names differ from icon names, e.g. crown -> crow) fetch with licences; check_env reports the Amharic packages and HyperFrames. Single-file display fonts are declared for every weight so the browser never fakes a bold.

## 2026-11-17 - Reference frames ship with the skill

The owner supplied the reference reels as copyright-free visual references and asked for them in the skill. One 12-frame contact sheet per reel (240 px frames, about 100 kB each, 2.4 MB in all) instead of loose frames or the videos: enough to judge finish by eye, small enough for every clone. Only reels the owner actually gave were included; other files in the same download folder were left out.

## 2026-11-17 - Fresh-clone rebuild: three gaps closed

Cloned the repo into an empty folder, made a new venv from requirements.txt alone and rebuilt the accepted snap short from the raw clip (the fresh clone reproduced the first cut exactly). Three things only worked on the original machine:

- The worked example named Freesound ids; a fresh fetch returns other sounds, so six of nine were missing. It now takes the named file when present, else the next sound of the same role from sfx/catalog.json; the music start point falls back to 0 for a shorter bed.
- Openverse now answers HTTP 401 to anonymous requests with page_size above 20 (measured 2026-11-17: 20 -> 200, 21 -> 401); fetch_assets.py asked for up to 50, so every music search failed. Capped at 20.
- Openverse has little commercial-safe music (mostly BY-SA), and the original bed had been fetched from Mixkit by hand. New fetch_music.py lists Mixkit tag/mood/genre pages and downloads with the licence checked on the day (listing links #musicFree, licence page reads "Stock Music Free License"); the restrictions (no broadcast, games, remixes, Content ID) go into licenses.json.

premium-design.md now says its measured numbers are not targets where the owner rejected them (text on screen ~95 %, UI cards as default, unducked music) and defers to craft-motion-design.md.

## 2026-11-18 - Finish rules from a study of a product-ad motion skill

The owner supplied a third-party "Motion Design" skill (no licence file, so treated as all rights reserved: techniques studied, nothing copied) and asked for everything useful in it. Two agents read it line by line against ours. Adopted, in our own code and words:

- Sound: render.py placed every SFX's first sample on its frame, although fetch_sfx measured each sound's peak; whooshes and hits landed late. SFX now take `align` (peak / start / end, the peak refined to the raw maximum within 10 ms), plus `pitch`, `lp`, `hp` and `pan`; plan_edit's auto SFX use `align: peak` and lose their fixed 3-frame lead.
- Synth kit v2: pass-by whooshes (band centre rises then falls), tick, soft_hit, air_bed. Stereo width only on airy sounds: a full Haas delay measured L/R correlation -0.4 on pops and ticks, which cancels on a phone speaker.
- 3D stages: one key light (LIGHT) drives every extrusion, drop shadow, box shadow and the set's light pool; one lens (PERSP 1800, STARTING DEFAULT, was 900-2200 per element); no yoyo floats, bounce or swing-back drifts; stages leave by pushing through the lens (or `exit: cut` under an unfolding card) instead of a 0.25 s dissolve; near/far dust for depth of field; headlines rack from blur; 4 px grid lines (2 px shimmered); floor reflections; the card keeps a slow push while held; brand fonts override the Amharic defaults.
- Title3D: `enter: words` (blur-rise per word, no overshoot), `still`, `sheen` (one light sweep, hero beat only), `track`.
- design_stills.py: every design event at -0.10 / 0 / +0.15 / +0.40 s on one sheet.
Not adopted: per-word blur-in captions (the owner rejected them as a machine tell), status lines with emoji, the product-ad workflow (logo rebuilds, phone mockups, posterised animation), and a sync "check" that only re-reads its own arithmetic.

## 2026-11-19 - Fresh grammar: every video designed from its own story

The owner rejected house v2 as generic and beginner-like: it re-used the snap edit's accepted pattern (3D stages, card folds, flips, pop captions, DM Serif) on a real-estate story with an ironic hook, and pointed to a property reel (words layered behind the speaker, a 3D orbit of property photos, comment cards, small light captions). Decisions:
- Round 7's pattern is demoted from "the pattern" to one answer for explainers; the first rule is now Fresh grammar (craft-motion-design.md): read the story and the subject's nouns, build graphics from them, show real photos from the footage, a new type voice per video.
- New kit lib/hf_editorial.py: Lockup, PhotoCard, Track, Fan, Call, Orbit (CSS 3D ring split into back/front halves around the matte, so no per-frame script), Strikes, Web; captions_whisper. render.py copies P/images into the HyperFrames project; previews were also fixed to lay out at delivery size.
- Repetition is now measured: lib/grammar.py records each final render's devices in ~/.pve/design_log.jsonl (user data, outside the repo); slop_check's fresh_grammar warns above 50 % reuse with one recent project (STARTING DEFAULT) or the same title font and caption style. Seeded from the earlier projects: v2 scored 71 % against snap, v3 15 %.

## 2026-11-19 - Spec-sheet kit, and two render fixes found on the Open Bodybuilding edit

The owner asked for a premium 3D explainer in the brand's dark green with the newest Amharic font. Decisions:
- New kit lib/hf_spec.py (World, Ring, Stat, FlipCard, NextUp overlays; Meters and Divisions under-scenes; `plate` captions), built from the subject (a competition spec sheet) rather than re-using round 7 or the editorial kit. fresh_grammar: 8 % reuse.
- Fonts: Difres and Tsega Elto, the two newest SIL OFL fonts on font.et (sorted by publishedAt).
- restraint.py: a backdrop replacement (`World`) is the stage, not a graphic, so it no longer counts toward persistent-overlay or concurrent-layer limits.
- Bug: the speaker cut-out was switched off at the end of the first of two overlapping behind spans (a backdrop and a ring), so he vanished from 6.3 s while the backdrop still covered the footage. Spans are now merged (test_spec.py).
- Bug: the HyperFrames footage cache (hf_media) was keyed on the chunk list only, so a new grade never reached the design pass. It now also keys on the graded picture's size and mtime.

## 2026-11-19: real 3D objects for premium explainers (hf_objects.py)
The owner rejected the amh3 v2 spec-sheet edit as generic: flat panels and a caption plate. Decision: premium explainers carry rendered 3D objects. Objects are modelled from primitives in Blender 5.2 headless (a per-project script, no third-party assets so nothing to license), rendered with transparent film at 640 px / 30 fps (STARTING DEFAULT), encoded VP9 yuva420p webm crf 30 (STARTING DEFAULT) into P/objects/, copied by render.py to assets/objects/. `Object3D` (rise/fly/drop in, push/drop/cut out, light pool, contact shadow, optional gold label), `Sweep` (light sweep over a fold) and `glint` captions. Meters rows take `icon`, a `hero` object and `kicker_size`; MAX tags moved to the sub line so icons never sit on the label. Divisions cards take `icon`, NextUp takes `bell`.

## 2026-11-19: motion principles from three external skills; sound spacing checks; find_sfx
Read in full LottieFiles motion-design-skill, ncklrs motion-designer and Remotion remotion-best-practices (all MIT). Distilled what the skill lacked into references/craft-motion-principles.md, crediting every number to its source and mapping each rule to the HyperFrames kit. Two of the sound rules are measurable, so they became warnings: `restraint_sfx_gap` (0.2 s minimum between sounds, sourced; sounds within one frame are a deliberate stack of at most 3, sourced) and `restraint_sfx_repeat` (one file at most 3 times, STARTING DEFAULT). The owner called the v3 sound "cheap": scripts/find_sfx.py indexes the local CC0 libraries the owner chose (sfx-kit, uisfx, soundcn) and copies picks with licences; soundcn's assets/wow pack is (c) Blizzard and is never indexed; Remotion's hosted meme sounds carry no licence and are not used. sfx events take `sync_s`, the library's measured sync point, which render.py lands on at_f (scaled by 1/pitch). The libraries live outside the repo.


## 2026-11-20: hero beats are full-frame 3D shots, not icons on panels; Freesound API
The owner said amh3 v3 was "the same" as v2, and a frame-by-frame comparison agreed: v3 added small 3D icons to v2's flat glass panels, so the edit's structure was unchanged. Decision: when a beat is the point of a scene, it becomes a full-frame Blender shot, not a decoration on a card. New `Plate` overlay (hf_objects.py) plays a 1080x1920 alpha webm full frame, with `behind: true` putting the speaker matte in front of it. Extruded Amharic works in Blender with the project's OFL TTFs (Tsega Elto, Difres), so type itself can be 3D. The amh3 v4 shots (work/amh3/type3d.py): a gold zero framing his head behind him, a thick slab that flips from the myth to the turn, gold bars that slam to MAX, and standing gold type. Render cost measured on this machine: EEVEE at 16 samples took about 2-4 s per 1080x1920 frame. fetch_sfx.py uses the Freesound APIv2 when a key is available (env FREESOUND_API_KEY or ~/.pve/freesound_key, outside the repo): CC0 filter, rated first, a duration window (so it finds music too), licence read from each sound's API record. The owner's key carried one stray character; the API's "Invalid token" reply is reported as-is.
