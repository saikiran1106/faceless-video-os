# 17. Prompting guide

You drive Faceless Video OS by talking to your agent (Claude Code or Codex) in plain words. This page is a **prompting system**: one master template, the vocabulary the agent maps to real settings, ready-made prompts for every audio/transcription/image combination, and the replies you give at each checkpoint.

## How the agent reads your prompt

The skills make anything you **name** binding. Anything you leave out is chosen for you (and announced before money is spent).

| You say | Setting the agent uses |
|---|---|
| "Short", "Reel", "TikTok", "vertical", "60 seconds" | `--format short` (9:16) |
| "long-form", "YouTube video", "8 minutes", "documentary" | `--format longform` (16:9, chapters) |
| "my voiceover / recording / narration: `<path>`" | `--voice upload` → `faceless voice ingest` |
| "AI voice", "generate the voice", "narrate it" | `--voice tts` → `faceless voice generate` |
| "ElevenLabs", "my cloned voice", "voice id `<id>`" | `voice generate --provider elevenlabs --voice-id <id>` |
| "OpenAI voice", "voice onyx/nova/…" | `voice generate --provider openai --voice-id <name>` |
| "local Whisper", "free transcription", "offline" | `transcribe --provider local` |
| "Scribe", "ElevenLabs transcription" | `transcribe --provider elevenlabs` |
| "OpenAI Whisper", "Whisper API" | `transcribe --provider openai` |
| "here's the script I read: `<path>`" | `script from-transcript --script-file <path>` (captions use your spelling) |
| "use my ChatGPT for images" (Claude Code) | `--host claude-code` (Playwright browser) |
| "use your image generation" (Codex) | `--host codex` |
| "use the OpenAI image API" | `--host api` |
| "give me the prompts, I'll make the images" | `--host manual` |
| "Telugu", "Hindi", "Spanish", … | `--language te|hi|es…` (+ a font for non-Latin captions) |
| "budget $3", "don't spend more than $5" | `--budget-usd 3` — paid calls beyond it are refused |
| "also for Instagram / TikTok" | extra `compose render --platform instagram|tiktok` |
| "use vidIQ for the title" | packaging with the `vidiq_*` MCP tools |

## The master prompt

Copy, fill in what you care about, delete the rest:

```text
Make a [Short (9:16) | long-form (16:9)] video.

SOURCE
  Topic: <what it's about>                     ← for AI-written + AI-voiced videos
  — or —
  My narration: <path/to/audio>                ← I recorded it myself
  My script (what I read): <path/to/script.txt> ← optional, fixes caption spelling

VOICE        [AI: ElevenLabs voice <id> | AI: OpenAI voice <name> | use my recording]
TRANSCRIBE   [local Whisper (free) | ElevenLabs Scribe | OpenAI Whisper | auto]
LANGUAGE     <en | hi | te | es …>
LENGTH       <~55 seconds | ~8 minutes>
AUDIENCE     <who it's for>, TONE <e.g. suspenseful documentary>
IMAGES       [my ChatGPT in the browser | your built-in image tool | OpenAI Images API | give me prompts]
STYLE        <visual style>; recurring characters: <names + looks>
BUDGET       $<N> for paid calls. Tell me min and worst-case cost and ask before each paid step.
DELIVER      YouTube render [+ Instagram + TikTok] and a publishing package [using vidIQ].
```

The agent runs `faceless doctor`, confirms anything missing, creates the project, and walks the stages. It stops for you at **CP1** (story) and **CP2** (final cut), and before every paid call.

---

## Part A — You upload your own audio

The pipeline transcribes your recording, understands its story (hook, promise, sections), shows you that understanding at CP1, then builds the visuals around your timing.

### A1. Your voice + local Whisper (completely free, offline)

```text
Here's my voiceover: ~/Desktop/titanic_twin.m4a
Make a vertical Short from it. Transcribe it with local Whisper (free, offline) — no paid APIs.
Language English. Use my ChatGPT in the browser for the images, cinematic painterly 1910s style.
Deliver YouTube Shorts and Instagram renders plus the posting package.
```
What happens: `init --voice upload --host claude-code` → `voice ingest` → `transcribe --provider local` → `script from-transcript` → CP1 → visuals → render → CP2 → package. Cost: $0 (images use your ChatGPT plan).

Tip: the first local run downloads the Whisper model (~150–500 MB). For best accuracy on long or accented audio say "use the medium Whisper model" (the agent sets `FACELESS_LOCAL_WHISPER_MODEL=medium`).

### A2. Your voice + ElevenLabs Scribe (most accurate, 90+ languages)

```text
My narration is at ./audio/ep07_telugu.wav — it's in Telugu. Make a long-form 16:9 video.
Transcribe with ElevenLabs Scribe. Budget $1 for transcription.
Images: your built-in image generation (Codex). Style: Indian mythology, painterly, temple lamp light.
Use font fonts/NotoSansTelugu-Bold.ttf for captions. Package it for YouTube with chapters.
```
Scribe costs roughly $0.40 per hour of audio; the agent shows the exact estimate first.

### A3. Your voice + OpenAI Whisper

```text
Turn ~/Podcasts/clip.mp3 into a 9:16 Short. Transcribe with OpenAI Whisper.
Use the OpenAI Images API for keyframes, budget $4 total, ask before generating.
```

