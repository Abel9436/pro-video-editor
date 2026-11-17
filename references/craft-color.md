# Colour

Read when footage is dark, mismatched, or needs a look. Order is fixed: **convert (log only), correct, match, grade, then finish.** Log footage is converted at ingest before anything else (references/craft-log.md).

## 1. Correction (render.py, `lib/color.correction`)
**Rule:** make the picture accurate first: exposure, white balance, contrast, saturation.
- Exposure: bring the face to L* 45-70 with a gamma change limited to +-0.25 (bigger moves show noise in 8-bit sources).
- White balance: neutralise the measured cast, gains limited to +-8 %.
*Every event when `color.correction` is "auto".* **Check:** qc.py `face_exposure` (fail when > 5 % of face pixels clip or crush).

## 2. Shot matching
**Rule:** every shot in a scene looks filmed at the same moment. Each event is moved 60 % toward the scene median of face L*, a*, b*.
**Check:** qc.py `shot_match`: neighbouring shots differ by no more than 8 L* or 6 a*b*.

## 3. Grade (a look at controlled strength)
**Rule:** apply a look by intent, blended at `strength` (0-1), never at full strength by default.

| Look | Use for |
|---|---|
| `warm_soft` | personal vlogs |
| `clean_neutral`, `clean_warm` | tech, education, talking heads |
| `muted_doc` | documentary |
| `punchy` | gaming |
| `teal_orange` | only where a cinematic style calls for it |
| `moody_night` | night scenes, thrillers |

Looks are generated `.cube` files (`assets/luts/generated/`), so no third-party LUT ships with the skill. A user LUT can be named by path.

## Skin is the anchor
- On a vectorscope, skin of all people clusters along one line between red and yellow. qc.py `skin_hue` isolates face regions and checks hue against that line as a reference (Lab hue band 5-60 degrees, wider than the line on purpose), flagging green or magenta casts. It is not a hard target.
- **Protect skin when applying a look**: generated looks pull their effect back inside the skin hue band (10-50 degrees).
- Check highlights are not clipped and shadows not crushed on faces (`face_exposure`).

## Pipeline notes
- Work in Rec.709 for SDR delivery. ingest.py tone-maps PQ/HLG sources to Rec.709 before anything else. The output is tagged bt709 (qc.py `format`).
- Preview on a phone-sized frame: `render.py --preview` renders 540 px wide.
- Very dark sources (`very_low_light` in media.json) get noisy when corrected: prefer a smaller gamma move plus a slightly warmer look over pushing exposure.

## 4. Finish
- **Halation** (`color.halation`, 0-1): film's red-orange glow around bright edges, from light scattering back through the emulsion. Highlights only, blurred and screened over the footage (graphics untouched). Try 0.2-0.4 for a film feel; 0 for clean commercial work.
- **Grain** (`design.finish.grain`): a 3D LUT cannot carry grain, halation or gate weave, so they are separate layers after the grade.
