# Community Shorts

Turns a raw customer testimonial or case study video into a ~40 second vertical ad for Instagram
Reels and YouTube Shorts (1080x1920, 30fps, -14 LUFS).

Every short:

- opens with a Community intro card over the customer's best line (the hook)
- cuts the talk down to the strongest beats: problem, how they use Community, proof, closer
- shows word-by-word captions sized for phones and kept clear of the Reels/Shorts UI
- adds a speaker name tag, product differentiator chips, and stat cards that count up
- ends on a Community end card with one call to action
- follows the Community brand system (warm white, near-black, one blue, Inter)

## How you use it

1. Drop the raw file in `community-shorts/raw/`.
2. Open Claude Code in this repo and say something like:

   > Make a short from raw/acme-interview.mp4. Lead with the revenue number, show that fans text
   > back and that they own the list, end on "Book a demo". Speaker is Jane Doe, VP Marketing at Acme.

3. Claude follows `.claude/skills/community-short/SKILL.md`: transcribes, picks the cuts, writes
   `projects/<name>/plan.json`, renders a draft, checks it, renders the final, and hands back
   `projects/<name>/<name>.mp4`.
4. Ask for changes in plain English ("drop the second chip", "start on the sold-out line",
   "make it 30 seconds"). Claude edits the plan and re-renders. Transcripts are cached.

## Setup (once per machine)

Needs Python 3.10+, Node.js 22+, and ffmpeg.

```bash
cd community-shorts
pip install -r requirements.txt
cp .env.example .env            # then paste your key: ELEVENLABS_API_KEY=...
npx --yes hyperframes@0.8.142 browser ensure   # headless Chrome for rendering
```

## Commands (what Claude runs)

```bash
python shorts.py transcribe raw/acme.mp4 --name acme   # ElevenLabs Scribe, cached
python shorts.py check projects/acme/plan.json         # print cuts, kept words, runtime, callouts
python shorts.py render projects/acme/plan.json --draft
python shorts.py render projects/acme/plan.json        # final: projects/acme/acme.mp4
python shorts.py qc projects/acme/acme.mp4             # frames + loudness report
```

`examples/plan.example.json` shows every plan field. The skill file explains each one.

## How it is built

| Step | Tool | Where it came from |
|---|---|---|
| Transcribe (word timestamps, speakers) | ElevenLabs Scribe | `browser-use/video-use` helpers |
| Cut, reframe to 9:16, grade, audio fades, concat | ffmpeg | `video-use` render rules |
| Intro, captions, chips, stats, end card | HyperFrames (HTML + GSAP) | `heygen-com/hyperframes` |
| Music ducking, two-pass loudnorm | ffmpeg | `video-use` audio rules |

The original skills are vendored in `.claude/skills/` (`video-use`, `hyperframes`,
`hyperframes-core`, `hyperframes-cli`, `talking-head-recut`) with their licenses.

```
community-shorts/
  shorts.py            CLI
  lib/                 transcribe, timeline (word snapping, anchors), cut, compose (HyperFrames), mix
  assets/              Inter fonts, GSAP, brand/ (drop logo-light.svg / logo-dark.svg here for the real logo)
  brand/messaging.md   pillars, approved differentiator chips, proof rules, end card options
  examples/            plan.example.json
  raw/                 your source videos (git-ignored)
  projects/<name>/     transcript, plan, renders (git-ignored)
```

## Notes

- The wordmark is type-only until real logo files are added to `assets/brand/`
  (`logo-light` for dark backgrounds, `logo-dark` for the end card, SVG or PNG).
- Uxum Grotesque is not bundled; headlines use Inter Bold/Black, the brand's stated fallback.
- No music is bundled. Add `"music": {"file": "path/to/track.mp3"}` to a plan to use a licensed track.
- A full-quality render of a 40s short takes a few minutes on a laptop.
