"""YouTube Data API v3 — authenticated client for Kodiak Cakes ingest.

No unauthenticated scrape. YouTube ToS prohibits scraping html/youtube.com without API.
This module uses only the official API https://www.googleapis.com/youtube/v3 with credentials.

Auth priority:
  1. explicit api_key / access_token passed to YouTubeClient(...)
  2. env: YOUTUBE_API_KEY (public reads), YOUTUBE_ACCESS_TOKEN / GOOGLE_OAUTH_TOKEN (Bearer),
     or OAuth refresh flow: YOUTUBE_OAUTH_CLIENT_ID + YOUTUBE_OAUTH_CLIENT_SECRET + YOUTUBE_OAUTH_REFRESH_TOKEN
  3. AWS SSM Parameter Store: /heraldstack/shared/youtube-oauth (JSON with api_key / refresh_token) — best-effort, no error if missing.

Endpoints implemented (httpx, no googleapiclient required):
  - channels.list (id=forUsername or handle, part=snippet,contentDetails,statistics)
  - search.list (channelId, q, type=video, order=date/viewCount)
  - playlistItems.list (playlistId = uploads playlist from channel)
  - videos.list (id, part=snippet,contentDetails,statistics,status)
  - captions.list / download (via captions.download with alt=media)

Quotas: channels.list 1 unit, search.list 100 units, videos.list 1 unit, playlistItems 1 unit.
Default project quota 10k/day — search is expensive, prefer playlistItems for full enumeration.

Usage:
  from creative_automation.ingest.youtube import YouTubeClient
  yt = YouTubeClient()  # reads env/SSM
  yt.assert_credentials()  # raises MissingCredentialsError with guidance if absent
  ch = yt.get_channel(handle="@Kodiakcakes")  # or yt.get_channel(username="Kodiakcakes")
  vids = yt.list_channel_videos(channel_id=ch["id"], max_results=50)
  details = yt.get_videos([v["id"] for v in vids])
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import httpx  # type: ignore
except ImportError:
    httpx = None  # type: ignore

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"

# SSM fallback paths (mirrors tiktok/youtube deep docs)
SSM_YOUTUBE_PATH = os.getenv("YOUTUBE_SSM_PATH", "/heraldstack/shared/youtube-oauth")
SSM_TIKTOK_PATH = os.getenv("TIKTOK_SSM_PATH", "/heraldstack/shared/tiktok-oauth")


class MissingCredentialsError(RuntimeError):
    """Raised when no YouTube credentials are configured. Guidance included — never falls back to scrape."""


class YouTubeAPIError(RuntimeError):
    """API returned non-2xx. Carries status, body, and quota hint."""


def _ssm_get_json(path: str) -> dict | None:
    """Best-effort SSM fetch. Returns dict or None. No exception on missing creds."""
    try:
        import boto3  # type: ignore

        region = os.getenv("AWS_REGION", os.getenv("BEDROCK_REGION", "us-east-1"))
        client = boto3.client("ssm", region_name=region)
        resp = client.get_parameter(Name=path, WithDecryption=True)
        val = resp["Parameter"]["Value"]
        try:
            return json.loads(val)
        except ValueError:
            return {"value": val}
    except Exception:  # noqa: BLE001 — best-effort SSM fetch; None on missing creds
        return None


def _resolve_youtube_credentials(
    api_key: str | None = None,
    access_token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    refresh_token: str | None = None,
) -> dict:
    """Resolve credentials in priority order. Returns dict with keys present."""
    # explicit args first
    creds: dict[str, str] = {}
    if api_key:
        creds["api_key"] = api_key
    if access_token:
        creds["access_token"] = access_token

    # env second
    env_api = os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    env_token = os.getenv("YOUTUBE_ACCESS_TOKEN") or os.getenv("YOUTUBE_OAUTH_TOKEN") or os.getenv("GOOGLE_OAUTH_TOKEN")
    env_cid = os.getenv("YOUTUBE_OAUTH_CLIENT_ID") or os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    env_csec = os.getenv("YOUTUBE_OAUTH_CLIENT_SECRET") or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    env_refresh = os.getenv("YOUTUBE_OAUTH_REFRESH_TOKEN") or os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN")

    if not creds.get("api_key") and env_api:
        creds["api_key"] = env_api
    if not creds.get("access_token") and env_token:
        creds["access_token"] = env_token
    if env_cid and not client_id:
        client_id = env_cid
    if env_csec and not client_secret:
        client_secret = env_csec
    if env_refresh and not refresh_token:
        refresh_token = env_refresh

    if client_id and client_secret and refresh_token:
        creds["client_id"] = client_id
        creds["client_secret"] = client_secret
        creds["refresh_token"] = refresh_token
        # If we have refresh flow but no access_token yet, we will mint one on demand
        # Still record flow availability
        creds["oauth_flow"] = "refresh_token"

    # SSM third — only if still missing
    if not creds.get("api_key") and not creds.get("access_token") and not creds.get("refresh_token"):
        ssm = _ssm_get_json(SSM_YOUTUBE_PATH)
        if ssm:
            if ssm.get("api_key") and not creds.get("api_key"):
                creds["api_key"] = ssm["api_key"]
            if ssm.get("access_token") and not creds.get("access_token"):
                creds["access_token"] = ssm["access_token"]
            if ssm.get("refresh_token"):
                creds["refresh_token"] = ssm["refresh_token"]
                creds["client_id"] = ssm.get("client_id", creds.get("client_id", ""))
                creds["client_secret"] = ssm.get("client_secret", creds.get("client_secret", ""))
                if creds.get("client_id"):
                    creds["oauth_flow"] = "refresh_token"

    return creds


def _mint_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    if httpx is None:
        raise YouTubeAPIError("httpx not installed — pip install httpx to mint OAuth token")
    resp = httpx.post(
        OAUTH_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise YouTubeAPIError(f"OAuth refresh failed {resp.status_code}: {resp.text[:600]}")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise YouTubeAPIError(f"OAuth refresh returned no access_token: {data}")
    return token


@dataclass
class YouTubeClient:
    """Thin httpx wrapper around YouTube Data API v3. Credential-gated, no scrape fallback."""

    api_key: str | None = None
    access_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None
    _resolved: dict | None = None

    def __post_init__(self):
        self._resolved = _resolve_youtube_credentials(
            api_key=self.api_key,
            access_token=self.access_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            refresh_token=self.refresh_token,
        )
        # propagate resolved into fields for convenience
        self.api_key = self._resolved.get("api_key")
        self.access_token = self._resolved.get("access_token")
        self.client_id = self._resolved.get("client_id")
        self.client_secret = self._resolved.get("client_secret")
        self.refresh_token = self._resolved.get("refresh_token")

    # ---- credential helpers ----
    def has_credentials(self) -> bool:
        r = self._resolved or {}
        return bool(r.get("api_key") or r.get("access_token") or r.get("refresh_token"))

    def assert_credentials(self):
        if not self.has_credentials():
            raise MissingCredentialsError(
                "YouTube credentials missing — unauthenticated scrape is prohibited (YouTube ToS §4/H). "
                "Configure one of: "
                "1) YOUTUBE_API_KEY env var (API key from https://console.cloud.google.com/apis/credentials — enable YouTube Data API v3) "
                "for public reads (channels.list, videos.list, playlistItems.list); "
                "2) OAuth refresh flow: YOUTUBE_OAUTH_CLIENT_ID + YOUTUBE_OAUTH_CLIENT_SECRET + YOUTUBE_OAUTH_REFRESH_TOKEN (scope https://www.googleapis.com/auth/youtube.readonly or youtube.upload) "
                "and exchange via https://oauth2.googleapis.com/token; "
                "3) YOUTUBE_ACCESS_TOKEN bearer (short-lived, from OAuth code flow); "
                "4) AWS SSM JSON at /heraldstack/shared/youtube-oauth with {\"api_key\": \"...\"} or {\"refresh_token\": \"...\", \"client_id\": \"...\", \"client_secret\": \"...\"}. "
                "Create API key: gcloud services enable youtube.googleapis.com && gcloud alpha services api-keys create. "
                "No scrape fallback will be attempted."
            )

    def _auth_params(self) -> dict:
        """Return query/header auth dict for next request. Mint refresh token if needed."""
        r = self._resolved or {}
        if r.get("access_token"):
            return {"headers": {"Authorization": f"Bearer {r['access_token']}"}}
        if r.get("refresh_token") and r.get("client_id") and r.get("client_secret"):
            # mint fresh access_token and cache
            token = _mint_access_token(r["client_id"], r["client_secret"], r["refresh_token"])
            self.access_token = token
            self._resolved["access_token"] = token  # type: ignore
            return {"headers": {"Authorization": f"Bearer {token}"}}
        if r.get("api_key"):
            return {"params": {"key": r["api_key"]}}
        return {}

    def _get(self, path: str, params: dict, headers: dict | None = None) -> dict:
        if httpx is None:
            raise YouTubeAPIError("httpx not installed")
        self.assert_credentials()
        auth = self._auth_params()
        merged_params = {**params, **auth.get("params", {})}
        merged_headers = {**(headers or {}), **auth.get("headers", {})}
        url = f"{YOUTUBE_API_BASE}{path}"
        # simple retry for 429/5xx (quota/backoff)
        for attempt in range(3):
            resp = httpx.get(url, params=merged_params, headers=merged_headers, timeout=20)
            if resp.status_code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2**attempt)
                continue
            if resp.status_code >= 400:
                # surface quota hint
                body = resp.text[:1200]
                hint = ""
                if "quotaExceeded" in body:
                    hint = " (quotaExceeded — request quota increase at https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas; search.list costs 100 units, prefer playlistItems.list at 1 unit)"
                raise YouTubeAPIError(f"YouTube API {path} {resp.status_code}{hint}: {body}")
            return resp.json()
        raise YouTubeAPIError(f"YouTube API {path} failed after retries")

    # ---- high-level API ----
    def get_channel(self, handle: str | None = None, username: str | None = None, channel_id: str | None = None) -> dict:
        """Fetch channel via channels.list. Use handle=@Kodiakcakes or username=Kodiakcakes or id=UCxxxx."""
        params: dict[str, Any] = {"part": "snippet,contentDetails,statistics,brandingSettings"}
        if channel_id:
            params["id"] = channel_id
        elif handle:
            # API supports forHandle (2023+) — try forHandle first, fallback to id search
            # Not all projects have forHandle, so we try channels.list?forHandle then search
            try:
                data = self._get("/channels", {**params, "forHandle": handle})
                if data.get("items"):
                    return self._normalize_channel(data["items"][0])
            except YouTubeAPIError:
                pass
            # fallback: search for handle (costs 100) then fetch by id
            s = self._get("/search", {"part": "snippet", "q": handle, "type": "channel", "maxResults": 5})
            for item in s.get("items", []):
                cid = item.get("id", {}).get("channelId")
                if cid:
                    data2 = self._get("/channels", {**params, "id": cid})
                    if data2.get("items"):
                        return self._normalize_channel(data2["items"][0])
            raise YouTubeAPIError(f"Channel not found for handle {handle}: {s}")
        elif username:
            params["forUsername"] = username
            data = self._get("/channels", params)
            if not data.get("items"):
                raise YouTubeAPIError(f"Channel not found for username {username}")
            return self._normalize_channel(data["items"][0])
        elif channel_id:
            data = self._get("/channels", params)
            if not data.get("items"):
                raise YouTubeAPIError(f"Channel not found for id {channel_id}")
            return self._normalize_channel(data["items"][0])
        else:
            raise ValueError("get_channel requires handle or username or channel_id")

    def _normalize_channel(self, item: dict) -> dict:
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        content = item.get("contentDetails") or {}
        uploads = (content.get("relatedPlaylists") or {}).get("uploads")
        return {
            "id": item.get("id"),
            "title": snippet.get("title"),
            "handle": snippet.get("customUrl") or snippet.get("title"),
            "description": snippet.get("description"),
            "publishedAt": snippet.get("publishedAt"),
            "country": snippet.get("country"),
            "thumbnails": snippet.get("thumbnails"),
            "uploads_playlist_id": uploads,
            "subscriber_count": int(stats.get("subscriberCount", 0)) if stats.get("subscriberCount") else None,
            "video_count": int(stats.get("videoCount", 0)) if stats.get("videoCount") else None,
            "view_count": int(stats.get("viewCount", 0)) if stats.get("viewCount") else None,
            "raw": item,
        }

    def list_channel_videos(self, channel_id: str | None = None, uploads_playlist_id: str | None = None, max_results: int = 50) -> list[dict]:
        """Enumerate videos via playlistItems.list on the uploads playlist (1 unit/page, quota-friendly).

        Prefer this over search.list (100 units/query). Returns list of {id, title, publishedAt, thumbnails}.
        """
        if not uploads_playlist_id:
            if not channel_id:
                raise ValueError("list_channel_videos needs channel_id or uploads_playlist_id")
            ch = self.get_channel(channel_id=channel_id)
            uploads_playlist_id = ch.get("uploads_playlist_id")
            if not uploads_playlist_id:
                raise YouTubeAPIError(f"No uploads playlist for channel {channel_id}")
        items: list[dict] = []
        page_token: str | None = None
        while len(items) < max_results:
            params: dict[str, Any] = {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": min(50, max_results - len(items)),
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get("/playlistItems", params)
            for it in data.get("items", []):
                snippet = it.get("snippet") or {}
                cd = it.get("contentDetails") or {}
                vid = cd.get("videoId") or snippet.get("resourceId", {}).get("videoId")
                if vid:
                    items.append({"id": vid, "title": snippet.get("title"), "publishedAt": snippet.get("publishedAt"), "thumbnails": snippet.get("thumbnails"), "raw": it})
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return items[:max_results]

    def search_videos(self, channel_id: str | None = None, query: str | None = None, max_results: int = 25, order: str = "date") -> list[dict]:
        """search.list wrapper (quota-expensive: 100 units). Prefer list_channel_videos for full enumeration."""
        params: dict[str, Any] = {"part": "snippet", "type": "video", "maxResults": min(50, max_results), "order": order}
        if channel_id:
            params["channelId"] = channel_id
        if query:
            params["q"] = query
        data = self._get("/search", params)
        out = []
        for it in data.get("items", []):
            vid = it.get("id", {}).get("videoId")
            sn = it.get("snippet") or {}
            if vid:
                out.append({"id": vid, "title": sn.get("title"), "publishedAt": sn.get("publishedAt"), "channelId": sn.get("channelId"), "raw": it})
        return out

    def get_videos(self, video_ids: list[str], parts: str = "snippet,contentDetails,statistics,status") -> list[dict]:
        """videos.list for up to 50 ids per call (1 unit)."""
        if not video_ids:
            return []
        out: list[dict] = []
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i : i + 50]
            data = self._get("/videos", {"part": parts, "id": ",".join(chunk)})
            for item in data.get("items", []):
                out.append(self._normalize_video(item))
        return out

    def _normalize_video(self, item: dict) -> dict:
        sn = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        cd = item.get("contentDetails") or {}
        return {
            "id": item.get("id"),
            "title": sn.get("title"),
            "description": sn.get("description"),
            "channelId": sn.get("channelId"),
            "channelTitle": sn.get("channelTitle"),
            "publishedAt": sn.get("publishedAt"),
            "tags": sn.get("tags", []),
            "categoryId": sn.get("categoryId"),
            "thumbnails": sn.get("thumbnails"),
            "duration": cd.get("duration"),  # ISO8601
            "duration_seconds": cd.get("duration"),
            "view_count": int(stats.get("viewCount", 0)) if stats.get("viewCount") else None,
            "like_count": int(stats.get("likeCount", 0)) if stats.get("likeCount") else None,
            "comment_count": int(stats.get("commentCount", 0)) if stats.get("commentCount") else None,
            "raw": item,
        }

    def get_captions(self, video_id: str) -> list[dict]:
        """captions.list — requires OAuth with youtube.force-ssl scope for owned content or public captions."""
        data = self._get("/captions", {"part": "snippet", "videoId": video_id})
        return data.get("items", [])

    def ingest_channel_to_deep(self, handle: str | None = None, username: str | None = None, channel_id: str | None = None, max_videos: int = 100, out_path: Path | str | None = None) -> dict:
        """High-level ingest: channel + video list + normalized shape compatible with youtube-deep.json.

        Returns dict with keys: channel, videos (normalized), fetched_at, credentials_used.
        Writes to out_path if provided (JSON).
        """
        ch = self.get_channel(handle=handle, username=username, channel_id=channel_id)
        vids = self.list_channel_videos(channel_id=ch["id"], max_results=max_videos)
        details = self.get_videos([v["id"] for v in vids])
        result = {
            "source": "youtube-data-api-v3",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "channel": ch,
            "videos": details,
            "credentials_used": "api_key" if self.api_key else "oauth",
            "quota_note": "channels.list 1 + playlistItems ceil(n/50) + videos ceil(n/50)",
        }
        if out_path:
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
