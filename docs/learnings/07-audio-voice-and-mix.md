# 7. Voice, audio and mix

## AI narration (ElevenLabs-style TTS)

- **Chunking:** keep each request ≤ ~1,000 characters for the v3 model; fewest possible uniform chunks (600–1,000 chars) split at scene breaks; never a tiny standalone chunk
  (voice shifts between chunks). A v4 request with a long section **plus** a 600-char `next_text` returned `400 invalid_argument` above ~900–1,300 chars; retry without `next_text`
  (keep previous ids), then step previous ids 3→2→1. Rejected requests cost nothing, **successful probes do**: probe with short text, and reuse the audio of any successful full-length probe.
- **Truncation gates:** verify every chunk. Characters-per-second is the primary guard (retake when ≥ 20 cps; the normal band for one voice was 13.5–15.2; English runs a little faster),
  combined with an expected-duration band (±10 %). Treat the tail as a hard cut only when the **last 40 ms exceed −6 dB** *and* cps is out of band; do not trust a positive tail gap.
- **Gate on audio, not on the script.** Transcribe **every** chunk (never a sample), normalise both sides (strip tags/punctuation/case; fold confusable consonants for non-Latin
  scripts), word-diff against the script, and fail on substitutions, dropped words, adjacent duplicates/prefix stutters, and wrong occurrence counts of story-critical names
  (`--require name:N`). Forced alignment of a *known* script gives exact timings for free but cannot detect substitutions.
- **Script wording is immutable.** A mispronunciation/stutter is a *generation* defect: re-roll (≤ 2 takes). Only spacing patches (same words, split for clarity) are allowed.
- **Tags:** open every chunk with the same baseline tag; put emotion tags inside the chunk at peaks only; verify none leaked into speech by transcription; avoid shouting/laughing tags in
  narration (carry anger in words and punctuation). `...` is a reliable pause lever.
- **Retake budget:** before a multi-unit paid run state min cost (chars × 1 take) **and** worst case (chars × max takes), get approval for the **total**, set `MAX_TAKES=2`, and stop
  on the first take that passes every gate. One run reached 3.86× the necessary spend because each re-roll "looked small".
- Don't over-specify a voice design; the model's default delivery is usually better than a long brief.

## Recorded human narration (post-production chain that sounded "studio, buttery")

Word-timestamp transcript (cloud timing; local Whisper only if you allow it) → keep the **last** take of any retake (word onsets run ~100 ms late, so find the true onset from energy and end the cut ≥ 100 ms before it;
verify every join on a spectrogram) → cloud voice isolation, lag-aligned, **restore 2–8 kHz timbre with a linear-phase FIR** → breath/click cleanup behind a **speech-safety gate** (speech mask = pitch-voicing + loud
tonal frames, gaps ≤ 180 ms filled, onset extension 120 ms, tail extension 300 ms, ramps outside speech, force back any transcript word the detector missed; result: pauses gated to digital silence and 0 words lost)
→ warm EQ, post-EQ de-ess, 2:1 compression, light parallel saturation and parallel compression → −14 LUFS with a 4×-oversampled true-peak limiter at −1.3 dBTP.
No mastering API exists, a voice changer re-synthesises the voice (not the narrator any more, a consent problem), and the narrator must never be cloned without consent: everything after isolation is local DSP.

## The mix

- Layers: narration (unity) + score + ambience beds + word/picture-locked SFX. **Sidechain-duck** music/beds ~6 dB and SFX ~3 dB under speech (15 ms attack, 250 ms release).
- Margins that tested well: music median ≈ 11.5 dB under the voice (never < 9.5); SFX buses ≥ 5 dB under; never let SFX *hide* a word (check with a transcript of the mix).
- SFX anchor on the **peak** of the sample, not its start (`t_event − peak_offset`), so the hit lands on the frame.
- Fill the dip-to-black at chapter turns with a sub-drop + whoosh so it never goes to dead air.
- Master two-pass `loudnorm` to −14 LUFS / −1.2 dBTP, then a limiter at ~0.89. **`loudnorm` in linear mode delays the output by ~240 samples (5 ms)**: when comparing a final mix to its stems, align by that lag.
- **Stems for editors:** re-run the mix code writing `Voice`, `Music_Score`, `Ambience_Beds`, `SFX` at the final level (`stem × G`, where `G` is the constant loudnorm gain fitted *after lag alignment* on 64-bit floats).
  Validate: stems sum to the pre-master mix within −60 dB; write any stem that peaks > 0.98 as 32-bit float (a loud SFX bus clipped 24-bit); tell the editor to put a limiter on the master bus.
