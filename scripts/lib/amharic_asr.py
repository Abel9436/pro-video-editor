"""Amharic speech-to-text inside the skill: a wav2vec2-BERT CTC model for the draft text, the MMS
forced aligner for word timings.

Whisper is not usable for Amharic (measured 2026-11-16: `medium` wrote Telugu script, a fine-tuned
small CT2 model wrote noise, and Whisper-SAM dropped 6 s of speech). `snapwre/hohe-asr-amharic` was
trained on Amharic and writes Ge'ez directly; it has no language model, so the draft has spelling
mistakes and no punctuation and must be read and corrected before captions are made from it.

Two steps, both CPU:
  draft(wav)               -> text           (hohe-asr, greedy CTC decode in windows)
  align(wav, text)         -> [{w,start,end,p}]   (MMS aligner on the uroman romanisation)

Ported from the user's clipper project (pipeline/transcribe.py, pipeline/align.py). Needs the
optional packages in requirements-amharic.txt (torch, torchaudio, transformers, uroman); everything
is imported lazily so the rest of the skill runs without them.

Plug-in for analyze.py (draft + align in one go, no correction step - use for a first look only):
    python scripts/analyze.py --project P --language am --transcriber lib.amharic_asr:HoheAsr
"""
from __future__ import annotations

import os
import re
import wave
from pathlib import Path

ASR_MODEL = os.environ.get("PVE_AM_ASR_MODEL", "snapwre/hohe-asr-amharic")
ALIGN_MODEL = os.environ.get("PVE_AM_ALIGN_MODEL", "MahmoudAshraf/mms-300m-1130-forced-aligner")
SR = 16000
ASR_CHUNK_S = 30.0      # STARTING DEFAULT carried over from clipper (ASR_CHUNK_SECONDS)
ALIGN_CHUNK_S = 60.0    # clipper's ALIGN_CHUNK_SECONDS; emission frames are ~20 ms, window edges do not move timings
END = re.compile(r"[.?!።]$")
TAG = re.compile(r"\[[A-Z]{2,4}\]")     # hohe-asr prefixes "[AMH]" to every decode


def _torch_safe_path() -> None:
    """scripts/profile.py shadows the stdlib `profile` module that torch imports (via cProfile);
    drop the scripts folder from sys.path before torch loads."""
    import sys
    here = Path(__file__).resolve().parents[1]
    sys.path[:] = [x for x in sys.path if Path(x or ".").resolve() != here]
    m = sys.modules.get("profile")
    if m is not None and Path(getattr(m, "__file__", "") or "").resolve().parent == here:
        del sys.modules["profile"]


def need() -> None:
    _torch_safe_path()
    missing = []
    for m in ("torch", "torchaudio", "transformers", "uroman"):
        try:
            __import__(m)
        except ImportError:
            missing.append(m)
    if missing:
        raise RuntimeError(f"Amharic ASR needs {', '.join(missing)}: "
                           "pip install -r requirements-amharic.txt (CPU torch: add --index-url https://download.pytorch.org/whl/cpu)")


def load_wav(path: Path):
    """16-bit PCM WAV -> 1-D float tensor at 16 kHz (ingest/analyze already write audio.wav that way)."""
    import numpy as np
    import torch
    with wave.open(str(path), "rb") as h:
        ch, sw, sr, raw = h.getnchannels(), h.getsampwidth(), h.getframerate(), h.readframes(h.getnframes())
    if sw != 2:
        raise RuntimeError(f"{path.name} is {sw * 8}-bit; convert to 16-bit PCM WAV first (ffmpeg -ac 1 -ar 16000 -c:a pcm_s16le)")
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    w = torch.from_numpy(x.copy())
    if sr != SR:
        import torchaudio.functional as F
        w = F.resample(w, sr, SR)
    return w


def draft(wav: Path, start: float = 0.0, end: float | None = None) -> str:
    """Draft Ge'ez text for the audio (or the span start-end in seconds)."""
    need()
    import torch
    from transformers import AutoModelForCTC, AutoProcessor
    proc = AutoProcessor.from_pretrained(ASR_MODEL)
    model = AutoModelForCTC.from_pretrained(ASR_MODEL).eval()
    w = load_wav(wav)
    w = w[int(start * SR): int(end * SR) if end else None]
    step, parts = int(ASR_CHUNK_S * SR), []
    with torch.inference_mode():
        for off in range(0, w.numel(), step):
            c = w[off: off + step]
            if c.numel() < SR // 2:
                break
            logits = model(**proc(c.numpy(), sampling_rate=SR, return_tensors="pt")).logits
            t = TAG.sub("", proc.batch_decode(torch.argmax(logits, dim=-1))[0]).strip()
            if t:
                parts.append(t)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


