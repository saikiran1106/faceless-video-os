"""YouTube Data/Analytics API tools for channel learning and publishing.

These tools intentionally use OAuth user consent, not service accounts.
The Google Cloud project owns API quota; the signed-in YouTube account owns
the channel permission.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

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
DEFAULT_CLIENT_SECRETS = ROOT / ".secrets" / "youtube-oauth-client.json"
DEFAULT_TOKEN_FILE = ROOT / ".secrets" / "youtube-token.json"

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
]


def _optional_google_imports() -> dict[str, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise DependencyError(
            "YouTube API tools require google-api-python-client and "
            "google-auth-oauthlib. Install with: pip install -r requirements.txt"
        ) from exc
    return {
        "Request": Request,
        "Credentials": Credentials,
        "InstalledAppFlow": InstalledAppFlow,
        "build": build,
        "MediaFileUpload": MediaFileUpload,
    }


def _resolve_path(value: str | None, default: Path) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    return default


def _load_credentials(
    *,
    client_secrets: str | None = None,
    token_file: str | None = None,
    interactive_auth: bool = False,
):
    google = _optional_google_imports()
    client_path = _resolve_path(
        client_secrets or os.environ.get("YOUTUBE_CLIENT_SECRETS"),
        DEFAULT_CLIENT_SECRETS,
    )
    token_path = _resolve_path(
        token_file or os.environ.get("YOUTUBE_TOKEN_FILE"),
        DEFAULT_TOKEN_FILE,
    )

    creds = None
    if token_path.is_file():
        creds = google["Credentials"].from_authorized_user_file(
            str(token_path), YOUTUBE_SCOPES
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(google["Request"]())

    if not creds or not creds.valid:
        if not interactive_auth:
            raise DependencyError(
                "No valid YouTube OAuth token. Run interactive auth first with "
                "interactive_auth=true, or create a token at "
                f"{token_path} using client secrets at {client_path}."
            )
        if not client_path.is_file():
            raise DependencyError(
                "Missing YouTube OAuth client secrets file. Download an OAuth "
                "Desktop client JSON from Google Cloud Console and save it to "
                f"{client_path}, or set YOUTUBE_CLIENT_SECRETS."
            )
        flow = google["InstalledAppFlow"].from_client_secrets_file(
            str(client_path), YOUTUBE_SCOPES
        )
        creds = flow.run_local_server(
            port=0,
            prompt="consent",
            authorization_prompt_message=(
                "Open this URL and sign in with you@example.com: {url}"
            ),
        )

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _service(api: str, version: str, inputs: dict[str, Any]):
    google = _optional_google_imports()
    creds = _load_credentials(
        client_secrets=inputs.get("client_secrets"),
        token_file=inputs.get("token_file"),
        interactive_auth=bool(inputs.get("interactive_auth", False)),
    )
    return google["build"](api, version, credentials=creds)


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _api_call(request: Any) -> dict[str, Any]:
    """Execute a Google API request, returning an error object on failure."""
    try:
        return request.execute()
    except Exception as exc:  # noqa: BLE001 - preserve API error for artifact
        return {"error": str(exc)}


def _analytics_query(
    analytics: Any,
    *,
    start_date: str,
    end_date: str,
    metrics: str,
    dimensions: str | None = None,
    filters: str | None = None,
    sort: str | None = None,
    max_results: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": metrics,
    }
    if dimensions:
        params["dimensions"] = dimensions
    if filters:
        params["filters"] = filters
    if sort:
        params["sort"] = sort
    if max_results:
        params["maxResults"] = max_results
    return _api_call(analytics.reports().query(**params))


class YouTubeChannelSnapshot(BaseTool):
    """Fetch channel metadata, recent videos, and analytics for learning."""

    name = "youtube_channel_snapshot"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API
    dependencies = [
        "python:googleapiclient",
        "python:google_auth_oauthlib",
        "python:google.oauth2.credentials",
    ]
    install_instructions = (
        "pip install -r requirements.txt; then place OAuth Desktop client JSON "
        "at .secrets/youtube-oauth-client.json and authenticate as you@example.com."
    )
    capability = "youtube_analytics"
    provider = "youtube"
    capabilities = ["channel_metadata", "recent_video_metadata", "channel_analytics"]
    resource_profile = ResourceProfile(network_required=True)
    best_for = [
        "Learning a YouTube channel niche from existing videos",
        "Fetching channel and recent-video metadata",
        "Pulling daily analytics for strategy planning",
    ]
    not_good_for = ["Downloading private Studio-only retention graphs"]
    supports = {
        "account": "you@example.com via OAuth",
        "default_video_limit": 50,
        "default_analytics_days": 28,
        "quota_cost_usd": 0.0,
    }

    input_schema = {
        "type": "object",
        "properties": {
            "max_videos": {"type": "integer", "default": 50},
            "analytics_days": {"type": "integer", "default": 28},
            "client_secrets": {"type": "string"},
            "token_file": {"type": "string"},
            "interactive_auth": {"type": "boolean", "default": False},
        },
    }

    def get_status(self) -> ToolStatus:
        try:
            self.check_dependencies()
        except DependencyError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        youtube = _service("youtube", "v3", inputs)
        analytics = _service("youtubeAnalytics", "v2", inputs)
        max_videos = int(inputs.get("max_videos", 50))
        analytics_days = int(inputs.get("analytics_days", 28))

        channel_response = youtube.channels().list(
            part="snippet,statistics,contentDetails,brandingSettings",
            mine=True,
        ).execute()
        channels = channel_response.get("items", [])
        if not channels:
            return ToolResult(False, error="No YouTube channel found for OAuth account.")

        channel = channels[0]
        uploads_playlist = (
            channel.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )

        video_ids: list[str] = []
        page_token = None
        while uploads_playlist and len(video_ids) < max_videos:
            playlist_response = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=uploads_playlist,
                maxResults=min(50, max_videos - len(video_ids)),
                pageToken=page_token,
            ).execute()
            video_ids.extend(
                item["contentDetails"]["videoId"]
                for item in playlist_response.get("items", [])
                if item.get("contentDetails", {}).get("videoId")
            )
            page_token = playlist_response.get("nextPageToken")
            if not page_token:
                break

        videos: list[dict[str, Any]] = []
        for batch in _chunks(video_ids, 50):
            video_response = youtube.videos().list(
                part="snippet,statistics,contentDetails,status",
                id=",".join(batch),
                maxResults=len(batch),
            ).execute()
            videos.extend(video_response.get("items", []))

        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=max(1, analytics_days - 1))
        analytics_response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics=(
                "views,estimatedMinutesWatched,averageViewDuration,"
                "subscribersGained,subscribersLost,likes,comments,shares"
            ),
            dimensions="day",
            sort="day",
        ).execute()

        return ToolResult(
            True,
            data={
                "channel": channel,
                "recent_videos": videos,
                "analytics": analytics_response,
                "analytics_window": {
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "days": analytics_days,
                },
                "quota_note": "YouTube APIs consume quota units, not Google Cloud dollars.",
            },
        )


class YouTubeDeepChannelSnapshot(BaseTool):
    """Fetch detailed channel/video analytics for growth-agent memory."""

    name = "youtube_deep_channel_snapshot"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API
    dependencies = [
        "python:googleapiclient",
        "python:google_auth_oauthlib",
        "python:google.oauth2.credentials",
    ]
    install_instructions = (
        "pip install -r requirements.txt; authenticate as you@example.com."
    )
    capability = "youtube_analytics"
    provider = "youtube"
    capabilities = [
        "full_video_inventory",
        "per_video_analytics",
        "traffic_source_analytics",
        "comment_sampling",
        "caption_track_inventory",
        "playlist_inventory",
    ]
    resource_profile = ResourceProfile(network_required=True)
    best_for = [
        "Building a channel niche model",
        "Understanding which videos and topics drive growth",
        "Preparing content automation memory",
    ]
    supports = {
        "account": "you@example.com via OAuth",
        "quota_cost_usd": 0.0,
        "default_analytics_days": 90,
    }
    input_schema = {
        "type": "object",
        "properties": {
            "max_videos": {"type": "integer", "default": 200},
            "analytics_days": {"type": "integer", "default": 90},
            "comments_per_video": {"type": "integer", "default": 20},
            "client_secrets": {"type": "string"},
            "token_file": {"type": "string"},
            "interactive_auth": {"type": "boolean", "default": False},
        },
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        youtube = _service("youtube", "v3", inputs)
        analytics = _service("youtubeAnalytics", "v2", inputs)
        max_videos = int(inputs.get("max_videos", 200))
        comments_per_video = int(inputs.get("comments_per_video", 20))
        analytics_days = int(inputs.get("analytics_days", 90))

        channel_response = youtube.channels().list(
            part=(
                "snippet,statistics,contentDetails,brandingSettings,status,"
                "topicDetails"
            ),
            mine=True,
        ).execute()
        channels = channel_response.get("items", [])
        if not channels:
            return ToolResult(False, error="No YouTube channel found for OAuth account.")
        channel = channels[0]
        uploads_playlist = (
            channel.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )

        video_ids: list[str] = []
        upload_items: list[dict[str, Any]] = []
        page_token = None
        while uploads_playlist and len(video_ids) < max_videos:
            playlist_response = youtube.playlistItems().list(
                part="snippet,contentDetails,status",
                playlistId=uploads_playlist,
                maxResults=min(50, max_videos - len(video_ids)),
                pageToken=page_token,
            ).execute()
            for item in playlist_response.get("items", []):
                video_id = item.get("contentDetails", {}).get("videoId")
                if video_id:
                    video_ids.append(video_id)
                    upload_items.append(item)
            page_token = playlist_response.get("nextPageToken")
            if not page_token:
                break

        videos: list[dict[str, Any]] = []
        video_parts = (
            "snippet,statistics,contentDetails,status,topicDetails,"
            "recordingDetails,liveStreamingDetails,localizations,player"
        )
        for batch in _chunks(video_ids, 50):
            video_response = youtube.videos().list(
                part=video_parts,
                id=",".join(batch),
                maxResults=len(batch),
            ).execute()
            videos.extend(video_response.get("items", []))

        playlists = _api_call(
            youtube.playlists().list(
                part="snippet,contentDetails,status",
                mine=True,
                maxResults=50,
            )
        )

        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=max(1, analytics_days - 1))
        start_s = start.isoformat()
        end_s = end.isoformat()

        core_metrics = (
            "views,estimatedMinutesWatched,averageViewDuration,"
            "averageViewPercentage,subscribersGained,subscribersLost,"
            "likes,comments,shares"
        )

        channel_analytics = {
            "daily": _analytics_query(
                analytics,
                start_date=start_s,
                end_date=end_s,
                metrics=core_metrics,
                dimensions="day",
                sort="day",
            ),
            "by_video": _analytics_query(
                analytics,
                start_date=start_s,
                end_date=end_s,
                metrics=core_metrics,
                dimensions="video",
                sort="-views",
                max_results=max_videos,
            ),
            "traffic_sources": _analytics_query(
                analytics,
                start_date=start_s,
                end_date=end_s,
                metrics="views,estimatedMinutesWatched",
                dimensions="insightTrafficSourceType",
                sort="-views",
            ),
            "countries": _analytics_query(
                analytics,
                start_date=start_s,
                end_date=end_s,
                metrics="views,estimatedMinutesWatched,averageViewDuration",
                dimensions="country",
                sort="-views",
                max_results=25,
            ),
            "subscribed_status": _analytics_query(
                analytics,
                start_date=start_s,
                end_date=end_s,
                metrics="views,estimatedMinutesWatched,averageViewDuration",
                dimensions="subscribedStatus",
                sort="-views",
            ),
        }

        per_video_analytics: dict[str, dict[str, Any]] = {}
        comments: dict[str, Any] = {}
        captions: dict[str, Any] = {}
        for video_id in video_ids:
            per_video_analytics[video_id] = {
                "daily": _analytics_query(
                    analytics,
                    start_date=start_s,
                    end_date=end_s,
                    metrics=core_metrics,
                    dimensions="day",
                    filters=f"video=={video_id}",
                    sort="day",
                ),
                "traffic_sources": _analytics_query(
                    analytics,
                    start_date=start_s,
                    end_date=end_s,
                    metrics="views,estimatedMinutesWatched",
                    dimensions="insightTrafficSourceType",
                    filters=f"video=={video_id}",
                    sort="-views",
                ),
            }

            if comments_per_video > 0:
                comments[video_id] = _api_call(
                    youtube.commentThreads().list(
                        part="snippet,replies",
                        videoId=video_id,
                        maxResults=min(100, comments_per_video),
                        order="relevance",
                        textFormat="plainText",
                    )
                )
            captions[video_id] = _api_call(
                youtube.captions().list(part="snippet", videoId=video_id)
            )

        return ToolResult(
            True,
            data={
                "channel": channel,
                "upload_playlist_items": upload_items,
                "videos": videos,
                "playlists": playlists,
                "channel_analytics": channel_analytics,
                "per_video_analytics": per_video_analytics,
                "comments": comments,
                "captions": captions,
                "analytics_window": {
                    "start_date": start_s,
                    "end_date": end_s,
                    "days": analytics_days,
                },
                "quota_note": "YouTube APIs consume quota units, not Google Cloud dollars.",
            },
        )


class YouTubeUploadVideo(BaseTool):
    """Upload a rendered video to YouTube after approval."""

    name = "youtube_upload_video"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API
    dependencies = [
        "python:googleapiclient",
        "python:google_auth_oauthlib",
        "python:google.oauth2.credentials",
    ]
    install_instructions = (
        "pip install -r requirements.txt; authenticate with you@example.com; "
        "call dry_run first and upload private by default."
    )
    capability = "publishing"
    provider = "youtube"
    capabilities = ["youtube_video_upload", "youtube_metadata_upload"]
    resource_profile = ResourceProfile(network_required=True)
    side_effects = ["uploads a video to the authorized YouTube channel"]
    best_for = ["Approved YouTube uploads from OpenMontage render outputs"]
    not_good_for = ["Unapproved automated public posting"]
    supports = {
        "default_visibility": "private",
        "quota_cost_usd": 0.0,
        "quota_bucket": "videos.insert",
    }
    input_schema = {
        "type": "object",
        "required": ["video_path", "title"],
        "properties": {
            "video_path": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "category_id": {"type": "string", "default": "22"},
            "privacy_status": {
                "type": "string",
                "enum": ["private", "unlisted", "public"],
                "default": "private",
            },
            "made_for_kids": {"type": "boolean", "default": False},
            "client_secrets": {"type": "string"},
            "token_file": {"type": "string"},
            "interactive_auth": {"type": "boolean", "default": False},
        },
    }

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        video_path = Path(inputs.get("video_path", ""))
        return {
            "tool": self.name,
            "status": self.get_status().value,
            "would_upload": video_path.is_file(),
            "video_path": str(video_path),
            "privacy_status": inputs.get("privacy_status", "private"),
            "estimated_cost_usd": 0.0,
            "quota_note": (
                "YouTube upload uses the videos.insert quota bucket; it does "
                "not spend Google Cloud GenAI credits."
            ),
        }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        video_path = Path(inputs["video_path"]).expanduser().resolve()
        if not video_path.is_file():
            return ToolResult(False, error=f"Video file not found: {video_path}")

        google = _optional_google_imports()
        youtube = _service("youtube", "v3", inputs)
        body = {
            "snippet": {
                "title": inputs["title"],
                "description": inputs.get("description", ""),
                "tags": inputs.get("tags", []),
                "categoryId": inputs.get("category_id", "22"),
            },
            "status": {
                "privacyStatus": inputs.get("privacy_status", "private"),
                "selfDeclaredMadeForKids": bool(inputs.get("made_for_kids", False)),
            },
        }
        media = google["MediaFileUpload"](str(video_path), chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            _, response = request.next_chunk()

        return ToolResult(
            True,
            data={
                "video_id": response.get("id"),
                "url": f"https://www.youtube.com/watch?v={response.get('id')}",
                "privacy_status": body["status"]["privacyStatus"],
                "response": response,
            },
            artifacts=[str(video_path)],
        )
