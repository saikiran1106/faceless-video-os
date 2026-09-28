# 3. Workflows

These are the commands the agent runs; you can run them yourself too. `<p>` is a project slug or path.

## A. AI-voiced Short from a topic (Claude Code + ElevenLabs)

```bash
faceless init olympic-twin --title "The Titanic Had a Twin" --format short --voice tts --host claude-code --language en --budget-usd 3
# agent writes 01-brief/brief.json
faceless complete olympic-twin brief
# agent writes 02-script/script.json
faceless complete olympic-twin script              # -> awaiting_human
faceless approve olympic-twin cp1_story --approver you
faceless voice generate olympic-twin --dry-run     # shows cost
faceless voice generate olympic-twin --yes
faceless complete olympic-twin voice
faceless transcribe olympic-twin --yes
faceless complete olympic-twin transcript
# agent writes 05-visual-bible/visual_bible.json
faceless complete olympic-twin visual_bible
faceless beats build olympic-twin                  # agent then directs every beat
faceless complete olympic-twin beats
faceless images jobs olympic-twin
faceless browser generate --project olympic-twin   # ChatGPT in the signed-in browser
faceless images manifest olympic-twin
faceless review contact-sheet olympic-twin         # agent looks, then:
faceless images qa olympic-twin all --pass
faceless complete olympic-twin keyframes
faceless compose render olympic-twin --platform youtube
faceless compose render olympic-twin --platform instagram
faceless review render-sheet olympic-twin
faceless compose report olympic-twin --reviewed --notes "watched"
faceless complete olympic-twin compose              # -> awaiting_human
faceless approve olympic-twin cp2_final_preview --approver you
faceless package draft olympic-twin                # agent fills it (vidIQ if connected)
faceless complete olympic-twin package
```

## B. Your own voice → long-form (Codex, no paid keys)

```bash
pip install -e ".[local-asr]"
faceless init ep03 --title "Episode 3" --format longform --voice upload --host codex --language en
# brief
faceless voice ingest ep03 ~/Desktop/ep03.m4a && faceless complete ep03 voice
faceless transcribe ep03 --provider local && faceless complete ep03 transcript
faceless script from-transcript ep03               # agent fills TODOs, never changes the words
faceless complete ep03 script && faceless approve ep03 cp1_story --approver you
# visual bible, beats as in A
faceless images jobs ep03
# Codex generates each job with its built-in image tool, then per image:
faceless images record ep03 KF001 /path/to/generated.png --host codex
# ... manifest, QA, compose, package as in A
```

## C. Same video for YouTube Shorts, Instagram Reels and TikTok

One project, three renders — only the end card changes (Subscribe vs Follow):
```bash
for p in youtube instagram tiktok; do faceless compose render <p> --platform $p; done
faceless compose report <p> --reviewed
```

## D. Fix one bad keyframe

```bash
faceless images qa <p> KF012 --fail --note "hands deformed"
# regenerate ONLY KF012 on your host (api: delete 07-keyframes/images/KF012.png, then)
faceless images generate <p> --only KF012 --yes
faceless images manifest <p>            # the new pixels come back as qa_status=pending
faceless images qa <p> KF012 --pass
faceless reopen <p> keyframes --reason "KF012 regenerated"   # only if keyframes had already completed
```

## E. Fix one mispronounced word (AI voice)

1. Add a respelling to `02-script/script.json` → `"pronunciation": {"Olympic": "Oh-limpik"}`.
2. `faceless reopen <p> voice --reason "pronunciation fix"`.
3. `faceless voice generate <p> --yes` — only the chunk whose text changed is re-bought.
4. `faceless transcribe <p> --yes`, then complete transcript and visual_bible again (the bible is unchanged; completing re-runs its gate).
5. `faceless beats build <p> --keep-directions` — beats are re-timed to the new audio; every beat whose words did not change keeps its direction AND its keyframe. Only changed lines come back as new beats needing direction and a new keyframe.
6. `faceless images jobs <p>`, generate only the new ones, then manifest → QA → compose as usual.

## F. Re-render after hand-tweaking overlays

```bash
faceless compose props <p> --platform youtube
# edit 08-compose/props_youtube.json
faceless compose render <p> --platform youtube --keep-props
```

## G. Mixed hosts

Hosts are interchangeable per frame. Generate most frames in Codex, a few via the API, and one by hand — each lands at the job's `output_path` with a receipt noting its source.
