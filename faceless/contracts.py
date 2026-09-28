from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import jsonschema

from .config import SCHEMA_ROOT


class ContractError(ValueError):
    pass


@lru_cache(maxsize=32)
def load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_ROOT / name
    if not path.exists():
        raise ContractError(f"Unknown schema: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate(name: str, payload: dict[str, Any]) -> None:
    try:
        jsonschema.Draft202012Validator(load_schema(name)).validate(payload)
    except jsonschema.ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        raise ContractError(f"{name} at {location}: {exc.message}") from exc
