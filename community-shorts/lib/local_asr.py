"""Offline fallback transcription (no API key, no network at run time).

Uses NVIDIA Parakeet TDT 0.6B v2 (English, punctuation + casing, token timestamps) through
sherpa-onnx. Output has the same shape as an ElevenLabs Scribe response, so everything
downstream works unchanged. ElevenLabs stays the default; use this when Scribe is unreachable.

Model setup (about 480 MB, once):
  pip install sherpa-onnx soundfile
  mkdir -p models && cd models
  curl -LO https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2
  tar xjf sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .common import ROOT, run

CHUNK_S = 24.0      # Parakeet is happiest on < 30s windows
SEARCH_S = 6.0      # look this far back for a silence to cut the window on


def model_dir() -> Path:
    env = os.environ.get("PARAKEET_MODEL_DIR")
    if env:
        return Path(env)
    hits = sorted((ROOT / "models").glob("sherpa-onnx-nemo-parakeet*"))
    if not hits:
        raise RuntimeError("Local model not found. See setup steps at the top of lib/local_asr.py")
    return hits[0]


def _silences(wav: Path) -> list[tuple[float, float]]:
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af",
               "silencedetect=noise=-35dB:d=0.25", "-f", "null", "-"]).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return list(zip(starts, ends))


def _windows(duration: float, silences: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out, a = [], 0.0
    while a < duration - 0.05:
        b = a + CHUNK_S
        if b >= duration:
            out.append((a, duration))
            break
        mids = [(s + e) / 2 for s, e in silences if b - SEARCH_S <= (s + e) / 2 <= b]
        b = max(mids) if mids else b
        out.append((a, b))
        a = b
    return out


def transcribe_local(wav16k: Path) -> dict:
    import sherpa_onnx
    import soundfile as sf

    d = model_dir()
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(d / "encoder.int8.onnx"), decoder=str(d / "decoder.int8.onnx"),
        joiner=str(d / "joiner.int8.onnx"), tokens=str(d / "tokens.txt"),
        model_type="nemo_transducer", num_threads=os.cpu_count() or 4,
    )
    audio, sr = sf.read(str(wav16k), dtype="float32")
    duration = len(audio) / sr
    tokens: list[tuple[str, float]] = []
    for a, b in _windows(duration, _silences(wav16k)):
        s = rec.create_stream()
        s.accept_waveform(sr, audio[int(a * sr):int(b * sr)])
        rec.decode_stream(s)
        tokens += [(t, a + ts) for t, ts in zip(s.result.tokens, s.result.timestamps)]

    # Tokens with a leading space start a new word; the rest (sub-words, punctuation) attach.
    words: list[dict] = []
    for tok, ts in tokens:
        if tok.startswith(" ") or not words:
            words.append({"text": tok.strip(), "start": ts, "last": ts})
        else:
            words[-1]["text"] += tok
            words[-1]["last"] = ts
    out = []
    for i, w in enumerate(words):
        nxt = words[i + 1]["start"] if i + 1 < len(words) else duration
        end = min(w["last"] + 0.12, nxt - 0.01) if nxt > w["last"] else w["last"] + 0.08
        out.append({"text": w["text"], "start": round(w["start"], 3), "end": round(max(end, w["start"] + 0.06), 3),
                    "type": "word", "speaker_id": "speaker_0"})
    return {"language_code": "en", "text": " ".join(w["text"] for w in out), "words": out,
            "engine": "parakeet-tdt-0.6b-v2 (local)"}
