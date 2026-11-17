# Premium design pass

What separates a "captions and zooms" edit from a premium one. Measured on 2026-11-15 from three
reference shorts, all 720x1280 at 30 fps, analysed frame by frame:

- Alimarel: a talking head plus a phone-UI tutorial.
- Artzen Media: a talking head with a split-screen product demo.
- EarnEdits: pure motion design over voice-over.

The numbers come from `fingerprint.py measure`. The techniques come from 30 fps frame strips.
Nothing from the references is copied into any output.

**Read with the owner's verdicts (2026-11-17).** These are what three references measure, not targets.
Applied literally they produced edits the owner rejected: text and HUD on screen most of the time and
UI-card scenes read as "generic" and "AI slop". The house style in [craft-motion-design.md](craft-motion-design.md)
overrules this page wherever they differ, and `scripts/slop_check.py` sets the limits. In particular:

- Text on screen: captions follow speech; designed graphics only where they explain an idea, never wall to wall.
- UI objects (phones, chat bubbles, notification stacks) are one tool among many, not the default scene; the accepted default is the footage folding into a 3D card over a built set.
- Music is always ducked under speech, to -20 dB.
- Type: the fonts below are the Latin defaults; Amharic uses the font.et fonts, and every video gets its own palette.

## Measured numbers

| Field | Alimarel | Artzen | EarnEdits | Use as |
|---|---|---|---|---|
| Text on screen (% of frames) | 90.6 | 96.7 | 95.9 | captions follow speech; designed text only where it explains (see above) |
| Designed text events per min | 53.7 | 66.5 | 58.1 | measured, not a target: the owner rejected this density |
| Words per caption card (median) | phrase titles | 3.0 | 4.0 | `PHRASE_MAX_WORDS = 3` |
| Visual change, re-hook every (s) | 1.2 | 0.77 | 0.5 | something new every 0.5 to 1.2 s |
| Longest stretch with no change (s) | 5.4 | 6.1 | 3.5 | keep under about 5 s |
| Cuts per min | 24 | 22.6 | 18.2 | |
| Zooms per min | 15.6 | 14.6 | 73 | motion-design pieces never sit still |
| Transitions | 82% cut, 18% dissolve | 82% cut, 18% dissolve | 45% whip, 27% zoom, 18% cut | whips and zooms between scenes, plain cuts inside them |
| Face on screen (%) | 62.5 | 100 (split screen) | 0 | the speaker is one layer of several |
| B-roll ratio | 0.375 | split screen | all graphics | |
| Integrated loudness | −14.1 LUFS | −14.5 LUFS | −14.4 LUFS | −14 LUFS master |
| Music bed | yes, no ducking | yes, 1 dB duck | yes, 6 dB duck | bed always present; this skill ducks it to -20 dB under speech |
| Strong SFX per min | 9.9 | 14.6 | 13.3 | plus quieter UI ticks |
| Titles with an SFX (%) | 13 | 22 | 23 | not every title needs a sound |

## Techniques seen frame by frame

1. **Two type voices, never one template.**
   - All three pair a handwritten kicker (Artzen, EarnEdits) or a light kicker (Alimarel) with a heavy headline.
   - Emphasis words change font, not just colour.
   - The skill uses three voices:
     - Inter Tight 800 for the words;
     - Instrument Serif italic in the accent colour for emphasis;
     - Caveat for kickers and annotations.
2. **Text lives inside objects.** Lines appear as:
   - phone notifications, chat bubbles and a notes app being typed (EarnEdits, Alimarel);
   - a website search box (Artzen);
   - a tracklist or social post (EarnEdits).
   
   A phrase shown as a UI object reads as a scene, not a subtitle. Use it sparingly: a video built mostly
   of UI cards was rejected as "generic".
3. **Depth.** Planes are tilted in 3D and drift slowly. Foreground objects are defocused and sweep across: EarnEdits uses hazard tape and blurred coins. Background objects are blurred, and focus racks onto the subject.
4. **One accent on a dark stage**, with light/paper scenes for contrast changes:
   - Alimarel: lime on near-black;
   - Artzen: yellow and lime;
   - EarnEdits: alternates dark and paper scenes.
