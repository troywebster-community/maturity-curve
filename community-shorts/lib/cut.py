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


IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def probe_any(path: Path) -> dict:
    """probe() for videos, plus still images (shown as clips of any length, silent)."""
    if path.suffix.lower() in IMAGE_EXT:
        from PIL import Image
        w, h = Image.open(path).size
        return {"width": w, "height": h, "duration": 3600.0, "fps": FPS, "hdr": False,
                "has_audio": False, "orientation": "portrait" if h > w else "landscape", "image": True}
    from .common import probe
    return {**probe(path), "image": False}


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
    if framing.get("box"):
        # Use only part of the frame, e.g. the video inside a YouTube page screen capture.
        x0, y0, x1, y1 = (float(v) for v in framing["box"])
        cw, ch = _even((x1 - x0) * sw), _even((y1 - y0) * sh)
        pre += f"crop={cw}:{ch}:{int(x0 * sw)}:{int(y0 * sh)},"
        sw, sh = cw, ch
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
    src_dur = r["end"] - r["start"]
    speed = float(r.get("speed", 1.0))          # >1 plays faster (cut to the beat)
    dur = src_dur / speed
    fr = {**framing, **(r.get("framing") or {})}          # a range can reframe its own shot
    vf, complex_ = frame_filter(info, fr, float(fr.get("zoom", 1.0)) * float(r.get("zoom", 1.0)))
    g = grade_filter(r.get("grade", grade))
    if g:
        vf = f"{vf},{g}"
    # hold_from: freeze the picture from this source time on (the shot ends before the words do).
    v_len = dur
    if "hold_from" in r:
        v_len = max(0.1, min(dur, float(r["hold_from"]) - float(r.get("video_from", r["start"]))))
        vf = f"{vf},tpad=stop_mode=clone:stop_duration={dur - v_len + 0.1:.3f}"
    if speed != 1.0:
        vf = f"{vf},setpts=PTS/{speed:.4f}"
    vf = f"{vf},fps={FPS},format=yuv420p"
    tempo = ""
    s_left = speed
    while s_left > 2.0:                          # atempo takes 0.5-2.0 per stage
        tempo += "atempo=2.0,"
        s_left /= 2.0
    if s_left != 1.0:
        tempo += f"atempo={s_left:.4f},"
    af = (f"{tempo}volume={float(r.get('volume', 1.0)):.3f},"
          f"afade=t=in:st=0:d=0.03,afade=t=out:st={max(0.0, dur - 0.03):.3f}:d=0.03")
    # video_from: keep this range's audio but show picture from another moment (b-roll).
    v_at = float(r.get("video_from", r["start"]))
    if info.get("image"):
        cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(source)]
    else:
        cmd = ["ffmpeg", "-y", "-ss", f"{v_at:.3f}", "-t", f"{v_len * speed:.3f}", "-i", str(source)]
    audio_in = "0"
    if info.get("image") or not info.get("has_audio", True):
        # silent source: a quiet track keeps every segment concat-compatible
        cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        audio_in = "1"
    elif "video_from" in r or "hold_from" in r:
        cmd += ["-ss", f"{r['start']:.3f}", "-t", f"{src_dur:.3f}", "-i", str(source)]
        audio_in = "1"
    if complex_:
        cmd += ["-filter_complex", vf + "[v]", "-map", "[v]", "-map", f"{audio_in}:a:0?"]
    else:
        cmd += ["-vf", vf, "-map", "0:v:0", "-map", f"{audio_in}:a:0?"]
    cmd += ["-t", f"{dur:.3f}"]
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
        extract(Path(r.get("_src", source)), r.get("_info", info), r, framing, grade, p, draft)
        paths.append(p)
    lst = work / "_concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))
    base = work / "base.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
         "-movflags", "+faststart", str(base)])
    lst.unlink()
    return base
