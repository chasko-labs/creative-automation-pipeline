"""Programmatic newsletter — Welcome to the Real Breakfast Club.

Renders MJML via Jinja2 from docs/newsletter-breakdown.md spec:
- Header: preheader + Free Shipping bar (Kodiak red #C1272D / brown-texture-2)
- Hero: circular KODIAK bear logo (180px), H1 welcome to the real breakfast club! (Roar/Noomkc 32px #C8102E), sub 16px brown #2c231b, pill BRKFSTCLUB
- CTAs: 3-up grid (mobile stacks) — maple pecan overnight oats / buttermilk power cakes / double dark chocolate muffin cup — 400x400 rounded 12px, Buy Now white on red
- Textures: brown-texture-2.webp header/footer #2c231b, mega-menu_red-bg.webp red bars
- Footer: whole grain greatness, @kodiakcakes, Privacy/Manage, Unsubscribe, address 8163 Gorgoza Pines Rd
- Programmatic: swaps product IDs from data/products/kodiak-full-catalog.json, hero from kodiak-primary-logo, historically great articles as Read More.

MJML is emitted as XML; compile to HTML with mjml CLI or use render_html fallback (Jinja directly to HTML table for email clients).
"""
from __future__ import annotations

import inspect
import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "newsletter.mjml.j2"

CATALOG_PATH = Path(__file__).parents[2] / "data" / "products" / "kodiak-full-catalog.json"
LOGO_CANDIDATES = [
    Path(__file__).parents[2] / "web" / "kodiak-posts-for-todays-frontier" / "assets" / "kodiak-primary-logo.png",
    Path(__file__).parents[2] / "input_assets" / "brand" / "logo.png",
]

DEFAULT_CTA_HANDLES = [
    "maple-pecan-overnight-oats",
    "buttermilk-power-cakes-flapjack-waffle-mix",
    "dark-chocolate-muffin-mix",
]

DEFAULT_ARTICLES = [
    {"title": "10 Tips to Cook a Flawless Flapjack", "url": "https://kodiakcakes.com/blogs/news/10-tips-to-cook-a-flawless-flapjack"},
]

BROWN_TEXTURE = "https://kodiakcakes.com/cdn/shop/t/97/assets/brown-texture-2.webp"
RED_TEXTURE = "https://kodiakcakes.com/cdn/shop/t/97/assets/mega-menu_red-bg.webp"
LOGO_URL_DEFAULT = "https://kodiakcakes.com/cdn/shop/files/Logo.svg"

def _load_catalog() -> dict:
    if CATALOG_PATH.exists():
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {"products": []}

def get_products_by_handles(handles: list[str] | None = None) -> list[dict[str, Any]]:
    """Resolve handles to {name, handle, url, image} from full catalog."""
    handles = handles or DEFAULT_CTA_HANDLES
    catalog = _load_catalog()
    # catalog stores products as list under 'products' or dict
    products = catalog.get("products", [])
    # fallback: if catalog top-level is list
    if isinstance(catalog, list):
        products = catalog
    index = {p.get("handle"): p for p in products if isinstance(p, dict)}
    out: list[dict[str, Any]] = []
    for h in handles:
        p = index.get(h)
        if p:
            imgs = p.get("images") or []
            img = imgs[0] if imgs else ""
            out.append({"handle": h, "name": p.get("name", h), "url": p.get("url", f"https://kodiakcakes.com/products/{h}"), "image": img, "price": p.get("price_usd", "")})
        else:
            # fallback stub for unknown handles — warn so placeholder rows never slip out silently
            try:
                stack = inspect.stack()
                caller_frame = stack[1] if len(stack) > 1 else None
                if caller_frame is not None:
                    caller_ctx = f"{caller_frame.filename}:{caller_frame.lineno} in {caller_frame.function}"
                else:
                    caller_ctx = "unknown"
                del stack
            except Exception:
                caller_ctx = "unknown"
            logger.warning("newsletter fallback stub for unknown product handle=%r (caller=%s)", h, caller_ctx)
            out.append({"handle": h, "name": h.replace("-", " ").title(), "url": f"https://kodiakcakes.com/products/{h}", "image": "", "price": ""})
    return out

def _jinja_env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=select_autoescape())

def render_newsletter_mjml(
    products: list[dict[str, Any]] | None = None,
    articles: list[dict[str, str]] | None = None,
    logo_url: str | None = None,
    discount_code: str = "BRKFSTCLUB",
    view_in_browser_url: str = "https://kodiakcakes.com",
    unsubscribe_url: str = "https://kodiakcakes.com/unsubscribe",
    extra_context: dict | None = None,
) -> str:
    """Render MJML via Jinja. Returns MJML XML string."""
    env = _jinja_env()
    tmpl = env.get_template(TEMPLATE_NAME)
    ctx: dict[str, Any] = {
        "products": products if products is not None else get_products_by_handles(),
        "articles": articles if articles is not None else DEFAULT_ARTICLES,
        "logo_url": logo_url or LOGO_URL_DEFAULT,
        "discount_code": discount_code,
        "view_in_browser_url": view_in_browser_url,
        "unsubscribe_url": unsubscribe_url,
        "brown_texture": BROWN_TEXTURE,
        "red_texture": RED_TEXTURE,
    }
    if extra_context:
        ctx.update(extra_context)
    return tmpl.render(**ctx)

def render_newsletter_html(*args, **kwargs) -> str:
    """Render MJML then naively wrap as HTML for preview.

    If mjml CLI is available, use it; otherwise return MJML with HTML comment wrapper.
    For email-client compatible HTML without mjml binary, downstream can call an MJML service.
    """
    mjml = render_newsletter_mjml(*args, **kwargs)
    # Try to compile via mjml if available (node)
    try:
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mjml", delete=False, encoding="utf-8") as f:
            f.write(mjml)
            tmp_mjml = f.name
        tmp_html = tmp_mjml + ".html"
        result = subprocess.run(["npx", "mjml", tmp_mjml, "-o", tmp_html], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and Path(tmp_html).exists():
            html = Path(tmp_html).read_text(encoding="utf-8")
            Path(tmp_mjml).unlink(missing_ok=True)
            Path(tmp_html).unlink(missing_ok=True)
            return html
        Path(tmp_mjml).unlink(missing_ok=True)
    except Exception:
        pass
    # Fallback: return MJML wrapped so callers can distinguish; also embed as HTML comment for preview
    return "<!-- MJML: compile with `npx mjml newsletter.mjml -o newsletter.html` -->\n" + mjml

def save_newsletter(out_dir: str | Path, filename: str = "newsletter.mjml", **kwargs) -> Path:
    """Render and save MJML + HTML preview to out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mjml = render_newsletter_mjml(**kwargs)
    (out / filename).write_text(mjml, encoding="utf-8")
    html = render_newsletter_html(**kwargs)
    html_name = filename.replace(".mjml", ".html") if filename.endswith(".mjml") else filename + ".html"
    (out / html_name).write_text(html, encoding="utf-8")
    return out / filename

# Convenience alias
render_newsletter = render_newsletter_mjml
