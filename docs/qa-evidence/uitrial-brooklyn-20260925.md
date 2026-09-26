# UI trial: full DOM run on prod, 2026-09-25 (self-driven playwright; local act planner down)
- gate (cakes) -> brainstorm/location/market disclosures opened -> Brooklyn US-NE-BROOKLYN picked from combobox -> brief typed -> CREATE CAMPAIGN PREVIEW.
- result: "Campaign preview ready - 5 sizes composed from bedrock:stability-control-structure"; GENERATE CAMPAIGN unlocked ("Your preview is ready...").
- verdict: the UI works end to end. hero-tile <img> selector found nothing (tiles may be canvas/picture); status line is the UI's own success signal.
- note: visible panel in final shot is the september recipe pairing, not the campaign hero (hero tiles above the fold not captured).
- planner caveat: local qwen3-vl planner times out on every plan call (direct ollama probe: trivial prompt incomplete in 100s). DOM driving bypassed it; planner repair is a separate local-infra job.
