"""Plan -> output timeline.

Snaps every cut to word boundaries (video-use Hard Rules 6 + 7), maps transcript words onto
the output timeline (Rule 5), and resolves callout anchors ("say this phrase" -> seconds).
"""

from __future__ import annotations

import re

PAD_IN = 0.06     # seconds kept before the first word of a range
PAD_OUT = 0.10    # seconds kept after the last word of a range
SNAP_WINDOW = 0.8


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9%$]+", "", s.lower())


def snap_ranges(ranges: list[dict], words: list[dict], source_duration: float,
                envelope: "Envelope | None" = None) -> list[dict]:
    """Move each range edge onto a word edge, then pad. Never cut inside a word.

    start -> the word starting nearest the given start.
    end   -> the end of the last word that starts before the given end.
    With an audio envelope, edges then slide outward through any still-audible sound
    (word timings drift; the waveform does not), stopping short of the neighbouring word.
    """
    out = []
    for r in ranges:
        a, b = float(r["start"]), float(r["end"])
        if b <= a:
            raise ValueError(f"range end before start: {r}")
        starts = [w for w in words if abs(w["start"] - a) <= SNAP_WINDOW]
        inside = [w for w in words if a - 0.15 <= w["start"] < b - 0.05]
        prev_end, next_start = 0.0, source_duration
        if starts:
            first = min(starts, key=lambda w: abs(w["start"] - a))
            before = [w for w in words if w["start"] < first["start"]]
            if before:
                prev = max(before, key=lambda w: w["start"])
                # ASR end times can overlap the next word; never reach back past real silence
                prev_end = prev["end"] if prev["end"] <= first["start"] - 0.08 else first["start"] - 0.06
            else:
                prev_end = 0.0
            a = max(first["start"] - PAD_IN, (prev_end + first["start"]) / 2, 0.0)
        if inside:
            last = max(inside, key=lambda w: w["start"])
            next_start = min([w["start"] for w in words if w["start"] > last["start"]], default=source_duration)
            b = min(last["end"] + PAD_OUT, (last["end"] + next_start) / 2, source_duration)
        if envelope is not None:
            a = envelope.quiet_before(a, floor=prev_end)
            b = envelope.quiet_after(b, ceiling=next_start - 0.03)
        # An edge that lands inside a neighbouring word gives that word up, never half of it.
        first_s = first["start"] if starts else None
        last_s = last["start"] if inside else None
        for w in words:
            if w["start"] < a < w["end"]:
                a = min(w["end"], first_s) if first_s is not None and w["start"] < first_s else w["start"] - 0.02
            if w["start"] < b < w["end"]:
                b = max(w["start"] - 0.01, a + 0.1) if last_s is not None and w["start"] > last_s else w["end"] + 0.02
        if b - a < 0.15:
            raise ValueError(f"range {r['start']}-{r['end']} holds no complete word after snapping")
        out.append({**r, "start": round(max(0.0, a), 3), "end": round(min(b, source_duration), 3)})
    return out


class Envelope:
    """10 ms RMS envelope of the source audio, for nudging cuts into real silence."""

    def __init__(self, source, step: float = 0.01):
        import array
        import math
        import subprocess
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:a:0", "-ac", "1",
                              "-ar", "8000", "-f", "s16le", "-"], capture_output=True).stdout
        pcm = array.array("h", raw)
        n = int(8000 * step)
        self.step = step
        self.rms = [math.sqrt(sum(x * x for x in pcm[i:i + n]) / n) for i in range(0, len(pcm) - n, n)]
        loud = sorted(self.rms)
        floor = loud[len(loud) // 10] if loud else 0
        speech = loud[len(loud) * 7 // 10] if loud else 1
        self.threshold = max(floor * 3, speech * 0.12, 60)

    def _loud(self, t: float) -> bool:
        i = int(t / self.step)
        return 0 <= i < len(self.rms) and self.rms[i] > self.threshold

    def quiet_after(self, t: float, ceiling: float, limit: float = 0.35) -> float:
        end = min(ceiling, t + limit)
        while t < end and self._loud(t):
            t += self.step
        return t

    def quiet_before(self, t: float, floor: float, limit: float = 0.25) -> float:
        start = max(floor, t - limit)
        while t > start and self._loud(t - self.step):
            t -= self.step
        return t


def output_words(ranges: list[dict], words: list[dict], corrections: dict[str, str]) -> list[dict]:
    """Words that survive the cut, with output-timeline times: t_out = t_src - range.start + offset."""
    fixes = {k.lower(): v for k, v in (corrections or {}).items()}
    result, offset = [], 0.0
    for idx, r in enumerate(ranges):
        a, b = r["start"], r["end"]
        for w in words:
            mid = (w["start"] + w["end"]) / 2
            if a <= mid <= b:
                text = w["text"]
                key = re.sub(r"[^\w']+$", "", text.lower())
                if key in fixes:
                    trail = text[len(key):] if text.lower().startswith(key) else ""
                    text = fixes[key] + trail
                result.append({
                    "text": text,
                    "start": round(max(w["start"], a) - a + offset, 3),
                    "end": round(min(w["end"], b) - a + offset, 3),
                    "segment": idx,
                })
        offset += b - a
    return result


def resolve_anchor(anchor: str, owords: list[dict]) -> float:
    """Output time of the first word of `anchor` (a phrase the speaker says)."""
    target = [_norm(t) for t in anchor.split() if _norm(t)]
    seq = [_norm(w["text"]) for w in owords]
    for i in range(len(seq) - len(target) + 1):
        if seq[i:i + len(target)] == target:
            return owords[i]["start"]
    # Looser: first word only
    for i, s in enumerate(seq):
        if target and s == target[0]:
            return owords[i]["start"]
    raise ValueError(f'anchor "{anchor}" not found in the kept words. Use a phrase that survives the cut, or "at".')


def chunk_captions(owords: list[dict], max_words: int = 3, max_chars: int = 18) -> list[list[dict]]:
    """Short-form caption pages: up to 3 words, break on punctuation, pauses and segment cuts."""
    pages, cur = [], []
    for i, w in enumerate(owords):
        cur.append(w)
        nxt = owords[i + 1] if i + 1 < len(owords) else None
        chars = sum(len(x["text"]) + 1 for x in cur)
        if (
            nxt is None
            or w["text"][-1] in ".!?,;:"
            or nxt["start"] - w["end"] >= 0.35
            or nxt["segment"] != w["segment"]
            or len(cur) >= max_words
            or chars + len(nxt["text"]) > max_chars
        ):
            pages.append(cur)
            cur = []
    return pages
