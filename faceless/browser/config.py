"""Configuration and persistent-profile management for the faceless browser adapter.

Security boundaries (see docs/browser-imagegen.md):
  * the persistent Chromium profile lives OUTSIDE the repository
  * no cookies, tokens or storage are ever read, logged or copied
  * remote debugging is never exposed
"""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field, asdict
from pathlib import Path

ADAPTER_VERSION = "1.0.0"
DEFAULT_PROFILE = Path.home() / ".faceless" / "browser-profiles" / "chatgpt-imagegen"
CHATGPT_URL = "https://chatgpt.com"
# Optional: a ChatGPT Project URL (https://chatgpt.com/g/g-p-.../project). A Project
# carries your channel's accumulated context (style notes, characters, past
# episodes) across chats, which keeps frames on-model. When unset, generation
# runs in a fresh chat at chatgpt.com.
CHATGPT_PROJECT_URL = ""


@dataclass
class BrowserConfig:
    """Every value is overridable by env var or CLI flag."""

    profile_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("FACELESS_BROWSER_PROFILE", str(DEFAULT_PROFILE))).expanduser())
    downloads_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("FACELESS_BROWSER_DOWNLOADS",
                       str(Path.home() / ".faceless" / "downloads"))).expanduser())
    diagnostics_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("FACELESS_BROWSER_DIAGNOSTICS",
                       str(Path.home() / ".faceless" / "diagnostics"))).expanduser())
    traces_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("FACELESS_BROWSER_TRACES",
                       str(Path.home() / ".faceless" / "traces"))).expanduser())
    # Traces are rich but contain full page content, so they are opt-in and are
    # written only for a technical failure, never for a routine job.
    trace_on_failure: bool = field(default_factory=lambda:
                                   os.environ.get("FACELESS_BROWSER_TRACE", "1")
                                   not in ("0", "false", "False"))
    # PRODUCTION DEFAULT IS HEADED. Headless Chromium stalls on Cloudflare's
    # "Just a moment..." interstitial, which hangs an unattended run. Debugging
    # can still opt in explicitly: FACELESS_BROWSER_HEADLESS=1.
    headless: bool = field(default_factory=lambda:
                           os.environ.get("FACELESS_BROWSER_HEADLESS", "0") in ("1", "true", "True"))
    # generous: image generation is slow and a timeout must never trigger a resubmit
    generation_timeout_s: int = int(os.environ.get("FACELESS_BROWSER_GEN_TIMEOUT", "180"))
    upload_timeout_s: int = int(os.environ.get("FACELESS_BROWSER_UPLOAD_TIMEOUT", "120"))
    # The send control stays disabled while attachments process; this is how
    # long we will wait for it to become clickable.
    send_ready_timeout_s: int = int(os.environ.get("FACELESS_BROWSER_SEND_READY", "120"))
    send_confirm_timeout_s: int = int(os.environ.get("FACELESS_BROWSER_SEND_CONFIRM", "25"))
    nav_timeout_s: int = int(os.environ.get("FACELESS_BROWSER_NAV_TIMEOUT", "90"))
    max_technical_retries: int = int(os.environ.get("FACELESS_BROWSER_MAX_RETRIES", "2"))
    max_creative_attempts: int = int(os.environ.get("FACELESS_BROWSER_MAX_CREATIVE", "2"))
    chatgpt_url: str = CHATGPT_URL
    project_url: str = field(default_factory=lambda: os.environ.get(
        "FACELESS_CHATGPT_PROJECT_URL", CHATGPT_PROJECT_URL))

    def ensure_dirs(self) -> "BrowserConfig":
        for d in (self.profile_dir, self.downloads_dir, self.diagnostics_dir,
                  self.traces_dir):
            d.mkdir(parents=True, exist_ok=True)
            try:  # best effort; not supported on every filesystem
                os.chmod(d, stat.S_IRWXU)  # 0700 - owner only
            except OSError:
                pass
        return self

    def describe(self) -> dict:
        d = {k: (str(v) if isinstance(v, Path) else v) for k, v in asdict(self).items()}
        d["adapter_version"] = ADAPTER_VERSION
        return d

    def profile_inside_repo(self, repo_root: Path) -> bool:
        """Guard: the profile must never live inside the git worktree."""
        try:
            self.profile_dir.resolve().relative_to(Path(repo_root).resolve())
            return True
        except ValueError:
            return False
