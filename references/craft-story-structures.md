# Story structures

Read when writing the paper edit. Pick the structure for the type (detect_type.py), then map transcript word ranges onto its beats. Beat `role` values the scripts understand: `hook`, `setup`, `tension`, `payoff`, `reveal`, `answer`, `body`, `ending`, `cta`.

| Type | Structure |
|---|---|
| Short-form | Hook in the first 1-2 s -> tension or curiosity -> payoff -> loop or call to action. |
| YouTube long-form | Cold open or hook -> promise of the payoff -> setup -> escalating segments with re-hooks -> payoff -> end screen during the last moment of value. |
| Talking head, educational | Claim -> why it matters -> steps or points, each with a visual -> recap in one line. |
| Vlog | The day's arc, small stories inside it, an emotional thread, music-led montages between scenes. |
| Cinematic travel | Sense of place -> movement -> peak moment -> quiet ending. Music drives the structure. |
| Long podcast | Clean conversation; switch to the active speaker; reaction shots; remove dead air and false starts; chapter markers. |
| Podcast clip | A self-contained moment with a strong first line, reframed vertical, captions, a title card. |
| Documentary | Three acts; interviews drive the story; B-roll as evidence; sound design for tension. |
| Ad | Problem -> agitation -> solution -> proof -> call to action. |
| Gaming, reaction | Facecam layout; zooms on key moments; meme inserts used sparingly. |
| Narrated 3D explainer | Narration-led; one idea per scene; scale comparisons; short scenes. |

## Openings
**Choose deductive (state the conclusion, then explain) or inductive (build to the reveal) on purpose, and record why** in the paper edit's `opening` field.
- Deductive suits short-form and education: the viewer gets value in the first seconds and stays for the how.
- Inductive suits stories and reveals, and only works when the reveal is real.

## Checks
- **Hook, payoff, ending present** as planned: qc.py `structure`.
- **First payoff by 8 s (short) / 60 s (long)** (STARTING DEFAULTS): retention_sim `late_payoff`, virality_score `first_payoff_s`.
- **Promise kept**: judged by Claude in `--judged` for virality_score.

## Worked example (from the build test)
Source: a 60 s pre-edited talking head with a motivational business point. Chosen structure: deductive short.
1. hook (words 75-105, words 81-84 removed): "I know that you wanted me to tell you that there's this secret AI technology that guarantees you're going to become a millionaire and all this BS."
2. payoff (106-111): "That's not the way it works." (answers the hook at ~7 s)
3. setup (4-25): the real rule: insider knowledge, behind a wall.
4. tension (26-56): two costly ways past the wall.
5. payoff (184-212): be an apprentice.
6. ending (213-239): "start your own venture", the strongest cadence, no goodbye.
