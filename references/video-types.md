# Video types

Read when choosing a type and style for new footage (stage 4).

## Types, detection signals and default style
| Type | Detection signals (detect_type.py) | What defines the edit | Style file |
|---|---|---|---|
| `short_form` | vertical target, or the brief asks for a short | Hook under 2 s, fast cuts, bold captions, dense SFX | `styles/short_form/pinterest_edit_refs.json` (**measured**, 13 refs) |
| `talking_head` | one speaker, face on screen most of the time | Jump cuts, punch-ins, B-roll on keywords, callouts | `styles/talking_head/talking_head_defaults.json` |
| `vlog` | handheld, many locations, mixed speech and scenery | Music-led, J and L cuts, ambience, montage | `styles/vlog/vlog_defaults.json` |
| `cinematic_travel` | little speech, scenery, camera movement | Cuts on the beat, speed ramps, grade, hidden-cut transitions | `styles/cinematic_travel/cinematic_travel_defaults.json` |
| `podcast_long` | two or more speakers, static cameras, long duration | Speaker switching, minimal effects, chapters | `styles/podcast_long/podcast_long_defaults.json` |
| `podcast_clip` | podcast source with a short vertical target | Reframe, animated captions, keyword pops | `styles/podcast_clip/podcast_clip_defaults.json` |
| `documentary` | interviews plus archival or B-roll | Slow pace, evidence B-roll, sound design | `styles/documentary/documentary_defaults.json` |
| `product_ad` | product shots, short target, call to action | Fast montage, motion graphics, clear ending | `styles/product_ad/product_ad_defaults.json` |
| `gaming_reaction` | screen capture plus facecam | Layouts, zooms on moments, inserts | `styles/gaming_reaction/gaming_reaction_defaults.json` |
| `explainer_3d` | voiceover plus generated or 3D visuals | Narration-led, short scenes, scale tricks | `styles/explainer_3d/explainer_3d_defaults.json` |

detect_type.py writes `project/type.json` with `type` (the delivery shape: `short_form` or `podcast_clip` for short targets), `content_type` (what the footage is), per-type scores and the evidence. Mixed footage can map to a sequence of types: say so and plan per section.

## Measured vs starting-default styles
Only `short_form/pinterest_edit_refs.json` is measured. Every `*_defaults.json` has `"measured": false` and every field carries `"basis": "STARTING DEFAULT"`: editors' rules of thumb, not measurements. detect_type.py prefers a measured style when one exists for the type.

**To measure a type:** collect 10 or more finished videos of that type (the user's own or licensed references; used for measurement only, never copied):
```
python scripts/fingerprint.py batch REFS_DIR --out-dir work/fingerprints/<type>
python scripts/fingerprint.py aggregate work/fingerprints/<type>/*.json --type <type> --name <name> --out styles/<type>/<name>.json
```

## Choosing a style
1. The user's explicit request (`--style`).
2. The creator profile's default for the platform (`default_styles`).
3. The best-matching fingerprint for type and platform (measured first).

State the choice in one line with the reason and let the user override it. Build the EDL to the style's numbers; where the footage cannot support them (too little B-roll, weak audio, pre-edited source), adapt and say so. After rendering, qc.py `style_distance` reports field by field; fix or explain the gaps.

## Eval projects
Each type needs an eval project built from footage the user owns (evals/README.md). They were not built for this release because no raw footage of those types was supplied; the defaults above remain unvalidated until they are.

## Style requests in words
Map phrases to fingerprint adjustments with revisions.md. A named creator's style is described by measured properties only. Do not imitate their branding, catchphrases or assets.
