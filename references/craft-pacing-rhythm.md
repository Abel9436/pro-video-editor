# Pacing and rhythm

Read when setting shot lengths, tightening speech, or cutting to music.

## Shot length
**Rule:** start from the style fingerprint's `shot_len_s.med` and range. Without one, use these STARTING DEFAULTS:

| Type | Average shot length |
|---|---|
| Short-form | 1-2 s (measured refs: median 2.0 s, range 1.4-5.1 s) |
| Talking head | 3-6 s |
| Vlog | 2-5 s |
| Cinematic, documentary | 4-10 s |
| Long podcast | 5-20 s |

**Check:** qc.py `style_distance` (fields `cuts_per_min`, `shot_len_s.med`).

## Pace in waves
**Rule:** fast, slow, fast. Constant speed tires the viewer. Speed up through setup; slow down for the important point.
*Anything over ~20 s.* **Check:** `plan_edit.py diff` and the per-beat event lengths; Claude marks the slow beat in the paper edit (`keep_pauses: true`).

## Cutting to speech
- **Cut in breath gaps, never inside a word.** plan_edit puts cuts between words; when the gap is tight it cuts in the middle of the gap. **Check:** qc.py `cut_inside_word`.
- **Leave air before a word** so the first consonant survives: `AIR_F_S` = 0.1 s (2-4 frames at 25-30 fps). **Check:** qc.py `first_consonant`.
- **Tighten the gap before a punchline; hold a beat after it.** Pauses longer than `MAX_PAUSE_S` (short-form 0.35 s, podcast clip 0.4 s, talking head 0.5 s, others 0.75 s, STARTING DEFAULTS) are tightened unless the beat is `keep_pauses`.
- **Remove fillers and false starts** (`speech.fillers` kind hard, `speech.false_starts`). Soft fillers ("like", "so") are judged in context.

## Cutting to music
- **Land important cuts on beats and the biggest moments on downbeats** (`music.beats_f`, `downbeats_f`). Do not cut on every beat: that reads as a metronome.
- **Align section changes** with musical section changes (`music.sections`).
- **Check:** fingerprint `audio.cuts_on_beat_pct` against `audio.cuts_on_beat_chance_pct` (what random cuts would score).

## Pattern interrupts (retention styles)
**Rule:** change something visible every few seconds: angle, scale, B-roll, text, or graphic. The interval is the style's `structure.max_no_change_s` (measured short-form refs: 4.5 s median; STARTING DEFAULT 4 s short / 10 s long).
**Check:** retention_sim `no_visual_change`; `"pattern_interrupts": "auto"` in the paper edit adds toggling punch-ins on word starts until no stretch exceeds the limit. Cuts already inside pre-edited source footage count as changes.
