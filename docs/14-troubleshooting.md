# 14. Troubleshooting

Start with `faceless doctor` and `faceless next <p>` — most answers are in their output.

| Symptom | Cause | Fix |
|---|---|---|
| Installer stopped at a step | that step failed (message shows which) | fix it, re-run `./install.sh` — finished steps are skipped |
| `faceless: command not found` | new terminal not opened, or `~/.local/bin` not on PATH | open a new terminal, or use `.venv/bin/faceless` |
| faster-whisper won't install | Python 3.14+ in `.venv` | `./install.sh --recreate-venv` (it picks 3.10–3.13) |
| Linux: Remotion/Chromium "error while loading shared libraries" | missing system libs | re-run `./install.sh` (installs them), or `sudo .venv/bin/playwright install-deps chromium` |
| Linux: Node too old | distro Node < 18 | `./install.sh` installs Node LTS with nvm; open a new terminal |
| `ffmpeg is not installed` | missing binary | install ffmpeg (see Getting started) |
| `Composer dependencies are missing` | no `node_modules` | `cd composer && npm install` |
| Remotion render fails on fonts | `style.font_file` path wrong | path is relative to the repo root; check `faceless doctor` |
| Non-Latin captions show boxes/tofu | no font covering the script | set `style.font_file` to a Noto font for that script |
| `confirm_required: true` | paid call without `--yes` | read the estimate, then re-run with `--yes` |
| `Budget exceeded` | approved budget too low | a human runs `faceless budget <p> --usd N --approver NAME` |
| `No TTS provider is configured` | no keys | add a key to `.env` or use `--voice upload` |
| `No transcription provider` | no keys, no local model | `pip install -e ".[local-asr]"` |
| OpenAI transcription "over 25 MB" | very long audio | use ElevenLabs Scribe or `--provider local` |
| FF-ASR-002 transcript of different audio | voice changed after transcribing | `faceless transcribe <p>` again |
| FF-ASR-006 low script match | TTS dropped/garbled lines | see `script_match.missing`, retake that chunk |
| `...exists and may already be directed` | rebuilding beats | `--keep-directions` after a voice change, `--force` to discard |
| FF-KF-006 aspect mismatch | image generated at the wrong shape | regenerate at the job's aspect; don't crop |
| FF-KF-002 recast | keyframe bound to another beat | regenerate the target beat; never move frames |
| Browser: `authentication_required` | ChatGPT signed out | `faceless browser setup` and sign in (human) |
| Browser: stuck on "Just a moment…" | bot check | run headed (default), clear it by hand; the adapter never solves it |
| Browser: `selector_drift` | ChatGPT UI changed | `faceless browser doctor --headed`, update `faceless/browser/selectors.py` |
| Browser batch images on wrong beats | batches come back reordered | never trust order; `images record` each by looking |
| `The current stage is X, not Y` | out-of-order complete | `faceless next <p>`; `faceless reopen` to go back |
| Approval refused: artifact changed | edited after its gate passed | `faceless complete <p> <stage>` again, then approve |
| Captions out of sync | beats/props built from an old transcript | re-transcribe, `beats build --keep-directions`, re-render |
| Render shorter than narration (FF-RENDER-004) | stale props | render without `--keep-props` |

## Getting help from the agent

Paste the JSON error into your agent and say "fix this". The error names the command, the stage and usually the remedy; the skills tell the agent the rest.
