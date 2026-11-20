# 10. CLI reference

All commands print JSON. `<p>` = project slug (under `projects/`) or a path. Exit codes: `0` ok, `1` error (message in JSON), `2` gate/doctor failed, `3` browser run blocked (auth/CAPTCHA).

## Setup

| Command | Does |
|---|---|
| `faceless setup` | create `channel.json`, `.env`, `projects/` from examples; sync skills |
| `faceless doctor` | capabilities, failing checks with fixes, one-step upgrades |
| `faceless demo [--format short\|longform] [--engine remotion\|ffmpeg] [--no-render]` | free offline end-to-end run |
| `faceless skills sync` | copy `skills/` → `.claude/skills/` and `.agents/skills/` |

## Project & state

| Command | Does |
|---|---|
| `faceless init <slug> --title T --format short\|longform --voice tts\|upload --host codex\|claude-code\|api\|manual [--language en] [--budget-usd 0] [--projects-root DIR]` | new project |
| `faceless next <p>` | current stage, status, skill, exact commands, blocking findings |
| `faceless status <p>` | full `run.json` |
| `faceless gate <p> <stage>` | validate + gate the artifact without advancing |
| `faceless complete <p> <stage>` | validate + gate + advance (or wait for a human) |
| `faceless approve <p> cp1_story\|cp2_final_preview --approver NAME [--note]` | record approval |
| `faceless reject <p> <gate> --note "..."` | send back with notes |
| `faceless reopen <p> <stage> --reason "..."` | go back; invalidates later stages |
| `faceless lock <p> NAME FILE [--reason]` / `unlock <p> NAME --reason` | freeze/unfreeze an artifact by hash |
| `faceless budget <p> --usd N --approver NAME` | change the spend ceiling |
| `faceless cost <p> --amount-usd N --provider X --operation-id ID --stage S` | record spend made elsewhere |

## Voice & transcript

| Command | Does |
|---|---|
| `faceless voice ingest <p> FILE` | use your recording |
| `faceless voice generate <p> [--provider auto\|elevenlabs\|openai] [--voice-id] [--model] [--retake C###] [--dry-run] [--yes]` | AI narration |
| `faceless transcribe <p> [--provider auto\|elevenlabs\|openai\|local] [--yes]` | word-timed transcript |
| `faceless script from-transcript <p> [--force] [--script-file FILE]` | draft script from uploaded narration (your script’s spelling for captions) |

## Beats & images

| Command | Does |
|---|---|
| `faceless beats build <p> [--force] [--keep-directions]` | measure beats (keep directions after a voice change) |
| `faceless images jobs <p> [--sheets]` | compile keyframe (or reference-sheet) jobs |
| `faceless images prompts <p> [--sheets]` | PROMPTS.md for manual generation |
| `faceless images generate <p> [--sheets] [--only IDS] [--limit N] [--yes]` | OpenAI Images API |
| `faceless images record <p> ID FILE [--host X]` | file one image against its job |
| `faceless images ingest <p> FOLDER` | file every `<ID>.png` in a folder |
| `faceless images apply-sheets <p>` | add sheets to the bible's references |
| `faceless images manifest <p>` | build `keyframe_manifest.json` |
| `faceless images qa <p> IDS... --pass\|--fail [--note]` | record review verdicts (`all` allowed) |
| `faceless browser setup [--wait S]` | one-time ChatGPT sign-in (human) |
| `faceless browser doctor [--headed]` | non-consuming adapter health check |
| `faceless browser generate --project <p> [--sheets] [--batch N] [--only IDS] [--limit N] [--new-conversation]` | generate via ChatGPT |
| `faceless browser resume --project <p>` | recover in-flight jobs |
| `faceless browser status --project <p>` | durable queue state |

## Review, compose, package

| Command | Does |
|---|---|
| `faceless review contact-sheet <p>` | keyframes beside their lines |
| `faceless review render-sheet <p> [--platform]` | frames from the render at each beat |
| `faceless compose props <p> [--platform]` | write props JSON |
| `faceless compose render <p> [--platform youtube\|instagram\|tiktok] [--engine remotion\|ffmpeg] [--keep-props]` | render MP4 |
| `faceless compose report <p> [--reviewed] [--notes]` | probe renders → `render_report.json` |
| `faceless package draft <p> [--force]` | package skeleton, chapters, SRT |

## Media logins and generation ([doc 19](19-media-logins.md))

| Command | Does |
|---|---|
| `faceless login images [--via browser\|codex] [--accounts N]` | connect image generation: ChatGPT window(s), or install + sign in the Codex CLI |
| `faceless login flow [--accounts N] [--only NAME] [--project-url NAME URL]` | one window per Google account; saves each Flow project URL |
| `faceless login status [--live]` | what is connected |
| `faceless gen images --jobs J --out DIR [--via codex\|browser\|api] [--workers N] [--only IDS] [--yes]` | one image per job → `DIR/<id>.png` |
| `faceless gen clips --project DIR --credit-cap N [--accounts ...] [--beats ...] [--dry-run] [--copy-to DIR]` | Flow clips split across accounts (PAID) |

## Wild-doc ([doc 18](18-wild-doc-style.md))

| Command | Does |
|---|---|
| `faceless wild-doc new SLUG --script S --audio A [--lang L] [--channel NAME] [--title T]` | start a project |
| `faceless wild-doc run P [--yes] [--auto] [--images-via V] [--provider X] [--preview]` | every ready step in order; stops with the next action |
| `faceless wild-doc setup [--depth] [--kit procedural\|elevenlabs] [--yes]` | Remotion packages, depth model, SFX kit |
| `faceless wild-doc transcribe P [--provider ...] [--yes]` · `align P [--no-split]` · `draft P [--force]` | clock + first cut |
| `faceless wild-doc status P` | what exists, what the shot list needs |
| `faceless wild-doc stock-search P "q" ...` · `stock-fetch P` | Pixabay footage by contact sheet; `06-assets/clips` |
| `faceless wild-doc refs-search P TAG "q" ...` · `refs-fetch P` | Commons evidence photos + credits |
| `faceless wild-doc images P [--via V] [--only IDS]` · `plates P` | AI plates + depth maps |
| `faceless wild-doc kit [--via procedural\|elevenlabs]` · `sound P --yes` | SFX kit; story SFX + chapter music |
| `faceless wild-doc plan P [--allow-missing]` · `grade P` · `render P [--chunks N ...]` | plan, baked grades, verified chunks |
| `faceless wild-doc mix P` · `assemble P` · `thumbnail P` · `qa P [--transcribe X]` · `package P` | finish |
| `faceless wild-doc voice P NEW_AUDIO` | replace the narration and re-time the film |

