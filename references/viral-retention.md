# Retention editing

Read for retention-style projects after the first draft, alongside the retention_sim.py output.

| Rule | Default (STARTING DEFAULT unless the style measures it) | Check |
|---|---|---|
| Remove dead air, fillers, false starts and repeats, except pauses that carry emotion or comedy | gap >= 0.6 s with nothing else happening is dead air | retention_sim `dead_air`, `repeated_point` (sentence similarity >= 0.6) |
| Change something visible regularly | style `structure.max_no_change_s`; 4 s short / 10 s long | retention_sim `no_visual_change`; `pattern_interrupts: auto` |
| Re-hook at intervals | short-form every 5-10 s, long-form every 30-60 s | virality_score `rehook_gaps_s` |
| First payoff early | by 8 s (short) / 60 s (long) | `late_payoff`, `first_payoff_s` |
| Give each named thing a visual | B-roll, callout or icon on concrete nouns | retention_sim `talking_only` (talking head with no B-roll or graphic for 2x the change limit) |
| Highlight one keyword per caption card | caption `highlight: keyword` | render.py |
| Escalate | each beat a little bigger than the last; second-best moment first, best last | Claude, in the paper edit |
| End on the payoff, no goodbye | end hold 1/3 s after the last word | qc.py `structure` |
| Loop the short | end a few frames early; make the last moment flow into the first | virality_score `loop_similarity` (target 0.6) |
| Length | as short as the story allows; 15-35 s for most shorts | qc.py `duration` against `target_duration_s` |

## Using retention_sim.py
`python scripts/retention_sim.py --edl P/edl/v1.json --project P` writes `retention.json` with a risk curve (0-1 per second) and dips (risk >= 0.35) with reasons. Fix the dips from the start of the video: an early dip loses viewers before the later fixes can matter. The curve is predicted structural risk. When the creator shares real retention, `profile.py analytics` compares predicted dips with real drops.

## What counts as a visible change
Cuts, transforms (punch-in, push, pull), B-roll in and out, graphics entrances, and cuts that already exist inside pre-edited source footage (`analysis.shots`). Caption cards changing do **not** count: they change every second and viewers stop seeing them as change.

## Guardrails
No fake hooks, no misleading edits of what someone said, no rage bait by default, no claims of guaranteed virality, no copying a trending video's content. Borrow structure only.
