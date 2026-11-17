# Effects catalogue: what pro short-form editors use, and how the skill makes each one

Two inputs went into this catalogue on 2026-11-15.

1. **Seven reference shorts, watched at 30 fps, every frame.** `scripts/deep_watch.py --sheets full`
   produces numbered 12x8 contact sheets of every frame, plus a per-event list of cuts, flashes,
   washes, blur transitions, zooms, whips, B&W beats, graphics appearing, and audio hits with a
   sound class. The references are:
   - marcel: an AI clipping tool explainer;
   - sumit: a free-marketing talking head;
   - vepro: an editing-tools tutorial;
   - foysal: a real-estate agent;
   - enginecy: an SEO agency ad;
   - cozy: a Portuguese cinematic monologue;
   - pin1129: a Portuguese tech talking head.
2. **Web research** into the After Effects effects and plugins editors name most, and the expressions
   they use. The sources are listed at the end.

Nothing from the references is copied. Only techniques and measured numbers are kept.

## 1. Measured numbers (deep_watch + fingerprint)

| Field | marcel | sumit | vepro | foysal | enginecy | cozy | pin1129 | Use as |
|---|---|---|---|---|---|---|---|---|
| Length (s) | 37.6 | 26.3 | 80.7 | 28.9 | 12.6 | 152 | 125 | |
| Text on screen (% of frames) | 93 | 84 | 89 | 95 | 84 | 98 | 92 | text is present almost all the time |
| Words per caption card (median) | **1** | 4 | 2 | 3 | **1** | 3.5 | 2.5 | 1 to 3 words, never sentences |
| Re-hook every (s) | 0.62 | 1.2 | 1.27 | 0.73 | 0.5 | 0.23 | 0.5 | something changes every 0.5 to 1.2 s |
| Longest stretch with no change (s) | 3.4 | 3.2 | 4.9 | 7.0 | 3.1 | 10.9 | 7.9 | keep it under about 5 s |
| Cuts per min (incl. inside transitions) | 83 | 75 | 37 | 21 | 43 | 88 | 39 | |
| Flash / overexpose per min | 11.2 | 9.1 | 4.5 | 2.1 | 0 | 6.7 | 6.7 | one flash transition every 6 to 13 s |
| Whip / directional smear per min | 12.8 | 45.6 | 8.2 | 29.1 | 0 | 1.2 | 15.3 | |
| Blur transitions per min | 11.2 | 25.1 | 5.2 | 8.3 | 14.4 | 12.2 | 6.7 | |
| Zoom events per min | 43 | 18 | 22 | 23 | 48 | 7 | 24 | |
| Face on screen (%) | 53 | 74 | 89 | 99.5 | 98 | 98.5 | 62 | |
| B-roll ratio | 0.47 | 0.26 | 0.11 | 0.01 | 0.02 | 0.02 | 0.38 | |
| Speech (words per min) | 201 | 208 | 219 | 214 | 192 | 149 | 183 | dense, fast speech |
| Integrated loudness (LUFS) | −14.1 | −16.9 | −20.9 | −13.3 | −14.4 | −30.3* | −15.3 | master to −14 |
| Audio hits per min (all classes) | 187 | 176 | 131 | 179 | 115 | 123 | 99 | upper bound: includes speech plosives |
| Risers per min | 27 | 16 | 18 | 29 | 24 | 32 | 23 | |
| Whooshes per min | 34 | 62 | 32 | 39 | 33 | 32 | 23 | one whoosh on almost every move |

\* cozy was measured from a quiet upload, so its loudness is not a target.

The audio classes are guessed from the sound's shape (HPSS percussive onset, pre-rise, decay,
centroid). Speech can produce "thud" and "click" hits, so read those per-minute figures as upper
bounds. Risers and whooshes are reliable, because they need ≥ 10 dB of rising energy before the
hit.

