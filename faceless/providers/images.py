"""Direct image-API adapter (OpenAI Images). Used by the `api` host.

The `codex` host uses Codex's built-in image tool, the `claude-code` host drives
ChatGPT in a browser (faceless/browser), and the `manual` host prints prompts for
a human. All four consume the same image_jobs.json.
"""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from ..config import env, has_key
from . import ProviderError

SIZES = {"9:16": "1024x1536", "16:9": "1536x1024", "1:1": "1024x1024"}


class OpenAIImages:
    name = "openai"

    def __init__(self, model: str = "", quality: str = ""):
        if not has_key("OPENAI_API_KEY"):
            raise ProviderError("OPENAI_API_KEY is not set")
        self.model = model or env("FACELESS_OPENAI_IMAGE_MODEL", "gpt-image-1")
        self.quality = quality or env("FACELESS_OPENAI_IMAGE_QUALITY", "medium")

    def estimate_usd(self, count: int) -> float:
        per_image = {"low": 0.02, "medium": 0.07, "high": 0.25}.get(self.quality, 0.07)
        return count * float(env("FACELESS_OPENAI_IMAGE_USD", str(per_image)))

    def generate(self, prompt: str, aspect: str, dest: Path, reference_paths: list[str] | None = None) -> Path:
        base = env("OPENAI_BASE_URL", "https://api.openai.com/v1")
        headers = {"Authorization": f"Bearer {env('OPENAI_API_KEY')}"}
        size = SIZES.get(aspect, "1024x1536")
        refs = [Path(p) for p in (reference_paths or []) if Path(p).exists()]
        if refs:
            # The edits endpoint accepts reference images that steer identity and style.
            files = [("image[]", (p.name, p.open("rb"), "image/png")) for p in refs[:10]]
            try:
                response = requests.post(f"{base}/images/edits", headers=headers, data={"model": self.model, "prompt": prompt, "size": size, "quality": self.quality, "n": "1"}, files=files, timeout=600)
            finally:
                for _, (_, handle, _) in files:
                    handle.close()
        else:
            response = requests.post(f"{base}/images/generations", headers=headers, json={"model": self.model, "prompt": prompt, "size": size, "quality": self.quality, "n": 1}, timeout=600)
        if response.status_code != 200:
            raise ProviderError(f"OpenAI Images {response.status_code}: {response.text[:300]}")
        item = response.json()["data"][0]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if item.get("b64_json"):
            dest.write_bytes(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            dest.write_bytes(requests.get(item["url"], timeout=120).content)
        else:
            raise ProviderError("OpenAI Images returned no image data")
        return dest