### A4. Your voice + the script you read from (exact caption spelling)

```text
Voiceover: ~/rec/olympic.wav. The script I read is ~/rec/olympic_script.txt —
use its spelling for the captions (names like "RMS Olympic", "Harland & Wolff").
Transcribe locally. Make a Short. Images via my ChatGPT.
```
The agent runs `script from-transcript --script-file`: your spelling on screen, your recording's timing. If less than 70% of the script was actually heard (wrong file, heavy ad-libbing), it stops and tells you which words are missing.

### A5. Zero cost, zero keys, any tools

```text
I have no API keys. My recording is ./ep1.mp3. Make a long-form video.
Use free local transcription and just give me the image prompts — I'll make them in Midjourney
and drop them in a folder named by keyframe id.
```
The agent uses `--host manual`, writes `07-keyframes/PROMPTS.md`, and later files your images with `faceless images ingest <project> <folder>`.

---

## Part B — The entire pipeline is AI-generated

The agent writes the script, you approve it at CP1, then it generates the voice, verifies what was spoken, and builds the video.

### B1. ElevenLabs voice (verified with Scribe)

```text
Make a 50-second YouTube Short: "The Titanic had a twin — why did she survive?"
Write the script yourself: hook in the first 3 seconds, one question answered at the end,
comment CTA. Voice: ElevenLabs, voice id 21m00Tcm4TlvDq8ikWAM, model eleven_multilingual_v2.
Verify the audio with Scribe. Images: my ChatGPT in the browser. Budget $2.
```
What happens: brief → script → **CP1** → `voice generate --provider elevenlabs --voice-id …` (dry-run cost first) → `transcribe --provider elevenlabs` (checks every script word was spoken) → visuals → render → **CP2** → package.

### B2. OpenAI voice + OpenAI Whisper (cheapest AI voice)

```text
Create an 8-minute long-form explainer on how lighthouses work, for curious adults.
OpenAI voice "onyx", calm documentary delivery. Transcribe with OpenAI Whisper.
Images with the OpenAI Images API, medium quality. Budget $6 — ask before each paid step.
Add chapters and use vidIQ for keyword research and title scoring.
```

### B3. AI voice from YOUR finished script

```text
Here's my finished script: ./scripts/ep12.md. Don't rewrite it — only fix things TTS would
misread and show me those changes. Generate the voice with my cloned ElevenLabs voice
<voice id>. Make a Short for YouTube, Instagram and TikTok. Images: Codex built-in.
```
The agent keeps your words, adds `pronunciation` respellings where needed, and asks at CP1.

### B4. AI voice + free local verification

```text
Make a 45-second Short about the Voynich manuscript. OpenAI voice "nova".
Verify the narration with local Whisper instead of a paid transcriber. Images: my ChatGPT.
```

### B5. A series

```text
Start a 5-part Short series "Lost Ships". Same visual bible and voice for every episode.
Do episode 1 now: the Mary Celeste. Save the visual bible so the next episodes reuse it.
```
Later: `"Episode 2 of Lost Ships: the Baychimo. Reuse the series visual bible."`

---

## Part C — Replies at checkpoints

| Moment | Say |
|---|---|
| CP1 story looks right | "Approved." |
| CP1 needs changes | "Reject: open on the iceberg line instead, and cut the second paragraph by half." |
| Cost estimate shown | "Yes, go." / "Do one chunk first so I can hear it." / "Too much — use OpenAI instead." |
| Contact sheet review | "KF007 and KF012 are wrong: KF007 should be night, KF012 has extra fingers. Regenerate only those." |
| CP2 final cut | "Approve the cut." / "Reject: captions too small, and hold KF003 longer." |

## Part D — Follow-up prompts

```text
Where are we on titanic-twin?                        → faceless next
Continue titanic-twin.                               → resumes at the current stage
The voice says "Olympic" wrong — fix only that word. → respelling + retake of one chunk
Re-voice line 3 only, keep all the other images.     → retake + beats build --keep-directions
Make the Instagram and TikTok versions too.          → compose render --platform instagram/tiktok
Change the caption color to cyan and re-render.      → channel.json style + render
Write the title, description and tags with vidIQ.    → package stage with vidiq_* tools
Make the thumbnail: the twin ship in fog, text "SHE SURVIVED".
```

## Part E — Prompting tips that improve output

1. **Say the promise.** "The viewer should want to know X; the ending answers it." It shapes the hook, script and thumbnail.
2. **Name the look once, concretely.** Era, medium, lighting, palette, lens. The agent writes it into the visual bible, and every frame inherits it.
3. **Describe recurring characters exactly** (face, age, clothes, props), or give reference images. A reference image beats any wording.
4. **Give a budget.** With `$0` nothing paid can run; a number lets the agent plan and stop at the ceiling.
5. **Ask for one unit first** on big runs ("generate one chunk / one frame first") to hear or see the result and the real cost before the batch.
6. **Correct precisely.** "KF007: make it night" gets exactly that. Vague notes ("make it better") get vague changes.
7. **For non-Latin languages**, mention the language and a font file for captions (e.g. Noto Sans Telugu/Devanagari).
