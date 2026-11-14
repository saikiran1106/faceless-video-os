# 3. Google Flow (Gemini Omni) video generation from an agent

Code: `automation/studio_os/flow` (session, selectors, generate, api, dialogue demo) and `fast/clips.py` (batch submit + harvest).

## What the model is good at (verified in use)

- **Frames mode** (start frame, optionally end frame) gives the highest likeness to your keyframe and one continuous shot that
  lands on the end frame. **Default for narration-synced beats.**
- **Ingredients mode** (reference images + saved voices) gives richer multi-shot progressions but lower likeness, the model chooses its own
  internal timing, and end poses are stiff. **Use it for dialogue** because it is how a saved voice is attached.
- `@` references in Frames mode *replace* the start frame; frames and @-refs do not combine.
- Durations 4/6/8/10 s, 9:16 and 16:9; **720p only in the plan we used**; credits scale with length (≈7–15 for a 720p clip). Native audio
  comes with every clip (mute it if your own mix is the soundtrack).
- Strong: environments, light, slow/static objects. Weak: articulated characters in complex motion, face drift across frames.

## Prompt rules

1. The reference does the looking; the prompt does the moving. Spend words on motion, camera, light, audio.
2. Five parts in order: subject anchor → timecoded motion beats (`[0-2s] … [2-4s] …`) → camera + lens → light/style ("keep the exact look of
   the start frame") → audio.
3. **Affirmative, not negative** ("smooth locked tripod shot", not "no shaking"). Negations are read as visual cues.
4. "Single continuous shot", otherwise it invents its own cuts. Cut in the edit.
5. No generated text; add overlays in the edit.
6. Humans stay still unless motion is the point; motion goes to objects, light, UI.
7. For a must-persist element ("solidifies into a permanent X that stays") reduce camera motion and check the **last** frame, not the first.
8. Policy blocks cost nothing and may leave no tile. Neutral staging of the same image usually passes (a "drop lands" instead of an explicit wound).

## Spend guards (every paid click)

Before the one paid click the adapter checks: the **Agent chip is off** (NORMAL mode only), the settings chip reads the planned
model/aspect/count, the planned frame ingredients are attached, the prompt landed whole, and **the price shown in the UI equals the expected
price**. Any failure stops the run (`GuardStop`).
- Hard `--credit-cap` is required; balance is read before/after each clip into a ledger.
- **Never resubmit on a timeout.** Re-run in harvest mode instead (free).
- Halt after clip 1 of a new setup for a burn-rate check. Do a free `--dry-run` rehearsal first.
- State minimum and worst-case credits and get an explicit yes first.
- Submit through the real Start button (it is protected by reCAPTCHA; we never mint tokens). Everything else can use Flow's own responses.

## Reading results without clicking tiles (harvest)

One project page load makes Flow call its `batchexecute` RPCs; listen and decode:
- `Zzl0ze` — the project's media list (filename/title, media id, prompt, model key such as `…_i2v_4s`, and the input frames with roles 1=start / 2=end).
- `nzlxg` — credits (`payload[0]` = remaining balance).
Binding a video to its beat = the video whose **start frame filename** is `<beat>.png`; this is exact and replaces counting tiles. Download with the
media URL's `=m22` variant. Roughly 15 clips submit back-to-back in ~4–5 minutes; renders run concurrently; harvest ~8 minutes.

## Dialogue films (characters that speak)

- Dialogue comes from **Flow's native audio only**; a text-to-speech/voice-changer/lip-sync route was rejected as sounding dubbed. Layer only SFX, music and a background narrator on top.
- One saved custom voice per character via Ingredients, **one speaker per clip, lines ≤ 6 s**.
- Verify each line by transcription **and** by ear; cap retakes at 2; run an A/B/A voice-consistency test before any bulk run.
- Write dialogue from a researched film-architecture document, not from a viral beat-list (beat-lists produce flat dialogue and heavy narration).

## Other generators

- **Veo (API):** persist the long-running **operation name to disk the instant the submit returns**, before polling; retry network errors inside the poll loop; keep the
  video write before the ledger write. A dropped connection once lost four billed generations because the operation names lived only in memory, and publisher-model
  operations have no list endpoint.
- **Seedance via a reference-binding UI:** give each `@reference` an explicit authority at first use (IDENTITY ONLY, WARDROBE ONLY, MOVEMENT ONLY …); never merely list them.
- Do not let a video model render text inside the frame.