**The density gap.** The skill's v4 edit had 5 strong SFX per minute. These references have
**20 to 60 whooshes and risers per minute**: every graphic that moves gets a sound. That is the
single biggest difference between them and v4.

## 2. Effects seen frame by frame, and the skill's version

The "Seen" column gives frame numbers at 30 fps, so each one can be checked on the sheets.

### Captions (the main graphic in every reference)

| Effect | Seen | Skill |
|---|---|---|
| **One-word slam.** A huge word in the top third. It arrives ghosted (40 % opacity, 1.25x, blurred) and solidifies in 4 f. The old word is gone on the same frame. | marcel f0-240; enginecy | `caption_style: "slam"` (`SlamCaption`), `max_words: 1` |
| **Neon tier.** Small white helper words, then the key word in the accent colour with a 3-layer bloom, switching on letter by letter like a neon tube (1 letter per frame, flicker on the first 3 f). | pin1129 whole video; sumit serif variant | `caption_style: "neon"` (`NeonCaption`) |
| **Coloured keywords.** Each key word is huge and takes the next colour of a palette, with small helper words above. Entry is blur plus scale-down over 5 f. The glow jitters (a wiggle). | foysal whole video | `caption_style: "keyword"` (`KeywordCaption`) |
| **Two-line italic tier.** Line 1 is small and white; line 2 is the accent colour with glow, in a heavy italic display face. Each word blurs in over 2 f. | vepro whole video | `caption_style: "tier"` (`TierCaption`) |
| **Phrase.** 3 words, emphasis in serif italic. | earlier set | `caption_style: "phrase"` (default) |
| **Text behind the subject.** The head or arms cover letters. | marcel f12, foysal f19, pin1129 f5-35 | `design.matte: true` plus `behind: true` overlays (`scripts/matte.py`) |

### Graphics

| Effect | Seen | Skill overlay type |
|---|---|---|
| Count-up number (slows into its target), icon above, glow pulse on landing, Indian or western grouping | sumit f170-460 | `Counter` |
| Figma selection frame: guides run to the frame edges, a rectangle with 8 handles draws on over 10 f | sumit f5-15, f212, f315 | `SelectionBox` |
| Glowing halo behind the head | sumit f259 | `Halo` (behind) |
| Chapter badge: numbered glowing circle pops 0 → 1.2 → 1 over 4 f, title types beside it | vepro x7 chapters | `ChapterBadge` |
| Countdown ring that ticks on real seconds ("60s" → "57s") | vepro f56-119 | `Countdown` |
| Tile row 1 \| 2 \| 3 popping 4 f apart, then flipping (scaleX squeeze) to logos | vepro f307-497 | `TileRow` |
| White label stack (source lists), each grows from a thin line | vepro f1575, f1930 | `LabelStack` |
| Search bar CTA: the pill grows from a line, the placeholder types, then the keyword lands | vepro f2321, enginecy f60 | `SearchCTA` |
| Full-frame colour word card that dollies out continuously (scale 1 → 0.45), first word slammed with horizontal blur | marcel f234-448 | `ColorCard` |
| Neon line icon drawing itself, stroke by stroke | enginecy f32-58, f180 | `LineIcon` (Lucide icons via `fetch_lineicons.py`) |
| Media card growing out of the subject, 0.3 → 1.3 with blur → sharp | marcel f739-767 | `GrowCard` |
| 3D icons and objects popping in hand or beside the head | pin1129 f64-191, foysal | `Icon` (3dicons CC0) |
| Background recoloured while the person stays natural (red room, B&W background) | vepro f144-180 | `design.bg` spans (needs the matte) |

### Transitions (`design.fx`)

