"""Local glimmer client — dev diagnostics + UI intelligence via 127.0.0.1:8181.

On-demand supervisor: glimmer_supervisor.py exposes stable OpenAI-compat at
GLIMMER_URL (8181) → proxy to llama-server 8182, serializes on valkey gpu_lock
vs fc-pool, IDLE 300s teardown. Today NGL=0 CPU fallback (reboot → 13 GPU).

Used as Muse Spark → glimmer delegate (local, no Bedrock bill):
- campaignBrief → structured brief JSON
- SKU picker 88 → 3
- local flavor season+source
- translation fallback after Nova Micro (unlimited Nova primary)
- visual QA via mmproj (screenshot → Bear at 24,24, Blaze ≤18%)

Always document Nova costs (Canvas per-image + Micro per-translate + Translate
per-char + CloudFront per-GB) but unlimited budget — go ham on
amazon.nova-2-multimodal-embeddings-v1:0 1024.

When 8181 unreachable (hosted d37333 / kodiak.bryanchasko.com), caller falls
through to Nova unlimited; offline dict only if Nova unreachable.
"""
from __future__ import annotations

import os
import json

try:
    import httpx  # type: ignore
except ImportError:
    httpx = None  # type: ignore

GLIMMER_URL = os.getenv("GLIMMER_URL", os.getenv("GLIMMER_ENDPOINT", "http://127.0.0.1:8181/v1"))
GLIMMER_MODEL = os.getenv("GLIMMER_MODEL", "muse-glimmer-30b")
TIMEOUT_S = int(os.getenv("GLIMMER_TIMEOUT_S", "60"))


def _post(path: str, payload: dict) -> dict | None:
    if httpx is None:
        return None
    try:
        r = httpx.post(f"{GLIMMER_URL}/{path.lstrip('/')}", json=payload, timeout=TIMEOUT_S)
        if r.status_code != 200:
            print(f"[glimmer] {path} {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"[glimmer] {path} unreachable (dev-only, fallback to Nova): {e}")
        return None


def glimmer_chat(prompt: str, max_tokens: int = 256, system: str | None = None) -> str | None:
    """Simple chat completion via 8181. Returns text or None if offline."""
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    data = _post("chat/completions", {"model": GLIMMER_MODEL, "messages": msgs, "max_tokens": max_tokens, "temperature": 0.3})
    if not data:
        return None
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def glimmer_parse_brief(brief_text: str) -> dict | None:
    """Freeform campaign brief → structured JSON (market hint, audience, message)."""
    sys = "You parse KODIAK frontier campaign briefs into JSON. Return ONLY JSON with keys: campaign_message (string, keep Keep It Wild / Nourishment punctuation if present), suggested_products (up to 3 names from KODIAK catalog), audience_hint (one of Park City HQ audience personas), region_hint (market code like US-SW-LASCRUCES if place mentioned)."
    prompt = f"Parse this brief into JSON, no prose:\n{brief_text}"
    out = glimmer_chat(prompt, max_tokens=400, system=sys)
    if not out:
        return None
    try:
        # extract first {..}
        start = out.find("{")
        end = out.rfind("}")
        if start != -1 and end != -1:
            return json.loads(out[start : end + 1])
    except Exception as e:
        print(f"[glimmer] parse_brief json fail: {e} :: {out[:200]}")
    return None


def glimmer_pick_skus(brief_text: str, catalog_names: list[str], k: int = 3) -> list[str] | None:
    """Rank catalog → top k SKUs for brief via glimmer."""
    sys = f"You are a KODIAK SKU ranker. Catalog has {len(catalog_names)} products. Return ONLY JSON array of {k} exact names from catalog, no prose."
    prompt = f"Brief: {brief_text}\nCatalog: {json.dumps(catalog_names[:40])}\nPick {k}."
    out = glimmer_chat(prompt, max_tokens=200, system=sys)
    if not out:
        return None
    try:
        import re
        m = re.search(r"\[.*\]", out, re.S)
        if m:
            arr = json.loads(m.group(0))
            # validate
            filtered = [x for x in arr if x in catalog_names][:k]
            if len(filtered) == k:
                return filtered
    except Exception:
        pass
    return None


def glimmer_diagnose_frontpage(html_snippet: str, screenshot_hint: str = "") -> str | None:
    """Visual QA prompt for diagnose.sh — checks Bear 24,24, Blaze, fonts, taste anti-slop."""
    sys = "You are a KODIAK brand QA + taste linter. Check: Bear at 24,24, Blaze Orange #E8530E ≤18% or 8px bar, gin headings (Typekit zjt4wyq n4) + museo-sans body, kodiak_sans hosted, Roar utility only, no purple/aura/cream #faf8f4/glass/bento/hover:scale. Return bullet fixes."
    prompt = f"HTML snippet (first 800 chars):\n{html_snippet[:800]}\nScreenshot hint: {screenshot_hint}\nList violations and fixes, no prose fluff."
    return glimmer_chat(prompt, max_tokens=500, system=sys)


def health() -> dict:
    """Probe 8181/v1/models — dev-only, fast."""
    data = _post("models", {})
    if data is None:
        # try GET fallback
        try:
            import httpx as hx
            r = hx.get(f"{GLIMMER_URL}/models", timeout=5)
            return {"ok": r.status_code == 200, "models": r.json() if r.status_code == 200 else None}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": True, "models": data}