5. **Layouts rotate** between three modes:
   - full speaker;
   - split screen, with the demo on top and the speaker below (Artzen);
   - full-screen scene (Alimarel's phone, EarnEdits throughout).
6. **Chapter or progress system.** Alimarel's 1-2-3 stepper: the active node arrives as a blurred light orb and racks into focus over about 12 frames, while a big numeral fades in.
7. **Hook reveal in 4 frames** (Artzen, frames 0 to 3): pixelated/blurred, white subject matte, blur, then sharp. Handwriting then types on at about 1 word per 4 frames.
8. **Transitions:**
   - zoom-blur whips (EarnEdits: 45% whip, 27% zoom);
   - blur whips (Artzen);
   - white flash;
   - light leaks;
   - glitch only as an accent.
9. **Annotation:**
   - hand-drawn arrows pointing at the CTA (Artzen end card);
   - marker strike-throughs and underlines;
   - doodle accent marks (Alimarel's follow CTA).
10. **Ending:** a text card or CTA with a gesture (all three).

## How the skill does it

HyperFrames is the default design engine now (`lib/hf_design.py`, `lib/hf_explainer.py` for the 3D
stages); the Remotion parts below are the alternative engine (`design.engine: "remotion"`). When the EDL has a `design` block, render.py runs `design_pass`. Remotion's `Design` composition then
builds the finished picture around the clean speaker cut, using the project folder as its public dir.
The parts live in `remotion/src/design/`:

| Part | File | Notes |
|---|---|---|
| Layout modes `full` / `split` / `hidden`, per-span zoom | Design.tsx | `face_y` puts the face in the split half |
| Phrase captions | type.tsx `PhraseCaption`, lib/captions.py `phrase_groups` | 3-word phrases, per-word blur-in on the spoken frame, emphasis switches to the serif italic accent |
| Kicker + headline | type.tsx `TitleStack` | handwriting typed on, then the headline words spring in |
| Progress stepper | type.tsx `Stepper` | the active node racks from blur to focus |
| Scenes | scenes.tsx | ScamNotifs (phone lock screen), MillionaireBS (counter, glitch, marker strike), Paywall, Checkout (cursor click), Ranks (career ladder), Notes (typing), YearFlip, Footage (real clip + editorial headline) |
| 3D icons | fx.tsx `Icon3D` | float, drop shadow, optional depth blur |
| FX | fx.tsx / Design.tsx | zoomblur, matte hook reveal, flash, glitch, light leak, grain, vignette |

Captions are hidden (`caption_hide`) wherever the scene itself carries the line. A word can be
dropped by text, or by its timeline frame for a known mis-transcription (`caption_skip`).

The colour look is applied to the footage *before* the design pass, so brand colours stay exact.

## Assets: where premium comes from at zero cost

Every source below states its licence on the item itself, and each was checked on 2026-11-15.
Downloads go into the **project** folder, never into the skill.

| Need | Source | Licence | How |
|---|---|---|---|
| 3D icons (lock, money, rocket, crown, key, bulb…) | 3dicons.co, about 120 icons in 4 styles | CC0 (site FAQ and GitHub repo `realvjy/3dicons`) | metadata `content/3dicons-meta/<name>.md` gives CDN URLs; use the `color` style, because `premium` renders near-black |
| Cinematic SFX (whoosh, riser, hit, cash, glitch…) | Freesound, filtered to CC0 | CC0, re-checked on each sound's page | `scripts/fetch_sfx.py` (no API key; HQ preview MP3s; writes `sfx/catalog.json`) |
| UI SFX (click, tick, glass, confirmation) | Kenney Interface Sounds | CC0 (License.txt in the zip) | zip via the site's download-link endpoint, Referer header required |
| Real footage | Wikimedia Commons / NASA | per file (public domain or CC) | Commons API |
| Fonts | Google Fonts via @remotion/google-fonts | SIL OFL | |

**Mixkit (verified 2026-11-15).** The licence text is served at `https://mixkit.co/license/modal/<videoFree|videoRestricted|musicFree|sfxFree>/`. Free-licence video, music and SFX may go in commercial social videos and ads with no attribution. Each video item page says Free or Restricted; Restricted items are personal-use only, so skip them. Free music may not go in TV or radio broadcast and must not be registered with Content ID.

Choose SFX by measurement, because their names are unreliable. Measure each candidate's onset and peak time, then start the sound `peak_s × fps` frames before the hit, so the peak lands on the cut. A whoosh with its peak 0.54 s in therefore starts 13 frames early. Use `in_s` and `dur_f` on the sfx track to trim.
