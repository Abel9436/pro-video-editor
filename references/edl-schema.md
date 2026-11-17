# Data formats

## Contents
- Conventions
- media.json (written by ingest.py)
- analysis.json (written by analyze.py)
- EDL
- Paper edit
- Other project files

## Conventions
- Every time is an integer frame count at the project rate `fps` (a string such as `"30"` or `"30000/1001"`). Field names end in `_f`.
- Paths inside project JSON are relative to the project folder, with forward slashes. Original media paths are absolute.
- Problem flags: `{"type", "severity": "info" | "warn" | "error", "detail"}`.

## media.json
| Field | Meaning |
|---|---|
| `fps`, `fps_reason` | timeline rate and why it was chosen |
| `items[].id` | stable id from the file name, used everywhere else |
| `items[].path` / `render_src` | original file / file to render from (conformed copy when VFR or HDR was fixed) |
| `items[].proxy`, `wav` | 540p proxy at the timeline rate; mono 16 kHz WAV |
| `items[].duration_f` | duration in timeline frames |
| `items[].video` | codec, size, `rotation`, `display_width/height`, `color`, `hdr` (`pq`, `hlg`, null), `vfr`, `evidence`, `fps_native` (measured cadence) |
| `items[].conform` | `applied` (e.g. `vfr_to_cfr_30`, `tonemap_pq_to_rec709`), `fps_method` (`native`, `drop_frames`, `drop_frames_retime`, `retime`, `frame_blend`, `slowmo_or_drop`) |
| `items[].sync` | `{group, offset_f}`: the file's frame 0 sits at `offset_f` on the group anchor's clock (negative = started earlier) |
| `sync_groups[]` | anchor, members with `offset_f`, `peak_z`, `pearson`, `overlap_s` |
| `problems[]` | every warn/error flag with its file id: `very_low_light`, `shaky`, `missing_audio`, `silent_audio`, `clipped_audio`, `broken_timestamps`, `fps_mismatch` |

## analysis.json
`files.<id>` holds:

| Field | Meaning |
|---|---|
| `transcript.words[]` | `{i, w, s_f, e_f, p, speaker}`; `i` is the index Claude cites in the paper edit |
| `transcript.sentences[]` | `{i_from, i_to, s_f, e_f, text, speaker, mean_p, complete}` |
| `transcript.readable` | Markdown transcript: `[#index timecode speaker] text`, `{fillers}` in braces |
| `transcript.ref`, `offset_f` | for a synced member: use the anchor's transcript shifted by `offset_f` |
| `speakers` | `method` (`pyannote`, `loudest_mic`, `mfcc_cluster`), `confidence`, `turns[]` |
| `speech.fillers[]` | `kind: hard` (safe to cut) or `soft` (judge in context) |
| `speech.false_starts[]` | `repeat`, `cutoff`, `restart`; each with the span to remove |
| `speech.retakes[]` | groups of takes of one sentence, `recommended` sentence index and `reason` |
| `speech.silences[]` | gaps >= 0.5 s, `kind` (`true_silence`, `gap_with_sound`), `position` |
| `speech.breaths[]`, `laughter`, `emphasis[]` | breath candidates; laughter tokens and loud non-speech; words louder or higher than the speaker's norm |
| `audio` | `noise_floor_db`, `loudness` (integrated LUFS, LRA, true peak, short-term series) |
| `music` | `bpm`, `beats_f`, `downbeats_f` (+ confidence), `sections`, `energy` (files with little speech, or audio-only files) |
| `shots[]` | `s_f`, `e_f`, `keyframes`, `sharpness`, `exposure`, `motion_pct_per_f`, `camera.type`, `faces` (`count`, `main.box/size/position`, `eyes_open`, `smile`) |

`perception` lists the contact sheets Claude views: `images[].shots` maps each tile to `[file id, shot n]`; `sampled` is true when the budget forced shot sampling.

