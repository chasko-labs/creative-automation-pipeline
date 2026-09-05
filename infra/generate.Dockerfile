FROM public.ecr.aws/lambda/python:3.11
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/
# Ship ONLY the sku-photo-map into the image (single file — never COPY data/ wholesale;
# data/vectors/ carries a 46MB embeddings file that must not bloat the image). The env
# var points _resolve_map_path() at this stable /var/task (LAMBDA_TASK_ROOT) location.
COPY data/products/sku-photo-map.json /var/task/data/products/sku-photo-map.json
ENV SKU_PHOTO_MAP_PATH=/var/task/data/products/sku-photo-map.json
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
# dir + the two context-pack files ONLY — never data/vectors/kodiak-embeddings.jsonl
# (46MB) which would bloat the image.
COPY data/localization/ /var/task/data/localization/
COPY data/vectors/image-clusters.json /var/task/data/vectors/image-clusters.json
COPY data/prompts/blog-sample-prompts.jsonl /var/task/data/prompts/blog-sample-prompts.jsonl
ENV CAP_DATA_ROOT=/var/task/data
RUN pip install --no-cache-dir --only-binary=:all: "pillow==10.4.0" && pip install --no-cache-dir . boto3
CMD ["creative_automation.generate_lambda.handler"]
