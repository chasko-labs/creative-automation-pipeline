"""Authenticated social ingest — YouTube Data API v3 + TikTok Research/Display API.

Prior child correctly refused unauthenticated scrape (violates YouTube ToS §4/H and TikTok ToS).
This module implements the credential-gated official APIs only.

- YouTube: https://developers.google.com/youtube/v3/docs  — channels.list, search.list, playlistItems.list, videos.list, captions.list
  Auth: API key (YOUTUBE_API_KEY) for public reads OR OAuth2 (YOUTUBE_OAUTH_REFRESH_TOKEN flow) for uploads/private.
- TikTok:
   * Display API: https://developers.tiktok.com/doc/tiktok-api-v2-get-started — user.info + video.list (OAuth access_token with video.list, user.info.basic)
   * Research API: https://developers.tiktok.com/doc/tiktok-research-api-get-started — /research/video/query + /research/user/info (client credentials + approved researcher token)
   * Content Posting API is separate (already documented in tiktok-deep.json) — not scrape.
   Auth: TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET -> client access token -> user access token via authorization code PKCE.

All functions raise MissingCredentialsError when credentials absent — no fallback to scrape.
Credentials resolved in order: explicit arg > env var > AWS SSM Parameter Store (/heraldstack/shared/{youtube,tiktok}-oauth).
"""
from .youtube import YouTubeClient, MissingCredentialsError as YouTubeMissingCredentials
from .tiktok import TikTokClient, MissingCredentialsError as TikTokMissingCredentials

__all__ = ["YouTubeClient", "TikTokClient", "YouTubeMissingCredentials", "TikTokMissingCredentials"]
