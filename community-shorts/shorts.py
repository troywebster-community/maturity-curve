#!/usr/bin/env python3
"""Community Shorts: raw testimonial -> 9:16 branded short (Reels / Shorts / TikTok).

  python shorts.py transcribe raw/acme.mp4 --name acme     # ElevenLabs Scribe + framing contact sheet
  python shorts.py check projects/acme/plan.json           # validate the plan, print the timeline
  python shorts.py render projects/acme/plan.json          # cut + HyperFrames graphics + mix -> mp4
  python shorts.py render projects/acme/plan.json --draft  # fast low-quality pass
  python shorts.py qc projects/acme/acme.mp4               # frames + loudness for review

The plan (plan.json) is where the editing decisions live. Claude writes it from the transcript and
your brief (see .claude/skills/community-short/SKILL.md), or you can write it by hand.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import compose, cut, mix  # noqa: E402
from lib.common import FPS, H, PROJECTS, ROOT, W, probe, project_dir, resolve, run  # noqa: E402
from lib.timeline import Envelope, output_words, resolve_anchor, snap_ranges  # noqa: E402

HYPERFRAMES = "hyperframes@0.8.142"
TARGET = (34.0, 48.0)   # final runtime window in seconds, CTA included


def contact_sheet(video: Path, out: Path, times: list[float], label: bool = True, width: int = 360) -> None:
    """A row of frames at the given times, for checking framing and graphics."""
    tmp = out.parent / "_frames"
    tmp.mkdir(exist_ok=True)
    frames = []
    for i, t in enumerate(times):
        f = tmp / f"f{i:02d}.jpg"
        vf = f"scale={width}:-2"
        if label:
            vf += f",drawtext=text='{t:.1f}s':x=12:y=12:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=6"
        run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", vf, "-q:v", "3", str(f)])
        frames.append(f)
    cols = min(len(frames), 6)
    inputs = sum([["-i", str(f)] for f in frames], [])
    # xstack layout: x = col*w0, y = row*h0
    layout = "|".join(f"{'+'.join(['w0'] * (i % cols)) or '0'}_{'+'.join(['h0'] * (i // cols)) or '0'}"
                      for i in range(len(frames)))
    if len(frames) == 1:
        shutil.copyfile(frames[0], out)
    else:
        run(["ffmpeg", "-y", *inputs, "-filter_complex",
             f"xstack=inputs={len(frames)}:layout={layout}:fill=black", "-q:v", "3", str(out)])
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------- transcribe

def cmd_transcribe(a) -> None:
    from lib.transcribe import transcribe
    video = Path(a.video).resolve()
    if not video.exists():
        sys.exit(f"not found: {video}")
    name = a.name or video.stem.lower().replace(" ", "-")
    proj = project_dir(name)
    info = probe(video)
    (proj / "probe.json").write_text(json.dumps({**info, "source": str(video)}, indent=2))
    print(f"source: {video.name}  {info['width']}x{info['height']} {info['orientation']}  "
          f"{info['duration']:.1f}s  {info['fps']}fps{'  HDR' if info['hdr'] else ''}")
    words = transcribe(video, proj, info, a.speakers, a.language, a.model, a.force,
                       Path(a.transcript).resolve() if a.transcript else None, a.engine)
    n = 6
    times = [info["duration"] * (i + 0.5) / n for i in range(n)]
    contact_sheet(video, proj / "source_frames.jpg", times, width=480 if info["orientation"] == "landscape" else 270)
    print(f"words: {len(words)}")
    print(f"project: {proj.relative_to(ROOT)}/")
    print("  transcript.md       phrase view with [start-end] times (read this to pick cuts)")
    print("  words.json          word-level timings")
    print("  source_frames.jpg   6 frames, to judge where the speaker sits (focus_x)")
    if not (proj / "plan.json").exists():
        plan = json.loads((ROOT / "examples" / "plan.example.json").read_text())
        plan["name"] = name
        plan["source"] = str(video)
        (proj / "plan.json").write_text(json.dumps(plan, indent=2))
        print("  plan.json           starter plan, edit it next")


# ---------------------------------------------------------------------------- plan loading

def load(plan_path: Path):
    plan = json.loads(plan_path.read_text())
    proj = plan_path.parent
    source = resolve(plan["source"], proj)
    if not source.exists():
        sys.exit(f"source video not found: {source}")
    info = probe(source)
    words_path = proj / "words.json"
    if not words_path.exists():
        sys.exit(f"{words_path} missing. Run: python shorts.py transcribe {source}")
    words = json.loads(words_path.read_text())
    ranges = snap_ranges(plan["ranges"], words, info["duration"], Envelope(source))
    # Alternate a punch-in on consecutive cuts so jump cuts read as intentional.
    if plan.get("auto_punch", True):
        for i, r in enumerate(ranges):
            r.setdefault("zoom", 1.0 if i % 2 == 0 else float(plan.get("punch_zoom", 1.12)))
    owords = output_words(ranges, words, plan.get("corrections") or {})
    return plan, proj, source, info, ranges, owords


def describe(plan, ranges, owords) -> float:
    base = sum(r["end"] - r["start"] for r in ranges)
    cta = float((plan.get("cta") or {}).get("duration", 3.0)) - compose.CTA_OVERLAP
    print(f"\n{'#':>2} {'src in':>8} {'src out':>8} {'len':>5} {'out at':>7}  beat / words")
    t = 0.0
    for i, r in enumerate(ranges):
        seg_words = " ".join(w["text"] for w in owords if w["segment"] == i)
        print(f"{i:>2} {r['start']:8.2f} {r['end']:8.2f} {r['end'] - r['start']:5.1f} {t:7.2f}  "
              f"[{r.get('beat', '')}] {seg_words[:90]}{'...' if len(seg_words) > 90 else ''}")
        t += r["end"] - r["start"]
    print(f"\nspeech {base:.1f}s + end card {cta + compose.CTA_OVERLAP:.1f}s "
          f"(overlapping the last {compose.CTA_OVERLAP}s of speech) = {base + cta:.1f}s total")
    for n, c in enumerate(plan.get("callouts") or []):
        at = float(c["at"]) if "at" in c else resolve_anchor(c["anchor"], owords)
        print(f"  callout {n} {c.get('kind', 'stat'):5} at {at:5.2f}s  "
              f"{c.get('value', '')} {c.get('label', '') or c.get('text', '')}")
    total = base + cta
    if not TARGET[0] <= total <= TARGET[1]:
        print(f"  ! total {total:.1f}s is outside the {TARGET[0]:.0f}-{TARGET[1]:.0f}s target")
    return total


def cmd_check(a) -> None:
    plan, proj, source, info, ranges, owords = load(Path(a.plan).resolve())
    describe(plan, ranges, owords)


# ---------------------------------------------------------------------------- render

def cmd_render(a) -> None:
    t0 = time.time()
    plan_path = Path(a.plan).resolve()
    plan, proj, source, info, ranges, owords = load(plan_path)
    name = plan.get("name") or proj.name
    describe(plan, ranges, owords)
    work = proj / ("work_draft" if a.draft else "work")
    work.mkdir(exist_ok=True)

    print("\n1/4 cutting 9:16 base video")
    framing = plan.get("framing") or {}
    if "mode" not in framing:
        framing["mode"] = "crop"
    base = cut.build_base(source, info, ranges, framing, plan.get("grade", "social_bright"), work, a.draft)
    D = probe(base)["duration"]
    (work / "ranges.snapped.json").write_text(json.dumps(ranges, indent=2))
    (work / "captions.words.json").write_text(json.dumps(owords, indent=0))

    print("2/4 building HyperFrames composition")
    hf = work / "hf"
    meta = compose.build(plan, ranges, owords, D, hf, base)
    for w in meta["warnings"]:
        print(f"  ! {w}")
    if a.no_render:
        print(f"composition written to {hf}/index.html (not rendered)")
        return

    print("3/4 rendering graphics with HyperFrames")
    picture = work / "picture.mp4"
    cmd = ["npx", "--yes", HYPERFRAMES, "render", str(hf), "-o", str(picture), "--fps", str(FPS),
           "--quality", "draft" if a.draft else "delivery", "--strict"]
    if a.workers:
        cmd += ["--workers", str(a.workers)]
    proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    if proc.returncode != 0 or not picture.exists():
        print(proc.stdout[-3000:], proc.stderr[-3000:])
        sys.exit("HyperFrames render failed")
    summary = [ln for ln in proc.stdout.splitlines() if ln.strip()][-6:]
    for ln in summary:
        print(f"  {ln.strip()}")

    print("4/4 mixing audio and finishing")
    music = None
    mcfg = plan.get("music") or {}
    if mcfg.get("file"):
        music = resolve(mcfg["file"], proj)
        if not music.exists():
            sys.exit(f"music file not found: {music}")
    out = proj / (f"{name}_draft.mp4" if a.draft else f"{name}.mp4")
    mix.finish(picture, base, out, meta["total"], D, music, float(mcfg.get("volume", 0.16)))

    report = qc(out, ranges, plan)
    print(f"\ndone in {time.time() - t0:.0f}s -> {out.relative_to(ROOT)}")
    print(json.dumps(report, indent=2))


def qc(video: Path, ranges: list[dict] | None = None, plan: dict | None = None) -> dict:
    info = probe(video)
    total = info["duration"]
    times = [0.4, 1.6]
    if ranges:
        t = 0.0
        for r in ranges[:-1]:
            t += r["end"] - r["start"]
            times.append(t + 0.25)
    cta = float(((plan or {}).get("cta") or {}).get("duration", 3.0))
    times += [total - cta + 0.9, total - 0.3]
    times = sorted({round(min(max(x, 0.0), total - 0.05), 2) for x in times})[:12]
    sheet = video.with_name(video.stem + "_qc.jpg")
    contact_sheet(video, sheet, times, width=270)
    loud = mix.loudness(video)
    ok = (info["width"], info["height"]) == (W, H)
    return {
        "file": str(video.relative_to(ROOT)) if video.is_relative_to(ROOT) else str(video),
        "resolution": f"{info['width']}x{info['height']}",
        "vertical_9x16": ok,
        "duration_s": round(total, 2),
        "fps": info["fps"],
        **loud,
        "qc_sheet": str(sheet.relative_to(ROOT)) if sheet.is_relative_to(ROOT) else str(sheet),
        "size_mb": round(video.stat().st_size / 1e6, 1),
    }


def cmd_qc(a) -> None:
    print(json.dumps(qc(Path(a.video).resolve()), indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transcribe", help="transcribe a raw video and start a project")
    t.add_argument("video")
    t.add_argument("--name")
    t.add_argument("--speakers", type=int, help="number of speakers, if known")
    t.add_argument("--language", help="ISO code, e.g. en. Omit to auto-detect")
    t.add_argument("--model", default="scribe_v1")
    t.add_argument("--force", action="store_true", help="re-transcribe even if cached")
    t.add_argument("--engine", choices=["elevenlabs", "local"], default="elevenlabs",
                   help="local = offline Parakeet model (see lib/local_asr.py) when ElevenLabs is unreachable")
    t.add_argument("--transcript", help="import an existing ElevenLabs Scribe JSON instead of calling the API")
    t.set_defaults(fn=cmd_transcribe)

    c = sub.add_parser("check", help="validate a plan and print the timeline")
    c.add_argument("plan")
    c.set_defaults(fn=cmd_check)

    r = sub.add_parser("render", help="render a plan to mp4")
    r.add_argument("plan")
    r.add_argument("--draft", action="store_true", help="fast, lower quality")
    r.add_argument("--no-render", action="store_true", help="build the composition only")
    r.add_argument("--workers", help="HyperFrames render workers (default auto)")
    r.set_defaults(fn=cmd_render)

    q = sub.add_parser("qc", help="frames + loudness report for a finished video")
    q.add_argument("video")
    q.set_defaults(fn=cmd_qc)

    a = ap.parse_args()
    PROJECTS.mkdir(exist_ok=True)
    a.fn(a)


if __name__ == "__main__":
    main()
