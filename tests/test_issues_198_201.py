"""Issues #198 + #201 — retailer coverage + output copy. OFFLINE, cred-free.

#198: chooser/retailer surfaces Costco, Publix, Target + the Kodiak DTC
subscription retailer-equivalent, weighted toward rural/frontier markets.
#201: (1) ES/PT rows never read as verbatim English — live Translate, else the
offline dictionary (real translated strings), else a tagged suffix; the Lambda
role carries the TranslateText grant. (2) per-platform post copy for all eight
publish targets. (3) the export table carries a blog row (1200x630).

No AWS: creds env is stripped, so the rewrite seam returns source="mock" and
every live-transport assertion runs against a stubbed boto3 client.
"""
from __future__ import annotations

import json
import pathlib

import pytest
import yaml

from creative_automation import platform_copy, retailers, text_rewriter
from creative_automation import platforms as platform_matrix
from creative_automation.asset_pack import market_retailers
from creative_automation.campaign import _plan_lockups
from creative_automation.generate_lambda import _build_localizations
from creative_automation.localize import OFFLINE

REPO = pathlib.Path(__file__).resolve().parents[1]

WASATCH = (
    "Keep It Wild \u2014 protein-packed whole grains for your Wasatch frontier. "
    "Nourishment for Today's Frontier"
)


@pytest.fixture(autouse=True)
def _no_creds(monkeypatch):
    for var in (
        "AWS_ACCESS_KEY_ID",
        "AWS_PROFILE",
        "AWS_SESSION_TOKEN",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    ):
        monkeypatch.delenv(var, raising=False)


# ---- #198: subscription retailer-equivalent -------------------------------- #

def test_subscription_aliases_resolve():
    for raw in (
        "subscription",
        "Kodiak subscription",
        "KODIAK CAKES SUBSCRIPTION",
        "Subscribe & Save",
        "DTC subscription",
    ):
        assert retailers.normalize_retailer(raw) == "subscription"


def test_supported_retailers_is_all_four():
    assert set(retailers.SUPPORTED_RETAILERS) == {"costco", "publix", "target", "subscription"}


def test_is_rural_market_weights_frontier():
    assert retailers.is_rural_market(
        "US-UT-KAMASVALLEY",
        "Kamas Valley \u2014 Peoa / Oakley, UT 84036 (Wasatch Back rural)",
    )
    assert retailers.is_rural_market("US-MW-PARKCITY-84098", "no commercial retail")
    assert retailers.is_rural_market(
        "US-SW-TIMBERON", "Sacramento Mountains homesteaders, Timberon General Store"
    )
    assert not retailers.is_rural_market("US-MW-PARKCITY-84098", "Park City, Utah 84098")
    assert not retailers.is_rural_market("US-SE-ATL", "Atlanta, Georgia")


def test_surface_retailers_chains_lead_subscription_trails():
    # metro Atlanta: Publix + Target, no subscription.
    assert retailers.surface_retailers("Publix, Target", "US-SE-ATL", "Atlanta") == [
        "publix",
        "target",
    ]
    # rural Kamas: no chain grocer -> subscription fulfillment.
    assert retailers.surface_retailers(
        "Oakley Farmers Market (Rodeo Grounds) + Kamas Valley Market \u2014 no commercial retail",
        "US-UT-KAMASVALLEY",
        "Kamas Valley rural",
    ) == ["subscription"]
    # rural market WITH a chain still gets subscription, trailing.
    assert retailers.surface_retailers("Target, Walmart", "US-SW-TIMBERON", "homestead") == [
        "target",
        "subscription",
    ]
    # canonical order regardless of field order.
    assert retailers.surface_retailers("Target, Publix, Costco", "US-SE-FL", "Miami") == [
        "costco",
        "publix",
        "target",
    ]


def test_subscription_flows_into_pack_and_lockup_plan():
    assert "subscription" in market_retailers("Target, Kodiak subscription")
    lockups, _warnings = _plan_lockups(["Target", "Kodiak subscription"], "US-SE-ATL", {"retailers": {}})
    sub = [lk for lk in lockups if lk["retailer"] == "subscription"]
    assert sub, "subscription must plan a fulfillment entry"
    assert sub[0]["executor"] == "fulfillment.subscription"
    assert sub[0]["fulfillment"] == retailers.SUBSCRIPTION_FULFILLMENT
    assert sub[0]["logo_asset"] is None


# ---- #201(1): translation — never verbatim English -------------------------- #

def _load_cfn(path: pathlib.Path) -> dict:
    """yaml.safe_load that tolerates CloudFormation intrinsic tags (!Ref, !GetAtt)."""
    loader = yaml.SafeLoader
    loader.add_multi_constructor("", lambda ldr, suffix, node: None)
    return yaml.load(path.read_text(encoding="utf-8"), Loader=loader)