| Effect | Seen | Measured timing | Skill fx type |
|---|---|---|---|
| Light-leak dip to white: warm leak from the bottom, 1-2 f white on the cut, decays | vepro x7 (every chapter) | 7 f in, 9 f out | `leakdip` |
| Smoke/fog flash: smoke rolls in from a corner, near-white hold with the cut, smoke thins as god rays sweep | cozy x17 | 6 + 4 + 10 f | `smoke` |
| Overexpose cut: blooms to white, cut at the peak, decays | sumit x4, marcel f0-4 | 2 + 3 f | `overexpose` |
| Colour wash in the brand colour from a corner | sumit f42, f112, f672; pin1129 f531 | 5 f in, 6 f out | `wash` (`color`, `from`) |
| Film burn / rainbow light streaks | enginecy f158-170 | 12 f | `burn` |
| Zoom-blur whip | earlier set, cozy f274 | 4 + 6 f | `zoomblur` |
| Directional whip (horizontal, or up) | foysal f95, f793; marcel f912 | 3 + 4 f | `whip` (`dir`) |
| B&W emphasis beat | vepro f498-550; cozy flashbacks | held for the line | `bw` (`dur`) |
| Defocus push: the background pushes toward camera and blurs while the CTA stays sharp | enginecy f329-345 | 12 f | `defocus` (`dur`) |
| Glitch accent, 2-4 f | sumit f103, f665 (magenta flicker) | | `glitch` |

### Structure patterns

- **Chapters with the same skeleton** (vepro): dip → badge → typed title → captions → demo card → dip.
  The viewer always knows where they are and how much is left.
- **Retention promise on screen**: a countdown ring (vepro), "7 SIMPLE STEPS" with numbered nodes,
  or a stepper.
- **Wide ↔ close alternation** (pin1129): hard cut between full body and face every 2 to 5 s, with a
  2-3 f settle.
- **Section transition every 6 to 13 s** (flash, wash, leak or smoke), with plain cuts inside a
  section.
- **CTA as a UI object**: a search bar with a keyword (vepro), a "Follow" pill, or a defocus handoff
  to a sharp CTA line (enginecy).

## 3. After Effects effects editors name, and the skill's equivalent

| After Effects effect / plugin | What editors use it for | Skill equivalent |
|---|---|---|
| Deep Glow (plugin) / Glow | neon text, light-tube words, glowing numbers | stacked `text-shadow` blooms (`NeonCaption`, `Counter`) |
| Motion Tile + Directional Blur / Transform (shutter angle), Pixel Motion Blur, ReelSmart Motion Blur | whips, slams, smears | `whip`, `SlamCaption` blur, `ColorCard` slam |
| CC Radial Fast Blur / Camera Lens Blur | zoom-blur transitions, defocus | `zoomblur`, `defocus` |
| Optical Flares / light-leak and film-burn stock | flash and leak transitions | `leakdip`, `burn`, `LightLeak` |
| Fractal Noise + Turbulent Displace | smoke, fog, organic textures | `SmokeFlash` (SVG feTurbulence) |
| Roto Brush / Rotobrush 3 | text behind the subject, background recolour | `scripts/matte.py` (PP-HumanSeg) + `behind` layer |
| Trim Paths (shape layers) | icons and frames drawing on | `LineIcon`, `SelectionBox`, `Scribble` |
| Slider Control + expression counter | counting numbers | `Counter` (`countTo` ease-out) |
| Shift Channels / Twitch / Universe Glitch | RGB-split glitch accents | `Glitch` |
| Lumetri / Tint / Black & White | B&W beats, colour washes | `bw`, `wash`, `bg` |
| Graph Editor (Easy Ease, influence) | the "premium" feel of every move | `eOut` = bezier(0.16, 1, 0.3, 1), spring `pop()` |
| Echo / Posterize Time | stutter, ghost trails | not built; use sparingly |

### Expressions, as the skill writes them (in `remotion/src/design/motion.tsx`)

- **`wiggle(freq, amp)`.** In AE this is smooth random motion. Here, `wiggle(f, fps, freq, amp, seed)`
  is the sum of two seeded sines: deterministic, with no frame-to-frame jitter. Use `freq` 6–10 and
  `amp` 1–3 px for "alive" text (foysal keywords), or `freq` 1–2 and `amp` 5–10 px for floating
  objects.
