# Platforms

Read when choosing the target, placing text, or exporting. Verify each platform's current upload guidance before a delivery that matters; the values below were set at build time (2026-11-15) and the bitrates are STARTING DEFAULTS.

## Edit requirements
| Platform | Aspect | Pacing | Required in the edit |
|---|---|---|---|
| TikTok, Reels, YouTube Shorts | 9:16 | Very fast | Hook under 2 s, captions, loop ending, UI-safe margins at the bottom and right |
| YouTube long-form | 16:9 | By type | Strong first minute, re-hooks, chapters, end screen |
| Instagram feed | 4:5 | Medium | Works with sound off |
| LinkedIn | 1:1 or 4:5 | Calm | Captions, since many watch muted |
| Podcast video | 16:9 | Slow | Speaker switching, clean audio, chapters |

## Export presets (package.py `presets.json`)
| Preset | Size | Video | Audio | Loudness |
|---|---|---|---|---|
| shorts / tiktok / reels | 1080x1920 | H.264 High, ~16 Mb/s | AAC 48 kHz 320 kb/s | -14 LUFS, -1 dBTP |
| youtube | 1920x1080 | H.264 High, ~12 Mb/s | AAC 48 kHz 384 kb/s | -14 LUFS, -1 dBTP |
| linkedin | 1080x1350 (or 1080x1080) | H.264, ~10 Mb/s | AAC 48 kHz 256 kb/s | -14 LUFS |
| podcast | 1920x1080 | H.264, ~10 Mb/s | AAC 48 kHz 320 kb/s | -16 LUFS (spoken word) |

All: MP4 with the faststart flag, constant frame rate, Rec.709 tags, yuv420p. **Checks:** qc.py `format`, `faststart`, `av_streams`. One master, then platform variants; reframe between aspect ratios with face tracking (render.py at the new size), never a centre crop.

## Safe zones (captions and graphics)
Fractions of frame height for the caption baseline; app UI covers the bottom and right of vertical video.
| Platform | Caption baseline | Notes |
|---|---|---|
| shorts | 0.70 | keep text out of the bottom ~25 % and the right ~12 % |
| tiktok, reels | 0.68 | the caption and button stack sit higher than on Shorts |
| youtube | 0.88 | bottom band; avoid the last 20 s area where end screens go |
| instagram_feed, linkedin | 0.85 | |
| podcast | 0.88 | |
Side margin 8 % of width. **Check:** qc.py `caption_safe_zone`.

## Platform length notes
- Shorts: up to 3 minutes; most strong shorts are 15-35 s (STARTING DEFAULT).
- Chapters (YouTube long-form): first at 0:00, at least 3, each at least 10 s; package.py builds them from beat boundaries.
