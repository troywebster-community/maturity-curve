---
name: community-short
description: Turn a raw Community customer testimonial or case study video into a ~40 second vertical (9:16) ad for Instagram Reels, YouTube Shorts and TikTok. Use whenever the user gives a raw video file (or a folder of them) plus a brief and wants an edited mp4 back, or asks to edit, cut, trim, caption or brand a testimonial, case study, customer story or short-form video for Community.
---

# Community short

Raw testimonial + plain-English brief in, branded 1080x1920 mp4 out. The pipeline lives in
`community-shorts/`. You (Claude) are the editor: you read the transcript, choose the cuts and
the graphics, and write `plan.json`. The scripts do the rest.

Built on two vendored skills in this folder:
- `video-use` (browser-use/video-use): ElevenLabs Scribe transcription, word-boundary cuts,
  30ms audio fades, per-segment extract then lossless concat, loudness rules, self-eval.
- `hyperframes`, `hyperframes-core`, `hyperframes-cli`, `talking-head-recut`
  (heygen-com/hyperframes): HTML + GSAP compositions rendered to video. The graphics layer.

Read `community-shorts/brand/messaging.md` before writing any on-screen text.

## Steps

All commands run from `community-shorts/`.

1. **Transcribe.**
   `python shorts.py transcribe raw/<file>.mp4 --name <slug>` (add `--speakers 2` for an interview).
   If ElevenLabs is unreachable, add `--engine local` (offline Parakeet model, setup steps at the
   top of `lib/local_asr.py`; its word end times are rougher, so read `check` output closely).
   This calls ElevenLabs Scribe with the key in `community-shorts/.env`, caches the result, and
   writes `projects/<slug>/transcript.md`, `words.json`, `source_frames.jpg` and a starter
   `plan.json`. Never re-transcribe a cached file.

2. **Read.** Read `transcript.md` and look at `source_frames.jpg` (where is the speaker's face,
   left to right? Is it a wide shot, a screen share, a Zoom grid? Burned-in subtitles?). If the
   source is already an edited video, map which stretches show the person and which show
   graphics (a 2-second contact strip helps:
   `ffmpeg -i raw/x.mp4 -vf "fps=1/2,scale=256:-2,tile=10x5" -frames:v 1 strip.jpg`). Note slips, filler, false
   starts, and every line that carries a number, a result, or a reason they chose Community.

3. **Plan the story.** Unless the brief says otherwise, aim for 34 to 40 seconds of speech plus
   a 3s end card (about 40s total). Default shape:

   | Beat | Length | What |
   |---|---|---|
   | HOOK | 3-5s | Their best result or boldest line. Starts the video, plays under the intro card |
   | PROBLEM | 3-6s | Life before Community (reach, algorithm, email, guessing) |
   | HOW | 8-14s | What they do with Community. Where the differentiator chips go |
   | PROOF | 6-12s | Numbers and outcomes. Where the stat cards go |
   | CLOSER | 2-4s | A line about owning the channel or recommending it |
   | CTA | 3s | End card (automatic, includes a 0.45s crossfade over the last words) |

   Ranges do not need to be in source order. Cut filler ("um", "so", "basically") by starting a
   range after it. Keep each range a full thought. Use the transcript times; `shorts.py` snaps
   every edge to a word boundary (start: the word starting nearest it; end: the last word that
   starts before it), then slides it into real silence using the audio waveform. To drop one
   word mid-sentence (a swear, a stumble), split it into two ranges around the word.

