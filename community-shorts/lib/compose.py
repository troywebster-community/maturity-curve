"""Build the HyperFrames composition that dresses the cut video.

Layers (bottom to top):
  a-roll video (cut base.mp4, slow push-in per segment)
  legibility scrims
  intro: Community + customer eyebrow, hook headline
  persistent Community bug, speaker tag
  callouts: stat (count-up), chip (product differentiator), punch (big statement)
  captions (word-by-word highlight), always above callouts
  CTA end card (Community warm-white surface, one primary button)

Colors and type follow the Community brand system (warm white / cool near-black / one blue,
Inter only, sentence-case headlines, atmospheric radial gradients, blue-tinted shadows).
"""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from .common import ASSETS, FPS, H, W
from .timeline import chunk_captions, resolve_anchor

# Reels / Shorts / TikTok UI covers the top ~200px, the bottom ~380px and a right rail.
SAFE_TOP = 210
CAPTION_Y = 1190          # caption block center
CALLOUT_TOP = 360
CTA_OVERLAP = 0.45        # end card fades in over the last moments of the video


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def emphasize(text: str) -> str:
    """'Made **$1.2M** from text' -> marker highlight behind the starred words."""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    out = []
    for p in parts:
        if p.startswith("**") and p.endswith("**"):
            words = p[2:-2].split()
            out.append(" ".join(f'<span class="hw"><span class="em">{esc(w)}</span></span>' for w in words))
        else:
            out.append(" ".join(f'<span class="hw">{esc(w)}</span>' for w in p.split()))
    return " ".join(x for x in out if x)


def parse_number(value: str):
    """'$1.2M' -> ('$', 1.2, 'M', 1). Returns None when the value is not a plain number."""
    m = re.fullmatch(r"\s*([^\d\-]*?)(-?\d[\d,]*\.?\d*)(.*?)\s*", value)
    if not m:
        return None
    num = m.group(2).replace(",", "")
    decimals = len(num.split(".")[1]) if "." in num else 0
    return m.group(1), float(num), m.group(3), decimals, "," in m.group(2)


def wordmark(variant: str) -> str:
    """Use a real logo file if one is dropped in assets/brand, else a type-only wordmark."""
    for ext in ("svg", "png"):
        f = ASSETS / "brand" / f"logo-{variant}.{ext}"
        if f.exists():
            return f'<img class="logo-img" src="assets/brand/{f.name}" alt="Community" />'
    return '<span class="wm-dot"></span><span class="wm-text">community</span>'


