"""Configuration for the Google Flow browser adapter.

Security boundaries (same as the ChatGPT adapter):
  * the persistent profile lives OUTSIDE the repository
  * the account owner signs in by hand; the agent never types Google credentials
  * no cookies, tokens or storage are ever read, logged or copied
"""
from __future__ import annotations

import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

ADAPTER_VERSION = "0.1.0"
DEFAULT_PROFILE = Path.home() / ".faceless" / "browser-profiles" / "google-flow"
FLOW_PROJECT_URL = "https://flow.google.com/project/3c980ff2-5d87-436d-8275-ec633a1dbdfb"   # "Tech Reels - ChatGPT Dots", you@example.com


@dataclass
class FlowConfig:
    profile_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("FACELESS_FLOW_PROFILE", str(DEFAULT_PROFILE))).expanduser())
    diagnostics_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("FACELESS_FLOW_DIAGNOSTICS",
                       str(Path.home() / ".faceless" / "diagnostics" / "flow"))).expanduser())
    project_url: str = field(default_factory=lambda: os.environ.get(
        "FACELESS_FLOW_PROJECT_URL", FLOW_PROJECT_URL))
    # Real Chrome, not bundled Chromium: Google sign-in rejects the bundled build.
    channel: str = field(default_factory=lambda: os.environ.get("FACELESS_FLOW_CHANNEL", "chrome"))
    nav_timeout_s: int = int(os.environ.get("FACELESS_FLOW_NAV_TIMEOUT", "90"))

    def ensure_dirs(self) -> "FlowConfig":
        for d in (self.profile_dir, self.diagnostics_dir):
            d.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(d, stat.S_IRWXU)
            except OSError:
                pass
        return self

    def describe(self) -> dict:
        d = {k: (str(v) if isinstance(v, Path) else v) for k, v in asdict(self).items()}
        d["adapter_version"] = ADAPTER_VERSION
        return d
