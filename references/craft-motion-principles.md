# Motion principles: the deep reference

Read with craft-human.md (restraint, one hero per moment) and craft-motion-design.md (house style, Fresh grammar). This page holds the detail those two summarise: how to choose timing, easing, layering, transitions, camera and sound for each move, and how each rule maps onto this skill's HyperFrames kit.

Numbers here come from three MIT-licensed skills, read in full on 2026-11-19, and are credited inline: **[L]** LottieFiles motion-design-skill, **[M]** ncklrs startup-os-skills/motion-designer, **[R]** remotion-dev skills/remotion-best-practices. They are the sources' rules of thumb, not our measurements. Where a rule is ours, it says so.

## 1. Before any move: three questions [L]

1. **What should the viewer feel?** Pick one emotion for the beat (table in §4). It drives easing, duration and amplitude.
2. **What is the micro-story?** Every move has setup, action and resolution, even a 200 ms one.
3. **How is it made believable?** Physics, secondary motion, arcs.

Then choose **one personality for the whole video** and keep about 90 % of moves in it [L].

| Personality | Durations quick / standard / slow | Signature ease | Overshoot | Entrance pattern |
|---|---|---|---|---|
| Premium | 350 / 500 / 800 ms | cubic-bezier(0.4,0,0.2,1) | 0 % | slow fade + scale 98→100 % |
| Corporate | 200 / 300 / 450 ms | cubic-bezier(0.2,0,0,1) | 0–3 % | slide + opacity |
| Energetic | 100 / 180 / 300 ms | ease-out-expo | 15–30 % | snap from edge + overshoot |
| Playful | 150 / 250 / 400 ms | ease-out-back | 10–20 % | bounce up from below |

Content defaults [L]: editorial and finance are Premium; sport, music and fitness are Energetic; social is Playful. A sport explainer for a premium brand (amh3) mixes them: the Premium ease on panels and type, and the Energetic ease only on the hero hit of each beat (the gauge into the red, the MAX slam).

**Our kit's eases** (judgement, not measured): `expo.out` is the Energetic entrance, `power2.inOut` sits near Premium (0.4,0,0.2,1), and `power2.in` / `power3.in` are exits. `sine.inOut` is for ambient loops. Use `back.out` only in a Playful video.

## 2. Three layers in every moment [L]

| Layer | Role | Amplitude | Timing |
|---|---|---|---|
| Primary | the move the viewer follows | 100 % | on the beat |
| Secondary | shadow, pool, icon, sibling reaction | 30–50 % | 50–100 ms after primary, different ease |
| Ambient | backdrop life, float, shimmer | 10–20 % | slow and continuous, never asks for attention |

Primary motion alone looks flat. In this kit, `Object3D` carries all three: the object is primary, its light pool and contact shadow are secondary (offset +0.1 s and +0.2 s), and the float is ambient. The `World` backdrop is ambient for the whole edit. A new component must carry all three layers too.

**Attention budget [L]:** one hero motion per moment. At most 2–3 elements move at once, and ambient doesn't count. Stagger them; don't move them in sync. (`restraint_concurrent_layers` enforces 3, captions included.)

## 3. Timing [L][M]

**Perception floor [M] at 30 fps:**
- 2 frames: something registers;
- 6 frames (0.2 s): it is recognised;
- 9 frames (0.3 s): the minimum for short text;
- 30 frames: one sentence read.

Never hold a caption group or label for less than 0.3 s.

**Durations by element [L]:**

| Element | Duration |
|---|---|
| micro-feedback | 80–120 ms |
| button | 120–180 ms |
| icon | 150–250 ms |
| card | 200–350 ms |
| modal | 300–400 ms |
| page or scene change | 400–600 ms |
| dramatic reveal | 600–1200 ms |
| ambient cycle | 2–20 s |

**Distance scales duration [L]:**

| Distance | Duration multiplier |
|---|---|
| 50 px | 0.8× |
| 100 px | 1.0× |
| 200 px | 1.3× |
| 300 px | 1.5× |
| 400 px | 1.6× |
| full frame | 1.8–2.0× |

**Material [L]:** pick by what the object is made of.

| Material | Duration | Overshoot |
|---|---|---|
| rigid (metal, stone) | 1.2× | 0 % |
| glass | 0.9× | 0 % |
| paper | 1.0× | 3–5 % |
| fluid | 1.5× | 5 % |
| elastic | 0.8× | 15–25 % |
| gas | 2.0× | 0 % |

