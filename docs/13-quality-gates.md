# 13. Quality gates

Every `faceless complete` runs the stage's schema validation and then its gate. **Critical** findings block the stage; **warnings** are shown to the agent and reviewer but don't block. Each finding has a `location` and usually a `fix`.

| Rule | Stage | Severity | Checks |
|---|---|---|---|
| FF-BRIEF-001 | brief | critical | Brief says voice_mode=… but the project is … |
| FF-BRIEF-002 | brief | critical | Brief says format=… but the project is … |
| FF-BRIEF-003 | brief | warning | Target …s is outside the … range …-…s |
| FF-BRIEF-004 | brief | warning | No promise question: what does the viewer want answered? |
| FF-TODO | brief | critical | Placeholder TODO left in the brief |
| FF-TODO | script | critical | Placeholder TODO left in the script |
| FF-SCRIPT-001 | script | critical | … words is off-target: …s at ~… wpm is ~… words (±25%) |
| FF-SCRIPT-002 | script | warning | Spaced dashes often make TTS pause oddly or read them aloud |
| FF-SCRIPT-003 | script | warning | Hook runs ~…s; aim for <= …s |
| FF-SCRIPT-004 | script | warning | Sections hold … words but the narration has … |
| FF-SCRIPT-005 | script | critical | Duplicate section_id |
| FF-SCRIPT-006 | script | warning | Long-form with fewer than 3 sections gets no useful chapters |
| FF-SCRIPT-007 | script | warning | Some factual claims have no source_refs |
| FF-VOICE-001 | voice | critical | Manifest mode … != project voice_mode … |
| FF-VOICE-002 | voice | critical | Narration master is missing: … |
| FF-VOICE-003 | voice | critical | Narration master changed after the manifest was written |
| FF-VOICE-004 | voice | critical | …s is longer than a Short can be (180s) |
| FF-VOICE-005 | voice | warning | …s is outside the … profile range |
| FF-VOICE-006 | voice | critical | Chunk … speaks … chars/s; the provider probably truncated it |
| FF-VOICE-007 | voice | warning | Chunk file missing: … |
| FF-ASR-001 | transcript | critical | No voice manifest; transcribe after the voice stage |
| FF-ASR-002 | transcript | critical | This transcript is of a different audio file than the current narration master |
| FF-ASR-003 | transcript | critical | Word timings go backwards at word … (…) |
| FF-ASR-004 | transcript | critical | Last word ends after the audio does |
| FF-ASR-005 | transcript | critical | AI-voice mode needs a script-vs-audio comparison |
| FF-ASR-006 | transcript | critical | Only … of the script was heard in the audio; the voice dropped or garbled lines |
| FF-ASR-007 | transcript | warning | … script match; check the missing words by ear |
| FF-VIS-001 | visual_bible | critical | Visual bible aspect … but … renders … |
| FF-VIS-002 | visual_bible | critical | Duplicate … … |
| FF-VIS-003 | visual_bible | critical | Reference image not found: … |
| FF-VIS-004 | visual_bible | warning | … prompt_contract is thin; identity will drift between frames |
| FF-VIS-005 | visual_bible | warning | style_contract is thin; frames will not look like one video |
| FF-TODO | visual_bible | critical | Placeholder TODO left in the visual bible |
| FF-SYNC-001 | beats | critical | Duplicate … …: one keyframe per beat, never shared |
| FF-SYNC-002 | beats | critical | Beat ends before it starts |
| FF-SYNC-003 | beats | critical | …s gap before this beat |
| FF-SYNC-004 | beats | critical | Overlaps the previous beat by …s |
| FF-SYNC-005 | beats | critical | …s hold on one image (max …s) |
| FF-DIR-001 | beats | critical | Beat has no visual_objective (what must the viewer SEE?) |
| FF-DIR-002 | beats | critical | Unknown character_id … |
| FF-DIR-003 | beats | critical | Unknown location_id … |
| FF-SYNC-006 | beats | critical | First beat does not start at 0s |
| FF-SYNC-007 | beats | critical | Beats end at …s but audio ends at …s |
| FF-DIR-004 | beats | warning | … of beats are '…' shots; it will read as static |
| FF-DIR-005 | beats | warning | Same camera move 4+ times in a row near … |
| FF-KF-001 | keyframes | critical | No keyframe for beat … (…) |
| FF-KF-002 | keyframes | critical | … was declared for … but is bound to … |
| FF-KF-003 | keyframes | critical | The same image file is used for … keyframes |
| FF-KF-004 | keyframes | critical | Image missing: … |
| FF-KF-005 | keyframes | critical | Image changed after it was recorded |
| FF-KF-006 | keyframes | critical | Aspect …x… does not match … |
| FF-KF-007 | keyframes | critical | Not visually reviewed/passed (qa_status=…) |
| FF-RENDER-001 | compose | critical | Render missing: … |
| FF-RENDER-002 | compose | critical | Render has no audio track |
| FF-RENDER-003 | compose | critical | …x… but … is …x… |
| FF-RENDER-004 | compose | critical | Render (…s) is shorter than the narration (…s) |
| FF-RENDER-005 | compose | warning | Render runs …s past the narration |
| FF-RENDER-006 | compose | critical | Nobody has watched the render yet |
| FF-TODO | package | critical | Placeholder TODO left in the package |
| FF-PKG-001 | package | critical | Title is … chars; YouTube's limit is 100 |
| FF-PKG-002 | package | warning | Title is … chars; it will be truncated in search/feed (~70) |
| FF-PKG-003 | package | warning | Description under 150 chars; the first 2 lines are prime search real estate |
| FF-PKG-004 | package | critical | Tags exceed YouTube's 500-character limit |
| FF-PKG-005 | package | critical | More than 15 hashtags: YouTube ignores ALL of them |
| FF-PKG-006 | package | warning | Use 3-5 focused hashtags |
| FF-PKG-007 | package | critical | The first chapter must start at 0:00 |
| FF-PKG-008 | package | critical | YouTube needs at least 3 chapters (or none) |
| FF-PKG-009 | package | critical | Chapters must be at least 10s apart |
| FF-PKG-010 | package | warning | Long-form without chapters |
| FF-PKG-011 | package | critical | Thumbnail missing: … |
| FF-PKG-012 | package | critical | Thumbnail is over YouTube's 2 MB limit |
| FF-PKG-013 | package | warning | No custom thumbnail; long-form lives or dies on it |

`FF-TODO` fires in any stage whose artifact still contains the word TODO — drafts generated by the CLI use it to force the agent to finish them.

Gate reports are written to `<stage-dir>/gate_report.json` and bound to the artifact's sha256. Run a gate without advancing: `faceless gate <p> <stage>`.

To add or change a rule, see [Extending](12-extending.md).
