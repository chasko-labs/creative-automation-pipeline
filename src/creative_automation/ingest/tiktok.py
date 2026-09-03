"""TikTok Research + Display API — authenticated client for Kodiak Cakes ingest.

No unauthenticated scrape. TikTok ToS and developer terms prohibit scraping tiktok.com html.
This module uses only the official TickTok APIs:

  Display API: https://developers.tiktok.com/doc/tiktok-api-v2-get-started
    - OAuth 2.0 Authorization Code with PKCE (scopes: user.info.basic, video.list)
    - GET https://open.tiktokapis.com/v2/user/info/
    - POST https://open.tiktokapis.com/v2/video/list/  (body: {max_count, cursor})

  Research API: https://developers.tiktok.com/doc/tiktok-research-api-get-started
    - Requires approved Research API access (apply via TikTok for Developers portal)
    - Client credentials: client_key + client_secret -> client_access_token via /v2/oauth/token/
    - POST https://open.tiktokapis.com/v2/research/video/query/
    - GET https://open.tiktokapis.com/v2/research/user/info/?username=...

  Content Posting API is documented in tiktok-deep.json programmatic_posting — not covered here
  (that API is for publishing, not ingest, and uses same OAuth with video.publish scope).

Auth priority (Display + Research share same client_key/secret, but Research needs approval):
  1. explicit args to TikTokClient(...)
  2. env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_CLIENT_TOKEN (client credentials),
     TIKTOK_ACCESS_TOKEN (user access token from OAuth code exchange), TIKTOK_REFRESH_TOKEN,
     TIKTOK_REDIRECT_URI (for code exchange), RESEARCH_ENABLED flag via TIKTOK_RESEARCH_ENABLED
  3. AWS SSM Parameter Store: /heraldstack/shared/tiktok-oauth JSON {client_key, client_secret, access_token, refresh_token}

All calls require bearer token. Without credentials, MissingCredentialsError is raised — no scrape fallback.
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

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
TIKTOK_OAUTH_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
# Research endpoints share same base but /research/ prefix
SSM_TIKTOK_PATH = os.getenv("TIKTOK_SSM_PATH", "/heraldstack/shared/tiktok-oauth")


class MissingCredentialsError(RuntimeError):
    """Raised when TikTok credentials missing. Never falls back to scrape."""


class TikTokAPIError(RuntimeError):
    """TikTok API returned non-2xx or error code != 0."""


def _ssm_get_json(path: str) -> dict | None:
    try:
        import boto3  # type: ignore

        region = os.getenv("AWS_REGION", os.getenv("BEDROCK_REGION", "us-east-1"))
        client = boto3.client("ssm", region_name=region)
        resp = client.get_parameter(Name=path, WithDecryption=True)
        val = resp["Parameter"]["Value"]
        try:
            return json.loads(val)
        except Exception:
            return {"value": val}
    except Exception:
        return None


def _resolve_tiktok_credentials(
    client_key: str | None = None,
    client_secret: str | None = None,
    access_token: str | None = None,
    refresh_token: str | None = None,
    client_token: str | None = None,
) -> dict:
    creds: dict[str, str] = {}
    if client_key:
        creds["client_key"] = client_key
    if client_secret:
        creds["client_secret"] = client_secret
    if access_token:
        creds["access_token"] = access_token
    if refresh_token:
        creds["refresh_token"] = refresh_token
    if client_token:
        creds["client_token"] = client_token

    env_ck = os.getenv("TIKTOK_CLIENT_KEY") or os.getenv("TIKTOK_CLIENT_TOKEN")  # some docs use TOKEN
    env_cs = os.getenv("TIKTOK_CLIENT_SECRET")
    env_at = os.getenv("TIKTOK_ACCESS_TOKEN") or os.getenv("TIKTOK_USER_ACCESS_TOKEN")
    env_rt = os.getenv("TIKTOK_REFRESH_TOKEN")
    env_ct = os.getenv("TIKTOK_CLIENT_TOKEN") or os.getenv("TIKTOK_CLIENT_ACCESS_TOKEN")
    env_redirect = os.getenv("TIKTOK_REDIRECT_URI")

    if not creds.get("client_key") and env_ck and not env_ck.startswith("eyJ"):  # avoid token confusion
        creds["client_key"] = env_ck
    if not creds.get("client_secret") and env_cs:
        creds["client_secret"] = env_cs
    if not creds.get("access_token") and env_at:
        creds["access_token"] = env_at
    if not creds.get("refresh_token") and env_rt:
        creds["refresh_token"] = env_rt
    if not creds.get("client_token") and env_ct and env_ct.startswith("eyJ"):
        creds["client_token"] = env_ct
    if env_redirect:
        creds["redirect_uri"] = env_redirect

    # SSM fallback if still missing core
    if not creds.get("client_key") or not creds.get("access_token"):
        ssm = _ssm_get_json(SSM_TIKTOK_PATH)
        if ssm:
            for k in ("client_key", "client_secret", "access_token", "refresh_token", "client_token", "redirect_uri"):
                if ssm.get(k) and not creds.get(k):
                    creds[k] = ssm[k]
            # legacy keys
            if ssm.get("accessToken") and not creds.get("access_token"):
                creds["access_token"] = ssm["accessToken"]

    return creds


def _mint_client_token(client_key: str, client_secret: str) -> str:
    """Client credentials grant — for Research API and server-to-server calls.

    POST https://open.tiktokapis.com/v2/oauth/token/
    body: client_key, client_secret, grant_type=client_credentials
    """
    if httpx is None:
        raise TikTokAPIError("httpx not installed")
    resp = httpx.post(
        TIKTOK_OAUTH_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"client_key": client_key, "client_secret": client_secret, "grant_type": "client_credentials"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise TikTokAPIError(f"TikTok client_credentials failed {resp.status_code}: {resp.text[:800]}")
    data = resp.json()
    token = data.get("access_token") or data.get("data", {}).get("access_token")
    if not token:
        raise TikTokAPIError(f"No access_token in client_credentials response: {data}")
    return token


def _refresh_user_token(client_key: str, refresh_token: str) -> dict:
    """Refresh user access_token via refresh_token grant."""
    if httpx is None:
        raise TikTokAPIError("httpx not installed")
    resp = httpx.post(
        TIKTOK_OAUTH_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"client_key": client_key, "refresh_token": refresh_token, "grant_type": "refresh_token"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise TikTokAPIError(f"TikTok refresh_token failed {resp.status_code}: {resp.text[:800]}")
    return resp.json()


def _exchange_code_for_token(client_key: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    """Authorization code -> user access_token (PKCE flow)."""
    if httpx is None:
        raise TikTokAPIError("httpx not installed")
    resp = httpx.post(
        TIKTOK_OAUTH_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise TikTokAPIError(f"TikTok authorization_code exchange failed {resp.status_code}: {resp.text[:800]}")
    return resp.json()


@dataclass
class TikTokClient:
    """httpx wrapper for TikTok Display + Research APIs. Credential-gated."""

    client_key: str | None = None
    client_secret: str | None = None
    access_token: str | None = None  # user access_token (Display/Research)
    refresh_token: str | None = None
    client_token: str | None = None  # client_credentials token (Research server-to-server)
    redirect_uri: str | None = None
    _resolved: dict | None = None

    def __post_init__(self):
        self._resolved = _resolve_tiktok_credentials(
            client_key=self.client_key,
            client_secret=self.client_secret,
            access_token=self.access_token,
            refresh_token=self.refresh_token,
            client_token=self.client_token,
        )
        self.client_key = self._resolved.get("client_key")
        self.client_secret = self._resolved.get("client_secret")
        self.access_token = self._resolved.get("access_token")
        self.refresh_token = self._resolved.get("refresh_token")
        self.client_token = self._resolved.get("client_token")
        self.redirect_uri = self._resolved.get("redirect_uri") or self.redirect_uri

    def has_credentials(self) -> bool:
        r = self._resolved or {}
        # Display needs access_token (+ client_key for refresh); Research needs client_key+secret or client_token
        return bool(r.get("access_token") or (r.get("client_key") and r.get("client_secret")) or r.get("client_token"))

    def has_display_credentials(self) -> bool:
        return bool((self._resolved or {}).get("access_token"))

    def has_research_credentials(self) -> bool:
        r = self._resolved or {}
        return bool((r.get("client_key") and r.get("client_secret")) or r.get("client_token") or r.get("access_token"))

    def assert_credentials(self, need: str = "any"):
        """need: any|display|research"""
        ok = False
        if need == "display":
            ok = self.has_display_credentials()
        elif need == "research":
            ok = self.has_research_credentials()
        else:
            ok = self.has_credentials()
        if not ok:
            raise MissingCredentialsError(
                "TikTok credentials missing — unauthenticated scrape is prohibited (TikTok ToS, Display/Research API terms). "
                "Configure via env: "
                "1) Display API (user data): TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET + TIKTOK_ACCESS_TOKEN (from OAuth authorization code flow via https://www.tiktok.com/v2/auth/authorize/ with scopes user.info.basic,video.list). "
                "Exchange code via POST https://open.tiktokapis.com/v2/oauth/token/ grant_type=authorization_code. "
                "2) Research API (public research): TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET then POST /v2/oauth/token/ grant_type=client_credentials to get client_access_token (requires approved Research API access from https://developers.tiktok.com/doc/tiktok-research-api-get-started — apply as researcher). "
                "3) Client token shortcut: TIKTOK_CLIENT_TOKEN (the client_access_token) for Research video/query. "
                "4) AWS SSM JSON at /heraldstack/shared/tiktok-oauth with {\"client_key\": \"...\", \"client_secret\": \"...\", \"access_token\": \"...\", \"refresh_token\": \"...\"}. "
                "No scrape fallback will be attempted. See tiktok-deep.json programmatic_posting for OAuth PKCE details."
            )

    def _bearer(self) -> str:
        """Return usable bearer token — prefer user access_token, else mint client_token."""
        r = self._resolved or {}
        if r.get("access_token"):
            return r["access_token"]
        if r.get("client_token"):
            return r["client_token"]
        if r.get("client_key") and r.get("client_secret"):
            # lazily mint client token for Research
            token = _mint_client_token(r["client_key"], r["client_secret"])
            self.client_token = token
            self._resolved["client_token"] = token  # type: ignore
            return token
        raise MissingCredentialsError("No TikTok bearer available — configure TIKTOK_ACCESS_TOKEN or TIKTOK_CLIENT_KEY/SECRET")

    def _headers(self) -> dict:
        token = self._bearer()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _check_tiktok_error(self, data: dict, status_code: int):
        # TikTok returns {error: {code, message, log_id}} or {data:..., error: {code: ok}}
        err = data.get("error") or {}
        code = err.get("code") if isinstance(err, dict) else None
        if code and code != "ok":
            raise TikTokAPIError(f"TikTok API error {code} http={status_code}: {err.get('message')} log_id={err.get('log_id')} body={str(data)[:800]}")
        if status_code >= 400:
            raise TikTokAPIError(f"TikTok HTTP {status_code}: {str(data)[:800]}")

    # ---- Display API ----
    def get_user_info(self, fields: str | None = None) -> dict:
        """GET /v2/user/info/ — Display API. Requires user.info.basic scope."""
        self.assert_credentials(need="display")
        if httpx is None:
            raise TikTokAPIError("httpx not installed")
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = fields
        else:
            params["fields"] = "open_id,union_id,avatar_url,display_name,bio_description,profile_deep_link,is_verified,follower_count,following_count,likes_count,video_count"
        resp = httpx.get(f"{TIKTOK_API_BASE}/user/info/", headers={"Authorization": f"Bearer {self._bearer()}"}, params=params, timeout=15)
        data = resp.json()
        self._check_tiktok_error(data, resp.status_code)
        return data.get("data", {}).get("user", data.get("data", data))

    def list_videos(self, max_count: int = 20, cursor: int = 0) -> dict:
        """POST /v2/video/list/ — Display API. Returns user's own videos (video.list scope)."""
        self.assert_credentials(need="display")
        if httpx is None:
            raise TikTokAPIError("httpx not installed")
        body: dict[str, Any] = {"max_count": min(20, max_count)}
        if cursor:
            body["cursor"] = cursor
        # fields per docs: id, create_time, cover_image_url, share_url, video_description, duration, height, width, title, embed_html, embed_link, like_count, comment_count, share_count, view_count
        body["fields"] = "id,create_time,cover_image_url,share_url,video_description,duration,height,width,title,embed_html,embed_link,like_count,comment_count,share_count,view_count"
        resp = httpx.post(f"{TIKTOK_API_BASE}/video/list/", headers=self._headers(), json=body, timeout=20)
        data = resp.json()
        self._check_tiktok_error(data, resp.status_code)
        return data.get("data", data)

    def query_videos_paginated(self, max_count: int = 50) -> list[dict]:
        """Helper: paginate Display API video.list until max_count or has_more=False."""
        out: list[dict] = []
        cursor = 0
        while len(out) < max_count:
            chunk = self.list_videos(max_count=min(20, max_count - len(out)), cursor=cursor)
            videos = chunk.get("videos", chunk.get("data", {}).get("videos", [])) if isinstance(chunk, dict) else []
            # API shape varies: data.videos
            if not videos and isinstance(chunk, dict):
                videos = chunk.get("videos") or chunk.get("data", {}).get("videos") or []
            if not videos:
                # fallback: data is dict with videos key
                videos = chunk.get("videos", [])
            if not videos:
                break
            out.extend(videos)
            has_more = chunk.get("has_more", chunk.get("data", {}).get("has_more", False))
            if not has_more:
                break
            cursor = chunk.get("cursor", chunk.get("data", {}).get("cursor", cursor + len(videos)))
            if cursor == 0 and has_more:
                cursor = len(out)
        return out[:max_count]

    # ---- Research API ----
    def research_query_videos(self, query: str | None = None, username: str | None = None, max_count: int = 100, start_date: str | None = None, end_date: str | None = None) -> dict:
        """POST /v2/research/video/query/ — Research API. Requires approved researcher + client token.

        query: textual search (optional), username: filter by @handle, start_date/end_date: YYYYMMDD.
        """
        self.assert_credentials(need="research")
        if httpx is None:
            raise TikTokAPIError("httpx not installed")
        body: dict[str, Any] = {"max_count": min(100, max_count)}
        if query:
            body["query"] = {"and": [{"operation": "IN", "field_name": "video_description", "field_values": [query]}]}
        if username:
            body["query"] = body.get("query") or {}
            # Research API uses field_name username
            and_clause = body["query"].setdefault("and", [])
            and_clause.append({"operation": "EQ", "field_name": "username", "field_values": [username.lstrip("@")]})
        if start_date:
            body["start_date"] = start_date  # YYYYMMDD
        if end_date:
            body["end_date"] = end_date
        # fields per research docs — must request explicit fields
        body["fields"] = "id,video_description,create_time,region_code,share_count,view_count,like_count,comment_count,music_id,hashtag_names,username,effect_ids,playlist_id,voice_to_text"
        resp = httpx.post(f"{TIKTOK_API_BASE}/research/video/query/", headers=self._headers(), json=body, timeout=20)
        data = resp.json()
        self._check_tiktok_error(data, resp.status_code)
        return data.get("data", data)

    def research_get_user_info(self, username: str) -> dict:
        """GET /v2/research/user/info/?username=@kodiakcakes — Research API."""
        self.assert_credentials(need="research")
        if httpx is None:
            raise TikTokAPIError("httpx not installed")
        resp = httpx.get(f"{TIKTOK_API_BASE}/research/user/info/", headers={"Authorization": f"Bearer {self._bearer()}"}, params={"username": username.lstrip("@")}, timeout=15)
        data = resp.json()
        self._check_tiktok_error(data, resp.status_code)
        return data.get("data", data)

    # ---- OAuth helpers (for setup, not ingest loop) ----
    def build_authorize_url(self, redirect_uri: str | None = None, scope: str = "user.info.basic,video.list", state: str | None = None) -> str:
        """Build https://www.tiktok.com/v2/auth/authorize/ URL for Display API OAuth (Authorization Code + PKCE)."""
        ck = (self._resolved or {}).get("client_key") or self.client_key
        if not ck:
            raise MissingCredentialsError("TIKTOK_CLIENT_KEY required to build authorize URL")
        rid = redirect_uri or self.redirect_uri or os.getenv("TIKTOK_REDIRECT_URI", "")
        if not rid:
            raise ValueError("redirect_uri required — set TIKTOK_REDIRECT_URI or pass redirect_uri")
        import urllib.parse

        params = {"client_key": ck, "response_type": "code", "scope": scope, "redirect_uri": rid}
        if state:
            params["state"] = state
        return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)

    def exchange_code(self, code: str, redirect_uri: str | None = None) -> dict:
        """Exchange authorization code for user access_token + refresh_token. Stores result."""
        ck = (self._resolved or {}).get("client_key") or self.client_key
        cs = (self._resolved or {}).get("client_secret") or self.client_secret
        if not ck or not cs:
            raise MissingCredentialsError("TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET required for code exchange")
        rid = redirect_uri or self.redirect_uri or os.getenv("TIKTOK_REDIRECT_URI", "")
        if not rid:
            raise ValueError("redirect_uri required for code exchange")
        data = _exchange_code_for_token(ck, cs, code, rid)
        # TikTok returns {access_token, expires_in, refresh_token, scope, open_id, ...} or {data: {...}}
        payload = data.get("data", data)
        if payload.get("access_token"):
            self.access_token = payload["access_token"]
            self.refresh_token = payload.get("refresh_token", self.refresh_token)
            if self._resolved is not None:
                self._resolved["access_token"] = self.access_token
                if self.refresh_token:
                    self._resolved["refresh_token"] = self.refresh_token
        return data

    def refresh_access_token(self) -> dict:
        ck = (self._resolved or {}).get("client_key") or self.client_key
        rt = (self._resolved or {}).get("refresh_token") or self.refresh_token
        if not ck or not rt:
            raise MissingCredentialsError("client_key + refresh_token required to refresh")
        data = _refresh_user_token(ck, rt)
        payload = data.get("data", data)
        if payload.get("access_token"):
            self.access_token = payload["access_token"]
            if self._resolved is not None:
                self._resolved["access_token"] = self.access_token
        return data

    # ---- high-level ingest ----
    def ingest_to_raw(self, handle: str = "@kodiakcakes", out_dir: Path | str | None = None, use_research: bool = False) -> dict:
        """High-level ingest: user info + video list, returns dict compatible with raw-ingest shape.

        If use_research=True, uses Research API video.query (public search); otherwise Display API (own account only).
        Writes tiktok.json + tiktok-deep.json shape to out_dir if provided.
        """
        mode = "research" if use_research else "display"
        user: dict = {}
        videos: list[dict] = []
        if use_research:
            # Research: public lookup by username
            user = self.research_get_user_info(handle)
            q = self.research_query_videos(username=handle, max_count=50)
            videos = q.get("videos", q.get("data", {}).get("videos", [])) if isinstance(q, dict) else []
            if not videos and isinstance(q, dict):
                videos = q.get("videos") or []
        else:
            user = self.get_user_info()
            vdata = self.query_videos_paginated(max_count=50)
            videos = vdata

        result = {
            "platform": "tiktok",
            "handle": handle,
            "url": f"https://www.tiktok.com/{handle}",
            "mode": mode,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "user": user,
            "videos": videos,
            "credentials_used": "research:client_token" if use_research else "display:access_token",
            "counts": {"videos": len(videos)},
        }
        if out_dir:
            p = Path(out_dir)
            p.mkdir(parents=True, exist_ok=True)
            # minimal tiktok.json (list of videos) + tiktok-deep elaboration
            tlist = [{"title": v.get("title") or v.get("video_description", "")[:80], "url": v.get("share_url") or v.get("embed_link") or f"https://www.tiktok.com/{handle}/video/{v.get('id')}", "description": v.get("video_description", ""), "thumb": v.get("cover_image_url", ""), "stats": {"view_count": v.get("view_count"), "like_count": v.get("like_count")}} for v in videos[:20]]
            (p / "tiktok.json").write_text(json.dumps(tlist, indent=2), encoding="utf-8")
            (p / "tiktok-ingest-raw.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