CSS = r"""
@font-face { font-family: "Inter"; font-weight: 400; src: url("assets/fonts/inter-latin-400-normal.woff2") format("woff2"); }
@font-face { font-family: "Inter"; font-weight: 500; src: url("assets/fonts/inter-latin-500-normal.woff2") format("woff2"); }
@font-face { font-family: "Inter"; font-weight: 600; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); }
@font-face { font-family: "Inter"; font-weight: 700; src: url("assets/fonts/inter-latin-700-normal.woff2") format("woff2"); }
@font-face { font-family: "Inter"; font-weight: 800; src: url("assets/fonts/inter-latin-800-normal.woff2") format("woff2"); }
@font-face { font-family: "Inter"; font-weight: 900; src: url("assets/fonts/inter-latin-900-normal.woff2") format("woff2"); }
:root {
  --background: oklch(0.985 0.002 80);
  --foreground: oklch(0.16 0.03 260);
  --primary: oklch(0.42 0.16 250);
  --primary-glow: oklch(0.62 0.15 250);
  --secondary: oklch(0.96 0.005 80);
  --muted-foreground: oklch(0.50 0.02 260);
  --dark-surface: oklch(0.18 0.025 260);
  --warm-white: oklch(0.985 0.002 80);
  --shade: oklch(0.16 0.03 260 / 0.55);
}
html, body { margin: 0; background: var(--dark-surface); }
body { font-family: "Inter", sans-serif; color: var(--warm-white); -webkit-font-smoothing: antialiased; }
#root { position: relative; width: 100%; height: 100%; overflow: hidden; background: var(--dark-surface); }
#stage { position: absolute; inset: 0; transform-origin: 50% 42%; }
#aroll { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.scrim-top { position: absolute; left: 0; right: 0; top: 0; height: 760px;
  background: linear-gradient(180deg, oklch(0.16 0.03 260 / 0.62) 0%, oklch(0.16 0.03 260 / 0.28) 55%, transparent 100%); }
.scrim-bottom { position: absolute; left: 0; right: 0; bottom: 0; height: 980px;
  background: linear-gradient(0deg, oklch(0.16 0.03 260 / 0.55) 0%, oklch(0.16 0.03 260 / 0.25) 55%, transparent 100%); }

/* wordmark */
.wm { display: flex; align-items: center; gap: 14px; }
.wm-dot { width: 22px; height: 22px; border-radius: 50%; background: var(--warm-white);
  box-shadow: 0 0 0 6px oklch(0.985 0.002 80 / 0.18); }
.wm-text { font-weight: 800; letter-spacing: -0.035em; }
.logo-img { height: 100%; width: auto; display: block; }

/* intro */
#intro { position: absolute; inset: 0; }
.intro-inner { position: absolute; left: 72px; right: 72px; top: 300px; }
.pill { display: inline-flex; align-items: center; gap: 18px; height: 72px; padding: 0 30px 0 24px; border-radius: 999px;
  background: oklch(0.99 0.002 80 / 0.16); border: 1px solid oklch(1 0 0 / 0.28);
  box-shadow: inset 0 1px 0 oklch(1 0 0 / 0.35), 0 8px 30px oklch(0.45 0.12 245 / 0.20);
  backdrop-filter: blur(20px) saturate(1.4); font-size: 34px; }
.pill .wm-text { font-size: 38px; }
.pill .x { opacity: 0.7; font-weight: 500; }
.pill .co { font-weight: 600; }
.eyebrow { margin-top: 34px; font-size: 26px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; opacity: 0.86; }
.headline { margin-top: 18px; font-size: 92px; line-height: 1.04; font-weight: 800; letter-spacing: -0.035em;
  text-shadow: 0 6px 30px oklch(0.16 0.03 260 / 0.55); }
.hw { display: inline-block; }
.em { position: relative; display: inline-block; z-index: 0; margin: 0 12px; }
.em::before { content: ""; position: absolute; left: -8px; right: -8px; top: 12%; bottom: 4%; border-radius: 12px;
  background: var(--primary); z-index: -1; }

/* intro, card style: light gradient opener */
.intro-card-bg { position: absolute; inset: 0; background:
  radial-gradient(ellipse at 15% 25%, oklch(0.72 0.03 250 / 0.40) 0%, transparent 55%),
  radial-gradient(ellipse at 85% 75%, oklch(0.85 0.03 60 / 0.35) 0%, transparent 50%),
  var(--background); }
.intro-card-inner { position: absolute; left: 80px; right: 80px; top: 0; bottom: 0; display: flex; flex-direction: column;
  justify-content: center; color: var(--foreground); padding-bottom: 160px; }
.intro-card-inner .wm { height: 110px; }
.intro-card-inner .wm-dot { width: 46px; height: 46px; background: var(--foreground); box-shadow: 0 0 0 12px oklch(0.16 0.03 260 / 0.08); }
.intro-card-inner .wm-text { font-size: 112px; }
.intro-card-inner .ic-eyebrow { margin-top: 44px; font-size: 30px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted-foreground); }
.intro-card-inner .ic-title { margin-top: 14px; font-size: 72px; line-height: 1.05; font-weight: 800; letter-spacing: -0.035em; }

/* quote card: full screen, covers the video while the quote plays */
.quote-bg { position: absolute; inset: 0; background:
  radial-gradient(ellipse at 80% 20%, oklch(0.85 0.04 60 / 0.50) 0%, transparent 55%),
  radial-gradient(ellipse at 20% 80%, oklch(0.72 0.03 250 / 0.40) 0%, transparent 55%),
  var(--background); }
.quote-inner { position: absolute; left: 84px; right: 84px; top: 0; bottom: 0; display: flex; flex-direction: column;
  justify-content: center; color: var(--foreground); padding-bottom: 120px; }
.q-mark { font-size: 260px; line-height: 0.6; height: 130px; font-weight: 900; color: var(--primary); letter-spacing: -0.05em; }
.q-text { margin-top: 30px; font-size: 92px; line-height: 1.06; font-weight: 800; letter-spacing: -0.035em; }
.q-text .em::before { background: oklch(0.42 0.16 250 / 0.16); }
.q-text .em { color: var(--primary); }
.q-by { margin-top: 48px; display: flex; align-items: center; gap: 20px; font-size: 34px; font-weight: 600; }
.q-by .q-rule { width: 56px; height: 4px; border-radius: 4px; background: var(--primary); }
.q-by .q-role { font-weight: 500; color: var(--muted-foreground); }

/* persistent bug + speaker tag */
#bug { position: absolute; left: 60px; top: 222px; height: 68px; padding: 0 26px 0 22px; border-radius: 999px;
  display: flex; align-items: center; background: oklch(0.16 0.03 260 / 0.38); border: 1px solid oklch(1 0 0 / 0.18);
  backdrop-filter: blur(16px); font-size: 28px; }
#bug .wm-dot { width: 18px; height: 18px; box-shadow: 0 0 0 4px oklch(0.985 0.002 80 / 0.18); }
#bug .wm-text { font-size: 36px; }
.speaker { position: absolute; left: 60px; top: 310px; padding: 22px 30px; border-radius: 22px; max-width: 760px;
  background: oklch(0.99 0.002 80 / 0.88); color: var(--foreground);
  box-shadow: 0 16px 40px oklch(0.45 0.12 245 / 0.22); }
.speaker .name { font-size: 46px; font-weight: 700; letter-spacing: -0.02em; }
.speaker .role { margin-top: 4px; font-size: 31px; font-weight: 500; color: var(--muted-foreground); }
.speaker .bar { position: absolute; left: 0; top: 18px; bottom: 18px; width: 6px; border-radius: 0 6px 6px 0; background: var(--primary); }

/* callouts */
.callout { position: absolute; left: 60px; right: 60px; }
.stat { padding: 40px 46px 44px; border-radius: 36px; background: oklch(0.18 0.025 260 / 0.72);
  border: 1px solid oklch(1 0 0 / 0.14); backdrop-filter: blur(22px) saturate(1.3);
  box-shadow: 0 24px 60px oklch(0.45 0.12 245 / 0.28), inset 0 1px 0 oklch(1 0 0 / 0.16); overflow: hidden; }
.stat .glow { position: absolute; right: -160px; top: -200px; width: 560px; height: 560px; border-radius: 50%;
  background: radial-gradient(circle, oklch(0.62 0.15 250 / 0.55) 0%, transparent 65%); }
.stat .kicker { position: relative; font-size: 26px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; opacity: 0.75; }
.stat .value { position: relative; margin-top: 6px; font-size: 168px; line-height: 1; font-weight: 900; letter-spacing: -0.05em; }
.stat .label { position: relative; margin-top: 10px; font-size: 44px; line-height: 1.15; font-weight: 600; letter-spacing: -0.015em; }
.stat .rule { position: relative; margin-top: 26px; height: 6px; width: 100%; border-radius: 6px; background: oklch(1 0 0 / 0.14); }
.stat .rule-fill { position: absolute; left: 0; top: 0; bottom: 0; width: 100%; border-radius: 6px; background: var(--primary-glow); transform-origin: 0 50%; }
.chip { display: flex; align-items: center; gap: 22px; padding: 26px 36px 26px 26px; border-radius: 999px; width: fit-content; max-width: 900px;
  background: oklch(0.99 0.002 80 / 0.92); color: var(--foreground); box-shadow: 0 18px 44px oklch(0.45 0.12 245 / 0.25); }
.chip .tick { flex: none; width: 64px; height: 64px; border-radius: 50%; background: var(--primary); display: grid; place-items: center; }
.chip .tick svg { width: 36px; height: 36px; }
.chip .txt { font-size: 50px; line-height: 1.15; font-weight: 700; letter-spacing: -0.02em; }
.chip .sub { display: block; font-size: 32px; font-weight: 500; letter-spacing: 0; color: var(--muted-foreground); margin-top: 4px; }
.punch { text-align: left; }
.punch .p-text { font-size: 104px; line-height: 1.02; font-weight: 900; letter-spacing: -0.045em;
  text-shadow: 0 8px 36px oklch(0.16 0.03 260 / 0.6); }

/* captions */
#captions { position: absolute; left: 70px; right: 70px; top: 0; height: 100%; }
.cap { position: absolute; left: 0; right: 0; top: CAPTION_TOPpx; display: flex; flex-wrap: wrap; justify-content: center;
  align-items: center; gap: 6px 16px; opacity: 0; }
.cw { position: relative; display: inline-block; padding: 2px 12px 8px; font-size: 82px; line-height: 1.08; font-weight: 800;
  letter-spacing: -0.025em; color: var(--warm-white);
  text-shadow: 0 3px 0 oklch(0.16 0.03 260 / 0.55), 0 6px 26px oklch(0.16 0.03 260 / 0.6); z-index: 0; }
.cw .hl { position: absolute; inset: 4px 0 0; border-radius: 16px; background: var(--primary); opacity: 0; z-index: -1;
  box-shadow: 0 10px 30px oklch(0.42 0.16 250 / 0.45); }

/* CTA end card */
#cta { position: absolute; inset: 0; }
.cta-bg { position: absolute; inset: 0; background:
  radial-gradient(ellipse at 15% 22%, oklch(0.72 0.03 250 / 0.42) 0%, transparent 55%),
  radial-gradient(ellipse at 85% 78%, oklch(0.85 0.04 60 / 0.42) 0%, transparent 52%),
  var(--background); }
.beacon { position: absolute; border-radius: 50%; }
.b1 { width: 900px; height: 900px; left: -260px; top: 120px; background: radial-gradient(circle, oklch(0.72 0.03 250 / 0.40) 0%, transparent 62%); }
.b2 { width: 980px; height: 980px; right: -320px; bottom: 140px; background: radial-gradient(circle, oklch(0.85 0.04 60 / 0.42) 0%, transparent 62%); }
.cta-inner { position: absolute; left: 80px; right: 80px; top: 540px; color: var(--foreground); }
.cta-inner .wm { height: 96px; }
.cta-inner .wm-dot { width: 40px; height: 40px; background: var(--foreground); box-shadow: 0 0 0 10px oklch(0.16 0.03 260 / 0.08); }
.cta-inner .wm-text { font-size: 92px; }
.cta-eyebrow { margin-top: 84px; font-size: 26px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted-foreground); }
.cta-head { margin-top: 20px; font-size: 84px; line-height: 1.05; font-weight: 800; letter-spacing: -0.035em; }
.cta-sub { margin-top: 26px; font-size: 38px; line-height: 1.4; font-weight: 400; color: var(--muted-foreground); max-width: 860px; }
.cta-btn-wrap { position: relative; margin-top: 64px; width: fit-content; }
.cta-btn { position: relative; display: inline-flex; align-items: center; gap: 18px; height: 116px; padding: 0 56px; border-radius: 999px;
  background: var(--primary); color: var(--warm-white); font-size: 44px; font-weight: 700; letter-spacing: -0.01em;
  box-shadow: 0 18px 44px oklch(0.42 0.16 250 / 0.35); }
.cta-btn svg { width: 40px; height: 40px; }
.cta-ring { position: absolute; inset: 0; border-radius: 999px; border: 3px solid var(--primary); opacity: 0; }
.cta-url { margin-top: 34px; font-size: 34px; font-weight: 600; color: var(--foreground); letter-spacing: -0.01em; }
""".replace("CAPTION_TOP", str(CAPTION_Y - 60))

