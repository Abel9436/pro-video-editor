# Audio

Read for every project with sound: always. Audio decides whether an edit feels professional. Dialogue is the spine; music and effects move around it.

## Levels (STARTING DEFAULTS unless noted)
| Element | Target | Implemented in | QC check |
|---|---|---|---|
| Master | -14 LUFS integrated, true peak -1 dBTP (YouTube, TikTok, Reels; spoken-word podcast -16) | `mix.loudnorm_master`, two-pass; rendered 1 dB under the ceiling because AAC overshoots (`CODEC_TP_MARGIN_DB`) | `loudness` (+-1 LU), `true_peak` |
| Dialogue | -16 LUFS, consistent across speakers | `mix.DIALOGUE_LUFS`, normalised per speaker before mixing | `speaker_consistency` (spread <= 3 LU) |
| Music under speech | 18-24 dB below the voice | `duck.depth_db` (music relative to voice during speech) | `music_voice_separation` (fail under 15 dB) |
| Music in gaps | about 6 dB below the voice level | `duck.gain_db` (default -6) | |
| Ducking | attack 50-100 ms, release 300-500 ms, sidechained from dialogue | `mix.duck_envelope` (exact attack/release ramps) | |
| SFX | bed ~ -24 dBFS, accents -18 to -12, impacts up to -6 | `gain_db` per SFX, placed by peak | |

**Normalise dialogue, music and SFX stems separately before mixing.** Hitting the loudness number is not enough: qc.py `intelligibility` re-transcribes the final mix and fails when the word error rate against the cut's words exceeds 15 % (STARTING DEFAULT), which means music or SFX is masking speech.

## Voice chain (in order)
1. Noise reduction: ffmpeg `afftdn` only when the noise floor sits between -60 and -40 dBFS. Quieter needs nothing; louder is usually music or ambience, and denoising it produces artefacts. (DeepFilterNet/RNNoise are not used: no torch in the target environment.)
2. High-pass near 80 Hz.
3. EQ: cut mud around 300 Hz (-2 dB), add presence around 4 kHz (+1.5 dB).
4. De-esser.
5. Gentle compression (2.5:1).
6. Limiter.
Settings adapt to the measured voice. **Do not over-process: artefacts are worse than a little noise.**

**Source with a music bed already in it** (steady level above -40 dBFS between words, measured in gaps only): render.py skips denoising, crossfades every cut with an equal-power 40 ms crossfade so the bed does not click, fills no room tone, and Claude does not add a second music track. This is common with downloaded or pre-edited clips.

## Sound design
- Every transition, text entrance and graphic **may** take a sound at low level, chosen by role from the kit: whoosh, pop, click, hit, riser, sub drop, glitch, shutter, ding. Density comes from the style (`audio.sfx_per_min`); calm styles use very few. `"sfx": "auto"` places them to the style's density.
- Risers lead into reveals. Hits land on impact text. **A short silence before a big moment makes it bigger.**
- **Never leave digital silence**: render.py fills it with room tone taken from the same recording (`mix.roomtone`). Check: `digital_silence`.
- Each location gets an ambient bed; carry ambience across cuts within a scene with J and L cuts.
- No audible pops at edit points: 8 ms edge fades on every dialogue event. Check: `pops`.

## Music editing
- Choose music by mood, energy and tempo that fit the pacing target (tag_assets.py: BPM, key, energy, vocals). Change track when the mood changes.
- **Edit music on bar lines**: shorten or extend by cutting between matching sections, never by fading mid-phrase (`end: "bar"`).
- **End on the track's real ending or a clean hit**, timed to the last picture (`end: "natural"` / `"hit"`). Avoid long fade-outs.
- **No vocals under speech** (tag_assets `vocals` flag, Whisper tiny on the track).

## Designed sound (2026-11-19)

Sound for a motion-graphics edit is designed per object and per move: craft-motion-principles.md section 9 (layer low/mid/high on a big moment, riser to impact to tail, 0.2 s between sounds, 3-5 different whooshes, one material-matched sound per 3D object). Find sounds with `scripts/find_sfx.py search`, copy them with `get`; sfx-kit sounds carry a measured `sync_s` that the mixer lands on `at_f`. With a Freesound key (env FREESOUND_API_KEY or ~/.pve/freesound_key, never in the repo) `scripts/fetch_sfx.py` searches the API for CC0 sounds by rating, and with `--min-dur 40 --max-dur 240` finds CC0 music beds; the licence is read from each sound's API record.

