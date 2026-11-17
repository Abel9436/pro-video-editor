"""Pluggable transcribers.

Every transcriber returns the same shape, with times in seconds (the decoder
edge; analyze.py converts them to timeline frames immediately):

    {"engine": str, "model": str, "language": "en", "language_prob": 0.98,
     "segments": [{"start": 0.0, "end": 2.1, "text": "...",
                   "words": [{"w": "Hello", "start": 0.0, "end": 0.4, "p": 0.97}]}]}

Select with --transcriber:
  faster-whisper            default; word timestamps built in, runs locally
  none                      skip transcription (music-only or picture-only projects)
  package.module:ClassName  any class implementing `Transcriber` - this is how a
                            fine-tuned Amharic model or an Afaan Oromo model plugs in
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Protocol

# Whisper has no Afaan Oromo ("om"). Amharic ("am") exists but its accuracy is low;
# a fine-tuned model should replace it through the plugin interface.
WHISPER_UNSUPPORTED = {"om": "Afaan Oromo", "ti": "Tigrinya"}
WHISPER_WEAK = {"am": "Amharic"}

# A verbatim-style prompt nudges Whisper to keep fillers ("um", "uh") that it
# otherwise silently cleans up; the edit needs to see them in order to cut them.
VERBATIM_PROMPT = "Umm, let me think, like, hmm... Okay, so, uh, here's what I, I mean, what I'm thinking."


class Transcriber(Protocol):
    name: str

    def transcribe(self, wav_path: Path, language: str | None = None,
                   vocabulary: list[str] | None = None) -> dict: ...


class TranscriberUnavailable(RuntimeError):
    pass


class FasterWhisper:
    name = "faster-whisper"

    def __init__(self, model: str = "small", device: str = "auto", verbatim: bool = True):
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise TranscriberUnavailable("faster-whisper is not installed: pip install faster-whisper") from e
        compute = "int8" if device in ("cpu", "auto") else "float16"
        try:
            self.model = WhisperModel(model, device=device, compute_type=compute)
        except Exception as e:  # model download or CUDA init failure
            if device != "cpu":
                self.model = WhisperModel(model, device="cpu", compute_type="int8")
            else:
                raise TranscriberUnavailable(f"could not load Whisper model '{model}': {e}") from e
        self.model_name = model
        self.verbatim = verbatim

    def transcribe(self, wav_path: Path, language: str | None = None,
                   vocabulary: list[str] | None = None) -> dict:
        if language in WHISPER_UNSUPPORTED:
            raise TranscriberUnavailable(
                f"Whisper does not support {WHISPER_UNSUPPORTED[language]} ('{language}'). "
                "Pass --transcriber package.module:ClassName with a model that does.")
        prompt = VERBATIM_PROMPT if self.verbatim and language in (None, "en") else None
        hotwords = " ".join(vocabulary) if vocabulary else None
        # Pass samples, not a path: ingest already made 16 kHz mono, and this avoids
        # faster-whisper's PyAV decoder (its API breaks across PyAV releases).
        import soundfile as sf
        audio, sr = sf.read(str(wav_path), dtype="float32")
        if sr != 16000:
            raise TranscriberUnavailable(f"{wav_path} is {sr} Hz; expected the 16 kHz WAV from ingest.py")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        segments, info = self.model.transcribe(
            audio, language=language, word_timestamps=True, vad_filter=True,
            initial_prompt=prompt, hotwords=hotwords, condition_on_previous_text=False)
        out = {"engine": self.name, "model": self.model_name, "language": info.language,
               "language_prob": round(float(info.language_probability), 3), "segments": []}
        for s in segments:
            words = [{"w": w.word.strip(), "start": float(w.start), "end": float(w.end),
                      "p": round(float(w.probability), 3)} for w in (s.words or []) if w.word.strip()]
            out["segments"].append({"start": float(s.start), "end": float(s.end), "text": s.text.strip(),
                                    "words": words})
        if info.language in WHISPER_WEAK:
            out["warning"] = (f"Whisper accuracy for {WHISPER_WEAK[info.language]} is low; "
                              "review the transcript or plug in a fine-tuned model")
        return out


class NoTranscriber:
    name = "none"

    def transcribe(self, wav_path: Path, language: str | None = None,
                   vocabulary: list[str] | None = None) -> dict:
        return {"engine": "none", "model": None, "language": language, "language_prob": None, "segments": []}


def load_transcriber(spec: str, model: str = "small", device: str = "auto") -> Transcriber:
    if spec == "faster-whisper":
        return FasterWhisper(model=model, device=device)
    if spec == "none":
        return NoTranscriber()
    if ":" in spec:
        mod_name, cls_name = spec.split(":", 1)
        try:
            cls = getattr(importlib.import_module(mod_name), cls_name)
        except (ImportError, AttributeError) as e:
            raise TranscriberUnavailable(f"cannot load transcriber plugin '{spec}': {e}") from e
        return cls()
    raise TranscriberUnavailable(f"unknown transcriber '{spec}' (use faster-whisper, none, or module:Class)")
