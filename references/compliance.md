# Compliance, accessibility and privacy

Read before delivery, and whenever the edit uses generated media, music, other people's footage, or a sponsor.

Policies checked on **2026-11-15**. Re-check before relying on them.

## AI disclosure
- **YouTube** requires creators to disclose realistic altered or synthetic content: a real person saying or doing something they did not, altered footage of real events or places, or realistic generated scenes. Since May 2026 YouTube also applies the label itself when it detects undisclosed photorealistic AI. AI-generated music and synthetic voices of real people count. Scripts, captions, colour changes, beauty filters, upscaling, background blur, audio repair and clearly unrealistic visuals do not.
- **TikTok and Meta** (Instagram, Facebook) have similar AI-content labels; TikTok asks for its AI-generated label on realistic AI content.
- **package.py** writes `disclosure.json` with `label_needed`, the reasons and the rule date. A label is recommended when the EDL contains:
  - an event or B-roll marked `synthetic` or `generated`;
  - a dialogue event marked `voice_clone`, `dub` or `synthetic`;
  - a ledger entry marked `synthetic_realistic` (e.g. AI-generated music or photoreal images).
  The skill's synthesized SFX are not realistic depictions of people or events and do not need a label.

## Music rights
- Prefer sources that clear Content ID for monetised uploads. CC-licensed music can still be claimed: keep the ledger entry (URL, license, date) as proof to dispute a claim.
- `licenses.json` holds an entry for every placed asset; qc.py `licenses` fails a missing entry or a license that does not allow the project's use (NC in a commercial project, ND for music, video or SFX).

## Footage and characters
- No reuse of copyrighted footage, music or characters without a license. Reference videos are measured, never copied.
- Meme and GIF inserts are flagged to the user to clear (`broll[].needs_clearance: true`).

## Truthfulness
- No edit that changes the meaning of what someone said. plan_edit notes every removal inside a sentence; Claude rereads each changed sentence.

## Sponsored content
When the brief or transcript mentions a sponsor, remind the user to turn on the platform's paid-promotion disclosure (YouTube "includes paid promotion", TikTok "branded content", Instagram "paid partnership").

## Photosensitivity
qc.py `photosensitivity` fails more than 3 flashes in any one second (a flash is a luminance swing of 20 % of full range and back) and large high-contrast flicker; soften or remove the sequence.

## Accessibility
- Always export SRT and VTT alongside burned-in captions (qc.py `sidecar_captions`; package.py copies both).
- Captions readable on a phone: size (5.8 % of frame height for pop_3word), stroke, contrast.
- Describe important on-screen text in the description when it is not spoken.

## Privacy
- On request, blur bystanders' faces, license plates, addresses and screens with private data, with tracking: the EDL's `privacy.blur_faces` ("bystanders": every face except the tracked speaker; "all") is applied by render.py per frame. Plates and screens are blurred with `privacy.regions` (boxes with time ranges).
- Never clone or synthesise a real person's voice or face without that person's permission.
- Analysis runs locally by default (Whisper, OpenCV, RapidOCR). Network use happens only for: model and font downloads at first run, and fetch_assets.py searches (Openverse, Pexels, Pixabay, Poly Haven, Iconify), which send search words, never footage. State it when a step sends anything out, and keep it optional.

## Truth on screen (2026-11-18)

Every number, claim or result a designed graphic shows must come from the speaker's own words or from the user. No invented statistics, prices, ratings, reviews or badges, and no "guaranteed" results. Logos and brand names only with permission. Anyone recognisable on screen has agreed to appear; ask when it isn't the user's own footage.
