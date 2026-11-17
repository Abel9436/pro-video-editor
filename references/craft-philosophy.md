# Craft philosophy

Read before writing any paper edit. These rules decide what a cut is for; the other craft files decide how.

Each rule: **the rule**, *when it applies*, and **check** (how the skill tests it).

## 1. Rule of Six (Walter Murch)
**Rank what a cut must serve: emotion 51 %, story 23 %, rhythm 10 %, eye trace 7 %, 2D plane of the screen 5 %, 3D spatial continuity 4 %.** When a cut cannot satisfy all six, give up from the bottom of the list first: a continuity error that keeps the emotion beats a clean match that loses it.
*Always.* Score emotion, story and rhythm 0-10 for the first cut of every beat, in the paper edit's `rule_of_six`.
**Check:** `plan_edit.py check` warns when a beat has no `rule_of_six`; a cut scoring below 5 on emotion and story both needs a better reason or should go.

Example: a speaker stumbles mid-sentence but the retake is flat. Keep the stumble (emotion 8, continuity 3) rather than the retake (emotion 4, continuity 9).

## 2. Kuleshov: meaning lives between two shots
**Ask what the pair of shots says together, not what each shows.** A neutral face followed by a coffin reads as grief; followed by soup, as hunger. B-roll is therefore a story decision, not filler.
*Every B-roll insert, cutaway and reaction shot.*
**Check:** every `broll[]` entry has a `reason` naming what it shows *and* what it means next to the line under it; generic "visual variety" reasons are rejected in review.

## 3. Every cut needs a reason
**Cut only for: new information, a reaction, emphasis, rhythm, or removing something that does not serve the viewer.** No reason, no cut.
*Every event in the EDL.*
**Check:** qc.py `reasons` fails any video event without a `reason`. Jump cuts inside a beat inherit "removes a pause or filler"; anything else is written by Claude.

## 4. Restraint
**Add an effect, zoom, sound or transition only when it serves the moment.** Most professional edits are mostly hard cuts; the measured short-form refs are 56 % hard cuts even in an energetic style.
*Every transform, transition, SFX and graphic.*
**Check:** qc.py `style_distance` compares zooms/min, SFX/min and the transition mix with the style; above the style's `hi` is a warning. plan_edit's `pattern_interrupts: auto` adds the minimum needed, never more.

## 5. Breathing room
**Let silence and held shots land emotion.** Do not remove every pause in emotional or comedic beats: the beat after a punchline is part of the joke.
*Beats marked `keep_pauses: true`, punchlines, reveals, the last line.*
**Check:** plan_edit keeps pauses in `keep_pauses` beats and holds `END_HOLD_S` (1/3 s) after the last word; retention_sim does not flag dead air at a planned hold.

## 6. Serve the viewer, not the footage
**Cut good material that does not serve the story.** The test is the viewer's question at that moment, not how hard the shot was to get.
*Selects and paper edit.*
**Check:** the paper edit's `notes` list every dropped beat with why (e.g. "Dropped the 'principles remain' beat: it delayed the answer").

## 7. Never change what a person meant
**Never join words into a sentence the speaker did not say.** Removing a filler or a restated clause is fine; removing "not", or splicing the start of one sentence onto the end of another to create a claim, is not.
*Every removal inside a sentence.*
**Check:** plan_edit writes a note for every removed span inside a beat ("Removed 'to come here and' (words 81-84...)"). Claude rereads the resulting sentence aloud before approving; qc.py `intelligibility` re-transcribes the mix so the delivered words can be compared with the plan.

## Workflow order
Organise -> selects -> paper edit -> assembly -> rough cut -> fine cut -> picture lock -> sound, colour, graphics, captions -> QC -> delivery. **Never polish before the story is approved** (checkpoint 1 is the paper edit, checkpoint 2 the preview).
