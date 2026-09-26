# Video trial: two own campaigns on dev (build 0.1.021-7f918d7), 2026-09-26

Self-driven Playwright (the local vision planner is down; the page, JS,
handlers, and backend are the real dev site). Videos are trimmed to 0–105s:
gate through ready. Full PNG frames alongside.

## Campaign A — Austin, normal path
Market US-SC-AUSTIN. Brief: "trailhead sunrise, oatmeal cups and campfire
coffee before a hill country hike". Video: campA-trim.webm.

Timeline (campA.log):
- 5s gate passed, app interactive
- 7s market set (combobox filter instant), brief filled
- 8s Create Campaign Preview clicked
- 48s scenic notice (idea beyond photo pool — SDXL background path)
- 58s "Still composing — 0s so far. Big renders take a minute or two;
  nothing is stuck…" (plain words, no backend/30s talk)
- 68s "Campaign preview ready — 5 sizes composed", Generate unlocked

Frames: campA-market.png (Austin picked), campA-brief.png (brief in),
campA-s66.png (recipe card with SDXL art zones generating, no 404 boxes),
campC-strip-ready.png is campaign C below.

## Campaign B — Seattle, edge path (impossible brief)
Market US-W-SEA. Brief: "astronauts eating pancakes on the moon".
Video: campB-trim.webm. Same shape: ready at 68s, no miss card, no errors.
The honesty path (no pool photo) holds without failing the render.

## Campaign C — Austin again, tiles proof
Brief: "blueberry campfire flapjacks at a hill country sunrise".
Frame campC-strip-ready.png: all five tiles VISIBLE — blueberry pancakes at
sunset, EN/ES/VI copy per tile (Austin localizes Spanish + Vietnamese),
Prev/Next arrows, dots, per-tile Download. Ready at 57s.

## Performance observed
- Click to ready: 57–68s across three runs, jobs path, zero wall misses.
- First paint of tiles immediate at ready; one tile still composing
  (live extends land after — each extend is extra backend spend).
- Recipe card + SDXL art zones render inline with placeholders, no 404s
  (art mirrored to the site buckets; verified 200s on dev and prod).
- Console noise still open: three 404s + one aborted S3 renders request
  in the debug run — paths not yet identified, no UX impact seen.
- Earlier "empty tiles" scare was auto-scroll: the app scrolls to the
  status line on ready, so static screenshots miss the strip. Tiles were
  always in DOM and loaded. Test scripts must scroll #preview into view.
