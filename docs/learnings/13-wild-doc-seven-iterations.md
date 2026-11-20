# 13. Wild-doc: what seven client iterations of one documentary taught

One client long-form (≈8 minutes, non-English narration, a prehistoric-wildlife survival story) went through seven
versions in under two weeks. The finished system is `faceless wild-doc` ([doc 18](../18-wild-doc-style.md)); this is the
story of why it looks the way it does.

## The arc
1. **v1 - a 30-minute raw recording.** Isolated the voice, word timings, an edit list of the last fluent take of every
   line, a shot list on words, Remotion with 2.5D plates, stock footage and karaoke captions. Worked, but generic.
2. **v2 - "follow my script".** The creator's own script fixed spellings and chapter titles; footage had to match the
   world (snow-only - one green forest breaks the illusion).
3. **v3 - approved.** QA without ears found 5 near-black shots (blackdetect) and proved the voice survived the mix
   (transcribe the final mix, 96.7% word match).
4. **v4 - the real brief arrived as notes on an approved film:** no subtitles and no native-script text (English
   graphics only); a new picture every 3-4 s or less; real fossil photos next to the AI images; heavy sound design (a
   whoosh/click/glitch on every text pop and transition); music louder, SFX louder than music. These notes *are* the style.
5. **v4b - "the voice sounds like a cartoon".** A 1.12x time-stretch plus small pitch corrections had ruined a human voice.
   Rule: never stretch or pitch the narrator; "faster" means removing dead air, and ideally the creator's own edit.
6. **v5/v6 - pacing by pauses only**, then tighter (≈149 wpm, 8:26); music settled at **11.5 dB under the voice**
   (never closer than 9.5).
7. **v7 - the creator sent their own edited voice.** Used as delivered; the whole film was re-timed by aligning the new
   words onto the old lines (sequence diff), keeping empty line slots so every shot anchor still resolved.

## Lessons that generalise
- **Clients describe the style after seeing a wrong version.** Ship a complete v1 fast; the notes on it are the brief.
- **The script is the text truth, the audio is the time truth.** Anchoring every cut on script words makes a re-edited
  voice a re-time, not a rebuild.
- **Fast cutting is mechanical, variety is not.** Auto jump-cuts keep the rhythm; real footage + evidence + plates keep it
  from looking like a slideshow.
- **Truth labels matter.** "REAL FOSSIL" on a reconstruction would be a lie; badges are part of the direction.
- **QA without ears:** transcribe the final mix and diff it against the clean voice; black/freeze detection; per-shot luma.
- **Hardware lies under heat:** seal, frame-count and decode-check every chunk and the master; re-verify a master's sha
  before reusing it (one bit-rotted on disk while the uploaded copy was fine).