## EDL
`project/edl/vN.json`, written by `plan_edit.py draft`, validated by `plan_edit.py check` (JSON Schema in `scripts/lib/edl.py`), executed by `render.py`. Never edited in place after approval: a revision is a new version.

**Time rules:** integer frames at `project.fps`. Video events sit back to back: `at_f` is the timeline start. `in_f`/`out_f` are source frames on the timeline-rate clock (proxies use the same clock); `out_f` is exclusive. `transform[].at_f` is relative to the event's own start.

| Field | Meaning |
|---|---|
| `version` | 1 |
| `project` | `fps`, `width`, `height`, `platform`, `type`, `style` (path), `profile` (path), `target_duration_f`, `commercial`, `kit` (`sound`, `type`, `icons`: one kit per video) |
| `tracks.video[]` | `id`, `src` (media id), `in_f`, `out_f`, `at_f`, **`reason`** (required), `role` (`hook`, `setup`, `tension`, `payoff`, `reveal`, `answer`, `body`, `ending`, `cta`), `rule_of_six` (`emotion`, `story`, `rhythm` 0-10), `reframe` (`mode`: `face_track`/`center`/`fixed`, `zoom` >= 1, `x`, `y`), `transform[]` (`at_f`, `type`: `punch_in`/`punch_out`/`push_in`/`pull_out`/`shake`, `scale`, `ease`, `dur_f`, `hold_f`), `speed`, `freeze_f` (hold the last frame this many frames), `cutaway` (true: picture only, e.g. a frozen demo under continuing dialogue; the dialogue track carries the sound and the picture is not paired with it), `transition_in` (`cut`/`dissolve`/`fade`/`whip`/`zoom`), `transition_dur_f`; optional `synthetic` (generated picture, sets the disclosure flag) |
| `tracks.broll[]` | `id`, `asset` (`cat:`/`kit:`/`file:`) or `src`, `in_f`, `at_f`, `dur_f`, `reason`, `transition_in`; optional `push` ([z0, z1] eased zoom over the clip), `speed` (<1 slow motion), `x`/`y` (crop centre, fractions of the source), `grade` (`gain`, `sat`, `vignette` 0-1: match bright stock to the main footage), `needs_clearance` (meme/GIF the user must clear), `synthetic` |
| `tracks.dialogue[]` | `id`, `src`, `in_f`, `out_f`, `at_f`, `split_edit` (`none`/`j_cut`/`l_cut`), `chain` (voice chain name), `gain_db`; optional `dub`, `voice_clone`, `synthetic` (disclosure) |
| `tracks.music[]` | `asset`, `at_f`, `in_f`, `dur_f`, `gain_db` (music vs voice in gaps, default -6), `end` (`bar`/`hit`/`fade`/`natural`), `duck` (`under`, `depth_db` music vs voice during speech, `attack_ms`, `release_ms`), `reason` |
| `tracks.sfx[]` | `asset`, `at_f`, `gain_db` (peak), `role`, `reason` |
| `tracks.captions` | `template` (`pop_3word`/`bold_1word`/`clean_line`), `source` (`transcript`), `highlight` (`keyword`/`none`/`active_word`), `keywords[]`, `language`, `safe_zone`, `position`, `words_per_card`, `fix` (`{card start frame: y}` per-card positions written by the QC fix loop) |
| `tracks.graphics[]` | `component` (`Title`, `Callout`, `LowerThird`, `ProgressBar`, `Title3D`), `at_f`, `dur_f`, `props` (`text`, `y`, ...), `reason` |
| `color` | `correction` (`auto`/`none`), `match_shots`, `look` (name or .cube path), `strength` 0-1 |
| `master` | `lufs` (default -14), `true_peak_db` (default -1) |
| `privacy` | `blur_faces` (`none`/`bystanders`/`all`), `regions[]` (`t0_f`, `t1_f`, `box` [x, y, w, h] as fractions of the output frame, `what`) |
| `notes[]` | every removal inside a sentence, every dropped beat, every automatic change (pattern interrupts, zoom budget) |
| `assumptions[]` | unattended mode: every default chosen without asking |

