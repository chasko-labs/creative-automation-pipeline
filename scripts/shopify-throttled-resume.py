#!/usr/bin/env python3
"""
Resume throttled Shopify fetch for Kodiak Cakes sitemap.
- reads data/raw-ingest/kodiakcakes/sitemap-manifest.json
- resumes by slug: skips existing pages (idempotent)
- 4s base delay between requests (Shopify/Cloudflare safe)
- exponential backoff on 429/503/520/522 + Cloudflare challenge: 4s, 8s, 16s, 32s, 60s max, up to 5 retries
- Cloudflare 429 after ~200 rapid requests mitigation
- writes pages as {index:04d}_{slug}.html using manifest index if available, else next max+1 for new URLs
- also handles images manifest if desired
"""
import json
import re
import sys
import time
from pathlib import Path

BASE = Path("/home/bryanchasko/code/chasko-labs/creative-automation-pipeline/data/raw-ingest/kodiakcakes")
MANIFEST = BASE / "sitemap-manifest.json"
PAGES_DIR = BASE / "pages"
IMAGES_DIR = BASE / "images"

def url_to_slug(u: str) -> str:
    s = re.sub(r'^https://kodiakcakes.com/', '', u).strip('/')
    if s == '':
        return 'root'
    return s.replace('/', '_')

def existing_slugs_and_max():
    slugs=set()
    max_n=-1
    for p in PAGES_DIR.iterdir():
        if p.suffix=='.html':
            m=re.match(r'^([0-9]+)_', p.name)
            if m:
                max_n=max(max_n, int(m.group(1)))
            if p.name=='000_.html':
                slugs.add('root')
            else:
                slug=re.sub(r'^[0-9]+_','',p.stem)
                if slug=='':
                    slug='root'
                slugs.add(slug)
    return slugs, max_n

def fetch_url(url: str, retries=5, base_delay=4):
    headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    delay=base_delay
    for attempt in range(retries+1):
        try:
            # use httpx if available, else curl via subprocess
            try:
                import httpx
                with httpx.Client(follow_redirects=True, timeout=30, headers=headers) as c:
                    r=c.get(url)
                    status=r.status_code
                    text=r.text
            except ImportError:
                import subprocess

                # fallback curl
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False) as tf:
                    out=tf.name
                subprocess.run(["curl","-L","-s","-A",headers["User-Agent"],"-H",f"Accept: {headers['Accept']}", url,"-o",out], check=False)
                text=Path(out).read_text(errors='ignore')
                status=200 if len(text)>500 else 429
            # detect cloudflare challenge / rate limit
            is_cf = False
            if status in (429,503,520,522,523,524):
                is_cf=True
            if "Just a moment" in text[:2000] or "cf-challenge" in text.lower() or "Attention Required! | Cloudflare" in text:
                is_cf=True
            if is_cf or status==429:
                if attempt==retries:
                    print(f"[429/cf] {url} failed after {retries} retries, status={status}")
                    return None, status
                print(f"[429/cf] {url} status={status} attempt {attempt+1}/{retries} backoff {delay}s")
                time.sleep(delay)
                delay=min(60, delay*2)
                continue
            if status>=400:
                if 500 <= status < 600 and attempt<retries:
                    print(f"[retry {status}] {url} attempt {attempt+1} backoff {delay}s")
                    time.sleep(delay)
                    delay=min(60, delay*2)
                    continue
                print(f"[error {status}] {url}")
                return None, status
            return text, status
        except Exception as e:  # noqa: BLE001 — retry-loop guard; any fetch failure backs off and retries
            if attempt==retries:
                print(f"[exception] {url} {e}")
                return None, 0
            print(f"[exception] {url} {e} backoff {delay}s")
            time.sleep(delay)
            delay=min(60, delay*2)
    return None, 0

def main():
    with open(MANIFEST) as f:
        data=json.load(f)
    urls=data['urls']
    existing, max_n = existing_slugs_and_max()
    missing=[(i,u,url_to_slug(u)) for i,u in enumerate(urls) if url_to_slug(u) not in existing]
    print(f"Manifest: {len(urls)} urls, existing pages: {len(existing)} (max idx {max_n}), missing: {len(missing)}")
    # also verify categories
    prod=[u for u in urls if '/products/' in u]
    coll=[u for u in urls if '/collections/' in u]
    blogs=[u for u in urls if '/blogs/' in u]
    prod_done=sum(1 for _,u,_ in [(i,u,url_to_slug(u)) for i,u in enumerate(urls) if '/products/' in u] if url_to_slug(u) in existing)
    coll_done=sum(1 for _,u,_ in [(i,u,url_to_slug(u)) for i,u in enumerate(urls) if '/collections/' in u] if url_to_slug(u) in existing)
    blogs_done=sum(1 for _,u,_ in [(i,u,url_to_slug(u)) for i,u in enumerate(urls) if '/blogs/' in u] if url_to_slug(u) in existing)
    print(f"Products {prod_done}/{len(prod)} collections {coll_done}/{len(coll)} blogs {blogs_done}/{len(blogs)}")
    # verify >100 pages but not complete before fetch
    pages_count=len(list(PAGES_DIR.glob("*.html")))
    print(f"Verify >100 pages but not complete: pages_count={pages_count} >100={pages_count>100} missing={len(missing)}>0={len(missing)>0}")
    if not missing:
        print("Nothing to fetch — already complete. Throttled resume verified idempotent.")
        return 0
    base_delay=4.0
    for idx, (manifest_idx, url, slug) in enumerate(missing):
        # use manifest_idx as file prefix for determinism, but avoid collision if that prefix exists for different slug
        # check if file with that idx already exists with same slug -> reuse idx, else use max_n+1 incremental
        expected = PAGES_DIR / f"{manifest_idx:04d}_{slug}.html"
        # if collision with different slug at same idx, use max+1
        if expected.exists():
            existing_slug_at_idx=re.sub(r'^[0-9]+_','',expected.stem)
            if existing_slug_at_idx != slug:
                max_n+=1
                out_path=PAGES_DIR / f"{max_n:04d}_{slug}.html"
            else:
                out_path=expected
        else:
            # check if any file already has slug (should have been filtered) -> shouldn't happen
            # need to ensure idx not colliding with existing different slug file
            colliding=[p for p in PAGES_DIR.iterdir() if p.name.startswith(f"{manifest_idx:04d}_")]
            if colliding:
                max_n+=1
                out_path=PAGES_DIR / f"{max_n:04d}_{slug}.html"
            else:
                out_path=expected
                max_n=max(max_n, manifest_idx)
        print(f"[{idx+1}/{len(missing)}] FETCH {url} -> {out_path.name} (manifest_idx {manifest_idx}) delay {base_delay}s")
        if idx>0:
            time.sleep(base_delay)
        text,status=fetch_url(url, retries=5, base_delay=base_delay)
        if text is None:
            print(f"  FAILED {url} status {status}")
            continue
        out_path.write_text(text, encoding='utf-8')
        print(f"  OK {len(text)} bytes -> {out_path}")
        # update existing set
        existing.add(slug)
    print("Done.")
    # update counts.json
    pages_count=len(list(PAGES_DIR.glob("*.html")))
    images_count=len(list(IMAGES_DIR.glob("*"))) if IMAGES_DIR.exists() else 0
    with open(BASE/"counts.json","w") as f:
        json.dump({"pages": pages_count, "images": images_count}, f, indent=2)
    print(f"counts.json updated: pages {pages_count} images {images_count}")
    return 0

if __name__=="__main__":
    sys.exit(main())
