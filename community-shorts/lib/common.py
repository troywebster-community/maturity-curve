"""Shared helpers: paths, .env loading, ffprobe, subprocess."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # community-shorts/
ASSETS = ROOT / "assets"
PROJECTS = ROOT / "projects"

# Output canvas: 9:16 vertical for Reels / Shorts / TikTok
W, H, FPS = 1080, 1920, 30


def load_env() -> dict[str, str]:
    """Read KEY=VALUE pairs from community-shorts/.env, then the repo root .env."""
    out: dict[str, str] = {}
    for candidate in (ROOT / ".env", ROOT.parent / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return out


def elevenlabs_key() -> str:
    """ELEVENLABS_API_KEY wins. A bare API_KEY (how the key was first handed over) also works."""
    env = load_env()
    for name in ("ELEVENLABS_API_KEY", "XI_API_KEY", "API_KEY"):
        v = os.environ.get(name) or env.get(name)
        if v:
            return v
    sys.exit("No ElevenLabs key found. Put ELEVENLABS_API_KEY=... in community-shorts/.env")


def run(cmd: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
        raise RuntimeError(f"command failed: {' '.join(map(str, cmd[:8]))} ...\n{tail}")
    if not quiet and proc.stdout:
        print(proc.stdout)
    return proc


def probe(video: Path) -> dict:
    """Display width/height (rotation applied), duration, fps, HDR flag, audio presence."""
    out = run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video),
    ]).stdout
    data = json.loads(out)
    vstreams = [s for s in data["streams"] if s.get("codec_type") == "video"]
    if not vstreams:
        raise RuntimeError(f"no video stream in {video}")
    v = vstreams[0]
    w, h = int(v["width"]), int(v["height"])
    rotation = 0
    for sd in v.get("side_data_list") or []:
        if sd.get("rotation") is not None:
            rotation = int(round(float(sd["rotation"])))
    if rotation % 180 != 0:
        w, h = h, w
    num, _, den = (v.get("avg_frame_rate") or "30/1").partition("/")
    try:
        fps = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        fps = 30.0
    return {
        "width": w,
        "height": h,
        "duration": float(data["format"].get("duration") or v.get("duration") or 0),
        "fps": round(fps, 3),
        "hdr": v.get("color_transfer") in {"smpte2084", "arib-std-b67"},
        "has_audio": any(s.get("codec_type") == "audio" for s in data["streams"]),
        "orientation": "portrait" if h > w else ("square" if h == w else "landscape"),
    }


def project_dir(name: str) -> Path:
    d = PROJECTS / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve(path: str | Path, base: Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    for cand in (base / p, ROOT / p, Path.cwd() / p):
        if cand.exists():
            return cand.resolve()
    return (base / p).resolve()
