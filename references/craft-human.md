# Edits that read as human

Read before designing any graphics pass. The rule: **one hero per moment, and every move explains something.** `scripts/slop_check.py` audits an EDL against this page before you render, and `qc.py` reports the same checks as warnings.

## What gives an edit away as machine-made

Measured on our own rejected edits (s25 v2 and amh2 v2, 2026-11-17) and named in the sources below:

| Tell | Our rejected s25 v2 | Fix |
|---|---|---|
| A sound on everything | 15 SFX in 19.7 s (46/min) | Sound only on an action the viewer sees land |
| Every caption has an emphasis | 11 emphasised words in 20 s | Emphasise the punchline only (`restraint_emphasis`) |
| Decoration that never leaves | Camera HUD on screen 79 % of the video | Show a graphic while it explains, then remove it |
| Five things moving at once | HUD + wipe line + labels + panel + captions | At most 3 layers, captions included |
| A camera that never rests | Animated zoom 79 % of the time | Hold most shots; one push where nothing else changes |
| The reveal spent repeatedly | The before/after line moved 4 times | One sweep, on the payoff |
| A cutaway that leaves the speaker for a template infographic | 4 s navy LUT cube | Show the real thing from the footage instead |
| Every word blurs and rises in | `cine`/`phrase` styles | `pop`: the phrase enters once, only the spoken word moves |

## What a seasoned editor does instead

- **Show what is being said, from the real footage.** "B-roll should explain, not decorate." Here, the knee-flexion line cuts back to the speaker's own rep, slows into the bottom and freezes, with the knee and line of action drawn on it (work/snap). Picture-only cutaways use `cutaway: true` on the video event.
- **Choose one idea per shot and one element to carry it.** "Animate only what supports it, and hold everything else still" (digicurator).
- **Punch in rarely**: "no more than once every three or four cuts" (Maximov). Hide jump cuts with a framing change, not a moving zoom.
- **Leave some air.** "A video with zero air feels nervous" (Maximov). Keep breaths after punchlines.
- **Use one consistent look** for type, colour and grade across the video. The grade comes from the location (craft-color.md).
- **Keep captions big, short and off the face.** Move them when a drawing needs the space (`caption_y_at`).
- **Set levels:** voice about −6 dB, SFX about −12 dB, music about −20 dB (Maximov). Our QC wants music 18–24 dB under the voice.

## Motion craft (LottieFiles motion-design skill, MIT, adapted to video)

- **Pick one personality per video and stay in it.** Premium: 350–600 ms, `cubic-bezier(0.4,0,0.2,1)`, no overshoot. Energetic: 100–250 ms, ease-out-expo, 15–30 % overshoot.
- **Pick one signature ease for about 80 % of moves**, and a palette of three durations.
- **Ease entrances out and exits in.** Entrances run 30–50 % longer than exits. Never use linear easing on spatial motion.
- **1/3 rules:** no move travels more than a third of the frame without a keyframe, and no more than a third of the elements move at once.
- **Keep the total stagger under 500 ms.** Follow-through offsets run 50–150 ms.
- **Ask whether it's still fine on the 100th viewing.** If the move is only there to be noticed, cut it.

The full tables (durations by element, material and distance; emotion and direction; ambient recipes; hierarchy; transition, camera and sound-design limits) are in craft-motion-principles.md.

## Limits used by slop_check (all warnings)

| Check | Limit | Source |
|---|---|---|
| `restraint_sfx` | 20 / min | STARTING DEFAULT (rejected edits ran 46–60/min) |
| `restraint_fx` | 4 / min | STARTING DEFAULT |
| `restraint_emphasis` | 2 per 10 s | STARTING DEFAULT ("only emphasise the punchlines") |
| `restraint_persistent_overlay` | 50 % of runtime | STARTING DEFAULT |
| `restraint_concurrent_layers` | 3 | STARTING DEFAULT (LottieFiles 1/3 rule; "five things at once reads as noise") |
| `restraint_moving_camera` | 40 % of runtime | STARTING DEFAULT |
| `restraint_punch_ins` | 1 per 3 shots | Maximov, "once every three or four cuts" |
| `restraint_reveal_spent_once` | 2 moves | STARTING DEFAULT |
| `restraint_sfx_gap` | no two sounds 1 frame to 0.2 s apart; same-frame stacks of at most 3 | motion-designer, sound-effects.md ("minimum 0.2 s", "layer 2-3 SFX") |
| `restraint_sfx_repeat` | one file at most 3 times | STARTING DEFAULT (motion-designer: "3-5 different whooshes") |

These are starting defaults, not measurements. Break one on purpose and say why in the EDL notes.

## Sources

- LottieFiles, motion-design-skill (MIT): github.com/LottieFiles/motion-design-skill, in particular SKILL.md, reference/troubleshooting.md and reference/quality-checklist.md.
- "AI Motion Graphics Skills That Don't Look Like Slop", blog.digicuratoragency.com.
- "AI Slop in Video", reap.video/blog/ai-slop-video.
- "To make AI video look real, we have to make it look less perfect", inizioengage.com.
- Evgeny Maximov, "Talking Head Video Editing", evgenymaximov.com/blog/talking-head-video-editing (agency house rules, not research).
- Taylor Gunn, "Retention editing isn't what you think" (paywalled; only the thesis was readable: over-editing mistakes fatigue for finesse).