_UROMAN = None


def _roman(text: str) -> str:
    global _UROMAN
    import uroman
    if _UROMAN is None:
        _UROMAN = uroman.Uroman()
    return _UROMAN.romanize_string(text, lcode="amh")      # ISO-639-3; "am" is not accepted


def _clean(s: str) -> str:
    return re.sub(r"[^a-z0-9']", "", s.lower())


def align(wav: Path, text: str) -> list[dict]:
    """Force-align corrected text to the audio. Returns [{"w", "start", "end", "p"}] in transcript order.
    Words with no alignable letters (digits romanise fine; bare punctuation does not) keep the
    neighbouring timing so the caption text is never silently dropped."""
    need()
    import torch
    import torchaudio.functional as F
    from transformers import AutoModelForCTC, AutoTokenizer
    model = AutoModelForCTC.from_pretrained(ALIGN_MODEL, dtype=torch.float32).eval()
    tok = AutoTokenizer.from_pretrained(ALIGN_MODEL)
    w = load_wav(wav)
    if w.numel() < SR // 2:
        raise RuntimeError("audio shorter than 0.5 s - nothing to align")
    step = int(ALIGN_CHUNK_S * SR)
    starts = list(range(0, w.numel(), step))
    if len(starts) > 1 and w.numel() - starts[-1] < SR // 2:
        starts.pop()
    em = []
    with torch.inference_mode():
        for i, off in enumerate(starts):
            c = w[off: starts[i + 1] if i + 1 < len(starts) else w.numel()]
            c = (c - c.mean()) / torch.sqrt(c.var() + 1e-7)
            em.append(torch.log_softmax(model(c.unsqueeze(0)).logits, dim=-1))
    em = torch.cat(em, dim=1)
    spf = w.numel() / em.shape[1] / SR
    vocab = tok.get_vocab()
    words = text.split()
    rom = _roman(text).split()
    if len(rom) != len(words):
        rom = [_roman(x).replace(" ", "") for x in words]
    targets, counts = [], []
    for r in rom:
        ids = [vocab[c] for c in _clean(r) if c in vocab]
        targets += ids
        counts.append(len(ids))
    if not targets:
        raise RuntimeError("no characters survived romanisation - is the text Ge'ez script?")
    blank = next((vocab[n] for n in ("<blank>", "<pad>", "-") if n in vocab), tok.pad_token_id or 0)
    ali, sc = F.forced_align(em.float(), torch.tensor([targets], dtype=torch.int32), blank=blank)
    spans = F.merge_tokens(ali[0], sc[0].exp())
    if len(spans) != len(targets):
        raise RuntimeError(f"alignment returned {len(spans)} spans for {len(targets)} tokens - text and audio may not match")
    out, cur = [], 0
    for word, n in zip(words, counts):
        sp = spans[cur: cur + n]
        cur += n
        if sp:
            out.append({"w": word, "start": round(sp[0].start * spf, 3), "end": round(sp[-1].end * spf, 3),
                        "p": round(sum(s.score for s in sp) / len(sp), 4)})
        else:       # punctuation-only token: attach to the previous word's end
            t = out[-1]["end"] if out else 0.0
            out.append({"w": word, "start": t, "end": t, "p": 0.0})
    return out


def segments(words: list[dict]) -> list[dict]:
    segs, cur = [], []
    for w in words:
        cur.append(w)
        if END.search(w["w"]):
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    return [{"start": s[0]["start"], "end": s[-1]["end"], "text": " ".join(x["w"] for x in s), "words": s} for s in segs]


class HoheAsr:
    """analyze.py transcriber plug-in: draft + align with no human correction (first look only)."""
    name = "hohe-asr-amharic"

    def transcribe(self, wav_path: Path, language: str | None = None, vocabulary: list[str] | None = None) -> dict:
        text = draft(Path(wav_path))
        words = align(Path(wav_path), text)
        return {"engine": self.name, "model": ASR_MODEL, "language": "am", "language_prob": 1.0,
                "segments": segments(words)}
