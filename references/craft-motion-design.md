# House style: motion design that reads as pro-edited

Read before designing any talking-head short. For the level of finish by eye, see the reference reels in [frames/](frames/README.md). This page is the owner's taste, learned from six rounds of rejected and accepted edits (2026-11-15 to 2026-11-17). [craft-human.md](craft-human.md) covers restraint; this page covers what the motion design must *be*. They don't conflict: every move must be motivated, and the motivated moves must be rich.

## What was rejected, and why

| Round | What we delivered | Verdict | Lesson |
|---|---|---|---|
| 1 | Star-field SVG scenes, line icons, no music | "robotic, AI-like" | Generated decoration is not design |
| 2 | Stock b-roll, 62-66 px captions in two styles | "use motion graphics, not b-roll"; captions "too small", "not consistent" | One caption style, ~85-100 px, same place all video |
| 3 | UI cards and boxed strip captions | "generic" | Never use the boxed strip captions |
| 4 | The same look again, 3D cartoon icons as stickers | "the same way", "same colour", "AI components" | A new palette and grade every video; no emoji or clip-art |
| 5 | A HUD on screen 79 % of the time, 46-60 SFX/min | "AI slop" | Excess is the tell: `slop_check.py` limits |
| 6 | Restrained overlays only | "you are just playing with the captions" | Restraint is not plainness: the footage itself must move |
| 7 | 3D explainer stages, footage folded into 3D cards, extruded titles, 3D flips | accepted | The pattern below |
| 8 | Round 7's pattern again on a real-estate video (stages, card fold, flips, pop captions, DM Serif) | "generic", "like a very beginner", "you are just copying the last video's effects" | Round 7 was one answer, not a template: design every video from its own story (Fresh grammar, below) |

## Fresh grammar: design each video from its own story (2026-11-19, the first rule)

When new raw footage comes in, act like an editor seeing it for the first time, not like a template:

1. **Read the story, then the subject.** One line on what it is about and where the joke or turn is (house v3: "they got ready to list and never had to"). List the nouns of the subject's world (listing, status, offers, a phone call, the rooms, showings, open houses, relationships) and make the graphics *from those things*: a listing card for this property stamped NEVER LISTED, a status track, offers fanning in, a call bar, the rooms orbiting her. A graphic that would fit any video is decoration.
2. **Show the real thing.** Photos come from the footage itself (stills of the rooms into `P/images/`), screenshots from the client, the real place. Never stock, never invented proof.
3. **Every kind of motion graphic, not only captions:** words layered behind the speaker (`Lockup`), UI-style cards (`PhotoCard`, `Call`, `Track`), objects that fly in (`Fan`), 3D around the speaker (`Orbit` front and back halves), marks drawn on (`Strikes`), systems that grow (`Web`), signatures (`Lockup` script). Stages and card folds (`Stage3D`, `card`) are still in the kit, for explainers.
4. **A new type voice every video.** Search beyond the default faces (DM Serif, Playfair, Cormorant, Instrument Serif, Montserrat, Anton are the AI tells). Pick from the subject: real estate and lifestyle got Bodoni Moda (fashion serif), Hanken Grotesk light (quiet captions), Italiana (thin capitals), Pinyon Script (signatures). Free licences only (OFL via `fetch_fonts.py`).
5. **Captions fit the voice.** Bold pop captions suit energy; a calm, premium speaker gets `whisper` captions (small, light, one word at a time) as in the property reels the owner sent.
6. **Second worked answer: an explainer in a branded world** (amh3, Open Bodybuilding, 2026-11-19). The subject is a competition spec, so the graphics are a spec sheet (lib/hf_spec.py): `World` replaces the speaker's backdrop with the brand's 3D studio (behind the matte, full-frame spans only), `Ring` draws the hook's zero round his head, `Stat` lands a slot number on 0, `FlipCard` turns the myth into the answer, `Meters` (under a camera `card`) slams each requirement to MAX, `Divisions` runs curve, strike and dealt cards, `NextUp` presses follow, `plate` captions. When the card folds, the original wall shows inside it: grade its hue to the brand (`color.look.hues` shift, test the shift on a still first) so the card matches the set.
7. **Check it.** `slop_check.py` runs `fresh_grammar`: it compares this edit's devices, title font and caption style with the last projects in the design log (`~/.pve/design_log.jsonl`, written by every final render) and warns when more than half is reused or the type voice is the same. v2 of the house edit scored 71 % against the snap edit; v3 scored 15 %.

## The pattern that was accepted in round 7 (an explainer answer, not a template)

1. **The footage moves.** At least twice in a 20-40 s short, the speaker's clip folds into a tilted 3D card (`camera` entry with `card`) and a set builds behind it (`Stage3D` or `Podium3D`, `under: true`). The card unfolds back to full frame when the idea ends: the end of a stage is the start of the next sentence, never later.
2. **Explain the idea, don't decorate it.** Each stage shows the argument being made: a claim struck through, a headline number, cards that flip in for each reason, a podium for a ranking. One idea per stage, one 3D icon per card at most, from the meaning of the line (gym for leg day, target for doing it properly, trophy for "the best").
3. **Type is solid and 3D.** Titles behind the speaker are `Title3D` (extruded, stand up from the floor or spin in), in a display font chosen for the language. One hero word or number at a time.
4. **Transitions turn in 3D.** `flip3d` where the picture source changes (speaker to demo and back); a flash only for a freeze. At most three transitions a video, each covering a real change.
5. **One hero beat from the real footage.** The best moment of the video re-uses the speaker's own picture: slow it into the key position, freeze, and draw the analysis on it (`Telestrate`, `cutaway: true`, `freeze_f`).
6. **Captions:** `pop` style (the phrase enters once, the spoken word lights up), 84-96 px, one font, at most 2 emphasis words per 10 s. Move them (`caption_y_at`) when a stage needs the space; never let two phrases show at once.
7. **Colour:** pick the accent from the location (the plates, the walls, the shirt) or take the owner's brand colour when given. Grade every video (`grade.json`, deep contrast, skin protected). For a dark brand colour, thin lines use a tint of it (`_tint`) so they stay visible.
8. **Sound:** music ducked to -20 dB under speech (-18 sits on the QC edge), about 9 SFX in 30 s, each on something that visibly lands. Give every SFX `"align": "peak"` so its loudest moment lands on the frame (a riser: `"end"`). Whooshes only under things that travel (a fold, a flip, a push); a cut, flash or landing gets a tick, pop or soft hit. No dings, bells or typing. Items arriving in a row get the same tick stepped up in `pitch` (0.94, 1.0, 1.06...), never the identical sample.

