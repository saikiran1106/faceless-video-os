"""studio_os CLI: browser automation for image + video generation.

  python -m studio_os.cli accounts show|doctor|login|keepalive    login manager for persistent browser profiles
  python -m studio_os.cli browser setup|doctor|generate|resume|status   ChatGPT image adapter (job store, resumable)
  python -m studio_os.cli flow setup|doctor|generate|harvest|...  Google Flow (Omni) video adapter
  python -m studio_os.cli fast storyboards|clips|...              parallel images + batch clips via each site's own API

Run from the `automation/` folder (or set PYTHONPATH=automation). Nothing here types credentials: you sign in by
hand once per profile and the login lives inside the profile directory, outside any git repo.
"""
from __future__ import annotations

import argparse
import sys

from . import accounts as accounts_mod
from .browser import cli as browser_cli
from .fast import cli as fast_cli
from .flow import cli as flow_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="studio_os", description="Browser automation for image and video generation")
    sub = parser.add_subparsers(dest="command", required=True)
    browser_cli.add_parser(sub)
    flow_cli.add_parser(sub)
    fast_cli.add_parser(sub)
    accounts_mod.add_parser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {"browser": browser_cli, "flow": flow_cli, "fast": fast_cli, "accounts": accounts_mod}
    return handlers[args.command].handle(args)


if __name__ == "__main__":
    sys.exit(main())
