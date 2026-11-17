# Localization

Read when the footage or the captions are not English, or when the user wants translated captions.

## Transcription
- The transcriber is pluggable (`lib/transcribe.py`, `--transcriber module:Class`): faster-whisper by default, so a fine-tuned model can replace it.
- **Amharic (`am`)**: do not use stock Whisper. Measured on a 38 s talking head (2026-11-16): `medium` wrote the wrong script, a ct2 fine-tune wrote noise, Whisper-SAM dropped 6 s of speech. `snapwre/hohe-asr-amharic` (wav2vec2-BERT) gave a near-correct transcript. Workflow, all inside the skill (`scripts/transcribe_am.py`, `lib/amharic_asr.py`; needs `requirements-amharic.txt`: CPU torch, transformers, uroman): (1) `transcribe_am.py draft --media clip.mp4 --out P/transcript_am_draft.txt` (hohe-asr, ~1 min for 35 s on CPU); (2) read and correct the text, adding ። ? ፣ (captions break phrases on them), and re-listen to unclear stretches with `draft --start S --end E`; (3) `transcribe_am.py align --media clip.mp4 --text P/transcript_am.txt --out P/words_am.json` (MMS forced aligner on the uroman romanisation); (4) `PVE_TRANSCRIPT=P/words_am.json python scripts/analyze.py --project P --language am --transcriber lib.transcript_file:FromFile`. For a first look without correcting, `--transcriber lib.amharic_asr:HoheAsr` does draft + align in one go. English said inside Amharic comes out as Ge'ez phonetics ("ፐርሊን" = "per lean"): write it the way the speaker's audience reads it. Delete `P/cache/transcript` when the word file changes. List every phrase that is still uncertain in the paper edit's `assumptions` for the user to proofread. Captions: `caption_style: "lockup"` works; fetch `Noto Sans Ethiopic` (600/800/900) and `Noto Serif Ethiopic` (600); keyword size ~150 px because a fidel is about twice as wide as a Latin letter. The planner tightens long pauses: restore a pause that is the joke.
- **Afaan Oromo (`om`)**: Whisper has no Oromo. The skill refuses to transcribe `om` with Whisper rather than produce a fake transcript. Supply a transcript (SRT or word JSON) or plug in a model.

## Ethiopic captions (Ge'ez script)
- Font: **Noto Sans Ethiopic** (downloaded to `assets/fonts/`; profile `fonts.ethiopic`; Abyssinica SIL works too). render.py switches a card to the Ethiopic font when it contains Ethiopic characters (U+1200-137F, U+2D80-2DDF, U+AB00-AB2F).
- **Words per card by syllable count, not Latin word length**: each Ethiopic character is one syllable (fidel). Limits: `pop_3word` 8 syllables, `bold_1word` 5, `clean_line` 24 (STARTING DEFAULTS).
- No uppercasing: Ethiopic has no case. Keyword highlight works the same way.
- Word separator: Whisper outputs spaces; the traditional `፡` is kept if present. Sentence end `።` and question mark `፧` are recognised by `sentences()`.
- **Test:** `tests/test_localization.py` renders an Amharic card with libass and checks that the glyphs drew (non-empty ink, no tofu boxes). The same check covers an Arabic right-to-left line and a mixed English+Amharic line.

## Right-to-left scripts
libass shapes Arabic and Hebrew with HarfBuzz and reorders them with FriBidi, so ASS text renders RTL correctly when the font has the glyphs (add a font such as Noto Sans Arabic to `assets/fonts/` and the profile). Do not reverse strings by hand.

## Translated caption tracks
Deliver translations as extra sidecar files next to the main captions (`captions.<lang>.srt`), timed from the source cards. Translation is done by Claude from the transcript, card by card, keeping the card boundaries. Never burn a translation in unless asked.

## Dubbing
Only with the speaker's permission, and with the AI disclosure flag set (compliance.md): mark the dialogue events `dub: true`.
