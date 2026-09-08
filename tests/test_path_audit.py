"""Path audit: definition of done + scorecard per campaign path family.

Runs the real generate_hero_set offline (Nova/Stability stubbed, theme seeds
real) once per representative theme across the four chip families — regional,
retailer, what-to-make, creative angle — plus the US Ski partner. Each path is
scored against the same DoD cards; the suite passes only at 100% (brutal
convention: no lenient C). A JSON scorecard is also written to /tmp for review.
"""
from __future__ import annotations

import json
import pathlib
import tempfile

from PIL import Image

from creative_automation import generate

_TMP = pathlib.Path(tempfile.gettempdir())

# path family -> representative themes shipped in the UI
PATHS: dict[str, list[str]] = {
    "regional": ["localized-costco"],  # market-framed retailer run exercises the regional path
    "retailer": ["localized-costco", "localized-publix", "localized-target", "kodiak-subscription"],
    "what-to-make": ["recipe-cards"],
    "creative-angle": ["wild-grizzly-bears", "riff-on-past-content"],
    "partner": ["us-ski-snowboard"],
}

_FIXTURE = pathlib.Path("tests/fixtures/dam-real-keys.txt")
_PREFIX = "brands/kodiak/raw-ingest/kodiakcakes/images/"


def _real_keys() -> set[str]:
    return {ln.strip() for ln in _FIXTURE.read_text().splitlines() if ln.strip()}


def _png(path: pathlib.Path, color=(120, 30, 200)) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (300, 300), color)
    d = Image.new("RGB", (60, 60), (10, 200, 90))
    img.paste(d, (40, 40))
    img.save(path, "PNG")
    return path


def _seed_offline(tmp_path, monkeypatch) -> None:
    seed = _png(tmp_path / "seed.png")
    import creative_automation.dam as dam

    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(dam, "fetch_dam_key", lambda key, dest: _png(dest))
    monkeypatch.setattr(generate, "_stability_control_hero",
                         lambda seed_path, prompt, out: _png(out))
    monkeypatch.setattr(generate, "_stability_outpaint", lambda *a, **k: None)
    # real dispatch text, no network: deterministic default drives the prompt
    monkeypatch.setattr(generate, "_nova_pro_scene_prompt",
                         lambda *a, **k: generate._default_scene_prompt(*a[1:6]))
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)
    monkeypatch.setattr(generate, "_author_recipe_fields", lambda *a, **k: None)


def _score_theme(theme: str, tmp_path, monkeypatch) -> dict:
    """Run one theme through the seeded ladder; return {card: bool} DoD results."""
    _seed_offline(tmp_path, monkeypatch)
    out_dir = tmp_path / f"set-{theme}"
    real = _real_keys()
    cards: dict[str, bool] = {}
    try:
        renders, source, prov = generate.generate_hero_set(
            product_id="power-cakes",
            product_name="Power Cakes",
            brief_msg=f"campaign brief for {theme}",
            region="us",
            audience="active families",
            out_dir=out_dir,
            theme=theme,
        )
    except Exception as e:  # noqa: BLE001 — a crash fails every card, honestly
        return {"ran": False, "error": str(e)}

    # DoD 1: all four ratios render at exact canvas dims
    dims = {r["ratio"]: (r["w"], r["h"]) for r in renders}
    cards["four-ratios-exact-dims"] = dims == {
        "1x1": (1080, 1080), "4x5": (1080, 1350),
        "9x16": (1080, 1920), "16x9": (1920, 1080),
    }
    # DoD 2: theme seed is a real DAM key, never fabricated — and the run
    # actually consumed the theme-photo path (not a silent product fallback)
    theme_key = generate._resolve_theme_photo(theme) or ""
    cards["real-dam-seed"] = theme_key.startswith(_PREFIX) and theme_key[len(_PREFIX):] in real
    cards["theme-photo-path-taken"] = prov.get("seed_selection") == "theme-photo"
    # DoD 3: scene prompt carries an explicit dispatch (no bare-noun branding)
    scene = str(prov.get("scene_prompt") or "")
    cards["explicit-scene-dispatch"] = len(scene) > 40 and "on-brand Kodiak" not in scene
    # DoD 4: copy sidecar ships with the brief + theme line
    sidecar = generate.build_copy_sidecar(prov, f"campaign brief for {theme}", theme=theme)
    cards["copy-sidecar"] = "campaign brief for" in sidecar["txt"] and f"theme: {theme}" in sidecar["txt"]
    # DoD 5: provenance is honest (engine + seed selection recorded)
    cards["honest-provenance"] = bool(prov.get("seed_selection")) and source is not None
    # DoD 6: no raw celebrity token anywhere near the prompts
    blob = (scene + " " + sidecar["txt"]).lower()
    cards["no-celebrity-token"] = "zac efron" not in blob and "zac-efron" not in blob
    # path-specific cards
    if theme in ("localized-costco", "localized-publix", "localized-target", "kodiak-subscription"):
        cards["retailer-framing-in-copy"] = "retailer framing:" in sidecar["txt"]
    if theme == "recipe-cards":
        cards["card-template-applied"] = prov.get("card_template") is True
        cards["recipe-author-recorded"] = prov.get("recipe_author") in ("nova", "default")
    if theme == "wild-grizzly-bears":
        cards["wild-dispatch"] = "grizzly-country meadow" in scene.lower()
    if theme == "us-ski-snowboard":
        cards["partner-mark-available"] = generate._PARTNER_MARK_ASSET.exists()
    return {"ran": True, "cards": cards}


def test_path_scorecards_all_green(tmp_path, monkeypatch) -> None:
    scorecard: dict[str, dict] = {}
    failures: list[str] = []
    for family, themes in PATHS.items():
        for theme in themes:
            result = _score_theme(theme, tmp_path / family, monkeypatch)
            scorecard[f"{family}/{theme}"] = result
            if not result.get("ran"):
                failures.append(f"{theme}: DID NOT RUN ({result.get('error')})")
                continue
            for card, ok in result["cards"].items():
                if not ok:
                    failures.append(f"{theme}: card failed: {card}")
    (_TMP / "path-audit-scorecard.json").write_text(json.dumps(scorecard, indent=1))
    assert not failures, "path audit failures:\n" + "\n".join(failures)
