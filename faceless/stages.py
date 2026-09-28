"""The production state machine's vocabulary.

Two voice modes share one set of stages; only the ORDER differs.

  tts     brief -> script -> voice -> transcript -> visual_bible -> beats -> keyframes -> compose -> package
  upload  brief -> voice -> transcript -> script -> visual_bible -> beats -> keyframes -> compose -> package

In `tts` mode the script is written first and the voice is generated from it;
the transcript then verifies what was actually spoken. In `upload` mode the
creator's own recording is the source of truth, so it is transcribed first and
the script stage becomes "understand the narration" - the agent derives the
story structure, hook and payoff from the transcript.
"""
from __future__ import annotations

STAGE_ORDER = {
    "tts": ("brief", "script", "voice", "transcript", "visual_bible", "beats", "keyframes", "compose", "package"),
    "upload": ("brief", "voice", "transcript", "script", "visual_bible", "beats", "keyframes", "compose", "package"),
}

STAGE_DIRS = {
    "brief": "01-brief",
    "script": "02-script",
    "voice": "03-voice",
    "transcript": "04-transcript",
    "visual_bible": "05-visual-bible",
    "beats": "06-beats",
    "keyframes": "07-keyframes",
    "compose": "08-compose",
    "package": "09-package",
}

STAGE_ARTIFACTS = {
    "brief": "01-brief/brief.json",
    "script": "02-script/script.json",
    "voice": "03-voice/voice_manifest.json",
    "transcript": "04-transcript/transcript.json",
    "visual_bible": "05-visual-bible/visual_bible.json",
    "beats": "06-beats/beat_manifest.json",
    "keyframes": "07-keyframes/keyframe_manifest.json",
    "compose": "08-compose/render_report.json",
    "package": "09-package/publishing_package.json",
}

STAGE_SCHEMAS = {stage: f"{stage.replace('_', '-')}.schema.json" for stage in STAGE_ARTIFACTS}

# Which skill an agent must read before working a stage.
STAGE_SKILLS = {
    "brief": "faceless-script",
    "script": "faceless-script",
    "voice": "faceless-voice",
    "transcript": "faceless-transcribe",
    "visual_bible": "faceless-visuals",
    "beats": "faceless-visuals",
    "keyframes": "faceless-visuals",
    "compose": "faceless-compose",
    "package": "faceless-package",
}

# The only moments that need the human. Everything else is gated by code + review.
HUMAN_GATES = {
    "script": "cp1_story",
    "compose": "cp2_final_preview",
}

FORMATS = ("short", "longform")
VOICE_MODES = tuple(STAGE_ORDER)
HOSTS = ("codex", "claude-code", "api", "manual")


def order_for(voice_mode: str) -> tuple[str, ...]:
    try:
        return STAGE_ORDER[voice_mode]
    except KeyError as exc:
        raise ValueError(f"Unknown voice mode {voice_mode!r}; expected one of {VOICE_MODES}") from exc
