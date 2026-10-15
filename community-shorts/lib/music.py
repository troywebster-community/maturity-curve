"""Original, royalty-free background music, synthesized from scratch (numpy + scipy).

For videos with no voiceover. Builds a four-on-the-floor dance track at a set tempo with
sections you place in seconds, so cuts and graphics can land on the beat:

  riser  : build-up (noise sweep, rising tone, snare roll), no kick
  drop   : full beat (kick, clap, hats, offbeat bass, pumping chords)
  lift   : drop plus a plucked arpeggio on top (the high-energy part)
  break  : filtered chords only, no drums
  outro  : chords and a soft kick, fading

  python shorts.py music --out music.wav --bpm 124 --length 50 \
      --sections "riser:0-0.97,drop:0.97-16.5,break:16.5-20.4,lift:20.4-46.5,outro:46.5-50"
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

SR = 44100
RNG = np.random.default_rng(7)          # fixed seed: same track every render

# A minor: Am - F - C - G, one chord per bar
CHORDS = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
ROOTS = [45, 41, 48, 43]


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, f, order=2):
    return sosfilt(butter(order, min(f, SR / 2 - 100), "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def saw(freq, n, phase=0.0):
    t = np.arange(n) / SR
    return 2 * ((t * freq + phase) % 1.0) - 1


def add(buf, sig, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i]


# ---------------------------------------------------------------- instruments

def kick(gain=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 46 + 120 * np.exp(-t * 30)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    click = RNG.standard_normal(n) * np.exp(-t * 400) * 0.25
    return np.tanh((body + click) * 1.6) * gain


def clap(gain=0.55):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    env = np.zeros(n)
    for d in (0.0, 0.011, 0.022):
        k = int(d * SR)
        env[k:] += np.exp(-(t[: n - k]) * (60 if d < 0.02 else 18))
    return bp(RNG.standard_normal(n), 900, 3200) * env * gain


def hat(open_=False, gain=0.11):
    n = int((0.18 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    return hp(RNG.standard_normal(n), 7000) * np.exp(-t * (14 if open_ else 90)) * gain


def bass_note(midi, dur, gain=0.42):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = saw(hz(midi), n) * 0.6 + np.sin(2 * np.pi * hz(midi) * t)
    env = np.minimum(1, t / 0.005) * np.exp(-t * 5)
    return lp(s, 420) * env * gain


def chord_pad(notes, dur, cutoff, gain=0.11):
    n = int(dur * SR)
    t = np.arange(n) / SR
    left = np.zeros(n)
    right = np.zeros(n)
    for m in notes:
        for k, det in enumerate((-0.12, -0.05, 0.0, 0.06, 0.13)):
            f = hz(m + 12) * 2 ** (det / 12)
            v = saw(f, n, phase=RNG.random())
            (left if k % 2 else right)[:] += v
            (right if k % 2 else left)[:] += v * 0.6
    env = np.minimum(1, t / 0.02) * np.minimum(1, (dur - t) / 0.05).clip(0, 1)
    return lp(left, cutoff) * env * gain, lp(right, cutoff) * env * gain


def pluck(midi, gain=0.16):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    s = saw(hz(midi), n) + saw(hz(midi) * 1.004, n)
    return lp(s, 3200) * np.exp(-t * 13) * gain


def riser(dur, gain=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = t / dur
    noise = RNG.standard_normal(n)
    out = np.zeros(n)
    block = 2048
    for i in range(0, n, block):
        f = 400 + 9000 * x[i] ** 2
        out[i:i + block] = bp(noise[i:i + block], f * 0.7, min(f * 1.4, SR / 2 - 200), order=1)
    tone = np.sin(2 * np.pi * np.cumsum(200 + 900 * x ** 2) / SR) * 0.25
    return (out + tone) * (x ** 1.6) * gain


def impact(gain=0.9):
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(30 + 60 * np.exp(-t * 8)) / SR) * np.exp(-t * 2.2)
    crash = hp(RNG.standard_normal(n), 3000) * np.exp(-t * 3.2) * 0.35
    return (boom + crash) * gain


# ---------------------------------------------------------------- arrangement

def build(length: float, bpm: float, sections: list[tuple[str, float, float]]) -> np.ndarray:
    beat = 60.0 / bpm
    bar = beat * 4
    n = int(length * SR) + SR
    L = np.zeros(n)
    R = np.zeros(n)
    mono = np.zeros(n)          # drums + bass, centred
    pump = np.ones(n)           # sidechain gain for the pads

    def kind_at(t):
        for k, a, b in sections:
            if a <= t < b:
                return k
        return None

    k_sig, c_sig = kick(), clap()
    oh, ch = hat(True), hat(False)
    total_beats = int(length / beat) + 1
    for i in range(total_beats):
        t = i * beat
        kind = kind_at(t)
        bar_i = int(t / bar) % 4
        if kind in ("drop", "lift", "outro"):
            outro_start = next((a for k, a, _ in sections if k == "outro"), length)
            g = 1.0 if kind != "outro" else max(0.0, 1 - (t - outro_start) / 3)
            add(mono, k_sig * g, t)
            j = int(t * SR)
            dip = 1 - 0.75 * np.exp(-np.arange(int(beat * SR)) / SR * 9)
            pump[j:j + len(dip)] = np.minimum(pump[j:j + len(dip)], dip[: len(pump[j:j + len(dip)])])
        if kind in ("drop", "lift"):
            if i % 2 == 1:
                add(mono, c_sig, t)
            add(mono, oh, t + beat / 2)
            for q in (0.25, 0.75):
                add(mono, ch, t + beat * q)
            add(mono, bass_note(ROOTS[bar_i], beat * 0.45), t + beat / 2)
        if kind == "lift":
            notes = CHORDS[bar_i] + [CHORDS[bar_i][0] + 12]
            for e in range(2):
                add(R if e else L, pluck(notes[(i * 2 + e) % 4] + 12), t + e * beat / 2)
                add(L if e else R, pluck(notes[(i * 2 + e) % 4] + 12) * 0.6, t + e * beat / 2 + 0.11)

    # Pads, one chord per bar, brightness by section
    bars = int(length / bar) + 1
    for b in range(bars):
        t = b * bar
        kind = kind_at(t + 0.01)
        if kind is None:
            continue
        cutoff = {"drop": 2600, "lift": 3400, "break": 700, "riser": 900, "outro": 1500}[kind]
        gain = {"break": 0.14, "riser": 0.09}.get(kind, 0.11)
        pl, pr = chord_pad(CHORDS[b % 4], bar, cutoff, gain)
        add(L, pl, t)
        add(R, pr, t)

    # Risers into every drop/lift, impacts on them
    for k, a, b in sections:
        if k == "riser":
            r = riser(b - a)
            add(L, r, a)
            add(R, r, a)
            # snare roll speeding up
            third = (b - a) / 3
            for step, div in enumerate((8, 16, 32)):
                start = a + third * step
                for s in range(int(third / (bar / div))):
                    add(mono, c_sig * (0.35 + 0.15 * step), start + s * bar / div)
        if k in ("drop", "lift") and a > 0.01:
            imp = impact()
            add(L, imp, a)
            add(R, imp, a)
        if k == "outro":
            imp = impact(0.7)
            add(L, imp, a)
            add(R, imp, a)

    L = L * pump + mono
    R = R * pump + mono
    st = np.stack([L, R], axis=1)[: int(length * SR)]
    fade = int(1.2 * SR)
    st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    st = np.tanh(st * 1.1)
    st /= np.max(np.abs(st)) / 0.89
    return st


def write(path: Path, length: float, bpm: float, sections: list[tuple[str, float, float]]) -> Path:
    audio = build(length, bpm, sections)
    pcm = (audio * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def parse_sections(spec: str) -> list[tuple[str, float, float]]:
    out = []
    for part in spec.split(","):
        kind, span = part.split(":")
        a, b = span.split("-")
        out.append((kind.strip(), float(a), float(b)))
    return out
