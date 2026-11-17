# Cut vocabulary

Read when choosing how two shots meet. For each: definition, purpose, when to use, when not to, and how it appears in the EDL.

| Cut | Definition and purpose | Use when | Avoid when | EDL |
|---|---|---|---|---|
| Hard cut | Instant change. The default. | Almost always. | Never "avoid"; it is the baseline. | `transition_in: "cut"` |
| Jump cut | Cut within one continuous shot to compress time. | Single-camera talking head, removing pauses and fillers. | Interviews meant to feel calm; when the jump would hide a meaning change. | Consecutive events from one `src`; plan_edit alternates `reframe.zoom` so the jump reads as intentional. |
| J-cut | The next shot's audio starts before its picture. Creates anticipation. | Introducing a speaker, entering a new scene with its sound. | When the new audio would talk over an important line. | Beat `"split": "j_cut", "split_f": N`; dialogue event marked `split_edit: "j_cut"`. |
| L-cut | The previous audio continues over the next picture. Extends emotion. | Reactions, B-roll over the end of a line, carrying ambience across a cut. | When the picture change needs its own sound to land. | `"split": "l_cut"`. |
| Match on action | Cut mid-movement so the motion hides the cut. | Multi-angle footage of the same action. | Single camera (no second angle). | Two events with `reason` naming the action; cut frame in the movement. |
| Match cut | Shape, motion or sound links two different shots. | Transitions between ideas, time jumps. | When the link is weak; a forced match looks clever, not good. | `reason: "match cut: round clock face -> round plate"`. |
| Smash cut | Abrupt tonal contrast. | Comedy, shock; once per video at most. | Serious or emotional pieces. | Hard cut + `reason` starting "smash cut". |
| Cutaway / insert | Show what is being talked about; also hides a jump cut. | Concrete nouns, numbers, objects, places. | When the B-roll does not show what is said (generic stock). | `broll[]` with `at_f`, `dur_f`, `asset` or `src`, and a `reason`. |
| Cross-cut | Alternate between two threads. | Parallel stories, before/after. | Short-form under 30 s (too little time to set up two threads). | Alternating `src` per beat. |
| Montage | A series of short shots compressing time or building up. | Vlogs between scenes, travel, process. | Talking points that need words. | A run of short events, usually cut on beats (`music.beats_f`). |
| Invisible cut | Whip pan, object wipe, or darkness hides the cut. | Energetic styles with matching motion direction. | Static footage (there is nothing to hide the cut with). | `transition_in: "whip"`. |
| Speed ramp | Speed changes within a shot. | Action peaks, travel, sport. | Speech (pitch and lip sync break). | `speed` on the event. |
| Freeze frame | Hold one frame. | Introducing a person, comedic beat. | More than once or twice per video. | `freeze_f`. |
| Split screen | Two pictures at once. | Before/after, reactions next to gameplay. | Vertical shorts where both halves get too small. | `graphics[]` layout component. |

## Transitions
- **Dissolve** for time passing. **Fade** for beginnings and endings of long-form (never on short-form: a fade at the start costs the hook).
- **Whip and zoom transitions** only in energetic styles, and only when the motion direction of both shots matches.
- The style's `transition_mix` sets the proportions; qc.py `style_distance` reports drift.

## Continuity and eye trace
- **180-degree rule:** keep the camera on one side of the line between two people. **30-degree rule:** a cut between two shots of the same subject needs at least a 30-degree angle change or a clear size change, or it reads as a jump (qc.py `jump_cuts` flags same-framing cuts with no zoom change).
- **Eyeline match, screen direction, consistent props and light** across a scene.
- **Eye trace:** put the next shot's subject where the viewer is already looking. Face-tracked reframing (render.py) keeps the face on the same thirds line across cuts for this reason.
