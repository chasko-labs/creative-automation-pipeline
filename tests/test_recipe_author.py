"""LLM-authored recipe fields + card legibility floor.

No network. Covers _validate_recipe_fields (strict shape, never fabricates),
_author_recipe_fields (None offline, parses a faked Converse reply, None on
garbage), and the _compose_recipe_card overflow guard (worst-case long lists
stay above the accent bar at every delivery ratio, with body ink present).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from creative_automation import generate


def _fields(**over):
    base = {
        "title": "Power Cakes Trail Stack",
        "ingredients": ["2 cups Power Cakes mix", "1 cup milk", "1 tbsp maple"],
        "steps": ["Whisk mix with liquid", "Cook on a hot griddle", "Stack and fuel up"],
    }
    base.update(over)
    return base


def test_validate_accepts_good_fields() -> None:
    out = generate._validate_recipe_fields(_fields(), "Power Cakes")
    assert out is not None and out["title"] == "Power Cakes Trail Stack"
    assert len(out["ingredients"]) == 3 and len(out["steps"]) == 3


def test_validate_rejects_garbage() -> None:
    assert generate._validate_recipe_fields(None, "P") is None
    assert generate._validate_recipe_fields([], "P") is None
    assert generate._validate_recipe_fields(_fields(title="  "), "P") is None
    assert generate._validate_recipe_fields(_fields(ingredients=["only one"]), "P") is None
    assert generate._validate_recipe_fields(_fields(steps=["a"] * 7), "P") is None
    assert generate._validate_recipe_fields(_fields(steps=["x" * 91] * 3), "P") is None
    assert generate._validate_recipe_fields(_fields(title="t" * 61), "P") is None
    assert generate._validate_recipe_fields(_fields(steps=[1, 2, 3]), "P") is None


def test_author_returns_none_offline(monkeypatch) -> None:
    monkeypatch.setattr(generate, "boto3", None)
    assert generate._author_recipe_fields("Power Cakes", "wild", "us") is None


class _FakeConverse:
    def __init__(self, text: str):
        self._text = text

    def converse(self, **kwargs):
        assert "maxTokens" in kwargs.get("inferenceConfig", {}), "maxTokens must be explicit"
        content = kwargs["messages"][0]["content"]
        assert all(set(c.keys()) == {"text"} for c in content), "author call is text-only"
        return {"output": {"message": {"content": [{"text": self._text}]}}}


def test_author_parses_valid_json(monkeypatch) -> None:
    monkeypatch.setattr(generate, "_bedrock_failfast_client", lambda **k: _FakeConverse(
        '{"title": "Wild Stack", "ingredients": ["2 cups mix", "1 cup milk"], '
        '"steps": ["whisk well", "cook golden"]}'
    ))
    out = generate._author_recipe_fields("Power Cakes", "wild mornings", "us")
    assert out is not None and out["title"] == "Wild Stack"


def test_author_returns_none_on_garbage(monkeypatch) -> None:
    monkeypatch.setattr(generate, "_bedrock_failfast_client", lambda **k: _FakeConverse(
        "just some prose, no json at all"
    ))
    assert generate._author_recipe_fields("Power Cakes", "wild", "us") is None
    monkeypatch.setattr(generate, "_bedrock_failfast_client", lambda **k: _FakeConverse(
        '{"title": "", "ingredients": [], "steps": []}'
    ))
    assert generate._author_recipe_fields("Power Cakes", "wild", "us") is None


def test_author_returns_none_on_client_error(monkeypatch) -> None:
    class _Boom:
        def converse(self, **kwargs):
            raise RuntimeError("throttled")

    monkeypatch.setattr(generate, "_bedrock_failfast_client", lambda **k: _Boom())
    assert generate._author_recipe_fields("Power Cakes", "wild", "us") is None


def _hero(path: Path, size=(640, 640)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (30, 90, 160)).save(path, "PNG")
    return path


def test_card_overflow_stays_above_accent_bar(tmp_path: Path) -> None:
    # worst case: 6 max-length items per column at every delivery ratio — no
    # text may touch the accent bar, and the body must carry real ink.
    hero = _hero(tmp_path / "hero.png")
    fields = {
        "title": "A Very Long Trail Stack Title That Must Wrap Nicely",
        "ingredients": [f"ingredient number {i} with extra words padding it out" for i in range(6)],
        "steps": [f"step number {i} do the thing then do the next thing" for i in range(6)],
    }
    accent = generate._hex_to_rgb(generate._accent_hex)
    for ratio in generate._DELIVERY_RATIOS:
        w, h = generate._CANVAS[ratio]
        out = generate._compose_recipe_card(hero, fields["title"], ratio, tmp_path / f"c-{ratio}.png", fields)
        with Image.open(out) as im:
            assert im.size == (w, h)
            rgb = im.convert("RGB")
            # accent bar intact across the full bottom row — nothing drew over it
            for x in (0, w // 4, w // 2, 3 * w // 4, w - 1):
                px = rgb.getpixel((x, h - 1))
                assert abs(px[0] - accent[0]) < 30 and abs(px[1] - accent[1]) < 30, (
                    f"{ratio}: accent bar overwritten at x={x}"
                )
            # body zone (below hero slot, above bar) carries text ink, not blank card
            body = [rgb.getpixel((x, y)) for x in range(60, w - 60, 17)
                    for y in range(int(h * 0.62), h - 20, 13)]
            ink = [p for p in body if sum(abs(a - b) for a, b in zip(p, (200, 170, 130))) > 90]
            assert len(ink) > len(body) // 20, f"{ratio}: body zone looks blank"