- **Inertial bounce.** The AE expression (Dan Ebberts, motionscript.com) is
  `v * amp * sin(freq * t * 2π) / exp(decay * t)` after the last keyframe, usually with `amp` .05,
  `freq` 2–4 and `decay` 4–8. Here it is `inertial(k, fps, v, amp, freq, decay)`. Remotion's
  `spring()` covers most cases. Use `inertial` when an object stops after a move and must overshoot
  in proportion to its speed.
- **`linear(time, t0, t1, a, b)` with easing on a Slider.** This is the counter, here
  `countTo(f, start, dur, to, from, power)`. It is ease-out to the power 4, so the big steps come
  first and the small ones last, as on sumit's counter.
- **Easy Ease influence.** Editors drag influence to 70–90 % for the "snappy then smooth" curve. The
  skill's `eOut` bezier is the same shape. STARTING DEFAULT: use it for every entrance, and `eInOut`
  only for moves that both start and stop on screen.

## 4. Sound design rules (layering)

These are measured on the references and supported by the sound-design sources at the end.

1. **Every visual move gets a sound.**
   - whoosh or swoosh: card slides, whips, word slams;
   - pop, click or tick: text and icon pop-ins, list items, tile flips;
   - riser into each section transition;
   - impact or boom on the cut out of that riser;
   - shutter or "vintage flash": white flashes;
   - reverse hit (a reversed cymbal or impact): into reveals.

   The references run 20–60 whooshes and risers per minute.
2. **Peak on the cut.** Start each SFX `round(peak_s × fps)` frames before its visual event.
   `fetch_sfx.py` writes `peak_s` and `onset_s` for every sound in `sfx/catalog.json`, and
   `--measure-only` backfills an older catalogue.
3. **Transition stack.** A riser of 0.5–1.5 s ending on the cut, then a whoosh peaking on the cut,
   then an impact on the frame after the flash. The riser should end; let the impact carry the
   tail.
4. **Levels.** Dialogue sits at −14 LUFS integrated. SFX sit about 6–12 dB under the dialogue peak,
   and UI pops quieter still. STARTING DEFAULT: the existing bus at about −10 LU. Do not let SFX hide
   consonants: place pops between words where possible.
5. **Vary the samples.** Rotate 3–4 whooshes and 3–4 pops so repeats do not sound mechanical.

## 5. Free assets, licences read on 2026-11-15

All assets are downloaded into the **project** folder, never the skill, with licence text kept.

| Need | Source | Licence (as read) | How the skill gets it |
|---|---|---|---|
| Edit SFX: whooshes, risers, impacts, reverse hits, shutters, UI pops, chimes (about 100) | videoeditingsfx.com | CC0. Each page's schema.org metadata carries `license: creativecommons.org/publicdomain/zero/1.0/`; no sign-up | `fetch_sfx.py --source ves --query "riser"` |
| Any SFX (large catalogue) | Freesound, filtered to CC0 | CC0, re-checked on each sound's page | `fetch_sfx.py` (default source) |
| UI SFX | Kenney Interface Sounds | CC0 (License.txt in the zip) | see premium-design.md |
| Big packs, by hand | Sonniss #GameAudioGDC bundle (2026: 7.47 GB) | Royalty-free, commercial use, no attribution. **No redistribution as sound effects, and no AI training or usage.** | manual download only. The no-AI-usage clause means an agent should not pull it automatically; a human editor may. |
| Animated line icons | Lucide (lucide-static 0.469.0) | ISC: keep the licence notice | `fetch_lineicons.py --project P monitor rocket …` |
| Lottie animated icons | useAnimations (300 icons) | MIT, no attribution required | not wired in. Lottie playback would need `@remotion/lottie`. |
| 3D icons | 3dicons.co | CC0 | see premium-design.md |
| Person matte model | PP-HumanSeg (OpenCV Zoo) | Apache-2.0 | `matte.py` downloads it to `assets/cache/models/` |
| Stock video and photos | Pexels | free; no attribution required; no resale as stock | needs an API key, so it is not automated |

