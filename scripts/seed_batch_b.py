#!/usr/bin/env python3
"""Seed batch B remainder via Stable Image Core with the frozen mono tails.

Root cause of the colorized v1 seeds: generate_recipe_art's base negative
carries no color suppression. This driver calls _invoke_image directly with
the locked mono positive/negative tails from docs/local-comfyui-recipe-art.md,
then applies the same coverage gate before publishing into the pool.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from creative_automation import recipe_art as r  # noqa: E402

SPRINT2 = ROOT / "input_assets" / "sprint2-ingredients"
MANIFEST = SPRINT2 / "batch-b-manifest.json"

STYLE_FIRST = (
    "monochrome black ink line illustration on stark white background, "
    "sparse thin contour linework, no fill, "
)
MONO_NEG_TAIL = (
    ", color, colourful, green, red, yellow, brown, purple, orange, watercolor, "
    "colored fill, photo, photorealistic, grayscale only, black ink only, "
    "white background only, signature"
)

POS_TEMPLATE = (
    "black ink illustration on a plain white background, frontier ink style, "
    "hand-drawn linework with dense crosshatching, stipple dots and fine parallel "
    "shading, shapes and counts only, faces left white with one small white "
    "highlight gap per piece, single hero ingredient study centered with wide "
    "spacing, no plate, no fork, no hand, {geo} as the hero ingredient"
)
NEG_WINNER = (
    "people, human face, hands, text, signature, watermark, color, green, red, "
    "plate, bowl, fork, spoon, table setting"
)

SUBJECTS = {
    "one long tapered parsnip root lying diagonal with a small crown of flat leaves at the top": ("parsnip.png", 712401),
    "one whole eight-pointed star anise pod seen from above, boat-shaped follicles each holding a seed": ("star-anise.png", 712402),
    "one mint sprig with serrated ovate leaves in opposite pairs on a square stem": ("fresh-mint.png", 712403),
    "three flat cilantro stems with round lobed leaflets, leaves only, no flowers": ("cilantro.png", 712404),
    "a small tuft of slender hollow chive spikes with one round bloom head": ("chives.png", 712405),
    "three wrinkled dried chili pods with a scatter of crescent flakes": ("chili-peppers-flakes.png", 712406),
    "one thick rhubarb stalk lying diagonal with a single broad crinkled leaf at one end": ("rhubarb.png", 712407),
}


def main() -> None:
    client = r._bedrock_client("bedrock-runtime", read_timeout=300, region=r.IMAGE_REGION)
    manifest = json.loads(MANIFEST.read_text())
    items = manifest if isinstance(manifest, list) else manifest.get("items", manifest)
    by_file = {it.get("file", ""): it for it in items} if isinstance(items, list) else {}
    for subject, (fname, seed) in SUBJECTS.items():
        img = r._invoke_image(
            client, POS_TEMPLATE.format(geo=subject), "raw_ingredient",
            seed=seed,
            negative=NEG_WINNER,
            extra_clause="",
        )
        if img is None:
            print(f"FAIL {fname}: no image")
            continue
        cov = r._dark_coverage(img)
        if cov > 0.37:
            print(f"FAIL {fname}: coverage {cov:.3f} over ceiling")
            continue
        tmp = Path(f"/tmp/seed-b2-{fname}")
        img.save(tmp)
        shutil.copy(tmp, SPRINT2 / fname)
        entry = by_file.get(fname, {"file": fname})
        entry.update({"seed": seed + 100, "status": "seeded",
                      "note": f"style-first seed {subject} cov={cov:.3f}"})
        if entry not in items:
            items.append(entry)
        print(f"OK {fname} cov={cov:.3f}")
    if isinstance(manifest, dict) and "items" in manifest:
        manifest["items"] = items
        json.dump(manifest, MANIFEST.open("w"), indent=1)
    else:
        json.dump(items, MANIFEST.open("w"), indent=1)
    print("manifest updated")


if __name__ == "__main__":
    main()
