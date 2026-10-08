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


def snap_ranges(ranges: list[dict], words: list[dict], source_duration: float) -> list[dict]:
    """Move each range edge onto the nearest word edge, then pad. Never cut inside a word."""
    out = []
    for r in ranges:
        a, b = float(r["start"]), float(r["end"])
        if b <= a:
            raise ValueError(f"range end before start: {r}")
        starts = [w for w in words if abs(w["start"] - a) <= SNAP_WINDOW]
        ends = [w for w in words if abs(w["end"] - b) <= SNAP_WINDOW]
        if starts:
            first = min(starts, key=lambda w: abs(w["start"] - a))
            prev_end = max([w["end"] for w in words if w["end"] <= first["start"]], default=0.0)
            a = max(first["start"] - PAD_IN, (prev_end + first["start"]) / 2, 0.0)
        if ends:
            last = min(ends, key=lambda w: abs(w["end"] - b))
            next_start = min([w["start"] for w in words if w["start"] >= last["end"]], default=source_duration)
            b = min(last["end"] + PAD_OUT, (last["end"] + next_start) / 2, source_duration)
        # A snap must never leave a word half inside the range.
        for w in words:
            if w["start"] < a < w["end"]:
                a = w["start"] - 0.02
            if w["start"] < b < w["end"]:
                b = w["end"] + 0.02
        out.append({**r, "start": round(max(0.0, a), 3), "end": round(min(b, source_duration), 3)})
    return out


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