def test_lambda_role_grants_translate_text():
    doc = _load_cfn(REPO / "infra" / "generate-endpoint.yaml")
    statements = doc["Resources"]["GenerateLambdaRole"]["Properties"]["Policies"][0][
        "PolicyDocument"
    ]["Statement"]
    grants = [s for s in statements if "translate:TranslateText" in s.get("Action", [])]
    assert grants, "GenerateLambdaRole must allow translate:TranslateText (issue #201)"


def test_offline_dictionary_carries_real_es_pt():
    assert "Salvaje" in OFFLINE["es"][WASATCH]
    assert "Selvagem" in OFFLINE["pt"][WASATCH]


def test_build_localizations_offline_gives_real_es_pt():
    localizations, langs = _build_localizations(WASATCH, "US-MW-PARKCITY-84098")
    assert langs == ["en", "es", "pt"]
    by_lang = {loc["lang_code"]: loc for loc in localizations}
    assert by_lang["en"]["headline"] == WASATCH
    # real translated strings, not verbatim English (the #201 defect).
    assert by_lang["es"]["headline"] == OFFLINE["es"][WASATCH] != WASATCH
    assert by_lang["pt"]["headline"] == OFFLINE["pt"][WASATCH] != WASATCH
    assert by_lang["es"]["source"] == "translated"
    assert by_lang["pt"]["source"] == "translated"


def test_build_localizations_unknown_headline_never_verbatim():
    headline = "A brand-new line no dictionary has ever seen."
    localizations, _langs = _build_localizations(headline, "does-not-exist")
    by_lang = {loc["lang_code"]: loc for loc in localizations}
    assert by_lang["es"]["headline"] != headline
    assert by_lang["pt"]["headline"] != headline


def test_build_localizations_live_translate_path(monkeypatch):
    """Stubbed Amazon Translate proves the IAM-granted seam yields a real string."""
    # US-SE-ATL top-2 is es + ko: the stub answers per target language, proving
    # the seam translates whatever the market resolves (not just es/pt).

    class _FakeTranslate:
        def translate_text(self, Text, SourceLanguageCode, TargetLanguageCode):
            assert SourceLanguageCode == "en"
            return {"TranslatedText": f"TR-{TargetLanguageCode}: {Text}"}

    def _fake_client(service, region_name=None):
        if service == "translate":
            return _FakeTranslate()
        raise RuntimeError(f"no live {service} in unit tests")

    import boto3

    monkeypatch.setattr(boto3, "client", _fake_client)
    monkeypatch.setattr(text_rewriter, "_has_creds", lambda: True)
    headline = "Some fresh headline."
    localizations, langs = _build_localizations(headline, "US-SE-ATL")
    assert langs == ["en", "es", "ko"]
    by_lang = {loc["lang_code"]: loc for loc in localizations}
    assert by_lang["en"]["headline"] == headline
    for code in ("es", "ko"):
        assert by_lang[code]["headline"] == f"TR-{code}: {headline}"
        assert by_lang[code]["headline"] != headline
        assert by_lang[code]["source"] == "translated"


# ---- #201(2): per-platform post copy for all eight publish targets --------- #

def test_default_copy_covers_all_eight_publish_targets():
    copy = platform_copy.generate_platform_copy("Fuel your morning", "Power Cakes", "US-UT")
    assert set(copy.keys()) == set(platform_copy.PUBLISH_TARGETS)
    assert len(copy) == 8


def test_homepage_and_blog_have_post_copy():
    copy = platform_copy.generate_platform_copy(
        "Fuel your morning", "Power Cakes", "US-UT", platforms=["homepage", "blog"]
    )
    assert copy["homepage"]["headline"]
    assert copy["homepage"]["body"]
    assert copy["homepage"]["hashtags"] == []
    assert copy["blog"]["headline"]
    assert copy["blog"]["body"]
    assert copy["blog"]["hashtags"]
    for entry in copy.values():
        assert entry["source"] == "fallback"  # offline, deterministic


def test_linkedin_still_available_on_request():
    copy = platform_copy.generate_platform_copy(
        "Fuel your morning", "Power Cakes", "US-UT", platforms=["linkedin"]
    )
    assert set(copy.keys()) == {"linkedin"}


# ---- #201(3): blog row in the export table ---------------------------------- #

def test_matrix_json_has_blog_export_row():
    data = json.loads((REPO / "data" / "platforms" / "platform-matrix.json").read_text())
    blog = data["ratios"]["blog"]
    assert (blog["w"], blog["h"]) == (1200, 630)
    assert blog["platforms"] == ["blog"]
    assert data["platforms"]["blog"]["label"] == "Blog"
    web = json.loads(
        (REPO / "web" / "kodiak-posts-for-todays-frontier" / "data" / "platforms" /
         "platform-matrix.json").read_text()
    )
    assert web["ratios"]["blog"] == blog


def test_platform_loader_serves_blog():
    assert platform_matrix.ratio_dims("blog") == (1200, 630)
    assert platform_matrix.ratios_for_platform("blog") == ["blog"]
    assert platform_matrix.platforms_for_ratio("blog") == ["blog"]
