# Anti-patterns

Read before approving a rough cut. Each entry: why it reads as amateur, how the skill detects it, and the fix.

| Anti-pattern | Why it reads amateur | Detection | Fix |
|---|---|---|---|
| Transitions on every cut | Draws attention to the edit instead of the content; pros are mostly hard cuts. | `style_distance` on the transition mix; plan_edit defaults every cut to `cut`. | Hard cuts; keep transitions for time passing or style. |
| Music louder than speech | The viewer strains, then leaves. | `music_voice_separation` (under 15 dB fails), `intelligibility` (WER > 15 %). | Duck deeper (`depth_db` -20 or lower); choose a track without vocals or mid-range energy. |
| Captions covering faces | The face carries the emotion. | `captions_on_faces`. | Fix loop moves cards above or below the face; `position: bottom`. |
| Cuts inside words | Audible clicks and missing syllables. | `cut_inside_word`, `first_consonant`. | plan_edit snaps cuts into word gaps (`check --fix`). |
| Random zooms | Movement without meaning is noise. | Zooms not on an emphasis word or interrupt point; `zooms_per_min` above the style range. | Punch on emphasis words (`punch: [word index]`) only. |
| Mixed icon styles | Looks assembled from different kits. | `project.kit.icons` set once; fetch_assets filters by set. | One Iconify set per video. |
| Stock that does not match what is said | Viewers notice and stop trusting the video. | Claude views a preview frame of every B-roll asset; the `reason` must name what it shows. | Leave the slot empty rather than fill it. |
| Long logo intros | Viewers swipe before the content. | `structure` (hook must be first); retention_sim `slow_start`. | Logo, if any, small in a corner (profile `logo`). |
| Fades on short-form | Costs the first second, which is the hook. | `virality` hook `motion_in_first_frame`. | Open on motion and the first word. |
| Effects before the story works | Polish cannot rescue a weak structure. | The workflow: no render before the paper edit is approved. | Fix the paper edit first. |
| Removing every pause from an emotional moment | Flattens emotion; jokes stop landing. | Beats marked `keep_pauses`; end hold. | Keep breath after punchlines and reveals. |
| Upscaled blurry inserts | Soft picture next to sharp picture. | `upscaling`. | Zoom budget; use higher-resolution B-roll. |
| Digital silence | Sounds like a dropout. | `digital_silence`. | Room tone fill. |
| Jump cuts with no framing change | Looks like an error. | `jump_cuts`. | Alternate framing or cover with B-roll. |
