---
name: elevenlabs-music-api-limits
description: ElevenLabs Music API ignores long timestamped prompts — returns wrong length and flat dynamics. Use short prompts + separate SFX impacts and shape the arc yourself in Remotion
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7341edb9-51a9-41ce-9535-b74e0d7e0ab1
  modified: 2026-08-16T05:53:18.226Z
---

Measured on the THE BOSE EFFECT teaser score, 2026-08-16. Two failed generations before getting a usable bed.

**`client.music.compose()` ignores elaborate timestamped prompts.**
A prompt written as a cue sheet ("0-5s sparse drone, 5-13s build, 22-27s peak, 37-39s silence…") produced:
- **wrong duration** — asked for 49,000 ms, got **94 s**
- **no dynamics at all** — RMS flat at −11 to −14 dB across the entire file, none of the described structure
- a **quiet first 2 s**, which is exactly the "dead air at the start" defect to avoid

A second attempt with the same style of prompt came back near-silent (−91 dB) for its first 26 s.

**What works:** a short prompt naming only genre, mood, instruments, and one intensity instruction. `music_length_ms` is then honoured (asked 50,000 → got 49.998 s). Example that worked:
> "Intense dark cinematic trailer score for a 1940s Indian war drama. Driving low taiko war drums and urgent tense strings, starting immediately at full intensity with no fade-in. Relentless building pulse, dread and defiance, subtle Indian sarangi texture. Orchestral, instrumental only, no vocals."

**Get dynamics from elsewhere, not from the music prompt:**
1. Generate a flat, intense **bed** with a short prompt.
2. Generate **impact hits separately** via `client.text_to_sound_effects.convert()` — an opening braam, a riser, a title hit. These come back punchy and correctly timed.
3. Shape the arc yourself in the Remotion `<Audio volume={f => …}>` callback — full under action, ~0.24 under dialogue, hard 0 for a silence beat.

**Verify levels with `volumedetect` over segments, not `astats`.** An `astats` pass with `reset=` gave readings that contradicted `loudnorm` and led to a wrong "this file is silent" conclusion. `ffmpeg -ss N -t D -i f -af volumedetect` per segment is unambiguous.

**Always master the finished render:** source clips from Higgsfield peak at 0.0 dB and will clip once layered. `loudnorm=I=-14:TP=-1.0:LRA=11,alimiter=…` brings peaks to about −0.3 dB and matches the social platforms' target.

Related: [[teaser-cutting-playbook]], [[elevenlabs-v3-narration]], [[ask-before-paid-api-calls]].
