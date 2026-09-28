---
name: faceless-transcribe
description: Create the word-timed transcript that syncs everything in a Faceless Video OS video - ElevenLabs Scribe when an ElevenLabs key exists, otherwise OpenAI Whisper, otherwise free local faster-whisper - and verify AI narration against its script. Use for the transcript stage, caption timing problems, or "the captions/beats are out of sync".
---

# Faceless Transcribe

```bash
faceless transcribe <p>                 # auto: elevenlabs -> openai -> local
faceless transcribe <p> --yes           # when it shows a cost estimate
faceless transcribe <p> --provider local  # free, offline (pip install 'faceless-video-os[local-asr]')
faceless complete <p> transcript
```

Output `04-transcript/transcript.json`: `words[{text,start,end}]`, full `text`, `language`, the audio's sha256, and in AI-voice mode a `script_match` (`ratio`, `missing`, `extra`).

## Provider notes

| Provider | Needs | Strengths |
|---|---|---|
| ElevenLabs Scribe (`scribe_v2`) | `ELEVENLABS_API_KEY` | Best word timings, 90+ languages, long files |
| OpenAI `whisper-1` | `OPENAI_API_KEY` | Word timestamps; audio auto-compressed under the 25 MB cap |
| Local faster-whisper | `pip install 'faceless-video-os[local-asr]'` | Free, private; slower; set `FACELESS_LOCAL_WHISPER_MODEL=medium` for accuracy |

Pass the right `--language` at `init`; auto-detection mislabels short clips.
If the user asked for a specific transcriber ("use local Whisper", "use Scribe"), pass `--provider` explicitly — `auto` prefers ElevenLabs whenever its key exists.

## Reading the result

- Gate **FF-ASR-002**: the transcript is of a different audio file than the current master → re-run after any voice change.
- AI-voice mode: `script_match.ratio < 0.85` blocks — the TTS dropped or garbled lines. Look at `missing` to find WHICH chunk, then retake only that chunk (`faceless-voice`). 0.85-0.93 is a warning: listen to those spots.
- ASR mis-hearing a proper noun is not a voice defect. Captions already use the script's spelling with the transcript's timing, so a misheard name in the transcript does not reach the screen.
- Upload mode: captions come from `02-script/script.json` `narration` (initially the transcript). Correct misheard names there, or use `--script-file` with the creator's own script, and tell the human which words you corrected. Timing always comes from the recording.

Next: upload mode → `faceless script from-transcript` (see `faceless-script`); AI-voice mode → `faceless-visuals`.
