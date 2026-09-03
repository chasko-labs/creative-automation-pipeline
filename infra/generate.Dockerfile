FROM public.ecr.aws/lambda/python:3.11
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --only-binary=:all: "pillow==10.4.0" && pip install --no-cache-dir . boto3
CMD ["creative_automation.generate_lambda.handler"]
