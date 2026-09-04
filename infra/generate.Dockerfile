FROM public.ecr.aws/lambda/python:3.11
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/
# Ship ONLY the sku-photo-map into the image (single file — never COPY data/ wholesale;
# data/vectors/ carries a 46MB embeddings file that must not bloat the image). The env
# var points _resolve_map_path() at this stable /var/task (LAMBDA_TASK_ROOT) location.
COPY data/products/sku-photo-map.json /var/task/data/products/sku-photo-map.json
ENV SKU_PHOTO_MAP_PATH=/var/task/data/products/sku-photo-map.json
RUN pip install --no-cache-dir --only-binary=:all: "pillow==10.4.0" && pip install --no-cache-dir . boto3
CMD ["creative_automation.generate_lambda.handler"]
