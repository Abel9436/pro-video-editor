# Revisions

Read when the user gives feedback on a cut. Map the phrase to concrete changes, make a new EDL version, and show the change list.

## Versions
- Every approved or revised EDL is saved as `edl/v1.json`, `v2.json`, `v3.json`... and is never overwritten. Paper edits are versioned the same way (`paper_v2.json`).
- After each revision: `python scripts/plan_edit.py diff P/edl/v1.json P/edl/v2.json --project P` writes `v2.changes.md`, a readable change list (length, cuts/min, zooms, shots added and removed with timecodes, new notes). Show it to the user.
- Any version can be re-rendered: `render.py --edl P/edl/vN.json`.
- After an approved revision: `profile.py learn NAME --from vN --to vN+1 --note "<the user's words>"`, so repeated preferences are learned.

## Feedback -> change
| The user says | Change |
|---|---|
| "punchier", "faster" | shorter shots (lower the style's `shot_len_s`), `MAX_PAUSE_S` down, more punch-ins on emphasis words, more SFX accents |
| "too slow in the middle" | run retention_sim.py; trim the risk span or add a re-hook there (B-roll, callout, punch-in) |
| "more emotional" | longer holds (`keep_pauses`), L-cuts on reactions, a music change, fewer effects |
| "cleaner", "less busy" | fewer SFX and zooms, `clean_line` captions, no callouts, hard cuts only |
| "more cinematic" | slower pace, a grade (`teal_orange` or `muted_doc` at 0.5-0.7), wider framing (`reframe.zoom` 1.0), music-led, fewer captions |
| "like a documentary" | switch the style to `documentary`, `muted_doc` look, lower thirds, evidence B-roll, dissolves for time |
| "more energy" | music with a higher BPM, cuts on beats, zoom transitions where motion matches |
| "the hook is weak" | hook_variants.py; export 2-3 variants for an A/B test |
| "the captions are too much" | `clean_line` or `bold_1word`; highlight off; fewer keywords |
| "can't hear him", "music too loud" | duck deeper (`depth_db` -24), lower `gain_db`, or remove music |
| "too long" | drop the weakest beat (lowest `rule_of_six` story score) before trimming inside beats |
| "don't cut that part" | restore the beat; add the phrase to the profile's `never_cut` |
| "wrong name spelling" | `profile.py add NAME names "Correct Spelling"`; re-render the captions |

**Ask one clarifying question only when a note could mean opposite things** (e.g. "make it more dramatic" could mean slower and darker or faster and louder). Otherwise apply the mapping and show the change list.

## Unattended mode
For scheduled or batch runs: ask no questions, apply the defaults, and list every assumption in the EDL's `assumptions` and the QC report.
