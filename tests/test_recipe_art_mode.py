"""mode=recipe-art: seeded DAM hit, generate+publish, bad inputs. Offline."""
from __future__ import annotations

from pathlib import Path

import creative_automation.generate_lambda as gl


def _stub_recipe(monkeypatch, name="Roasted Grape Flapjack Topper"):
    monkeypatch.setattr(gl, "_recipe_catalog_name", lambda rid: name if rid == "r1" else None)


def test_unknown_zone_rejected(monkeypatch) -> None:
    _stub_recipe(monkeypatch)
    resp = gl._handle_recipe_art({"recipe_id": "r1", "zone": "nope"})
    assert resp["ok"] is False


def test_unknown_recipe_rejected(monkeypatch) -> None:
    _stub_recipe(monkeypatch)
    resp = gl._handle_recipe_art({"recipe_id": "missing", "zone": "raw_ingredient"})
    assert resp["ok"] is False


def test_seeded_hit_returns_site_url(monkeypatch, tmp_path: Path) -> None:
    _stub_recipe(monkeypatch)

    class _Dam:
        @staticmethod
        def recipe_art_exists(slug: str, zone: str) -> bool:
            return True

        @staticmethod
        def recipe_art_site_url(slug: str, zone: str) -> str:
            return f"/recipe-art/{slug}/{zone}.png"

    class _Ra:
        @staticmethod
        def art_slug_candidates(subject: str) -> list[str]:
            return ["roasted-grape-flapjack-topper"]

    import creative_automation.generate_lambda as _gl
    import creative_automation.dam as _real_dam

    monkeypatch.setattr(_real_dam, "recipe_art_exists", _Dam.recipe_art_exists)
    monkeypatch.setattr(_real_dam, "recipe_art_site_url", _Dam.recipe_art_site_url)
    import creative_automation.recipe_art as _real_ra

    monkeypatch.setattr(_real_ra, "art_slug_candidates", _Ra.art_slug_candidates)
    resp = _gl._handle_recipe_art({"recipe_id": "r1", "zone": "technique"})
    assert resp == {
        "ok": True,
        "url": "/recipe-art/roasted-grape-flapjack-topper/technique.png",
        "seeded": True,
        "zone": "technique",
    }


def test_generate_publish_path(monkeypatch, tmp_path: Path) -> None:
    _stub_recipe(monkeypatch)
    made = tmp_path / "raw_ingredient.png"
    made.write_bytes(b"png")

    import creative_automation.dam as _real_dam
    import creative_automation.recipe_art as _real_ra

    monkeypatch.setattr(_real_dam, "recipe_art_exists", lambda slug, zone: False)
    monkeypatch.setattr(
        _real_dam, "upload_recipe_art", lambda local, slug, zone: f"/recipe-art/{slug}/{zone}.png"
    )
    monkeypatch.setattr(_real_ra, "art_slug_candidates", lambda subject: ["roasted-grape"])
    monkeypatch.setattr(_real_ra, "generate_recipe_art", lambda *a, **k: made)
    resp = gl._handle_recipe_art({"recipe_id": "r1", "zone": "raw_ingredient"})
    assert resp["ok"] is True
    assert resp["seeded"] is False
    assert resp["url"] == "/recipe-art/roasted-grape/raw_ingredient.png"


def test_generate_none_keeps_placeholder(monkeypatch) -> None:
    _stub_recipe(monkeypatch)
    import creative_automation.dam as _real_dam
    import creative_automation.recipe_art as _real_ra

    monkeypatch.setattr(_real_dam, "recipe_art_exists", lambda slug, zone: False)
    monkeypatch.setattr(_real_ra, "art_slug_candidates", lambda subject: ["roasted-grape"])
    monkeypatch.setattr(_real_ra, "generate_recipe_art", lambda *a, **k: None)
    resp = gl._handle_recipe_art({"recipe_id": "r1", "zone": "finished_plate"})
    assert resp["ok"] is False