The chrome dumbbell and gold trophy are rigid: slower, and never bouncy. A card may settle 3–5 %.

**Weight [L]:**

| Weight | Duration | Overshoot |
|---|---|---|
| heavy (full-frame panels) | 300–500 ms | 0 % |
| medium (cards) | 200–350 ms | 3–5 % |
| light (badges, icons) | 80–200 ms | 5–15 % |

**Rhythm of an element [M]:** entrance 1, hold 2–3, exit 0.5–0.7. Exits run 65–75 % of the entrance [L]. A symmetric 1:1:1 reads as mechanical.

**Scene length [M]:**

| Scene type | Length |
|---|---|
| title | 2–5 s |
| simple information | 3–7 s |
| complex information | 5–12 s |
| a change of some kind | at least every 8–12 s |

**Vary the pace [M].** A flat medium pace for the whole video is monotonous; mix fast and slow. For example, a fast hook, a medium build, a slow key point, a fast run-up, then a slow resolve.

**Stagger [L][M]:**

| Pattern | Delay | Total |
|---|---|---|
| micro | 20–40 ms | < 200 ms |
| standard | 50–100 ms | < 400 ms |
| dramatic | 100–200 ms | < 600 ms |

Never exceed 500 ms in total. A group uses one ease family; vary only the start times. The last element may carry a small overshoot as punctuation.

## 4. Emotion and direction [L]

| Emotion | Path | Ease | Duration |
|---|---|---|---|
| confidence | straight, horizontal | ease-out | 200–400 ms |
| surprise / impact | radial outward | ease-out-expo | 150–300 ms |
| elegance | long arcs | (0.4,0,0.2,1) | 400–700 ms |
| urgency | straight lines | ease-out | 100–200 ms |
| calm | gentle curves | sine in-out | 500–1000 ms |
| weight / sadness | drooping, downward | cubic in-out | 600–1200 ms |

Direction carries meaning:
- **Up:** growth, achievement (the trophy rises).
- **Down:** settling, gravity (a stamp lands).
- **Right:** progress, arrival.
- **Left:** going back.
- **Outward:** importance.
- **Inward:** dismissal.
- **Toward the centre:** focus.

Angular paths read as tense, curves as friendly. Give organic moves a 10–20 px arc at the midpoint; mechanical ones can stay straight [L].

**Counter-motion [L]:** when the hero moves, something answers it at 20–30 % speed.
- It slides right: the background drifts left.
- It scales up: its shadow spreads.
- It lifts: its shadow drops and softens.

**Micro-story proportions [L]** for a move of 400–800 ms:

| Phase | Share | What happens |
|---|---|---|
| anticipation | 15–20 % | a wind-up of 10–20 % opposite to the move |
| action | 30–40 % | the move itself |
| reaction | 15–20 % | shadows and siblings follow 50–150 ms later |
| resolution | 20–25 % | the move settles |

After it, leave 100–200 ms of stillness before the next move. Skip anticipation on anything under 150 ms.

## 5. Entrances, exits and ambient [L]

**Entrance offsets by personality:**

| Personality | Slide-in offset | Starting scale |
|---|---|---|
| Premium | 15–25 px | 95–98 % |
| Corporate | 20–30 px | 90–95 % |
| Energetic | 40–80 px | 50–70 % |

Mask reveals run 300–500 ms. Assembled entrances (parts arriving one after another) total 300–600 ms.

**Exits:**
- slide, dissolve or collapse to 85–95 %, eased in, over 150–250 ms;
- the exit point sits near the next entrance, with 100–150 ms of overlap.

**Ambient [L]:**

| Motion | Range | Cycle |
|---|---|---|
| breathing | scale 0.98–1.02 | 2–4 s |
| float | ±5–15 px, rotation ±2–3° | 3–5 s |

- Above ±5 % scale, a pulse starts demanding attention.
- In layered floats, give each element its own period (for example 4 s, 5.5 s, 3.5 s) so they never move in sync.
- A shimmer sweep takes 1.5–2.5 s, with 2–5 s between sweeps.
- Particles: at most 20, using transform and opacity only.
- Total ambient energy: at most 20 % of the primary's.

## 6. Hierarchy and composition [M]

