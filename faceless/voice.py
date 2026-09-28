"""Voice stage: generate narration with AI, or ingest the creator's own recording."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .config import load_channel
from .engine import ProductionEngine, StateError
from .io import atomic_write_json, load_json, sha256_file, sha256_text, utc_now
from .media import concat_audio, duration, normalize_voice, probe
from .providers import chunk_text
from .providers.tts import select_tts

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".webm", ".mp4", ".mov"}


def apply_pronunciations(text: str, mapping: dict[str, str]) -> str:
    """Respell words the voice gets wrong (script.pronunciation: {"word": "respelling"}).
    Only the TTS input changes; captions still show the real spelling."""
    for word, respelling in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(word, respelling)
    return text


def plan_generation(engine: ProductionEngine, provider: str = "auto", voice_id: str = "", model: str = "") -> dict[str, Any]:
    state = engine.state()
    if state["voice_mode"] != "tts":
        raise StateError("This project uses your own recording. Use `faceless voice ingest` instead.")
    script_path = engine.artifact_path("script")
    if not script_path.exists():
        raise StateError("Write and approve 02-script/script.json before generating the voice")
    if state["approvals"]["cp1_story"]["status"] != "approved":
        raise StateError("The script has not been approved (cp1_story). Paid voice generation waits for that.")
    script = load_json(script_path)
    tts = select_tts(load_channel(), provider, voice_id, model)
    spoken = apply_pronunciations(script["narration"], script.get("pronunciation", {}))
    chunks = chunk_text(spoken, tts.max_chars)
    chars = sum(len(c) for c in chunks)
    return {
        "provider": tts.name,
        "model": getattr(tts, "model", ""),
        "voice_id": getattr(tts, "voice_id", getattr(tts, "voice", "")),
        "chunks": len(chunks),
        "characters": chars,
        "estimated_usd": round(tts.estimate_usd(chars), 4),
        "worst_case_usd": round(tts.estimate_usd(chars) * 3, 4),
        "note": "Worst case assumes every chunk needs 2 retakes. Retakes are capped at 2 per chunk.",
        "_tts": tts,
        "_chunks": chunks,
    }


def generate(engine: ProductionEngine, provider: str = "auto", voice_id: str = "", model: str = "", only_chunk: str = "") -> dict[str, Any]:
    """Synthesize chunk by chunk. Resumable: a chunk whose text is unchanged is reused, not re-bought.
    `only_chunk` forces a paid retake of just that chunk."""
    plan = plan_generation(engine, provider, voice_id, model)
    tts, chunks = plan["_tts"], plan["_chunks"]
    project = engine.project_root
    chunk_dir = project / "03-voice" / "chunks"
    index_path = chunk_dir / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    manifest_chunks, parts = [], []
    for number, text in enumerate(chunks, 1):
        chunk_id = f"C{number:03d}"
        dest = chunk_dir / f"{chunk_id}.mp3"
        digest = sha256_text(f"{tts.name}|{plan['voice_id']}|{plan['model']}|{text}")
        prior = index.get(chunk_id, {})
        takes = prior.get("takes", 0)
        reuse = dest.exists() and prior.get("text_sha256") == digest and chunk_id != only_chunk
        if not reuse:
            if prior.get("text_sha256") == digest and takes >= 3:
                raise StateError(f"{chunk_id} already has 3 paid takes. Stop and listen before spending more.")
            cost = tts.estimate_usd(len(text))
            engine.record_cost(cost, tts.name, f"tts:{engine.project_root.name}:{chunk_id}:{digest[:12]}:{takes + 1}", "voice")
            tts.synthesize(text, dest, previous_text=chunks[number - 2] if number > 1 else "", next_text=chunks[number] if number < len(chunks) else "")
            takes = takes + 1 if prior.get("text_sha256") == digest else 1
            index[chunk_id] = {"text_sha256": digest, "takes": takes, "generated_at": utc_now()}
            atomic_write_json(index_path, index)
        parts.append(dest)
        manifest_chunks.append({"chunk_id": chunk_id, "text": text, "path": str(dest.relative_to(project)), "duration_s": round(duration(dest), 3), "chars": len(text), "takes": takes})
    raw = concat_audio(parts, project / "03-voice" / "narration_raw.wav", gap_s=0.0)
    master = normalize_voice(raw, project / "03-voice" / "narration.wav")
    info = probe(master)
    manifest = {
        "version": "1.0",
        "mode": "tts",
        "provider": tts.name,
        "model": plan["model"],
        "voice_id": plan["voice_id"],
        "master_path": "03-voice/narration.wav",
        "master_sha256": sha256_file(master),
        "duration_s": round(info["duration_s"], 3),
        "sample_rate": info.get("sample_rate", 48000),
        "chunks": manifest_chunks,
        "cost_usd": round(engine.state()["budget"]["spent_usd"], 4),
    }
    atomic_write_json(engine.artifact_path("voice"), manifest)
    return manifest


def ingest(engine: ProductionEngine, source: Path) -> dict[str, Any]:
    """Bring in the creator's own narration. The original is kept untouched beside the master."""
    state = engine.state()
    if state["voice_mode"] != "upload":
        raise StateError("This project generates its voice with AI. Re-init with --voice upload to use your own recording.")
    source = Path(source).expanduser().resolve()
    if not source.exists():
        raise StateError(f"Audio file not found: {source}")
    if source.suffix.lower() not in AUDIO_EXTS:
        raise StateError(f"Unsupported audio type {source.suffix}; use one of {sorted(AUDIO_EXTS)}")
    project = engine.project_root
    original = project / "03-voice" / f"original{source.suffix.lower()}"
    shutil.copy2(source, original)
    master = normalize_voice(original, project / "03-voice" / "narration.wav")
    info = probe(master)
    manifest = {
        "version": "1.0",
        "mode": "upload",
        "provider": "upload",
        "model": "",
        "voice_id": "",
        "original_path": str(original.relative_to(project)),
        "master_path": "03-voice/narration.wav",
        "master_sha256": sha256_file(master),
        "duration_s": round(info["duration_s"], 3),
        "sample_rate": info.get("sample_rate", 48000),
        "chunks": [],
        "cost_usd": 0.0,
    }
    atomic_write_json(engine.artifact_path("voice"), manifest)
    return manifest