## Finish: what makes the motion read as filmed, not assembled

Learned from a study of a product-ad motion skill (2026-11-18) and kept only where it fits edited footage. Most are built into `lib/hf_explainer.py`; the rest are review habits.

1. **One key light.** Every extrusion, drop shadow, box shadow and set glow comes from `LIGHT` (default high, front-left). Shadows pointing different ways are what make 3D type look like clip-art.
2. **One lens.** Every 3D element uses `PERSP`. Mixed perspectives make a set look stitched together.
3. **Moves never turn back.** No zoom in then out, no float that bobs up and down, no bounce or elastic. Drifts go one way and settle. The card keeps a slow push while it is held, so the unfold carries the same move on.
4. **No dissolves between design shots.** A stage leaves by pushing through the lens (`exit: "push"`, the default) or holds until the unfolding card covers it (`exit: "cut"`).
5. **Depth of field.** The set has sharp far specks and large blurred near motes. Headlines rack from blur into focus as they land. Footage stays sharp.
6. **Slow settles.** Arrive fast, settle for longer than the arrival took (expo.out). If a move needs a second look to read, make it about 50 % longer.
7. **Lines that survive a push.** Nothing thinner than 3-4 px moves in perspective or under a camera push; it shimmers. Fetch icons at twice the largest size they reach.
8. **A still, centred end.** The closing word or call to action holds still (`still: true`) for 0.6-1 s, centred by what you see of it.
9. **Spend the finish once.** One light sweep (`sheen`) on the hero word, one riser ending exactly on the hero beat. Nowhere else.
10. **Titles that are lines.** `enter: "words"` brings each word up out of a blur, no overshoot. Captions stay `pop`: the owner rejected blur-in captions.
11. **Vary the grammar, not only the palette.** A new video changes at least two of: which side the card folds to, its tilt, the flip direction, the stage type, and where the title stands.

**Review transitions, not holds.** After the render, run `scripts/design_stills.py --video P/exports/vN.mp4 --edl P/edl/vN.json`. It makes a sheet with every design event at -0.10, 0, +0.15 and +0.40 s. Look for shapes passing through each other, a frame of nothing, a card leaving the frame or a misplaced word, then watch the video: stills are not playback.

**Design storyboard (when there is time for a gate).** Before the full render, show the beats as a numbered table: time, the words each hangs on, what moves, how it becomes the next beat, and the sound on it. Ask whether every beat turns into the next, whether the key thing sits where the eye already is, whether something drifts in every hold, and whether any move is too quick. Take notes by beat number.

## Fonts and assets (all licensed, fetched per project)

| Need | Source | Fetch |
|---|---|---|
| Amharic captions and titles | font.et, SIL OFL entries only. Newest first (sort fonts.json by `publishedAt`): Difres (2026-11-04, variable 300-700, captions and body), Tsega Elto (2026-10-12, geometric titles), Nael Tarik; earlier Menbere, Zemach, Bela Bereka. Change the pair per video | `scripts/fetch_fontet.py get --project P Difres "Tsega Elto"` |
| Latin display and numbers | Google Fonts, chosen per video (e.g. Bodoni Moda, Hanken Grotesk, Italiana, Pinyon Script for property; not the overused defaults) | `scripts/fetch_fonts.py --project P "Bodoni Moda:italic400" ...` |
| Photos for cards and orbits | stills from the footage itself, graded: `ffmpeg -ss T -i P/render/final/picture_graded.mp4 -frames:v 1 P/images/room.jpg` | copied into the HyperFrames project by render.py |
| 3D icons in stages | 3dicons, CC0, `color` style | `scripts/fetch_3dicons.py get --project P gym trophy target` |
| Line icons to draw on | Lucide, ISC | `scripts/fetch_lineicons.py` |
| SFX | Freesound CC0 / Kenney | `scripts/fetch_sfx.py` |
| Music | Mixkit Stock Music Free License (social, ads, YouTube; no broadcast, no Content ID) | `scripts/fetch_music.py get --project P --query workout --pick 0` |

Never ship a font or asset inside the skill; every fetch writes its licence into `P/licenses.json`.

## Worked example

`examples/snap/make_edl.py` builds the accepted edit (Amharic gym coach, 27 s): reasons stage with struck claim, "2 reasons" headline and two flip cards; podium where the exercise rises to #1 and a trophy lands; 3D "1" behind him; flip into his slowed, frozen rep with the knee angle and line of action drawn on; 3D call-to-action word. Read it before writing a new video's design script: it shows how word timings drive every beat.

## Before/after reels

When the owner wants to show the work, `scripts/before_after.py` builds the showcase format (amber set, tilted black-and-white Before card with the raw footage cut like the edit, the After card, neon handwritten labels, an EDL-drawn timeline with a moving playhead). It needs a licensed handwritten font (`--script-font`, e.g. Mrs Saint Delafield, OFL, from github.com/google/fonts).
