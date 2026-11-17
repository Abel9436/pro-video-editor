# Motion and typography

Read when placing captions, titles, callouts, lower thirds or zooms.

## Type
- **At most two type families per video** (profile `fonts.caption` and `fonts.heading`; defaults Poppins ExtraBold and Anton, plus Noto Sans Ethiopic for Ge'ez). **Check:** render.py uses only the profile fonts.
- **High contrast against the background**: white text with a black stroke, or a box. **Check:** qc.py `caption_contrast` (white fill with a black stroke gives 21:1 against any background; a template without a stroke or box must be checked by eye).
- **Inside each platform's safe zone** (platforms.md). **Check:** `caption_safe_zone`.

## Captions
| | Short-form | Long-form |
|---|---|---|
| Template | `pop_3word` (or `bold_1word`) | `clean_line` |
| Words per card | 1-3 (measured refs: median 3) | full readable lines, two lines at most |
| Timing | to the spoken word | to the sentence |
| Highlight | one keyword per card, in the profile's primary colour | none or speaker colour |
| Position | centre band (y 0.70 for Shorts) | bottom |

- **Reading speed:** at most 25 characters per second short, 20 long (STARTING DEFAULTS). **Check:** `reading_speed`.
- **Never over a face.** render.py moves a card off a face it would cover; qc.py `captions_on_faces` (faces scoring >= 0.85, aspect 0.9-1.8, 20th-80th percentile box per card, so a hand or microphone does not count) and the fix loop moves remaining cards.
- **Always deliver SRT and VTT** alongside burned-in captions (`sidecar_captions`).

## Motion principles
- Ease in and out, anticipation, overshoot and settle, staggered entrances. **Never linear movement.** EDL `ease`: `out_cubic`, `in_out_sine`, `out_back` (overshoot). The pop_3word caption scales 80 % -> 106 % -> 100 % over 150 ms.
- **The viewer should know where to look within half a second.** One focal point at a time: do not show a callout while a title is on screen.
- **One icon family, one 3D style, one sound kit per video**, recorded in `project.kit`.

## Zoom grammar
| Move | Meaning | EDL |
|---|---|---|
| Slow push-in | builds intensity over a line | `push_in`, `in_out_sine`, duration = the line |
| Punch-in | emphasises one word | `punch_in`, scale 1.08-1.2, 4 frames, `out_cubic`, on the word's first frame |
| Pull-out | reveals context | `pull_out` |
| Alternating framing | makes a jump cut look intentional | `reframe.zoom` alternates between 1.0 and the punch scale |

**Zoom budget:** the total zoom (reframe x punch-ins) is capped so the source is never upscaled beyond 2x (plan_edit `fit_zoom_budget`). A 720p source in a 1080p frame starts at 1.5x, so it gets about 1.32x of zoom; 4K footage gets far more. **Check:** qc.py `upscaling` (warn > 1.5x, fail > 2x).

**Random zooms are an anti-pattern:** every punch-in sits on an emphasis word, a keyword, or a pattern-interrupt point.
