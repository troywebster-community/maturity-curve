"""Final audio: speech from the cut, optional music bed ducked under speech, two-pass loudnorm
to the social standard (-14 LUFS, -1 dBTP), muxed onto the HyperFrames picture."""

from __future__ import annotations

import json
from pathlib import Path

from .common import run

LUFS, TP, LRA = -14.0, -1.0, 11.0


def _graph(total: float, voice_end: float, music: Path | None, music_vol: float,
           duck: bool = True) -> tuple[list[str], str]:
    inputs: list[str] = []
    if music is None:
        return inputs, f"[1:a]apad=whole_dur={total:.3f},atrim=0:{total:.3f}[mix]"
    inputs = ["-stream_loop", "-1", "-i", str(music)]
    if duck:
        # Speech-led video: music sits low under the voice, lifts after the last word.
        level = f"volume='if(gte(t,{voice_end:.3f}),{min(1.0, music_vol * 2.4):.3f},{music_vol:.3f})':eval=frame"
        side = "[bed][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[ducked];"
    else:
        # Music-led video: steady level, the source audio rides underneath.
        level = f"volume={music_vol:.3f}"
        side = "[key]anullsink;[bed]anull[ducked];"
    graph = (
        f"[1:a]apad=whole_dur={total:.3f},atrim=0:{total:.3f},asplit=2[voice][key];"
        f"[2:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,aformat=channel_layouts=stereo,{level},"
        f"afade=t=in:st=0:d=0.6,afade=t=out:st={max(0.0, total - 0.9):.3f}:d=0.9[bed];"
        f"{side}[voice][ducked]amix=inputs=2:normalize=0:duration=first[mix]"
    )
    return inputs, graph


def _measure(cmd_prefix: list[str], graph: str) -> dict | None:
    proc = run(cmd_prefix + [
        "-filter_complex", f"{graph};[mix]loudnorm=I={LUFS}:TP={TP}:LRA={LRA}:print_format=json[out]",
        "-map", "[out]", "-f", "null", "-",
    ])
    err = proc.stderr
    a, b = err.rfind("{"), err.rfind("}")
    try:
        return json.loads(err[a:b + 1])
    except (ValueError, json.JSONDecodeError):
        return None


def finish(picture: Path, base: Path, out: Path, total: float, voice_end: float,
           music: Path | None = None, music_vol: float = 0.16, duck: bool = True) -> None:
    extra, graph = _graph(total, voice_end, music, music_vol, duck)
    prefix = ["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(picture), "-i", str(base), *extra]
    m = _measure(prefix, graph)
    if m:
        norm = (f"loudnorm=I={LUFS}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
                f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    else:
        norm = f"loudnorm=I={LUFS}:TP={TP}:LRA={LRA}"
    run(prefix + [
        "-filter_complex", f"{graph};[mix]{norm},aresample=48000[out]",
        "-map", "0:v:0", "-map", "[out]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-t", f"{total:.3f}", "-movflags", "+faststart", str(out),
    ])


def loudness(video: Path) -> dict:
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    summary = err[err.rfind("Summary:"):]
    out = {}
    for line in summary.splitlines():
        line = line.strip()
        if line.startswith("I:"):
            out["integrated_lufs"] = float(line.split()[1])
        elif line.startswith("Peak:"):
            out["true_peak_dbtp"] = float(line.split()[1])
    return out