CHECK_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="oklch(0.985 0.002 80)" stroke-width="2.6" '
             'stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>')
ARROW_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
             'stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>')


def build(plan: dict, ranges: list[dict], owords: list[dict], base_duration: float, hf_dir: Path,
          base_video: Path) -> dict:
    hf_dir.mkdir(parents=True, exist_ok=True)
    (hf_dir / "assets").mkdir(exist_ok=True)
    for sub in ("fonts", "vendor", "brand"):
        dst = hf_dir / "assets" / sub
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ASSETS / sub, dst)
    dst_video = hf_dir / "assets" / "base.mp4"
    shutil.copyfile(base_video, dst_video)

    D = round(base_duration, 3)
    intro = plan.get("intro") or {}
    cta = plan.get("cta") or {}
    speaker = plan.get("speaker") or {}
    company = plan.get("company") or speaker.get("company") or ""
    cta_dur = float(cta.get("duration", 3.0))      # end card on screen, crossfade included
    total = round(D + cta_dur - CTA_OVERLAP, 3)
    layout = plan.get("layout") or {}
    callout_top = int(layout.get("callout_top", CALLOUT_TOP))
    intro_dur = float(intro.get("duration", 2.6))

    js: list[str] = []          # timeline statements
    els: list[str] = []         # overlay HTML
    warnings: list[str] = []

    # --- slow push-in per segment (makes jump cuts feel intentional) --------------------
    t = 0.0
    for i, r in enumerate(ranges):
        seg = r["end"] - r["start"]
        z0, z1 = (1.0, 1.045) if i % 2 == 0 else (1.045, 1.0)
        js.append(f'tl.fromTo("#stage", {{scale: {z0}}}, {{scale: {z1}, duration: {seg:.3f}, ease: "sine.inOut", '
                  f'immediateRender: {"true" if i == 0 else "false"}}}, {t:.3f});')
        t += seg

    # --- intro --------------------------------------------------------------------------
    eyebrow = intro.get("eyebrow", "Customer story")
    headline = intro.get("headline", "")
    if intro.get("style", "overlay") == "card":
        # Full-screen light gradient opener. The video (and its audio) already runs underneath,
        # so the first words land while Community is on screen.
        title = f'<div class="ic-title" id="ic-title">{emphasize(headline)}</div>' if headline else ""
        els.append(f'''
    <section id="intro" class="clip" data-start="0" data-duration="{intro_dur:.3f}" data-track-index="3">
      <div id="intro-fade" style="position:absolute;inset:0">
        <div class="intro-card-bg"></div>
        <div class="intro-card-inner">
          <div class="wm" id="ic-wm">{wordmark("dark")}</div>
          <div class="ic-eyebrow" id="ic-eyebrow">{esc(eyebrow)}{(" · " + esc(company)) if company else ""}</div>
          {title}
        </div>
      </div>
    </section>''')
        fade = min(0.25, intro_dur * 0.3)
        js += [
            'tl.fromTo("#ic-wm", {y: 30, opacity: 0}, {y: 0, opacity: 1, duration: 0.3, ease: "power3.out"}, 0);',
            'tl.fromTo("#ic-eyebrow", {opacity: 0}, {opacity: 1, duration: 0.25, ease: "power2.out"}, 0.12);',
            f'tl.to("#intro-fade", {{opacity: 0, scale: 1.04, duration: {fade:.2f}, ease: "power2.in"}}, {intro_dur - fade:.3f});',
        ]
        if headline:
            js.append('tl.fromTo("#ic-title .hw", {y: 30, opacity: 0}, {y: 0, opacity: 1, duration: 0.3, stagger: 0.03, ease: "power3.out"}, 0.15);')
    else:
        co_html = f'<span class="x">×</span><span class="co">{esc(company)}</span>' if company else ""
        els.append(f'''
    <section id="intro" class="clip" data-start="0" data-duration="{intro_dur:.3f}" data-track-index="3">
      <div class="intro-inner" id="intro-inner">
        <div class="pill wm" id="intro-pill">{wordmark("light")}{co_html}</div>
        <div class="eyebrow" id="intro-eyebrow">{esc(eyebrow)}</div>
        <div class="headline" id="intro-headline">{emphasize(headline)}</div>
      </div>
    </section>''')
        js += [
            'tl.fromTo("#intro-pill", {y: -30, opacity: 0}, {y: 0, opacity: 1, duration: 0.45, ease: "power3.out"}, 0.05);',
            'tl.fromTo("#intro-eyebrow", {opacity: 0}, {opacity: 0.86, duration: 0.4, ease: "power2.out"}, 0.25);',
            'tl.fromTo("#intro-headline .hw", {y: 60, opacity: 0}, {y: 0, opacity: 1, duration: 0.5, stagger: 0.06, ease: "power3.out"}, 0.3);',
            'tl.fromTo("#intro-headline .em", {scale: 0.9}, {scale: 1, duration: 0.35, ease: "power3.out"}, 0.75);',
            f'tl.to("#intro-inner", {{y: -40, opacity: 0, duration: 0.35, ease: "power2.in"}}, {intro_dur - 0.35:.3f});',
        ]

    # --- persistent bug -----------------------------------------------------------------
    bug_start = intro_dur - 0.1
    bug_dur = max(0.5, D - bug_start)
    els.append(f'''
    <div id="bug-clip" class="clip" data-start="{bug_start:.3f}" data-duration="{bug_dur:.3f}" data-track-index="4">
      <div id="bug" class="wm">{wordmark("light")}</div>
    </div>''')
    js.append(f'tl.fromTo("#bug", {{opacity: 0, x: -20}}, {{opacity: 1, x: 0, duration: 0.4, ease: "power3.out"}}, {bug_start + 0.05:.3f});')

    # --- speaker tag --------------------------------------------------------------------
    busy: list[tuple[float, float]] = []
    quote_windows: list[tuple[float, float]] = []
    if intro.get("style", "overlay") == "card":
        quote_windows.append((0.0, intro_dur))     # no captions over the light opener
    if speaker.get("name"):
        s_at = float(speaker.get("at", intro_dur + 0.2))
        s_dur = float(speaker.get("duration", 3.2))
        role = ", ".join(x for x in [speaker.get("title"), speaker.get("company", company)] if x)
        els.append(f'''
    <div id="spk-clip" class="clip" data-start="{s_at:.3f}" data-duration="{s_dur:.3f}" data-track-index="5">
      <div class="speaker" id="spk" style="top:{int(layout.get("speaker_top", 310))}px"><div class="bar"></div>
        <div class="name">{esc(speaker["name"])}</div>{f'<div class="role">{esc(role)}</div>' if role else ""}</div>
    </div>''')
        js += [
            f'tl.fromTo("#spk", {{x: -60, opacity: 0}}, {{x: 0, opacity: 1, duration: 0.45, ease: "power3.out"}}, {s_at:.3f});',
            f'tl.to("#spk", {{x: -40, opacity: 0, duration: 0.3, ease: "power2.in"}}, {s_at + s_dur - 0.3:.3f});',
        ]
        busy.append((s_at, s_at + s_dur))

    # --- callouts -----------------------------------------------------------------------
    for n, c in enumerate(plan.get("callouts") or []):
        cid = f"co{n}"
        at = float(c["at"]) if "at" in c else resolve_anchor(c["anchor"], owords)
        at = max(0.0, at + float(c.get("offset", -0.15)))
        dur = float(c.get("duration", 3.0))
        if at + dur > D:
            dur = max(1.2, D - at)
        top = callout_top
        if c.get("kind") != "quote" and any(a < at + dur and at < b for a, b in busy):
            top = callout_top + 190
            warnings.append(f"callout {n} overlaps the speaker tag; moved down")
        if at < intro_dur and c.get("kind") != "quote":
            warnings.append(f"callout {n} at {at:.2f}s starts during the intro card")
        kind = c.get("kind", "stat")
        if kind == "stat":
            num = parse_number(str(c.get("value", "")))
            kicker = f'<div class="kicker">{esc(c["kicker"])}</div>' if c.get("kicker") else ""
            inner = f'''<div class="stat" id="{cid}-card"><div class="glow"></div>{kicker}
          <div class="value" id="{cid}-val">{esc(c.get("value", ""))}</div>
          <div class="label">{esc(c.get("label", ""))}</div>
          <div class="rule"><div class="rule-fill" id="{cid}-fill"></div></div></div>'''
            js += [
                f'tl.fromTo("#{cid}-card", {{y: 50, opacity: 0, scale: 0.96}}, {{y: 0, opacity: 1, scale: 1, duration: 0.45, ease: "power3.out"}}, {at:.3f});',
                f'tl.fromTo("#{cid}-fill", {{scaleX: 0}}, {{scaleX: 1, duration: {min(1.4, dur - 0.6):.3f}, ease: "power2.out"}}, {at + 0.25:.3f});',
            ]
            if num:
                pre, val, suf, dec, commas = num
                fmt = f"let s=o.v.toFixed({dec});"
                if commas:
                    fmt += f's=Number(s).toLocaleString("en-US",{{minimumFractionDigits:{dec}}});'
                count_dur = max(0.4, min(1.1, dur - 0.8))
                js.append(
                    f'(function(){{const o={{v:0}};const el=document.getElementById("{cid}-val");'
                    f'tl.fromTo(o,{{v:0}},{{v:{val},duration:{count_dur:.3f},ease:"power2.out",immediateRender:false,'
                    f'onUpdate:()=>{{{fmt}el.textContent={json.dumps(pre)}+s+{json.dumps(suf)};}}}},{at + 0.1:.3f});}})();'
                )
        elif kind == "chip":
            sub = f'<span class="sub">{esc(c["sub"])}</span>' if c.get("sub") else ""
            inner = f'''<div class="chip" id="{cid}-card"><div class="tick">{CHECK_SVG}</div>
          <div class="txt">{esc(c.get("text", ""))}{sub}</div></div>'''
            js += [
                f'tl.fromTo("#{cid}-card", {{x: -80, opacity: 0}}, {{x: 0, opacity: 1, duration: 0.45, ease: "power3.out"}}, {at:.3f});',
                f'tl.fromTo("#{cid}-card .tick", {{scale: 0.4}}, {{scale: 1, duration: 0.35, ease: "back.out(1.6)"}}, {at + 0.12:.3f});',
            ]
        elif kind == "punch":
            inner = f'<div class="punch" id="{cid}-card"><div class="p-text">{emphasize(c.get("text", ""))}</div></div>'
            js.append(f'tl.fromTo("#{cid}-card .hw", {{y: 50, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.4, stagger: 0.07, ease: "power3.out"}}, {at:.3f});')
        elif kind == "quote":
            who = c.get("by") or speaker.get("name", "")
            role = c.get("role", "")
            by = (f'<div class="q-by" id="{cid}-by"><span class="q-rule"></span><span>{esc(who)}</span>'
                  f'{f"<span class=q-role>{esc(role)}</span>" if role else ""}</div>') if who else ""
            els.append(f'''
    <section id="{cid}" class="clip" data-start="{at:.3f}" data-duration="{dur:.3f}" data-track-index="7">
      <div id="{cid}-card" style="position:absolute;inset:0">
        <div class="quote-bg"></div>
        <div class="quote-inner"><div class="q-mark">&ldquo;</div>
          <div class="q-text" id="{cid}-text">{emphasize(c.get("text", ""))}</div>{by}</div>
      </div>
    </section>''')
            js += [
                f'tl.fromTo("#{cid}-card", {{opacity: 0}}, {{opacity: 1, duration: 0.18, ease: "power2.out"}}, {at:.3f});',
                f'tl.fromTo("#{cid}-text .hw", {{y: 40, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.35, stagger: 0.05, ease: "power3.out"}}, {at + 0.08:.3f});',
                f'tl.to("#{cid}-card", {{opacity: 0, duration: 0.2, ease: "power2.in"}}, {at + dur - 0.2:.3f});',
            ]
            if who:
                js.append(f'tl.fromTo("#{cid}-by", {{opacity: 0}}, {{opacity: 1, duration: 0.3}}, {at + 0.4:.3f});')
            quote_windows.append((at, at + dur))
            continue
        else:
            raise ValueError(f"unknown callout kind '{kind}' (use stat, chip, punch or quote)")
        js.append(f'tl.to("#{cid}-card", {{opacity: 0, y: -24, duration: 0.3, ease: "power2.in"}}, {at + dur - 0.3:.3f});')
        els.append(f'''
    <div id="{cid}" class="clip callout" style="top:{top}px" data-start="{at:.3f}" data-duration="{dur:.3f}" data-track-index="6">
      {inner}
    </div>''')
        busy.append((at, at + dur))

    # --- captions -----------------------------------------------------------------------
    cap_cfg = plan.get("captions") or {}
    if cap_cfg.get("enabled", True):
        def under_quote(t: float) -> bool:
            return any(a - 0.05 <= t < b for a, b in quote_windows)
        kept = [w for w in owords if not under_quote(w["start"])]
        pages = chunk_captions(kept, int(cap_cfg.get("max_words", 3)), int(cap_cfg.get("max_chars", 18)))
        cap_html = []
        for p, page in enumerate(pages):
            start = page[0]["start"]
            nxt = pages[p + 1][0]["start"] if p + 1 < len(pages) else D
            end = min(nxt, page[-1]["end"] + 0.6, D)
            end = min([end] + [a for a, b in quote_windows if a > start])
            words_html = "".join(f'<span class="cw" id="w{p}_{k}"><span class="hl"></span>{esc(w["text"])}</span>'
                                 for k, w in enumerate(page))
            cap_html.append(f'<div class="cap" id="cap{p}">{words_html}</div>')
            js.append(f'tl.fromTo("#cap{p}", {{opacity: 0, y: 16, scale: 0.94}}, {{opacity: 1, y: 0, scale: 1, duration: 0.12, ease: "power3.out", immediateRender: false}}, {start:.3f});')
            js.append(f'tl.set("#cap{p}", {{opacity: 0}}, {end:.3f});')
            for k, w in enumerate(page):
                w_end = page[k + 1]["start"] if k + 1 < len(page) else end
                js.append(f'tl.set("#w{p}_{k} .hl", {{opacity: 1}}, {w["start"]:.3f}); tl.set("#w{p}_{k} .hl", {{opacity: 0}}, {w_end:.3f});')
        els.append(f'''
    <div id="captions" class="clip" data-start="0" data-duration="{D:.3f}" data-track-index="8">
      {"".join(cap_html)}
    </div>''')

    # --- CTA end card -------------------------------------------------------------------
    c_start = max(0.0, D - CTA_OVERLAP)
    c_dur = round(total - c_start, 3)
    btn = cta.get("button", "Book a demo")
    els.append(f'''
    <section id="cta" class="clip" data-start="{c_start:.3f}" data-duration="{c_dur:.3f}" data-track-index="10">
      <div class="cta-bg" id="cta-bg"><div class="beacon b1" id="b1"></div><div class="beacon b2" id="b2"></div></div>
      <div class="cta-inner">
        <div class="wm" id="cta-wm">{wordmark("dark")}</div>
        <div class="cta-eyebrow" id="cta-eyebrow">{esc(cta.get("eyebrow", "Text-first marketing"))}</div>
        <div class="cta-head" id="cta-head">{emphasize(cta.get("headline", "Own the line to your audience"))}</div>
        {f'<div class="cta-sub" id="cta-sub">{esc(cta["subline"])}</div>' if cta.get("subline") else ""}
        <div class="cta-btn-wrap"><div class="cta-ring" id="cta-ring"></div>
          <div class="cta-btn" id="cta-btn">{esc(btn)}{ARROW_SVG}</div></div>
        <div class="cta-url" id="cta-url">{esc(cta.get("url", "community.com"))}</div>
      </div>
    </section>''')
    js += [
        f'tl.fromTo("#cta-bg", {{opacity: 0}}, {{opacity: 1, duration: {CTA_OVERLAP:.2f}, ease: "power2.inOut"}}, {c_start:.3f});',
        f'tl.fromTo("#b1", {{x: 0, y: 0, scale: 1}}, {{x: 40, y: -30, scale: 1.06, duration: {c_dur:.3f}, ease: "sine.inOut"}}, {c_start:.3f});',
        f'tl.fromTo("#b2", {{x: 0, y: 0, scale: 1}}, {{x: -30, y: 20, scale: 0.97, duration: {c_dur:.3f}, ease: "sine.inOut"}}, {c_start:.3f});',
        f'tl.fromTo("#cta-wm", {{y: 40, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.5, ease: "power3.out"}}, {D - 0.1:.3f});',
        f'tl.fromTo("#cta-eyebrow", {{opacity: 0}}, {{opacity: 1, duration: 0.4}}, {D + 0.2:.3f});',
        f'tl.fromTo("#cta-head .hw", {{y: 50, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.45, stagger: 0.05, ease: "power3.out"}}, {D + 0.25:.3f});',
        f'tl.fromTo("#cta-btn", {{y: 30, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.45, ease: "power3.out"}}, {D + 0.85:.3f});',
        f'tl.fromTo("#cta-url", {{opacity: 0}}, {{opacity: 1, duration: 0.4}}, {D + 1.1:.3f});',
        f'tl.fromTo("#cta-ring", {{opacity: 0.8, scale: 1}}, {{opacity: 0, scale: 1.25, duration: 0.9, ease: "power2.out", immediateRender: false}}, {D + 1.5:.3f});',
    ]
    if cta.get("subline"):
        js.append(f'tl.fromTo("#cta-sub", {{opacity: 0, y: 20}}, {{opacity: 1, y: 0, duration: 0.45, ease: "power3.out"}}, {D + 0.55:.3f});')

    page = f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>{esc(plan.get("name", "community-short"))}</title>
    <script src="assets/vendor/gsap.min.js"></script>
    <style>{CSS}</style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-width="{W}" data-height="{H}" data-duration="{total:.3f}">
      <div id="stage">
        <video id="aroll" class="clip" src="assets/base.mp4" muted playsinline data-start="0" data-duration="{D:.3f}" data-track-index="0"></video>
      </div>
      <div class="scrim-top"></div>
      <div class="scrim-bottom"></div>
      {"".join(els)}
    </div>
    <script>
      (async () => {{
        const need = ["400 40px Inter", "600 40px Inter", "700 40px Inter", "800 40px Inter", "900 40px Inter"];
        await Promise.all(need.map((f) => document.fonts.load(f)));
        for (const f of need) {{ if (!document.fonts.check(f)) throw new Error("font failed to load: " + f); }}
        const tl = gsap.timeline({{ paused: true }});
        {chr(10).join("        " + s for s in js).lstrip()}
        window.__timelines["main"] = tl;
      }})();
    </script>
  </body>
</html>
'''
    (hf_dir / "index.html").write_text(page)
    (hf_dir / "hyperframes.json").write_text(json.dumps({"name": plan.get("name", "community-short")}, indent=2))
    return {"total": total, "base": D, "warnings": warnings, "fps": FPS}
