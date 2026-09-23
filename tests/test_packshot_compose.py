"""Packshot-first compose fix — the white-bread/candy root-cause repair.

Contract source: docs/architecture/compose-fix/compose-fix-spec.md.

The pipeline generated food from a text prompt instead of compositing the real
product BOX it already owns (Banana Muffin rendered white bread, Chocolate Fudge
Brownie rendered candy). The fix makes product-composite the DEFAULT and generation
the FALLBACK:

  a) a mapped SKU resolves to a real 705599* box and takes the packshot-composite path
     (product_layer set on compose_creative), NEVER reaching generate_hero for its pixels
  b) an unmapped SKU resolves no packshot and falls through to generate_hero (generation)

These tests exercise the resolver (asset_store.resolve_packshot) and the _render_asset branch
offline: fetch_asset_key is monkeypatched to hand back a local box PNG for mapped keys, so
the S3 layer is not required and CI stays deterministic.
"""
from pathlib import Path

from PIL import Image

from creative_automation import campaign as campaign_mod
from creative_automation import asset_store


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_box_png(path: Path) -> Path:
    """A tiny opaque RGBA 'box' stand-in — stands for a real 705599* packshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (400, 600), (200, 120, 40, 255)).save(path, "PNG")
    return path


def _local_box_fetch(tmp_path: Path):
    """Return a fetch_asset_key replacement that materializes any 705599* key locally."""
    def _fetch(key: str, dest: Path):
        if key and "705599" in key.rsplit("/", 1)[-1]:
            return _make_box_png(Path(dest))
        return None

    return _fetch


def _asset(iso_name: str = "kodiak_us-sw_banana_1x1_en.png") -> dict:
    return {"iso_name": iso_name, "headline": "Fuel your frontier morning", "ratio": "1x1"}


# --------------------------------------------------------------------------- #
# resolver — asset_store.resolve_packshot reads sku-packshot-map.json
# --------------------------------------------------------------------------- #
def test_resolver_reads_packshot_map_for_mapped_skus():
    # the map is loaded from the committed manifest and carries the three flagship boxes
    m = asset_store._load_packshot_map()
    assert m, "packshot manifest did not load"
    for sku in (
        "banana-muffin-quick-bread-mix",
        "chocolate-fudge-brownie-mix",
        "blueberry-muffin-mix",
    ):
        entry = asset_store._packshot_entry_for(sku)
        assert entry is not None, f"{sku} not resolved from the manifest"
        assert "705599" in entry["packshot_key"], f"{sku} packshot_key is not a real box"


def test_resolver_returns_box_path_for_mapped_sku(tmp_path, monkeypatch):
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))
    hit = asset_store.resolve_packshot("banana-muffin-quick-bread-mix")
    assert hit is not None, "mapped SKU should resolve to a real box"
    assert Path(hit).exists()
    assert "705599" in Path(hit).name


def test_resolver_normalizes_handles(tmp_path, monkeypatch):
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))
    # display-name form (spaces, mixed case) still lands the chocolate-fudge box
    hit = asset_store.resolve_packshot("Chocolate Fudge Brownie Mix")
    assert hit is not None
    assert Path(hit).exists()


def test_resolver_returns_none_for_unmapped_sku(tmp_path, monkeypatch):
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))
    # no manifest entry and no local box on disk -> None (caller falls to generation)
    assert asset_store.resolve_packshot("totally-made-up-sku-xyz") is None


# --------------------------------------------------------------------------- #
# _render_asset branch — packshot precedence over generation
# --------------------------------------------------------------------------- #
def test_mapped_sku_takes_packshot_path_and_skips_generate_hero(tmp_path, monkeypatch):
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))

    # generate_hero must NOT paint the product pixels for a mapped SKU. It is still used
    # to paint the BACKGROUND scene, so we stub it to a plain background and record calls.
    calls = {"generate_hero": 0}

    def _fake_generate_hero(*, product_id, product_name, brief_msg, region, audience, out_path, idx):
        calls["generate_hero"] += 1
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (800, 800), (30, 60, 30)).save(out_path, "PNG")
        return Path(out_path), "mock", {}

    # capture the product_layer arg compose received
    seen = {}
    real_compose = campaign_mod.compose_creative

    def _spy_compose(*args, **kwargs):
        seen["product_layer"] = kwargs.get("product_layer")
        return real_compose(*args, **kwargs)

    monkeypatch.setattr(campaign_mod, "generate_hero", _fake_generate_hero)
    monkeypatch.setattr(campaign_mod, "compose_creative", _spy_compose)

    out_root = tmp_path / "out"
    product = {"id": "banana-muffin-quick-bread-mix", "name": "Banana Muffin and Quick Bread Mix"}
    patch = campaign_mod._render_asset(
        _asset(), product, "Fuel your frontier morning", "US-SW-LASCRUCES", "families",
        pack={}, out_root=out_root, idx=0,
    )

    assert patch["generated"] is True
    # the box was composited — product_layer reached compose and is a real 705599* file
    assert seen["product_layer"] is not None, "packshot not passed to compose_creative"
    assert "705599" in Path(seen["product_layer"]).name
    # hero_source records the packshot-composite mode, not a bare generated scene
    assert patch["hero_source"] == "asset-store:packshot-composite"
    assert patch["packshot"] is not None and "705599" in patch["packshot"]
    # the rendered ISO exists on disk
    assert Path(patch["file_path"]).exists()


def test_flagship_skus_all_take_packshot_path(tmp_path, monkeypatch):
    # Banana Muffin, Chocolate Fudge Brownie, Blueberry Muffin — the three retro exemplars
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))

    def _fake_generate_hero(*, product_id, product_name, brief_msg, region, audience, out_path, idx):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (800, 800), (30, 60, 30)).save(out_path, "PNG")
        return Path(out_path), "mock", {}

    monkeypatch.setattr(campaign_mod, "generate_hero", _fake_generate_hero)

    flagship = [
        ("banana-muffin-quick-bread-mix", "Banana Muffin and Quick Bread Mix"),
        ("chocolate-fudge-brownie-mix", "Chocolate Fudge Brownie Mix"),
        ("blueberry-muffin-mix", "Blueberry Muffin Mix"),
    ]
    for i, (pid, pname) in enumerate(flagship):
        out_root = tmp_path / f"out_{i}"
        patch = campaign_mod._render_asset(
            _asset(f"kodiak_us-sw_{pid}_1x1_en.png"),
            {"id": pid, "name": pname},
            "Fuel your frontier morning", "US-SW-LASCRUCES", "families",
            pack={}, out_root=out_root, idx=i,
        )
        assert patch["hero_source"] == "asset-store:packshot-composite", f"{pid} did not composite the box"
        assert "705599" in patch["packshot"], f"{pid} packshot is not a real box"


def test_unmapped_sku_falls_through_to_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))

    calls = {"generate_hero": 0}

    def _fake_generate_hero(*, product_id, product_name, brief_msg, region, audience, out_path, idx):
        calls["generate_hero"] += 1
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (800, 800), (30, 60, 30)).save(out_path, "PNG")
        return Path(out_path), "mock", {}

    seen = {}
    real_compose = campaign_mod.compose_creative

    def _spy_compose(*args, **kwargs):
        seen["product_layer"] = kwargs.get("product_layer")
        return real_compose(*args, **kwargs)

    monkeypatch.setattr(campaign_mod, "generate_hero", _fake_generate_hero)
    monkeypatch.setattr(campaign_mod, "compose_creative", _spy_compose)

    out_root = tmp_path / "out"
    product = {"id": "totally-made-up-sku-xyz", "name": "Nonexistent Product"}
    patch = campaign_mod._render_asset(
        _asset(), product, "Fuel your frontier morning", "US-SW-LASCRUCES", "families",
        pack={}, out_root=out_root, idx=0,
    )

    assert patch["generated"] is True
    # generation path: generate_hero produced the hero, no packshot composited
    assert calls["generate_hero"] == 1
    assert seen["product_layer"] is None, "unmapped SKU should not composite a box"
    assert patch["hero_source"] in ("mock", "bedrock:nova-pro")
    assert patch["packshot"] is None
    assert Path(patch["file_path"]).exists()


# --------------------------------------------------------------------------- #
# compose.py — product_layer composites verbatim, generation-free
# --------------------------------------------------------------------------- #
def test_compose_creative_composites_product_layer(tmp_path):
    from creative_automation.compose import compose_creative

    hero = _make_box_png(tmp_path / "bg.png")  # reuse helper for a plain background
    Image.new("RGB", (800, 800), (30, 60, 30)).save(hero, "PNG")
    box = _make_box_png(tmp_path / "705599018848_box.png")
    out = tmp_path / "iso.png"
    res = compose_creative(
        hero_path=hero, out_path=out, message="Keep it wild", ratio_key="1x1",
        product_layer=box,
    )
    assert Path(res).exists()
    img = Image.open(res)
    assert img.size == (1080, 1080)


def test_compose_creative_without_product_layer_still_renders(tmp_path):
    from creative_automation.compose import compose_creative

    hero = tmp_path / "bg.png"
    Image.new("RGB", (800, 800), (30, 60, 30)).save(hero, "PNG")
    out = tmp_path / "iso.png"
    res = compose_creative(hero_path=hero, out_path=out, message="Keep it wild", ratio_key="1x1")
    assert Path(res).exists()
    assert Image.open(res).size == (1080, 1080)


# --------------------------------------------------------------------------- #
# /generate handler code path — generate_hero (what _handle_preview/_handle_full call)
# --------------------------------------------------------------------------- #
# The LIVE website POST /generate runs generate_lambda.py -> _handle_preview ->
# generate.generate_hero (and _handle_full -> generate_hero_set -> generate_hero). The
# batch/CLI path (campaign.py::_render_asset, covered above) already threaded
# packshot-first; these tests prove the SAME precedence now runs on the generate_hero
# seam so a mapped SKU on the endpoint composites the verbatim box and the Stability
# restyle NEVER paints the product pixels. An unmapped SKU falls through to generation.
from creative_automation import generate as generate_mod  # noqa: E402 — mid-file import documents the generate_hero seam under test


def test_generate_hero_mapped_sku_takes_packshot_and_skips_stability(tmp_path, monkeypatch):
    # a mapped SKU (banana-muffin) resolves a real 705599* box -> generate_hero returns
    # the asset_store:packshot-composite source, sets provenance.packshot, and NEVER invokes the
    # Stability control-structure restyle (the generative step must not touch the box).
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))
    # no theme/sku/disk seed so the background falls to the deterministic mock backdrop —
    # keeps the test offline and isolates the packshot branch from seed resolution.
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)

    stability_calls = {"n": 0}

    def _spy_stability(seed, prompt, out_path, **_k):
        stability_calls["n"] += 1

    monkeypatch.setattr(generate_mod, "_stability_control_hero", _spy_stability)

    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="banana-muffin-quick-bread-mix",
        product_name="Banana Muffin and Quick Bread Mix",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )

    assert result.exists()
    # the endpoint's provenance field (top-level source) reports the composite path
    assert source == generate_mod.PACKSHOT_SOURCE == "asset-store:packshot-composite"
    # provenance carries the additive packshot fields the /generate response ships
    assert prov["engine"] == "packshot-composite"
    assert prov["seed_selection"] == "packshot"
    assert prov["packshot"] is not None and "705599" in prov["packshot"]
    # the generative restyle was NEVER called — the product pixels are the pasted box
    assert stability_calls["n"] == 0


def test_generate_hero_mapped_sku_composites_verbatim_box(tmp_path, monkeypatch):
    # the real box reaches compose_creative's product_layer verbatim on the generate_hero
    # path (same guarantee _render_asset gives): compose is the only thing that paints the
    # product, and it pastes the box as-is (no cover-fit, no scrim, no restyle).
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o: None)

    seen = {}
    import creative_automation.compose as compose_mod
    real_compose = compose_mod.compose_creative

    def _spy_compose(*args, **kwargs):
        seen["product_layer"] = kwargs.get("product_layer")
        return real_compose(*args, **kwargs)

    monkeypatch.setattr(compose_mod, "compose_creative", _spy_compose)

    out = tmp_path / "hero.png"
    result, source, _prov = generate_mod.generate_hero(
        product_id="chocolate-fudge-brownie-mix",
        product_name="Chocolate Fudge Brownie Mix",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    assert source == "asset-store:packshot-composite"
    assert seen.get("product_layer") is not None, "packshot not passed to compose_creative"
    assert "705599" in Path(seen["product_layer"]).name


def test_generate_hero_unmapped_sku_falls_through_to_generation(tmp_path, monkeypatch):
    # an unmapped SKU resolves NO packshot -> generate_hero must reach the generative
    # seam (Stability restyle on a real seed), NOT the packshot-composite branch.
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))
    seed = tmp_path / "seed.png"
    seed.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1024, 1024), (180, 90, 30)).save(seed, "PNG")
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: seed)

    stability_calls = {"n": 0}

    def _spy_stability(s, prompt, out_path, **_k):
        stability_calls["n"] += 1

    monkeypatch.setattr(generate_mod, "_stability_control_hero", _spy_stability)
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: None)

    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="totally-made-up-sku-xyz",
        product_name="Nonexistent Product",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    # generation path — Stability was invoked (then fell back to pillow-compose)
    assert stability_calls["n"] == 1
    assert source == "bedrock:nova-pro"
    assert prov["engine"] == "pillow-compose"
    assert prov["packshot"] is None
    assert prov["seed_selection"] != "packshot"
