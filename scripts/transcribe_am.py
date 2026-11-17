"""Amharic transcription for the skill: a draft from snapwre/hohe-asr-amharic, then word timings
by forced alignment of the corrected text (MMS aligner). Prints JSON.

  draft:  python scripts/transcribe_am.py draft --media clip.mp4 --out P/transcript_am_draft.txt
          (optionally --start/--end seconds to re-listen to one unclear stretch)
  align:  python scripts/transcribe_am.py align --media clip.mp4 --text P/transcript_am.txt --out P/words_am.json

Then feed the words to the pipeline:
  PVE_TRANSCRIPT=P/words_am.json python scripts/analyze.py --project P --language am \
      --transcriber lib.transcript_file:FromFile
(delete P/cache/transcript first when the word file changed).

The draft has no punctuation and misspells; read it against the audio and fix it before aligning.
Put ። ? ፣ in the corrected text - captions break phrases on them. Needs requirements-amharic.txt."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):              # Ge'ez text on a Windows cp1252 console
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import amharic_asr as am  # noqa: E402


def to_wav(media: Path, tmp: Path) -> Path:
    if media.suffix.lower() == ".wav":
        return media
    out = tmp / "audio16k.wav"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out)],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg could not read {media}: {r.stderr.strip()[-300:]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft", help="draft Ge'ez text with hohe-asr")
    d.add_argument("--media", required=True, type=Path)
    d.add_argument("--out", type=Path, help="write the draft text here")
    d.add_argument("--start", type=float, default=0.0)
    d.add_argument("--end", type=float)
    a = sub.add_parser("align", help="word timings for corrected text")
    a.add_argument("--media", required=True, type=Path)
    a.add_argument("--text", required=True, type=Path, help="corrected transcript (UTF-8)")
    a.add_argument("--out", required=True, type=Path, help="word JSON for lib.transcript_file:FromFile")
    args = ap.parse_args()
    try:
        if not args.media.exists():
            raise RuntimeError(f"no such file: {args.media}")
        with tempfile.TemporaryDirectory() as td:
            wav = to_wav(args.media, Path(td))
            if args.cmd == "draft":
                text = am.draft(wav, args.start, args.end)
                if args.out:
                    args.out.parent.mkdir(parents=True, exist_ok=True)
                    args.out.write_text(text + "\n", encoding="utf-8")
                res = {"ok": True, "model": am.ASR_MODEL, "words": len(text.split()), "text": text,
                       "out": str(args.out) if args.out else None,
                       "next": "correct the text (spelling, ። ? ፣), then run: transcribe_am.py align"}
            else:
                text = args.text.read_text(encoding="utf-8").strip()
                words = am.align(wav, text)
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
                low = [w["w"] for w in words if w["p"] < 0.3]
                res = {"ok": True, "model": am.ALIGN_MODEL, "words": len(words), "out": str(args.out),
                       "low_confidence": low[:30], "span_s": [words[0]["start"], words[-1]["end"]] if words else None}
    except Exception as e:          # noqa: BLE001 - one clear JSON error for any failure
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