4. **Write `projects/<slug>/plan.json`.** Start from the generated one. Field guide:
   - `source`, `name`, `brief` (paste the user's brief), `company`, `speaker.name`, `speaker.title`.
   - `framing`: `{"mode": "crop", "focus_x": 0.0-1.0, "focus_y": 0.0-1.0, "zoom": 1.0}` centres
     the 9:16 crop on the speaker. Use `"mode": "fit"` for screen shares or wide group shots (full
     frame over a blurred copy). Burned-in subtitles at the bottom of a landscape source: use
     `"focus_y": 0.0, "zoom": 1.2` so the crop drops the bottom ~17% of the frame.
     Any range can override it with its own `"framing": {...}` (different shot, different spot).
   - `layout`: `{"callout_top": 1350, "speaker_top": 1350}` moves chips and the name tag below
     the captions when a tight close-up puts the face in the top half. Defaults are 360 / 310.
   - `grade`: `social_bright` (default), `neutral_punch`, `warm_soft`, `subtle`, `none`, or a raw
     ffmpeg filter.
   - `intro`: `eyebrow` ("Customer story"), `headline` (sentence case, under ~45 characters,
     the result in their words, wrap the key word in `**...**` for the blue marker), `duration`.
     `"style": "overlay"` (default) floats it over the hook; `"style": "card"` is a full-screen
     light gradient opener (good at 1.0s, headline optional) with the hook audio running under it.
   - `ranges`: `[{"start", "end", "beat"}]`. Optional per range: `"zoom": 1.15`.
     `auto_punch` alternates a 1.12 punch-in on every other cut so jump cuts feel intentional.
   - `callouts`: timed to a phrase the speaker says with `"anchor"` (must survive the cut), or
     `"at"` seconds on the output timeline. Kinds:
     - `stat`: `value` ("30%", "$1.2M", "4x", "40 min"; numbers count up), `label`, `kicker`.
     - `chip`: product differentiator, `text` + optional `sub`. Pick from `brand/messaging.md`.
     - `punch`: one big statement, `text` with `**emphasis**`. Use at most once.
     - `quote`: full-screen light card with the customer's exact words while that audio plays,
       plus `by` (defaults to the speaker) and optional `role`. It covers the video, so use it
       where the source shows graphics or b-roll, and to make "quotes" the star. Captions hide
       under it. Time it with `at` + `duration` matching the ranges it covers (`check` prints
       each range's output time). Quote words must match what is said; mark cuts with "…".
     Space callouts at least ~1s apart, 2.5-3.2s each, none during the intro card.
   - `corrections`: fix ASR spellings in captions, e.g. `{"community": "Community"}`. Keep that
     one unless the speaker uses "community" as a plain noun.
   - `cta`: `eyebrow`, `headline`, `subline`, `button`, `url`, `duration` (total seconds the end
     card is on screen, crossfade included; default 3.0). Options in `brand/messaging.md`.
   - `music`: `{"file": "path.mp3", "volume": 0.16}` if the user supplies a track (ducked
     under speech automatically). Leave `null` otherwise. Never use music you were not given.

5. **Check.** `python shorts.py check projects/<slug>/plan.json` prints every cut with the words
   it keeps, the total runtime and where each callout lands. Read the kept words: each range
   must start and end cleanly. Fix and re-check until it reads like a tight ad.

6. **Draft render.** `python shorts.py render projects/<slug>/plan.json --draft` (a few minutes).
   Then look at `projects/<slug>/<slug>_draft_qc.jpg` (a frame after every cut plus the end
   card). Check: speaker centred, nothing important under captions or cards, captions readable,
   end card clean, duration in range, loudness near -14 LUFS. Fix the plan and re-render if
   needed (max 3 passes, then tell the user what is still off).

7. **Final render.** `python shorts.py render projects/<slug>/plan.json` gives
   `projects/<slug>/<slug>.mp4`. Send it to the user with a 3-line summary: runtime, the story
   in one sentence, and which numbers/claims appear on screen and where they came from.

8. **Iterate** on feedback by editing `plan.json` and re-rendering. Never re-transcribe.

## Hard rules

- On-screen numbers must be said in the footage or come from the `community-case-studies` skill.
  Never invent or round up a result. Flag anything you are unsure about.
- Every short opens by introducing Community (the intro card does this) and ends on the CTA card.
- Sentence-case headlines, no trailing punctuation, no competitor names on screen.
- Do not cut a sentence so it changes what the customer meant.
- Keep `.env` out of git. Never print the API key.
- Do not edit the vendored skill folders; they are reference copies.

## When things fail

- `ElevenLabs Scribe returned 401`: the key in `community-shorts/.env` is wrong or expired.
- Network blocked to `api.elevenlabs.io`: if the user already has a Scribe JSON, import it with
  `python shorts.py transcribe raw/x.mp4 --transcript path/to/scribe.json`.
- `anchor ... not found`: the phrase was cut. Pick a phrase from the `check` output, or use `at`.
- HyperFrames render errors: run `npx hyperframes@0.8.142 lint projects/<slug>/work/hf` and read
  `.claude/skills/hyperframes-core/SKILL.md`. First run needs `npx hyperframes browser ensure`.
