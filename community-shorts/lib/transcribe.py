"""ElevenLabs Scribe transcription, adapted from video-use/helpers/transcribe.py.

Writes into the project folder:
  transcript.json   raw Scribe response (cached; never re-uploaded for the same source)
  words.json        flat word list [{text, start, end, speaker}]
  transcript.md     phrase-level reading view, one line per phrase with [start-end]
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import requests

from .common import elevenlabs_key, run

SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
PHRASE_GAP_S = 0.5


def _fingerprint(video: Path) -> str:
    st = video.stat()
    return hashlib.sha1(f"{video.name}:{st.st_size}:{int(st.st_mtime)}".encode()).hexdigest()[:12]


def call_scribe(audio: Path, num_speakers: int | None, language: str | None, model: str) -> dict:
    data = {
        "model_id": model,
        "diarize": "true",
        "tag_audio_events": "true",
        "timestamps_granularity": "word",
    }
    if num_speakers:
        data["num_speakers"] = str(num_speakers)
    if language:
        data["language_code"] = language
    with open(audio, "rb") as f:
        resp = requests.post(
            SCRIBE_URL,
            headers={"xi-api-key": elevenlabs_key()},
            files={"file": (audio.name, f, "audio/wav")},
            data=data,
            timeout=1800,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs Scribe returned {resp.status_code}: {resp.text[:400]}")
    return resp.json()


def flatten_words(payload: dict) -> list[dict]:
    words = []
    for w in payload.get("words", []):
        if w.get("type") != "word" or w.get("start") is None:
            continue
        text = (w.get("text") or "").strip()
        if not text:
            continue
        words.append({
            "text": text,
            "start": round(float(w["start"]), 3),
            "end": round(float(w["end"]), 3),
            "speaker": w.get("speaker_id") or "S0",
        })
    return words


def pack(words: list[dict], payload: dict, duration: float) -> str:
    """Phrase-level view: break on silence >= 0.5s or speaker change."""
    lines = [f"# Transcript  (source duration {duration:.1f}s, {len(words)} words)", ""]
    events = [e for e in payload.get("words", []) if e.get("type") == "audio_event"]
    phrase: list[dict] = []

    def flush():
        if phrase:
            a, b = phrase[0]["start"], phrase[-1]["end"]
            text = " ".join(w["text"] for w in phrase)
            lines.append(f"[{a:07.2f}-{b:07.2f}] {phrase[0]['speaker']}  {text}")

    for w in words:
        if phrase and (w["start"] - phrase[-1]["end"] >= PHRASE_GAP_S or w["speaker"] != phrase[-1]["speaker"]):
            flush()
            phrase = []
        phrase.append(w)
    flush()
    if events:
        lines += ["", "## Audio events"]
        lines += [f"[{e['start']:07.2f}-{e['end']:07.2f}] {e.get('text')}" for e in events]
    return "\n".join(lines) + "\n"


def transcribe(video: Path, proj: Path, info: dict, num_speakers: int | None = None,
               language: str | None = None, model: str = "scribe_v1", force: bool = False,
               import_json: Path | None = None, engine: str = "elevenlabs") -> list[dict]:
    raw_path = proj / "transcript.json"
    meta_path = proj / "transcript.meta.json"
    fp = _fingerprint(video)
    cached = raw_path.exists() and meta_path.exists() and json.loads(meta_path.read_text()).get("fingerprint") == fp
    if import_json:
        print(f"  using existing Scribe JSON {import_json.name}")
        payload = json.loads(import_json.read_text())
        raw_path.write_text(json.dumps(payload, indent=1))
        meta_path.write_text(json.dumps({"fingerprint": fp, "source": str(video), "model": "imported"}))
    elif cached and not force:
        print(f"  transcript cached ({raw_path.name})")
        payload = json.loads(raw_path.read_text())
    else:
        if not info["has_audio"]:
            raise RuntimeError(f"{video.name} has no audio track")
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "audio.wav"
            run(["ffmpeg", "-y", "-i", str(video), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
                 "-c:a", "pcm_s16le", str(wav)])
            if engine == "local":
                from .local_asr import transcribe_local
                print("  transcribing locally (Parakeet via sherpa-onnx)")
                payload = transcribe_local(wav)
                model = "parakeet-local"
            else:
                print(f"  uploading audio to ElevenLabs Scribe ({wav.stat().st_size / 1e6:.1f} MB)")
                payload = call_scribe(wav, num_speakers, language, model)
        raw_path.write_text(json.dumps(payload, indent=1))
        meta_path.write_text(json.dumps({"fingerprint": fp, "source": str(video), "model": model}))
    words = flatten_words(payload)
    (proj / "words.json").write_text(json.dumps(words, indent=0))
    (proj / "transcript.md").write_text(pack(words, payload, info["duration"]))
    return words
