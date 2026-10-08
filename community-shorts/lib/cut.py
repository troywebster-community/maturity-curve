"""Cut the raw file into a 1080x1920 base video.

Follows the video-use render rules: per-segment extract with grade and 30ms audio fades baked in,
then a lossless -c copy concat (no double encode).
"""

from __future__ import annotations

from pathlib import Path

from .common import FPS, H, W, run

GRADES = {
    "none": "",
    # from video-use grade.py
    "subtle": "eq=contrast=1.03:saturation=0.98",
    "neutral_punch": "eq=contrast=1.06:saturation=1.0,curves=master='0/0 0.25/0.23 0.75/0.77 1/1'",
    # bright, clean social look: lifted mids, a little more color. Safe on skin.
    "social_bright": "eq=contrast=1.07:brightness=0.015:saturation=1.08,curves=master='0/0 0.25/0.24 0.6/0.64 1/1'",
    # warm, soft. Pairs with Community's warm-white end card.
    "warm_soft": "eq=contrast=1.04:saturation=1.02,colorbalance=rs=0.02:bs=-0.02:rm=0.02:bm=-0.015",
}

TONEMAP = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
           "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def grade_filter(grade: str | None) -> str:
    if not grade:
        return ""
    return GRADES.get(grade, grade)  # unknown names are treated as a raw ffmpeg filter


def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def frame_filter(info: dict, framing: dict, zoom: float) -> tuple[str, bool]:
    """Return (filter, is_complex). Crop fills the 9:16 frame around focus_x/focus_y.
    Fit keeps the whole shot and puts it over a blurred copy of itself."""
    sw, sh = info["width"], info["height"]
    pre = TONEMAP + "," if info.get("hdr") else ""
    mode = framing.get("mode", "crop")
    fx = float(framing.get("focus_x", 0.5))
    fy = float(framing.get("focus_y", 0.4))
    if mode == "fit":
        fg_w = _even(W * zoom)
        fg_h = _even(sh * fg_w / sw)
        if fg_h > H:
            fg_h = H
            fg_w = _even(sw * H / sh)
        y = int((H - fg_h) * float(framing.get("fit_y", 0.38)))
        bg_scale = max(W / sw, H / sh)
        return (
            f"[0:v]{pre}split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={_even(sw * bg_scale)}:{_even(sh * bg_scale)},crop={W}:{H},"
            f"boxblur=40:2,eq=brightness=-0.12:saturation=0.8[bg];"
            f"[fgsrc]scale={fg_w}:{fg_h}[fg];"
            f"[bg][fg]overlay=(W-w)/2:{y},setsar=1",
            True,
        )
    s = max(W / sw, H / sh) * zoom
    cw, ch = _even(sw * s), _even(sh * s)
    x = min(max(fx * cw - W / 2, 0), cw - W)
    y = min(max(fy * ch - H / 2, 0), ch - H)
    return f"{pre}scale={cw}:{ch},crop={W}:{H}:{int(x)}:{int(y)},setsar=1", False


def extract(source: Path, info: dict, r: dict, framing: dict, grade: str, out: Path, draft: bool) -> None:
    dur = r["end"] - r["start"]
    fr = {**framing, **(r.get("framing") or {})}          # a range can reframe its own shot
    vf, complex_ = frame_filter(info, fr, float(fr.get("zoom", 1.0)) * float(r.get("zoom", 1.0)))
    g = grade_filter(r.get("grade", grade))
    if g:
        vf = f"{vf},{g}"
    vf = f"{vf},fps={FPS},format=yuv420p"
    af = f"afade=t=in:st=0:d=0.03,afade=t=out:st={max(0.0, dur - 0.03):.3f}:d=0.03"
    cmd = ["ffmpeg", "-y", "-ss", f"{r['start']:.3f}", "-i", str(source), "-t", f"{dur:.3f}"]
    if complex_:
        cmd += ["-filter_complex", vf + "[v]", "-map", "[v]", "-map", "0:a:0?"]
    else:
        cmd += ["-vf", vf, "-map", "0:v:0", "-map", "0:a:0?"]
    cmd += [
        "-af", af,
        "-c:v", "libx264", "-preset", "ultrafast" if draft else "fast", "-crf", "26" if draft else "18",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(out),
    ]
    run(cmd)


def build_base(source: Path, info: dict, ranges: list[dict], framing: dict, grade: str,
               work: Path, draft: bool = False) -> Path:
    seg_dir = work / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    for old in seg_dir.glob("seg_*.mp4"):
        old.unlink()
    paths = []
    for i, r in enumerate(ranges):
        p = seg_dir / f"seg_{i:02d}.mp4"
        print(f"  [{i:02d}] {r['start']:7.2f}-{r['end']:7.2f} ({r['end'] - r['start']:4.1f}s) "
              f"zoom {float(r.get('zoom', 1.0)):.2f}  {r.get('beat', '')}")
        extract(source, info, r, framing, grade, p, draft)
        paths.append(p)
    lst = work / "_concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))
    base = work / "base.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
         "-movflags", "+faststart", str(base)])
    lst.unlink()
    return base
