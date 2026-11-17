"""Transcriber plug-in: use a transcript the caller already has (word JSON), instead of running ASR.

    PVE_TRANSCRIPT=path/to/words.json python scripts/analyze.py --project P --language am \
        --transcriber lib.transcript_file:FromFile

words.json is a list of {"w": "word", "start": seconds, "end": seconds, "p": 0-1 (optional)}.
This is the path for languages Whisper handles badly (Amharic) or not at all (Afaan Oromo):
transcribe with a fine-tuned model, correct the text by hand, force-align it to the audio
(e.g. MMS forced aligner), and hand the word timings in here. Sentences are split on . ? ! and
the Ethiopic full stop."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

END = re.compile(r"[.?!።]$")


class FromFile:
    name = "transcript-file"

    def transcribe(self, wav_path: Path, language: str | None = None, vocabulary: list[str] | None = None) -> dict:
        src = os.environ.get("PVE_TRANSCRIPT")
        if not src or not Path(src).exists():
            raise RuntimeError("set PVE_TRANSCRIPT to a word JSON file: [{\"w\", \"start\", \"end\"}]")
        words = json.loads(Path(src).read_text(encoding="utf-8"))
        segs, cur = [], []
        for w in words:
            cur.append({"w": w["w"], "start": float(w["start"]), "end": float(w["end"]), "p": float(w.get("p", 1.0))})
            if END.search(w["w"]):
                segs.append(cur)
                cur = []
        if cur:
            segs.append(cur)
        return {"engine": self.name, "model": Path(src).name, "language": language or "und", "language_prob": 1.0,
                "segments": [{"start": s[0]["start"], "end": s[-1]["end"], "text": " ".join(x["w"] for x in s), "words": s} for s in segs]}
