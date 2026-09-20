FROM public.ecr.aws/lambda/python:3.11
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/
# Ship ONLY the sku-photo-map into the image (single file — never COPY data/ wholesale;
# large data/ files ship only via their own single-file COPY lines with rationale).
# The env var points _resolve_map_path() at this stable /var/task location.
COPY data/products/sku-photo-map.json /var/task/data/products/sku-photo-map.json
ENV SKU_PHOTO_MAP_PATH=/var/task/data/products/sku-photo-map.json
# Ship the full product catalog (112KB) — dam_library's product-line facet joins
# raw-ingest keys to catalog categories via the sku-photo-map + this file.
# Without it the index soft-empties and every tile carries product_line=None.
COPY data/products/kodiak-full-catalog.json /var/task/data/products/kodiak-full-catalog.json
COPY data/products/theme-asset-map.json /var/task/data/products/theme-asset-map.json
ENV THEME_ASSET_MAP_PATH=/var/task/data/products/theme-asset-map.json
# Ship the packshot manifest (sku-packshot-map.json) — the compose-fix root-cause repair.
# Same class of bug as sku-photo-map (ba5855e) + theme-asset-map (1f1fb67): dam.py resolves
# it via parents[2]/docs/... which does NOT exist under the site-packages install, so
# without this COPY resolve_packshot() returns None for every SKU and the packshot-first
# composite silently degrades to generated-scene. The committed manifest lives at
# docs/architecture/compose-fix/; SKU_PACKSHOT_MAP_PATH points the resolver at the stable
# /var/task copy.
COPY docs/architecture/compose-fix/sku-packshot-map.json /var/task/data/products/sku-packshot-map.json
ENV SKU_PACKSHOT_MAP_PATH=/var/task/data/products/sku-packshot-map.json
# Ship the localization tables the runtime reads (retailer-frontier-pairs.json,
# market-languages.json, dialect/*.jsonl) plus the context-pack inputs (image-clusters,
# blog sample prompts). Without these the localization chain errored to fallback with
# "[Errno 2] .../data/localization/retailer-frontier-pairs.json" — pip install . does
# NOT bundle data/, so parents[2]/data does not exist in the image. CAP_DATA_ROOT points
# _datapaths.data_root() at this stable /var/task/data location. Copy the localization
# dir + the two context-pack files ONLY (the embeddings library ships via its own
# COPY below with rationale).
COPY data/localization/ /var/task/data/localization/
COPY data/vectors/image-clusters.json /var/task/data/vectors/image-clusters.json
# Ship the brand-voice embedding library (46MB) — director_memory.retrieve() reads it
# via CAP_DATA_ROOT. Without this COPY the library is absent in the image, retrieve()
# yields [], and every headline silently degrades to stock Nova even with the
# kill-switch on. Shipped as a single file (never data/ wholesale); 46MB is well
# within the container image limit and it parses once per warm container (lazy).
COPY data/vectors/kodiak-embeddings.jsonl /var/task/data/vectors/kodiak-embeddings.jsonl
COPY data/prompts/blog-sample-prompts.jsonl /var/task/data/prompts/blog-sample-prompts.jsonl
# Ship the safety blocklist — safety.check_text (localize_service's last hop) reads
# data/safety/blocklist.json via CAP_DATA_ROOT; pip install . does not bundle data/, so
# without this COPY every /localize degrades to error-fallback. CAP_DATA_ROOT already
# points at /var/task/data (set below), so this lands where safety.py resolves it.
COPY data/safety/blocklist.json /var/task/data/safety/blocklist.json
# Ship the recipe catalog (688K single file) — recipe_card._load_recipes() reads
# data/recipes/kodiak-recipes.json via _datapaths.data_path(); without this COPY
# the season table has no records in the image and every season pairing quietly
# resolves to nothing. Shipped as a single file (never data/ wholesale).
COPY data/recipes/kodiak-recipes.json /var/task/data/recipes/kodiak-recipes.json
ENV CAP_DATA_ROOT=/var/task/data
RUN pip install --no-cache-dir --only-binary=:all: "pillow==10.4.0" && pip install --no-cache-dir . boto3
CMD ["creative_automation.generate_lambda.handler"]
