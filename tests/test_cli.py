"""CLI subcommand tests — newsletter, scorecards, recipes.

Runs from repo root (relative data paths). Uses cli.main(argv) directly so the
legacy-flag routing and subcommand dispatch are both exercised without a subprocess.
"""
import json
from pathlib import Path

from creative_automation import cli
from creative_automation.brief import load_brief
from creative_automation.pipeline import run_pipeline


def test_newsletter_subcommand_writes_files(tmp_path):
    out = tmp_path / "nl"
    rc = cli.main(["newsletter", "--out", str(out), "--discount-code", "BRKFSTCLUB"])
    assert rc == 0
    mjml = out / "newsletter.mjml"
    html = out / "newsletter.html"
    assert mjml.exists(), f"missing {mjml}"
    assert html.exists(), f"missing {html}"
    # mjml is non-trivial and carries the discount code
    assert "BRKFSTCLUB" in mjml.read_text(encoding="utf-8")


def test_scorecards_subcommand_produces_scorecards_json(tmp_path):
    # generate a small batch first so there are creatives to score
    brief = load_brief("briefs/kodiak-on-the-go.yaml")
    out = tmp_path / "out"
    run_pipeline(brief, Path("input_assets"), out)

    rc = cli.main(["scorecards", "--out", str(out)])
    assert rc == 0
    dest = out / "scorecards.json"
    assert dest.exists(), f"missing {dest}"
    result = json.loads(dest.read_text(encoding="utf-8"))
    assert result["images_scored"] == 9
    assert "overall_brutal_pass" in result
    assert isinstance(result["brutal_cards"], list) and result["brutal_cards"]


def test_recipes_subcommand_filters_by_category(capsys):
    rc = cli.main(["recipes", "--category", "flapjacks", "--limit", "5"])
    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    # header + up to 5 recipe rows
    assert lines[0].startswith("[recipes]")
    rows = [line for line in lines[1:] if line.strip()]
    assert 1 <= len(rows) <= 5
    # every listed row is in the flapjacks category
    assert all("flapjacks" in row for row in rows)


def test_recipes_subcommand_query_and_json(capsys):
    rc = cli.main(["recipes", "--query", "chocolate", "--limit", "3", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert 1 <= len(payload) <= 3
    # substring match holds against name or product
    for r in payload:
        blob = f"{r.get('name', '')} {r.get('product', '')}".lower()
        assert "chocolate" in blob


def test_legacy_flag_form_routes_to_generate(tmp_path):
    # bare --brief form must still work (routes to `generate` subcommand)
    out = tmp_path / "legacy"
    rc = cli.main(["--brief", "briefs/kodiak-on-the-go.yaml", "--assets", "input_assets", "--out", str(out)])
    assert rc == 0
    assert (out / "report.json").exists()



def test_campaign_subcommand_prints_counts_and_returns_zero(capsys):
    # D1 campaign fan-out via the CLI, bare market key, offline (no render)
    rc = cli.main(["campaign", "--market", "US-SE-ATL", "--month", "2026-09"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[campaign]" in out
    # prints asset + card + lockup counts
    assert "assets=" in out
    assert "recipe_cards=" in out
    assert "lockups=" in out
    assert "market=US-SE-ATL" in out
