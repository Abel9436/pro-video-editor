# Reference frames

The owner's reference reels (supplied 2026-11-15 to 2026-11-17 as copyright-free visual references), one contact sheet each: 12 frames spread evenly through the video, read left to right, top row first. Look at them before designing a short, to calibrate "premium" by eye; the measured timings are in [effects-catalog.md](../effects-catalog.md) and [premium-design.md](../premium-design.md). They are references for the level of finish, not looks to copy: the house style is [craft-motion-design.md](../craft-motion-design.md).

Rebuild or add one: `ffmpeg -i REEL.mp4 -vf "fps=12/DURATION,scale=240:-2,tile=6x2:padding=4" -frames:v 1 -q:v 6 NN-creator.jpg`.

| Sheet | Creator | Length | What to look at |
|---|---|---|---|
| 01, 02 | Alimarel | 42 s, 49 s | Talking head with phone-UI tutorial cards; light kicker over heavy headline |
| 03 | Artzen Media | 45 s | Split-screen product demo, website search box, handwritten kicker |
| 04, 05 | EarnEdits | 36 s, 23 s | Pure motion design over voice-over: notifications, chat bubbles, tracklist |
| 06 | Edits By Ahmed | 26 s | Cinematic podcast: dark red grade, serif type, strike-through word swap, red slash shapes, framed photo cards |
| 07 | Honeyycomps | 19 s | White studio explainer: grey 3D shapes, cut-out images on cards, bold italic headline with light helper word |
| 08 | Islam Mohammed | 22 s | Gold-gradient tool showcase: UI windows sliding in, tiny kicker over key word |
| 09 | Joao Mendes (Studio Astreon) | 50 s | Green-lit talking head, single-word captions low in frame, light flash transition |
| 10 | John Ogwum | 35 s | Desk talking head, two-weight captions (light helper, bold key), white text-card interludes |
| 11, 18 | marcelgrau | 24 s, 38 s | One-word slam in the top third, overexpose cuts, text behind the subject, whips |
| 12 | PaidPro Digital | 17 s | Neon-yellow keyword captions, REC frame HUD, circle-highlight on the speaker, red chat pill |
| 13 | Tahacreate | 45 s | Clean minimal: soft gradient title cards, small centred captions, cursor and UI demo |
| 14 | Carlos Herique | 28 s | Warm grade, script + serif keyword captions, editing-timeline B-roll, framed photo pop-ins |
| 15 | Enginecy | 13 s | SEO ad: neon line icons drawing on, search-bar CTA, film burn, defocus push |
| 16 | Foysal Hossain | 29 s | Real estate: coloured keywords each in the next palette colour, 3D icons, whips |
| 17 | Hermes | 125 s | Text behind the head, 3D objects in hand, colour washes |
| 19 | Sumit Sharma | 26 s | Figma selection frame round the keyword, neon serif keyword, counter with icon, overexpose exits |
| 20 | Video Editing Pro | 81 s | Tool tutorial; search-bar CTA |
| 21 | Klickpin | 26 s | **The before/after format** that `scripts/before_after.py` builds |
| 22, 23 | Klickpin | 152 s, 45 s | Cozy-aesthetic and self-care reels: soft palette, slow pace |
