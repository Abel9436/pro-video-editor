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

## The pattern that was accepted

1. **The footage moves.** At least twice in a 20-40 s short, the speaker's clip folds into a tilted 3D card (`camera` entry with `card`) and a set builds behind it (`Stage3D` or `Podium3D`, `under: true`). The card unfolds back to full frame when the idea ends: the end of a stage is the start of the next sentence, never later.
2. **Explain the idea, don't decorate it.** Each stage shows the argument being made: a claim struck through, a headline number, cards that flip in for each reason, a podium for a ranking. One idea per stage, one 3D icon per card at most, from the meaning of the line (gym for leg day, target for doing it properly, trophy for "the best").
3. **Type is solid and 3D.** Titles behind the speaker are `Title3D` (extruded, stand up from the floor or spin in), in a display font chosen for the language. One hero word or number at a time.
4. **Transitions turn in 3D.** `flip3d` where the picture source changes (speaker to demo and back); a flash only for a freeze. At most three transitions a video, each covering a real change.
5. **One hero beat from the real footage.** The best moment of the video re-uses the speaker's own picture: slow it into the key position, freeze, and draw the analysis on it (`Telestrate`, `cutaway: true`, `freeze_f`).
6. **Captions:** `pop` style (the phrase enters once, the spoken word lights up), 84-96 px, one font, at most 2 emphasis words per 10 s. Move them (`caption_y_at`) when a stage needs the space; never let two phrases show at once.
7. **Colour:** pick the accent from the location (the plates, the walls, the shirt) or take the owner's brand colour when given. Grade every video (`grade.json`, deep contrast, skin protected). For a dark brand colour, thin lines use a tint of it (`_tint`) so they stay visible.
8. **Sound:** music ducked to -20 dB under speech (-18 sits on the QC edge), about 9 SFX in 30 s, each on something that visibly lands.

## Fonts and assets (all licensed, fetched per project)

| Need | Source | Fetch |
|---|---|---|
| Amharic captions and titles | font.et, SIL OFL entries only: Menbere (captions, variable 100-700), Zemach (titles), Bela Bereka (emphasis) | `scripts/fetch_fontet.py get --project P Menbere Zemach "Bela Bereka"` |
| Latin display and numbers | Google Fonts (Anton, Montserrat, JetBrains Mono) | `scripts/fetch_fonts.py` |
| 3D icons in stages | 3dicons, CC0, `color` style | `scripts/fetch_3dicons.py get --project P gym trophy target` |
| Line icons to draw on | Lucide, ISC | `scripts/fetch_lineicons.py` |
| SFX | Freesound CC0 / Kenney | `scripts/fetch_sfx.py` |
| Music | Mixkit Stock Music Free License (social, ads, YouTube; no broadcast, no Content ID) | `scripts/fetch_music.py get --project P --query workout --pick 0` |

Never ship a font or asset inside the skill; every fetch writes its licence into `P/licenses.json`.

## Worked example

`examples/snap/make_edl.py` builds the accepted edit (Amharic gym coach, 27 s): reasons stage with struck claim, "2 reasons" headline and two flip cards; podium where the exercise rises to #1 and a trophy lands; 3D "1" behind him; flip into his slowed, frozen rep with the knee angle and line of action drawn on; 3D call-to-action word. Read it before writing a new video's design script: it shows how word timings drive every beat.

## Before/after reels

When the owner wants to show the work, `scripts/before_after.py` builds the showcase format (amber set, tilted black-and-white Before card with the raw footage cut like the edit, the After card, neon handwritten labels, an EDL-drawn timeline with a moving playhead). It needs a licensed handwritten font (`--script-font`, e.g. Mrs Saint Delafield, OFL, from github.com/google/fonts).
