"""#203 honesty tests: every scored card runs a real test that can fail."""
from pathlib import Path

from PIL import Image

from creative_automation import scorecards as sc


def _flat(path: Path, size=(1080, 1080), color=(255, 248, 240)):
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def test_logo_card_fails_on_flat_image(tmp_path):
    p = _flat(tmp_path / "KODIAK-CAKES-BUTTERMILK-US-PARKCITY-HP-1X1-20260908-v01.png")
    cards = {c["id"]: c for c in sc.score_image_determinism(p)["cards"]}
    assert cards["logo"]["pass"] is False
    assert cards["logo"]["score"] == 0


def test_logo_card_passes_on_varied_mark(tmp_path):
    p = tmp_path / "KODIAK-CAKES-BUTTERMILK-US-PARKCITY-HP-1X1-20260908-v01.png"
    img = Image.new("RGB", (1080, 1080), (255, 248, 240))
    px = img.load()
    for x in range(24, 164):
        for y in range(24, 164):
            px[x, y] = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 3) % 256)
    img.save(p, "PNG")
    cards = {c["id"]: c for c in sc.score_image_determinism(p)["cards"]}
    assert cards["logo"]["pass"] is True


def test_font_card_fails_without_gin(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "load_tokens", lambda: {"headline": "DejaVu Sans"})
    p = _flat(tmp_path / "KODIAK-CAKES-BUTTERMILK-US-PARKCITY-HP-1X1-20260908-v01.png")
    cards = {c["id"]: c for c in sc.score_image_determinism(p)["cards"]}
    assert cards["font"]["pass"] is False


def test_bear_check_can_fail(tmp_path):
    # flat parchment: bear pixel IS parchment -> compose must fail (no `or True`)
    p = _flat(tmp_path / "KODIAK-CAKES-BUTTERMILK-US-PARKCITY-HP-1X1-20260908-v01.png")
    cards = {c["id"]: c for c in sc.score_image_determinism(p)["cards"]}
    assert cards["compose"]["pass"] is False


def test_unscored_cards_excluded_from_verdict(tmp_path):
    p = _flat(tmp_path / "KODIAK-CAKES-BUTTERMILK-US-PARKCITY-HP-1X1-20260908-v01.png")
    result = sc.score_image_determinism(p)
    by_id = {c["id"]: c for c in result["cards"]}
    for cid in ("report", "variants", "provenance"):
        assert by_id[cid].get("scored") is False
        assert by_id[cid]["max"] == 0
    scored = [c for c in result["cards"] if c.get("scored", True)]
    assert result["total"] == sum(c["score"] for c in scored)
    assert result["max"] == sum(c["max"] for c in scored)
    assert result["pass"] is False  # flat image fails real cards; placeholders can't rescue it
