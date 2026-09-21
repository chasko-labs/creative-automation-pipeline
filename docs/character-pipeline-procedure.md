# character pipeline: local proof → locked style → cloud scale

Rule of the road: nothing touches paid cloud until the signature style is
approved on the free local box. Local proves, cloud scales.

## phase 1 — local proof of concept (this box, ComfyUI `:8188`, $0)

1. Import `comfyui-workflows/character-sheet-base-ui.json` (drag onto canvas).
   Read `comfyui-workflows/character-sheet-GUIDE.md` first if ComfyUI is new —
   it names every node, wire, and widget.
2. Paste the character identity paragraph over `__IDENTITY__`. Queue. Iterate
   WORDS only (never settings) until the sheet matches the description.
3. Lock it: record seed + export the workflow file. Sheet + seed + workflow =
   the character definition. Get signoff on the sheet before anything else.
4. Action test: duplicate the positive box, append ONE action clause
   (e.g. "tying a bowline knot, rope in hands"), new seed, Queue. Confirm the
   face/hair/uniform survive the pose change. Two passing actions = procedure
   proven.

## phase 2 — style lock (still local, still $0)

5. Freeze three text blocks into the project: identity paragraph (verbatim
   forever), style anchor (comic ink + halftone wording), negative list.
6. Write the action list (approved survival tasks only — first aid demo, knot
   tying, tent pitching, trail navigation, water safety, campfire cooking).
7. Produce the matrix file: characters × actions × seeds. One row per render,
   same shape as `data/seeding/matrix-oh-oc.json`.

## phase 3 — cloud scale (Bedrock, paid, fast)

8. One shakedown shot through `stability.stable-image-core-v1:1` (us-west-2,
   ~$0.04) using the frozen blocks. Confirm the cloud holds the style.
9. Port the matrix to the cloud driver pattern (`scripts/seed_campaign_cells.py`:
   existence gate, JSON-lines manifest, prompt stamped into PNG metadata).
10. Run markets/characters in parallel — quota is 90 req/min, per-shot latency
    is the clock driver. Verify with the coverage audit pattern, eyeball a
    sample per character for drift, commit + push everything including renders.

## modesty gate — kid-safe Girl Scout art (every sheet, pre-phase 2)

Ground: the Girl Scout Promise — On my honor, I will try: to serve God
and my country, to help people at all times, and to live by the Girl
Scout Law. Artwork carries that honor: kid-safe, always.

Bar: full-length shirts, zero midriff showing. High necklines.
Full-length pants or skirts. Athletic wear only as shorts-over-tights:
tights or leggings layer under every short, no exceptions. Blades never
open and never raised — closed/folded knives held down at the side only.

Gate: eyeball every sheet pass/fail against this bar before it leaves
proof-of-concept. Failures re-render words-only (never settings) until
they pass. No pass, no phase 2.

## what comes back to Bryan per phase

- phase 1: approved character sheet PNG + seed + exported workflow.
- phase 2: frozen text blocks + matrix file.
- phase 3: manifest + coverage report + pushed pool renders.