Excerpt (from the build test):
```json
{"id": "v2", "src": "romance_source", "in_f": 503, "out_f": 659, "at_f": 18,
 "reason": "jump cut inside beat 0: removes a pause or filler; framing alternates so the jump reads as intentional",
 "role": "hook", "transition_in": "cut", "reframe": {"mode": "face_track", "zoom": 1.155},
 "transform": [{"at_f": 16, "type": "punch_in", "scale": 1.155, "ease": "out_cubic", "dur_f": 4}]}
```

## Paper edit
`project/edl/paper_vN.json`, written by Claude, turned into an EDL by `plan_edit.py draft`. Claude works in **word indices** from the transcript (`analysis/transcript_<id>.md`), never in frames.

| Field | Meaning |
|---|---|
| `platform`, `type`, `style`, `profile` | target and rules |
| `target_duration_s`, `commercial` | duration target (qc.py `duration` +-10 %), license filter |
| `opening` | deductive or inductive, and why |
| `beats[]` | `src`, `words` [first, last] (inclusive), `role`, **`reason`**, `rule_of_six`; optional `drop` [[a, b], ...] word spans removed inside the beat, `punch` [word indices], `zoom`, `push_in`, `keep_pauses`, `split` (`j_cut`/`l_cut`) + `split_f`, `transition_in`, `transition_dur_f`, `hold_f`, `reframe`, `alternate_framing`, `drop_fillers`, `drop_false_starts` |
| `pattern_interrupts` | `"auto"`: add toggling punch-ins on word starts until no stretch exceeds the style's `max_no_change_s` |
| `captions` | as in the EDL (template, highlight, keywords) |
| `graphics[]`, `broll[]` | as in the EDL, but timed with `at_word` (word index) and `dur_s` |
| `sfx` | a list (`asset`, `at_f` or `at_word`, `gain_db`, `role`, `reason`) or `"auto"` (density from the style) |
| `music` | an object or list as in the EDL |
| `color`, `master`, `privacy`, `notes`, `assumptions` | copied into the EDL |

What `draft` does: cuts land in word gaps with 0.1 s of air before the first word and 2/15 s after the last (1/3 s hold at the end); hard fillers and flagged false starts inside a beat are removed; pauses over the type's limit are tightened; jump cuts alternate framing; `punch` words get punch-ins; framing is scaled down to the zoom budget (no more than 2x upscaling of the source); each removed span is written to `notes`.

Excerpt:
```json
{"src": "romance_source", "words": [26, 56], "role": "tension", "drop": [[38, 46]],
 "reason": "Tension: the two costly ways past the wall - pay to play, or work up through a company",
 "rule_of_six": {"emotion": 6, "story": 8, "rhythm": 7}}
```

## Other project files
| File | Written by | Holds |
|---|---|---|
| `type.json` | detect_type.py | type, content type, scores, evidence, chosen style and why |
| `edl/vN.check.json` | plan_edit.py | errors, warnings, fixes, stats |
| `edl/vN.changes.md` | `plan_edit.py diff` | readable change list between versions |
| `hooks.json` | hook_variants.py | scored opening candidates |
| `retention.json`, `virality.json` | retention_sim.py, virality_score.py | risk curve and dips; score, risks, fixes |
| `render/<mode>/render.json` | render.py | what was rendered, colour plan, sound measurements, captions |
| `qc/qc_report.json`, `.md` | qc.py | every check with status, value, timestamps, fixes applied |
| `licenses.json` | render.py, fetch_assets.py | the license ledger |
| `timeline/` | export_timeline.py | .otio, .fcpxml, .xml, captions .srt, alpha overlay .mov, round-trip report |
| `package/<edl>/` | package.py | video, captions, titles, description, tags, thumbnails, credits, presets, disclosure, QC report |