- **One primary per frame,** at 10–20 % of the frame. Secondary takes 20–30 %, tertiary 50–70 %. Show them in that order: primary, then secondary, then tertiary.
- **Five tools:** size, contrast, colour, motion, position. Only the primary gets a complex move. Only one element carries the saturated accent colour. In this kit, gold is reserved for the hero number or word.
- **Size ratio for text:** about 4 : 2 : 1 (hero : subhead : body).
- **Contrast tiers:**

  | Tier | Contrast ratio |
  |---|---|
  | primary | 12:1 or more |
  | secondary | about 7:1 |
  | tertiary | 4.5:1 minimum |

- **Three-second rule:** within 3 s the viewer knows what this is, why it matters and what comes next.
- **Squint test:** squint at a still frame; the primary must still read.
- **Negative space:** at least 30 % of the frame. Isolation creates focus; crowding kills it.
- **Depth:** give foreground, midground and background different speeds (§8) and shadows sized by importance.

## 7. Transitions [M][R]

- **Pick the transition by need.** The best transition is often a cut. Spend about one designed transition every 5–10 s, about 3–6 in 30 s [M].

  | Transition | Duration |
  |---|---|
  | cut | 0 s |
  | fast crossfade | 0.3 s |
  | crossfade | 0.5–1.2 s |
  | slide | 0.4–1 s |
  | scale | 0.5–1.5 s |
  | wipe | 0.3–0.8 s |
  | morph (shared element) | 0.8–2 s |

- **Overlap.** A crossfade with no overlap shows a gap. Overlap the two sides by about 8 frames [M]. Stagger multi-element transitions: background, then text, then icon, 2 frames apart.
- **Keep one direction.** Forward moves always go the same way. Random directions confuse.
- **Sound for each transition [M]:**

  | Transition | Sound |
  |---|---|
  | cut | none |
  | crossfade | soft whoosh |
  | slide | directional swoosh |
  | scale | whoosh + impact |
  | wipe | sharp swoosh |
  | morph | shimmer |

  Start the whoosh about 5 frames before the cut so it bridges both sides.
- **Overlays at the cut [R].** A light leak or light sweep plays over the cut point and doesn't shorten the timeline; a crossfade does. This kit's `Sweep` overlay is that pattern. A light leak reveals during the first half of its progress and retracts during the second.
- **Motion blur [R].** Exposure is (shutter angle ÷ 360) ÷ fps. A 180° shutter at 30 fps exposes 1/60 s. Blur is the average of 8–16 samples inside that exposure. Fast moves without blur read as CG. GSAP's blur filter on a fast entrance is the cheap version of this; set it in proportion to the speed, and clear it once the element settles.

## 8. Camera [M]

**Durations:**

| Move | Range | Typical |
|---|---|---|
| quick pan | 0.5–2 s | 1 s |
| smooth pan | 2–6 s | 4 s |
| zoom in | 0.8–3 s | 1.5 s |
| zoom out | 0.5–2 s | 1 s |
| orbit | 3–8 s | 5 s |

**Limits:**
- Zoom at most 3×.
- A dutch angle of 5–15° adds energy; 45° only to disorient on purpose.
- No instant starts or stops.
- Scale around the subject: translate to compensate, or the zoom runs off from a corner.

**Parallax speeds:** foreground 1.5×, midground 1×, background 0.5×. For ambient depth, LottieFiles uses 1 / 0.5 / 0.2 / 0.1.

**Shake:** a decaying spring of about 10 px, used only on an impact. Handheld drift: about 2 px.

**Rack focus:** blur the background up to about 10 px while the foreground sharpens, over about 1 s. Keep the 180° rule across a sequence of shots.

## 9. Sound design [M][R]

