#!/usr/bin/env python3
"""Fill the DAM thumb cache: 320px JPEG derivatives under thumbs/.

Reads every library category key list, HEADs thumbs/<key>.thumb.jpg, and for
misses downloads the full file, resizes to 320px wide (PIL, JPEG q70), and
uploads it back. list_library only ever presigns existing derivatives, so this
script is what makes grid tiles fast; until it runs, tiles fall back to full
files (slow but correct).

Usage:
  python3 scripts/build-thumb-cache.py [--category ideas] [--limit 200] [--dry-run]

Writes to the real DAM bucket — this is the feature, not an accident. Bounded
by --limit per category (default 200, matches the list cap).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from creative_automation import dam, dam_library


def _fetch(key: str, dest: Path) -> bool:
    try:
        return bool(dam.fetch_dam_key(key, dest))
    except Exception as e:  # noqa: BLE001
        print(f"  fetch failed {key}: {e}")
        return False


def _resize(src: Path, dest: Path, width: int = 320) -> bool:
    try:
        from PIL import Image

        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > width:
                im = im.resize(
                    (width, max(1, round(im.height * width / im.width))),
                    Image.LANCZOS,
                )
            im.save(dest, "JPEG", quality=70, optimize=True)
        return True
    except Exception as e:  # noqa: BLE001 — one bad file must not sink the fill
        print(f"  resize failed {src}: {e}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default=None)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not dam._s3_enabled():
        print("DAM S3 not configured — nothing to do.")
        return 0
    bucket, _ = dam._s3_bucket_and_prefix()
    client = dam._s3_client()
    if not bucket or client is None:
        print("S3 client init failed.")
        return 1

    wanted = (
        [args.category]
        if args.category in dam_library._CATEGORIES
        else list(dam_library._CATEGORIES)
    )
    for name in wanted:
        made = skipped = failed = 0
        cfg = dam_library._CATEGORIES[name]
        try:
            keys = dam_library._gather_keys(name, cfg, client, bucket, {})
        except Exception as e:  # noqa: BLE001
            print(f"{name}: gather failed: {e}")
            continue
        for key in keys[: max(1, args.limit)]:
            # Derivatives are JPEGs — JSON sidecars and other non-images can
            # never fill, so skip them before the HEAD/fetch/resize spend.
            if Path(key).suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                skipped += 1
                continue
            tkey = dam_library._thumb_key(key)
            thumb_exists = True
            try:
                client.head_object(Bucket=bucket, Key=tkey)
            except Exception:  # noqa: BLE001 — missing-thumb probe; absent means fill it
                thumb_exists = False
            if thumb_exists:
                skipped += 1
                continue
            if args.dry_run:
                print(f"  would fill {tkey}")
                made += 1
                continue
            with tempfile.TemporaryDirectory() as tmp:
                full = Path(tmp) / "full"
                small = Path(tmp) / "thumb.jpg"
                if not _fetch(key, full):
                    failed += 1
                    continue
                if not _resize(full, small):
                    failed += 1
                    continue
                try:
                    client.upload_file(
                        str(small), bucket, tkey,
                        ExtraArgs={"ContentType": "image/jpeg"},
                    )
                    made += 1
                except Exception as e:  # noqa: BLE001
                    print(f"  upload failed {tkey}: {e}")
                    failed += 1
        print(f"{name}: made={made} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
