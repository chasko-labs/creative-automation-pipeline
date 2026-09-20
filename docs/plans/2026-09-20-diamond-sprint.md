## Goal

Make the KODIAK app layer diamond-strong end to end with a full team: close the
season-coverage gap (26 dropdown options resolve to 5 outcomes today), add the
three forward-deployed engineer personas, extend not-nova-act with localized
tests for every persona city/frontier, and ship it all through adversarial
review to merge with zero bounce-back to Bryan.

## Success Criteria

- Seasonal select offers only what resolves: every month maps to a season
  pairing, every holiday maps to a real catalog recipe (no quiet default).
- All 26 seasonal options resolve to real pairings from the 516-record catalog; each new pairing has a test + dev receipt.
- Persona cards 24–26 (Adam, Ryan, Drew) land in the persona doc in the
  existing card convention.
- not-nova-act gains a localized KODIAK suite parameterized by persona city
  (7) and featured frontier, green in CI.
- Adversarial mentors find nothing above minor; all findings fixed or filed
  with owners. Merge to dev with receipts; nothing returns to Bryan
  unresolved.

## Context And Current Facts

- Dev HEAD 63b20ee; critic SIGNOFF ×2; Lambda on image c416b997; dev live.
- Season chain: `season_pairing.py` (4 season keys + static default;
  the dropdown's 26 options — 12 months + 4 seasons + 10 holidays — collapse
  to 5 outcomes), `recipe_card._season_fallback_recipe`, `_season_pairing` /
  `_seasonal_recipe_default` in `generate_lambda.py`, 516-record
  `data/recipes/kodiak-recipes.json` (4 wired, 512 not).
- Dropdown (`market-disclosure.js`): 12 months + 4 seasons + 10 holidays = 26
  options collapsing to 5 outcomes.
- Personas: `docs/ux-personas-kodiak-complete.md` (23 cards, 7 cities:
  Park City ×15, Salt Lake area ×4, Chicago, Cincinnati, Minneapolis area,
  Denver, Austin).
- Harness: `~/code/heraldstack/not-nova-act` (`eval/test_r4_kodiak.py`
  pattern: browser_act + pydantic extract against live site).
- Open issues in scope: #40 Publix logo, #198 retailer coverage, #305 seed
  expansion, #280 frontier granularity, #201 preview copy/exports, #246
  export header. New issue to file: season-26 coverage.
- Adam/Ryan/Drew: names + forward-deployed titles only (no profile fetch;
  locations default Remote unless they say otherwise).

## Constraints And Non-goals

- Nothing bounces to Bryan: agents own tooling/research gaps; confidence
  re-rated until every owner exceeds 80%.
- No mocks reported as success; mocked unit tests stay separate from live
  receipts (sprint standard).
- Every merge carries tests + docs + kodiak-dev receipt.
- No LinkedIn scraping (auth-walled); no invented persona details.
- Prod push stays a separate deliberate step.

## Key Decisions

- Pair by ingredient/month moment, not by inventing recipes: new pairings
  point at real catalog records with reasons, same as the current 4.
- Dropdown prunes to what resolves rather than warning on dead options (the
  complaint class is silent dead ends).
- Localized tests drive the live dev site through browser_act, parameterized
  by city market + frontier, asserting copy/telemetry not pixel equality.
- Team shape: 3 builders, 1 test lead, 2 adversarials, 1 reviewer, 1 merger
  (reviewer and merger are different agents; merger never approves own work).

## Recommended Approach

Phase 0 (planning round, first dispatch): owners read their issues, rate
confidence, name tooling needs; leads fill gaps until all exceed 80%.
Phase 1 (build fan-out): season pairing expansion + dropdown prune + persona
cards + localized suite, in parallel under isolation. Phase 2 (adversarial):
mentors attack the delta against persona bars; findings return to owners.
Phase 3: reviewer signoff, merger lands to dev with receipts, critic
re-check, close issues.

## Work Plan

0. Planning round (lead: architect): file season-26 issue; assign #40+#198
   → builder-retail, #305+#280 → builder-geo, season table+dropdown →
   builder-season, suite → test-lead, personas → architect; collect
   confidence + tooling needs; unblock to >80%.
1. builder-season: wire all 26 options to real records + reasons (months →
   season keys, holidays → dedicated pairings); prune anything left that
   lands on default; python tests + live receipt per new pairing.
2. builder-retail + builder-geo: close or advance assigned issues with
   receipts; file follow-ups with owners for anything unclosable.
3. architect: persona cards 24–26 in card convention (flows doc updated).
4. test-lead: `not-nova-act/eval/test_r5_kodiak_localized.py` — city ×
   frontier matrix, copy/telemetry assertions, dev URL.
5. mentor-a (app vs persona bars), mentor-b (suite honesty: mocks, dead
   options, silent defaults); findings → owners, re-verify.
6. reviewer: full-diff review; merger: land to dev, deploy receipts, issue
   updates, critic re-check workflow.

## Validation Plan

- `pytest tests/test_preview_campaign_data.py tests/test_preview_extend.py`
  + new pairing tests; `vitest run tests/vitest`.
- Live POST per new pairing (recipe + source==season-table); dropdown audit
  script: every option resolves non-default or is gone.
- `pytest not-nova-act/eval/test_r5_kodiak_localized.py` green.
- Critic workflow SIGNOFF with empty remaining; issues closed with receipt
  links.

## Risks / Rollback

- Holiday→recipe mapping is judgment: reasons cite the record, never invent;
  disputed pairings ship as default + filed follow-up.
- Browser-act flakiness: retry budget per test, quarantine file for flakes,
  never weaken assertions to green.
- Rollback: dev-only deploys; `git revert` per commit; Lambda image tags
  pinned per deploy.

## Planning Round Results (all owners >80)

- builder-season: 4 wired 95, months 90, holidays 82 (curated map verified
  against catalog), audit+receipts 80. Owns #313.
- builder-retail: #40 85 (PNGs landed, SVG/provenance follow-up), #198 82
  (Walmart strings-only decision recorded).
- builder-geo: #305 88 (SF/ATL/UT calendars sourced), #280 85 (Julian market
  confirmed, Pescadero/Castroville frozen), #304 schema first in own queue.
- test-lead: localized suite 82 (r4 pattern studied, 7 cities mapped).

## Open Questions

None. Adam/Ryan/Drew locations default Remote; corrected if they say
otherwise.
