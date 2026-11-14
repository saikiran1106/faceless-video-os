"""Instagram Graph API tools for channel intelligence and publishing setup."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from tools.base_tool import (
    BaseTool,
    DependencyError,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LONG_TOKEN_FILE = ROOT / ".secrets" / "instagram-long-token.json"
GRAPH_VERSION = "v23.0"
GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _redact_url_token(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, "[REDACTED]" if key == "access_token" else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _sanitize_graph_payload(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if key == "access_token":
                clean[key] = "[REDACTED]"
            elif key in {"next", "previous"} and isinstance(item, str):
                clean[key] = _redact_url_token(item)
            else:
                clean[key] = _sanitize_graph_payload(item)
        return clean
    if isinstance(value, list):
        return [_sanitize_graph_payload(item) for item in value]
    return value


def _load_env_file() -> dict[str, str]:
    env_path = ROOT / ".env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        values[key.strip()] = value
    return values


def _load_token(token_file: str | None = None) -> str:
    path = Path(token_file).expanduser().resolve() if token_file else DEFAULT_LONG_TOKEN_FILE
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        token = data.get("access_token") or data.get("response", {}).get("access_token")
        if token:
            return token
    env = _load_env_file()
    token = os.environ.get("INSTA_ACCESS_TOKEN") or env.get("INSTA_ACCESS_TOKEN")
    if token:
        return token
    raise DependencyError(
        "Missing Instagram access token. Expected .secrets/instagram-long-token.json "
        "or INSTA_ACCESS_TOKEN in .env."
    )


def _load_app_credentials() -> tuple[str | None, str | None]:
    env = _load_env_file()
    app_id = os.environ.get("INSTA_APP_ID") or env.get("INSTA_APP_ID")
    app_secret = (
        os.environ.get("INSTA_APP_SECRET")
        or os.environ.get("INSTA_APP_SECRETS")
        or env.get("INSTA_APP_SECRET")
        or env.get("INSTA_APP_SECRETS")
    )
    return app_id, app_secret


def _graph_get(path: str, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if params is None:
        params = {}
    params = dict(params)
    params["access_token"] = token
    url = path if path.startswith("https://") else f"{GRAPH_ROOT}/{path.lstrip('/')}"
    try:
        response = requests.get(url, params=params, timeout=10)
        data = _sanitize_graph_payload(response.json())
    except Exception as exc:  # noqa: BLE001 - preserve error for artifact
        return {"error": {"message": str(exc), "type": "RequestError"}}
    if response.status_code >= 400 and "error" not in data:
        data["error"] = {"message": response.text, "code": response.status_code}
    return data


def _paged_graph_get(
    path: str,
    token: str,
    params: dict[str, Any] | None = None,
    *,
    max_pages: int = 10,
) -> dict[str, Any]:
    first = _graph_get(path, token, params)
    items = list(first.get("data", [])) if isinstance(first.get("data"), list) else []
    errors = []
    if first.get("error"):
        errors.append(first["error"])
    next_url = first.get("paging", {}).get("next")
    pages = 1
    while next_url and pages < max_pages:
        page = _graph_get(next_url, token, {})
        if page.get("error"):
            errors.append(page["error"])
            break
        items.extend(page.get("data", []))
        next_url = page.get("paging", {}).get("next")
        pages += 1
    return {"data": items, "pages_fetched": pages, "errors": errors}


class InstagramGraphSnapshot(BaseTool):
    """Fetch Instagram profile, media, insights, comments, and Page linkage."""

    name = "instagram_graph_snapshot"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API
    dependencies = ["python:requests"]
    install_instructions = (
        "Create a Meta app, generate a Facebook Login token with Instagram "
        "permissions, exchange it for a long-lived token, and save it to "
        ".secrets/instagram-long-token.json."
    )
    capability = "instagram_analytics"
    provider = "meta_graph"
    capabilities = [
        "facebook_page_inventory",
        "instagram_account_profile",
        "instagram_media_inventory",
        "instagram_media_insights",
        "instagram_comments",
        "instagram_messages_permission_check",
    ]
    resource_profile = ResourceProfile(network_required=True)
    best_for = [
        "Fetching Instagram account and Reel/Post analytics",
        "Linking Instagram media performance into growth-agent memory",
        "Checking organic publishing and messaging permissions",
    ]
    supports = {
        "token_source": ".secrets/instagram-long-token.json or INSTA_ACCESS_TOKEN",
        "quota_cost_usd": 0.0,
    }
    input_schema = {
        "type": "object",
        "properties": {
            "token_file": {"type": "string"},
            "media_limit": {"type": "integer", "default": 100},
            "comments_limit": {"type": "integer", "default": 25},
            "max_pages": {"type": "integer", "default": 5},
        },
    }

    def get_status(self) -> ToolStatus:
        try:
            self.check_dependencies()
            _load_token()
        except Exception:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def _debug_token(self, token: str) -> dict[str, Any]:
        app_id, app_secret = _load_app_credentials()
        if not app_id or not app_secret:
            return {"error": "Missing INSTA_APP_ID or INSTA_APP_SECRET(S)"}
        return _graph_get(
            "debug_token",
            token=f"{app_id}|{app_secret}",
            params={"input_token": token},
        )

    def _account_insights(self, ig_id: str, token: str) -> dict[str, Any]:
        metrics = [
            "reach",
            "profile_views",
            "website_clicks",
            "accounts_engaged",
            "total_interactions",
        ]
        results: dict[str, Any] = {}
        for metric in metrics:
            result = _graph_get(
                f"{ig_id}/insights",
                token,
                {"metric": metric, "period": "day"},
            )
            message = result.get("error", {}).get("message", "")
            if "metric_type=total_value" in message:
                result = _graph_get(
                    f"{ig_id}/insights",
                    token,
                    {"metric": metric, "period": "day", "metric_type": "total_value"},
                )
            results[metric] = result
        return results

    def _media_insights(self, media_id: str, token: str) -> dict[str, Any]:
        metrics = [
            "reach",
            "saved",
            "likes",
            "comments",
            "shares",
            "plays",
            "ig_reels_avg_watch_time",
        ]
        results: dict[str, Any] = {}
        for metric in metrics:
            results[metric] = _graph_get(
                f"{media_id}/insights",
                token,
                {"metric": metric},
            )
        return results

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        token = _load_token(inputs.get("token_file"))
        media_limit = int(inputs.get("media_limit", 100))
        comments_limit = int(inputs.get("comments_limit", 25))
        max_pages = int(inputs.get("max_pages", 5))

        debug = self._debug_token(token)
        me = _graph_get("me", token, {"fields": "id,name"})
        pages = _paged_graph_get(
            "me/accounts",
            token,
            {
                "fields": (
                    "id,name,category,access_token,"
                    "instagram_business_account{"
                    "id,username,name,biography,followers_count,follows_count,"
                    "media_count,profile_picture_url,website"
                    "}"
                ),
                "limit": 100,
            },
            max_pages=max_pages,
        )

        instagram_accounts = []
        for page in pages.get("data", []):
            ig = page.get("instagram_business_account")
            if not ig:
                continue
            page_token = page.get("access_token") or token
            ig_id = ig["id"]
            profile = _graph_get(
                ig_id,
                page_token,
                {
                    "fields": (
                        "id,username,name,biography,followers_count,follows_count,"
                        "media_count,profile_picture_url,website"
                    )
                },
            )
            media = _paged_graph_get(
                f"{ig_id}/media",
                page_token,
                {
                    "fields": (
                        "id,caption,comments_count,like_count,media_type,"
                        "media_product_type,media_url,permalink,thumbnail_url,"
                        "timestamp,username,children{id,media_type,media_url,thumbnail_url}"
                    ),
                    "limit": min(media_limit, 100),
                },
                max_pages=max_pages,
            )

            enriched_media = []
            for item in media.get("data", [])[:media_limit]:
                media_id = item["id"]
                enriched_media.append({
                    **item,
                    "insights": self._media_insights(media_id, page_token),
                    "comments": _paged_graph_get(
                        f"{media_id}/comments",
                        page_token,
                        {"fields": "id,text,username,timestamp,like_count", "limit": comments_limit},
                        max_pages=1,
                    ),
                })

            conversations = _paged_graph_get(
                f"{page['id']}/conversations",
                page_token,
                {
                    "platform": "instagram",
                    "fields": "id,updated_time,participants,message_count",
                    "limit": 25,
                },
                max_pages=1,
            )

            instagram_accounts.append({
                "page": {k: v for k, v in page.items() if k != "access_token"},
                "profile": profile,
                "account_insights": self._account_insights(ig_id, page_token),
                "media": enriched_media,
                "media_fetch": {
                    "count": len(enriched_media),
                    "pages_fetched": media.get("pages_fetched"),
                    "errors": media.get("errors"),
                },
                "conversations": conversations,
            })

        return ToolResult(
            True,
            data={
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "graph_version": GRAPH_VERSION,
                "debug_token": debug,
                "me": me,
                "pages": {
                    "count": len(pages.get("data", [])),
                    "items": [
                        {k: v for k, v in page.items() if k != "access_token"}
                        for page in pages.get("data", [])
                    ],
                    "errors": pages.get("errors", []),
                },
                "instagram_accounts": instagram_accounts,
                "token_note": "Long-lived user tokens commonly expire after about 60 days.",
            },
        )


class InstagramTokenDebug(BaseTool):
    """Inspect a Meta token without printing the token itself."""

    name = "instagram_token_debug"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API
    dependencies = ["python:requests"]
    capability = "instagram_analytics"
    provider = "meta_graph"
    capabilities = ["token_debug"]
    resource_profile = ResourceProfile(network_required=True)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        token = _load_token(inputs.get("token_file"))
        app_id, app_secret = _load_app_credentials()
        if not app_id or not app_secret:
            return ToolResult(False, error="Missing INSTA_APP_ID or INSTA_APP_SECRET(S)")
        data = _graph_get(
            "debug_token",
            token=f"{app_id}|{app_secret}",
            params={"input_token": token},
        )
        expires_at = data.get("data", {}).get("expires_at")
        return ToolResult(
            True,
            data={
                "debug_token": data,
                "expires_at_iso": (
                    datetime.fromtimestamp(expires_at, timezone.utc).isoformat()
                    if expires_at else None
                ),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
        )