**Not used.** These sources were rejected because their terms could not be read, or because they
add conditions:
- Mixkit: licence read 2026-11-15 (see assets-sources.md); use Free items only, never Restricted.
- Pixabay: its terms forbid automated collection.
- Lots of Sounds: CC0, but searching needs a paid key.
- LottieFiles: free licence, but its terms forbid compiling files.
- ActionVFX and Selekt: their pages were rate-limited and could not be read.

## 6. How to study a new reference

```
python scripts/deep_watch.py REF.mp4 --out-dir refs/dw/NAME --sheets full    # every frame, 96 per sheet
python scripts/fingerprint.py measure REF.mp4 --out refs/NAME.fp.json        # text, structure, loudness
```

1. Read `events.json` first, to find where the cuts, flashes, washes and audio hits cluster.
2. Open the sheets around those frames.
3. Write down each effect with its frame range and duration in frames.
4. Map each one onto a row in section 2, or build the missing component.

## Sources (read 2026-11-15)

- After Effects plugins and effects editors name:
  - spotlightfx.com/blog/best-after-effects-plugins
  - kirtanfx.com/top-after-effects-effects/
  - videomaker.com (plugins guide)
  - insideeditors.com/instagram-video-editing-effects/
- Trends:
  - olafmotion.com (social media animation trends 2026)
  - graphicdesignjunction.com (video and motion creative trends 2026)
- Expressions and easing:
  - helpx.adobe.com/after-effects/using/expression-examples.html
  - motionscript.com/articles/bounce-and-overshoot.html
  - mtmograph.com (bounce/overshoot)
  - cursa.app (graph editor easing)
  - creativecow (easy-ease thread)
- Sound design:
  - sonilo.com/blog/guides/transition-effect-sound-video-edits
  - fish.audio/blog/using-sound-effects-for-short-form-content
- Asset licences:
  - videoeditingsfx.com/sfx/
  - sonniss.com/gdc-bundle-license
  - unpkg.com/lucide-static@0.469.0/LICENSE
  - useanimations.com/licencing-and-terms
  - lottiefiles.com/page/license
  - pexels.com/license/
  - pixabay.com/service/terms/
  - lotsofsounds.com/license
  - github.com/opencv/opencv_zoo (PP-HumanSeg, Apache-2.0)

## 9. Lockup captions and camera, re-measured at 30 fps (2026-11-16)

Frame counts read from `deep_watch.py --sheets full` sheets of the same set (sumit, marcel, vepro, foysal watched in part; all seven sampled at 3 fps). They are the timings `captions_lockup` uses.

| Move | Measured | Where |
|---|---|---|
| Selection frame + guide lines land before any word | ~5-6 frames | sumit f120-126, f313-320 |
| Keyword wipes in left to right, with a light streak | ~5-6 frames | sumit f223-227, f339-343 |
| Keyword glow builds after the wipe | ~6-8 frames | sumit f343-350 |
| Dark gradient band behind the caption half of the frame | whole card | sumit f120-158 |
| Lockup hold | ~1.2-1.4 s | sumit |
| Exit: white overexpose with the caption push-blurring | 2-4 frames | sumit f159-162, f254-257, f310-313 |
| Counter with an icon above it: count with ease-out, label after | ~35 frames | sumit f271-309 |
| Word-by-word type behind the head, hard swap | every 6-10 frames | marcel f96-114 |
| Section change: colour leak builds, white flash, tint decays | 6 + 2 + 8 frames | vepro f246-262 |
| Word exit by whip-slide with motion blur | ~4 frames | foysal f233-239 |

A caption there is a composition (small line + one huge keyword), not a strip. A uniform boxed strip reads as generic.
