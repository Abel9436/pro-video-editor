# Why people share

Read for retention-style projects when judging the cut (the judged fields of virality_score.py).

## STEPPS (Jonah Berger)
Score each 0-10 with a one-line reason, and pass them to `virality_score.py --judged`.
| Field | Question to ask of the edit |
|---|---|
| `social_currency` | Does sharing this make the sharer look smart, early or funny? |
| `triggers` | Is it tied to an everyday cue that will bring it back to mind? |
| `emotion` | Does it make the viewer feel something strongly? |
| `public` | Is the idea visible and easy to copy? |
| `practical_value` | Is it useful enough to send to someone? |
| `stories` | Is there a narrative worth retelling? |

## Arousal
- High-arousal emotions drive sharing: awe, excitement, amusement, and also anger and anxiety. Low-arousal states (sadness, contentment) reduce it.
- **Default to awe, humour, surprise and curiosity. Do not manufacture outrage.** Rage bait is off unless the user asks for it and the content is honest.
- Record `emotion: {"dominant": ..., "arousal": "high"|"low"}` in the judged file.

## Curiosity, novelty, load, identity
- **Curiosity gap:** open a question early, answer it late, but not later than the first payoff limit (8 s short / 60 s long, STARTING DEFAULTS). Open loops: promise what is coming ("the third one surprised me").
- **Novelty:** the brain notices change. This is why pattern interrupts work (craft-pacing-rhythm.md).
- **Cognitive load:** never stack dense text, a busy picture and fast speech at once. One focal point.
- **Identity:** people share what says something about who they are. Frame for the viewer's identity ("if you're starting out...").

## Judged file format
```json
{"emotion": {"dominant": "surprise", "arousal": "high"},
 "stepps": {"social_currency": 7, "triggers": 4, "emotion": 8, "public": 5, "practical_value": 6, "stories": 7},
 "promise_kept": true,
 "reasons": {"emotion": "contrarian hook flips the viewer's expectation", "promise_kept": "the hook's question is answered at 0:07"}}
```
