# Asset sources and licensing

Read when an edit needs music, SFX, B-roll, images, icons, 3D or fonts, and before delivery (credits).

## Lookup order (every asset need)
1. **The user's own paid library** in `assets/local/` (Artlist, Epidemic Sound, Envato, Motion Array...). Always preferred.
2. **The curated editor kit** (`assets/kit/manifest.json`, `kit:<role>` in the EDL).
3. **Bulk free packs** in `assets/library/` (Sonniss, Kenney...).
4. **Online sources** with a commercial-use filter (`fetch_assets.py search --commercial`).
5. **Nothing good enough: leave the slot empty and tell the user.** An empty slot beats a cheap-looking asset.

`tag_assets.py build` catalogues 1-3 into `assets/catalog.json`; `tag_assets.py find "short bright whoosh"` searches it; `fetch_assets.py search/get` covers 4 and adds `cat:<origin>:<id>` entries.

## Sources and license status
"Verified" means the provider's own terms page was read on that date. Anything else is a third-party summary: confirm it before a commercial delivery.

| Need | Source | Access in the skill | License (status) |
|---|---|---|---|
| B-roll video, photos | Pexels | `fetch_assets.py`, free key `PEXELS_API_KEY` | Free commercial use, no attribution required; API terms ask for a link back to Pexels (**verified 2026-11-15**) |
| B-roll, illustrations | Pixabay | free key `PIXABAY_API_KEY` | Commercial use, no attribution; no standalone resale of the content (**verified 2026-11-15**, summary page) |
| Photos | Unsplash | not implemented | Unsplash license (not checked) |
| Curated B-roll | Mixkit, Coverr | download into the project (`P/broll/`) | Mixkit: two licences per item, read on the item page. **Free** = commercial and non-commercial use, social posts and ads, no attribution, no standalone redistribution. **Restricted** = personal, non-monetised use only: never use for a client or monetised video. Licence texts: `https://mixkit.co/license/modal/videoFree/` (also `videoRestricted`, `musicFree`, `sfxFree`). Coverr: not checked |
| Archival, science, space | Wikimedia Commons, NASA, Smithsonian Open Access | manual | PD or CC per item (not checked) |
| HDRIs, textures, 3D | Poly Haven | `fetch_assets.py --kind hdri/texture/model`, no key | CC0 (**verified 2026-11-15**) |
| Materials | ambientCG | manual | CC0 (not checked) |
| Stylised 3D | Kenney, Quaternius, KayKit | bulk download | CC0 (Kenney **verified 2026-11-15**) |
| Specific 3D models | Sketchfab | manual | mixed: filter to CC0 or CC-BY |
| SFX, studio grade | Sonniss GDC bundles | bulk download to `assets/library/sonniss/` | Royalty-free, commercial, no attribution; no resale; **no ML training** (**verified 2026-11-15**) |
| SFX, UI and transitions | Kenney audio, Mixkit, 99Sounds | download (Mixkit: `https://assets.mixkit.co/active_storage/sfx/<id>/<id>.wav`) | Kenney CC0 (verified); Mixkit Sound Effects Free License (verified 2026-11-15: web, social, film, broadcast; no standalone redistribution, no Content ID registration); 99Sounds not checked |
| SFX and music search | Openverse | `fetch_assets.py`, no key (rate-limited: HTTP 401 after a burst) | per-item license fields; Openverse's own API terms page was not published (2026-11-15) |
| SFX, rare | Freesound | **excluded on commercial projects** | API use for commercial purposes is negotiated case by case (**verified 2026-11-15**); filter to CC0 otherwise |
| SFX | ZapSplat | manual | free tier requires credit |
| Music | YouTube Audio Library | manual in YouTube Studio | safe for YouTube; some tracks need credit |
| Music | Pixabay Music | manual | commercial, no attribution; Content ID claims possible |
| Music | Uppbeat free tier | manual | requires its exact credit line; monthly limit |
| Music | Incompetech | manual | CC-BY, credit required |
| Music | Jamendo (via Openverse) | `fetch_assets.py --kind music` | CC per track; the free Jamendo API tier is non-commercial, so tracks are reached through Openverse and filtered by license |
| Icons | Iconify | `fetch_assets.py --kind icon --icon-set <prefix>` | license per icon set; Iconify's license page returned 404 on 2026-11-15, so the per-set license field is used |
| Animated elements | LottieFiles | manual | filter to free; marketplace items differ |
| Fonts | Google Fonts | `lib/kit.ensure_fonts` (Poppins, Anton, Noto Sans Ethiopic) | SIL Open Font License |
| LUTs | generated `.cube` | `lib/color.look_path` | own work |

**Never for commercial work:** BBC Sound Effects (personal, educational and research use only).

## The commercial flag
`commercial: true` in the paper edit (default) makes `license_ok` reject: NC licenses, SA licenses (share-alike would bind the whole video), Freesound API results and the Jamendo free tier. ND licenses are rejected for music, video and SFX on every project, because the edit is a derivative.

## Premium look rules
- Real 3D for titles, objects and explainer scenes: Blender headless or Three.js in Remotion (`remotion/src/Title3D.tsx`), lit with Poly Haven HDRIs. No flat clip-art and no AI-generated icons.
- **One icon family, one 3D style, one sound kit, one type system per video**, recorded in the EDL's `project.kit`.
- **Quality filter before use:** minimum resolution (images: 1080 px short side; video: 1080 px high), no watermark, no visible compression, matching style. **Claude views a preview frame of every visual asset before placing it.**
- **B-roll must show what is being said at that moment.** Generic stock that only fills time is rejected.

## The editor kit
`assets/kit/manifest.json` holds about 300 role slots (whoosh short and long, swipe, pop, click, hit, riser, sub drop, glitch, shutter, ding, notification, paper, camera, room tone, ambience). Each slot names its source pack and file, so the kit can be rebuilt from the user's downloads. **No pack files ship with the skill.** `tag_assets.py kit` fills the slots from tagged packs. Until then, `kit:<role>` resolves to a sound the skill synthesizes (`pve_synth_v1`, no third-party rights), so an edit never blocks on downloads.

## Tagging and embeddings
`tag_assets.py` measures duration, loudness, brightness, attack, BPM, key, energy and a role guess for audio; size, duration, colour and motion for visuals. An audio-text embedding (CLAP) needs torch, which this environment lacks, so search ranks by tags and features and says so. Computing embeddings is inference, which the terms checked so far allow; training on pack audio is not allowed (Sonniss forbids it). Record the check per pack in its `LICENSE.json`.

## License ledger
Every asset placed in an EDL adds a line to `project/licenses.json`: id, source, license, URL, date checked, attribution text, restrictions. render.py writes it; qc.py `licenses` checks it; package.py writes `credits.txt` with the exact attribution wording and warns about a non-commercial asset in a commercial project. **Keep the ledger as proof of license for music**, so a Content ID claim can be disputed.
