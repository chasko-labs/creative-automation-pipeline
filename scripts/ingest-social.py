#!/usr/bin/env python3
"""Authenticated ingest for YouTube Data API v3 + TikTok Research/Display API -> raw-ingest/kodiakcakes.

Refuses unauthenticated scrape. All calls require credentials (env or SSM); without them
the script exits 2 with guidance (matching prior child's correct refusal, but now providing
the credential-gated path to actually fetch).

YouTube: YOUTUBE_API_KEY or OAuth refresh flow (see src/creative_automation/ingest/youtube.py)
TikTok: TIKTOK_CLIENT_KEY/SECRET (+ TIKTOK_ACCESS_TOKEN for Display) or TIKTOK_CLIENT_TOKEN for Research

Usage:
  # YouTube public channel enumeration (1 unit/page — quota friendly)
  YOUTUBE_API_KEY=AIza... uv run python scripts/ingest-social.py --youtube --handle @Kodiakcakes --out data/raw-ingest/kodiakcakes --max 100
  YOUTUBE_API_KEY=AIza... uv run python scripts/ingest-social.py --youtube --username Kodiakcakes --out data/raw-ingest/kodiakcakes

  # TikTok Display API (requires user access_token from OAuth code flow)
  TIKTOK_CLIENT_KEY=... TIKTOK_ACCESS_TOKEN=... uv run python scripts/ingest-social.py --tiktok --handle @kodiakcakes --out data/raw-ingest/kodiakcakes

  # TikTok Research API (requires approved researcher + client_credentials)
  TIKTOK_CLIENT_KEY=... TIKTOK_CLIENT_SECRET=... uv run python scripts/ingest-social.py --tiktok-research --handle @kodiakcakes --out data/raw-ingest/kodiakcakes

  # Both (credential-gated each)
  YOUTUBE_API_KEY=... TIKTOK_CLIENT_KEY=... TIKTOK_CLIENT_SECRET=... uv run python scripts/ingest-social.py --all --out data/raw-ingest/kodiakcakes

Env can also be SSM: /heraldstack/shared/youtube-oauth and /heraldstack/shared/tiktok-oauth as JSON.

Exit codes: 0 success, 2 missing credentials (with guidance), 1 API error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src on path when run via `python scripts/...` without uv
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main():
    ap = argparse.ArgumentParser(description="Authenticated YouTube + TikTok ingest (no scrape)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--youtube", action="store_true", help="YouTube Data API v3 only")
    g.add_argument("--tiktok", action="store_true", help="TikTok Display API only")
    g.add_argument("--tiktok-research", action="store_true", help="TikTok Research API only")
    g.add_argument("--all", action="store_true", help="YouTube + TikTok (Display) + TikTok Research (if creds allow)")
    ap.add_argument("--handle", default="@Kodiakcakes", help="Channel handle e.g. @Kodiakcakes")
    ap.add_argument("--username", default=None, help="YouTube legacy username (e.g. Kodiakcakes for /user/Kodiakcakes)")
    ap.add_argument("--channel-id", default=None, help="YouTube channel ID UC...")
    ap.add_argument("--out", default="data/raw-ingest/kodiakcakes", help="Output dir (writes youtube-ingest-raw.json / tiktok-ingest-raw.json)")
    ap.add_argument("--max", type=int, default=100, help="Max videos to fetch (YouTube) / 50 for TikTok")
    ap.add_argument("--dry-run", action="store_true", help="Check credentials only, no API calls")
    args = ap.parse_args()

    if not any([args.youtube, args.tiktok, args.tiktok_research, args.all]):
        args.all = True

    out = Path(args.out)
    ran = 0
    failed = 0

    # ---- YouTube ----
    if args.youtube or args.all:
        try:
            from creative_automation.ingest.youtube import YouTubeClient

            yt = YouTubeClient()
            if args.dry_run:
                yt.assert_credentials()
                print(f"[youtube] credentials OK: {'api_key' if yt.api_key else 'oauth'}")
                ran += 1
            else:
                yt.assert_credentials()
                print(f"[youtube] fetching handle={args.handle} username={args.username} channel_id={args.channel_id} max={args.max} out={out}")
                handle = args.handle if args.handle else None
                # allow @ prefix normalization — youtube handle needs @
                if handle and not handle.startswith("@"):
                    handle = "@" + handle
                res = yt.ingest_channel_to_deep(handle=handle, username=args.username, channel_id=args.channel_id, max_videos=args.max, out_path=out / "youtube-ingest-raw.json")
                # also enrich youtube-deep.json counts if out is kodiakcakes
                print(f"[youtube] done: channel={res['channel'].get('title')} id={res['channel'].get('id')} videos={len(res['videos'])} -> {out / 'youtube-ingest-raw.json'}")
                ran += 1
        except Exception as e:  # noqa: BLE001 — report-and-continue CLI guard; any provider failure becomes SKIP/ERROR
            # MissingCredentialsError is the expected credential-gated refusal
            msg = str(e)
            if "credentials missing" in msg.lower() or "MissingCredentials" in type(e).__name__:
                print(f"[youtube] SKIP — {e}", file=sys.stderr)
                print("[youtube] Set YOUTUBE_API_KEY (or OAuth refresh flow) — unauthenticated scrape will NOT be attempted (YouTube ToS).", file=sys.stderr)
                if args.youtube and not args.all:
                    sys.exit(2)
                failed += 1
            else:
                print(f"[youtube] ERROR — {type(e).__name__}: {e}", file=sys.stderr)
                failed += 1
                if args.youtube and not args.all:
                    sys.exit(1)

    # ---- TikTok Display ----
    if args.tiktok or args.all:
        try:
            from creative_automation.ingest.tiktok import TikTokClient

            tt = TikTokClient()
            if args.dry_run:
                tt.assert_credentials(need="display")
                print("[tiktok:display] credentials OK")
                ran += 1
            else:
                tt.assert_credentials(need="display")
                handle = args.handle
                print(f"[tiktok:display] fetching handle={handle} out={out}")
                res = tt.ingest_to_raw(handle=handle, out_dir=out, use_research=False)
                print(f"[tiktok:display] done: user handle={handle} videos={res['counts']['videos']} -> {out / 'tiktok.json'} (+ tiktok-ingest-raw.json)")
                ran += 1
        except Exception as e:  # noqa: BLE001 — report-and-continue CLI guard; any provider failure becomes SKIP/ERROR
            msg = str(e)
            if "credentials missing" in msg.lower() or "MissingCredentials" in type(e).__name__:
                print(f"[tiktok:display] SKIP — {e}", file=sys.stderr)
                print("[tiktok:display] Set TIKTOK_CLIENT_KEY + TIKTOK_ACCESS_TOKEN (Display OAuth) — scrape will NOT be attempted.", file=sys.stderr)
                if args.tiktok and not args.all:
                    sys.exit(2)
                failed += 1
            else:
                print(f"[tiktok:display] ERROR — {type(e).__name__}: {e}", file=sys.stderr)
                failed += 1
                if args.tiktok and not args.all:
                    sys.exit(1)

    # ---- TikTok Research ----
    if args.tiktok_research or args.all:
        # For --all we attempt research only if credentials exist; otherwise skip quietly
        try:
            from creative_automation.ingest.tiktok import TikTokClient

            tt = TikTokClient()
            # For --all, if no research creds, skip without error
            if args.all and not tt.has_research_credentials():
                print("[tiktok:research] SKIP — no research credentials (need TIKTOK_CLIENT_KEY+SECRET or TIKTOK_CLIENT_TOKEN + approved researcher) — not an error for --all", file=sys.stderr)
            else:
                if args.dry_run:
                    tt.assert_credentials(need="research")
                    print("[tiktok:research] credentials OK")
                    ran += 1
                else:
                    tt.assert_credentials(need="research")
                    handle = args.handle
                    print(f"[tiktok:research] fetching handle={handle} out={out} (Research API video/query)")
                    res = tt.ingest_to_raw(handle=handle, out_dir=out, use_research=True)
                    print(f"[tiktok:research] done: handle={handle} videos={res['counts']['videos']} -> {out / 'tiktok-ingest-raw.json'} (research mode)")
                    ran += 1
        except Exception as e:  # noqa: BLE001 — report-and-continue CLI guard; any provider failure becomes SKIP/ERROR
            msg = str(e)
            if "credentials missing" in msg.lower() or "MissingCredentials" in type(e).__name__ or "approved" in msg.lower():
                print(f"[tiktok:research] SKIP — {e}", file=sys.stderr)
                if args.tiktok_research and not args.all:
                    sys.exit(2)
                failed += 1
            else:
                print(f"[tiktok:research] ERROR — {type(e).__name__}: {e}", file=sys.stderr)
                failed += 1
                if args.tiktok_research and not args.all:
                    sys.exit(1)

    if ran == 0 and failed > 0:
        print(f"[ingest] no provider succeeded (ran=0 failed={failed}) — configure credentials per guidance above", file=sys.stderr)
        # For --all with zero creds, exit 2 to signal credential gap (not API error)
        sys.exit(2)
    print(f"[ingest] done ran={ran} failed/skipped={failed} out={out}")


if __name__ == "__main__":
    main()