- **Layers, by level** [M], given as % volume (they're the source's terms; this skill's dB targets are in craft-audio.md):

  | Layer | Level |
  |---|---|
  | dialogue | 80–100 % |
  | SFX | 60–80 % |
  | music | 40–60 % |
  | ambient texture | 20–30 % |

  The mix must never exceed 100 %.
- **Hit the peak of the action, not before it.** Use the library's sync point. sfx-kit records where each sound should meet the action, for example 0.98 s into `riser-1s-soft`. In the EDL this is `align` (`peak`, `start` or `end`).
- **Layer a big moment across the spectrum** with 2–3 sounds:
  - low: an impact or boom under 250 Hz;
  - mid: a whoosh, 250–2000 Hz;
  - high: a shimmer above 2 kHz.

  One generic swoosh alone sounds cheap.
- **Riser, then impact, then tail:** the riser ends on the reveal frame, the impact lands with it, and the reverb tail carries on.
- **Silence:** 0.5 s of silence before a reveal makes the hit land harder.
- **Space between sounds.** Leave at least 0.2 s between effects. Use 3–5 different whooshes, not one file on every transition. In lists, step each repeated pop down a little in level. (`restraint_sfx_gap` and `restraint_sfx_repeat` check the gap and the repeats.)
- **One sound for each object, and only that object.** Give each object a sound that matches what it is made of [ours, amh3 v3]:
  - metal: a clang (`cinematic-metal-big`) and a ratchet for a dial;
  - gold or award: a shimmer;
  - a stamp: `impact-medium-hard`;
  - a bell: `tone-ding-*`.
- **Music [M]:**
  - Choose the mood and energy from the matrix: dramatic + high energy is cinematic action; inspiring + medium is a building rhythm.
  - The energy follows the story arc: hook, build, peak, resolve.
  - Fade in and out over 0.5–1 s; never cut music hard.
  - Duck the music 6–12 dB under the SFX hits as well as under speech.
- **Sources.** Use sfx-kit (CC0) for designed moments; `scripts/find_sfx.py` searches the local libraries and copies picks with licence entries. soundcn is MIT code with mostly CC0 sounds, **but its 110 World of Warcraft sounds are © Blizzard**: never use them (find_sfx excludes them). Remotion's hosted meme sounds (vine-boom, bruh, …) have no licence stated: don't use them.

## 10. Finishing techniques from Remotion [R], mapped to this kit

- **Colour correction order.** Exposure, then white balance, then shadows/highlights, then contrast, saturation and vibrance, with any LUT last. A LUT must receive the corrected footage. (Our grade path: craft-color.md.)
- **Matting recipes.** These match our camfg cut-out.
  - Text behind the subject: base, then text, then foreground.
  - Background replacement: new backdrop, then foreground (our `World` overlay).
  - Subject-only glow: apply it to the foreground layer only.

  Matting doesn't rebuild what was behind him. A strong background blur leaves a halo, so keep the blur light.
- **Annotations.** Hand-drawn highlights, circles, underlines and strike-throughs are driven by a 0–1 progress value tied to time. Our `Divisions` strike is one.
- **Keep layers on one clock.** A shot's video, captions and synced overlays share one timing boundary. An overlay that spans cuts lives at the scope it spans. Don't shorten a sound to make it fit; give it its natural tail.
- **3D.** Everything 3D must be driven by the timeline (no self-running loops), because any self-animation flickers in a frame-by-frame render. This is why `objects3d.py` bakes the Blender animation to a clip.
- **Posterised frame rate** (for example 12 fps on a type move) is an artistic choice. Use it only on purpose.

## 11. Before delivery (merged checklists [L][M])

- Is every move either a primary, a secondary or an ambient? Does each moment have exactly one hero?
- No linear easing on spatial moves. Entrances eased out, exits eased in. Entrances longer than exits.
- The 1/3 rule for both distance and element count. Total stagger under 500 ms. Follow-through 50–150 ms.
- Text held at least 0.3 s. Scenes paced to their content. A change at least every 8–12 s.
- Transitions: about one every 5–10 s, each with its matching sound, all in one direction.
- Sounds land on peaks, at least 0.2 s apart, several different files, with big moments layered low, mid and high.
- Music follows the arc, fades in and out, and ducks under speech and hits.
- It passes the squint test and the three-second rule, and still feels fine on the 100th viewing.

## Sources

- LottieFiles, motion-design-skill, MIT: github.com/LottieFiles/motion-design-skill (SKILL.md, director/*, reference/*, patterns/*).
- ncklrs, startup-os-skills/skills/motion-designer, MIT: github.com/ncklrs/startup-os-skills (SKILL.md, rules/*).
- Remotion, skills/remotion-best-practices: github.com/remotion-dev/skills (remotion-markup: effects, motion-blur, light-leaks, transitions, timing, color-correction, video-editing, video-matting, text-highlights, sfx, 3d; remotion-captions).
