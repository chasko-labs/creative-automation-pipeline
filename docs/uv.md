# package index — what each dependency does here

this is the human-readable map of the project's direct dependencies, managed by `uv` (`pyproject.toml` is the authoritative source, `uv.lock` pins the full transitive tree). it covers the direct runtime set, the optional extras, and the dev group only — not the transitive dependencies each of these pulls in. read this instead of decoding `uv.lock` by hand.

each row links to the package's official repository and one additional reference — an official docs page or a reputable tutorial. the "what it does here" column describes the role in this project, sourced from the inline comments in `pyproject.toml` where those exist.

## runtime dependencies

these ship with the pipeline and the api server.

| package | what it does here | official repo | reference |
| --- | --- | --- | --- |
| fastapi | web framework for the api server that fronts the pipeline | https://github.com/fastapi/fastapi | https://fastapi.tiangolo.com/ |
| uvicorn | asgi server that runs the fastapi app | https://github.com/encode/uvicorn | https://www.uvicorn.org/ |
| httpx | async http client for outbound calls | https://github.com/encode/httpx | https://www.python-httpx.org/ |
| python-multipart | parses multipart form uploads for fastapi file endpoints | https://github.com/Kludex/python-multipart | https://fastapi.tiangolo.com/tutorial/request-files/ |
| boto3 | aws sdk — cloud storage, bedrock, and the dam bucket access | https://github.com/boto/boto3 | https://boto3.amazonaws.com/v1/documentation/api/latest/index.html |
| botocore | low-level core that boto3 is built on; pinned alongside it | https://github.com/boto/botocore | https://botocore.amazonaws.com/v1/documentation/api/latest/index.html |
| pillow | server-side image compose layer — draws text and lays out creatives | https://github.com/python-pillow/Pillow | https://pillow.readthedocs.io/ |
| pyyaml | reads the campaign brief yaml files under `briefs/` | https://github.com/yaml/pyyaml | https://pyyaml.org/wiki/PyYAMLDocumentation |
| pydantic | data validation and models for briefs and api payloads | https://github.com/pydantic/pydantic | https://docs.pydantic.dev/latest/ |
| jinja2 | templating for generated text and html output | https://github.com/pallets/jinja | https://jinja.palletsprojects.com/ |
| strands-agents | agent sdk whose BedrockModel targets the kodiak art-director imported-model arn via the converse api (`art_director.py`); pinned 1.54.0 because the streaming=False + imported-model arn path is version-sensitive | https://github.com/strands-agents/sdk-python | https://strandsagents.com/latest/documentation/docs/ |
| arabic-reshaper | reshapes arabic into presentation forms before pillow draws it — pillow does no shaping, so unshaped glyphs render isolated | https://github.com/mpcabd/python-arabic-reshaper | https://mpcabd.xyz/python-arabic-text-reshaper/ |
| python-bidi | bidi reordering of shaped text before `ImageDraw.text`, so right-to-left runs render in the correct visual order | https://github.com/MeirKriheli/python-bidi | https://python-bidi.readthedocs.io/ |

## optional extras

these install only when the named extra is requested (`uv sync --extra <name>`). the code paths that use them degrade or no-op when absent.

| package | extra | what it does here | official repo | reference |
| --- | --- | --- | --- | --- |
| maturin | rust | builds the pyo3 rust extension `creative_automation._kodiak_local` from `rust/kodiak-local` | https://github.com/PyO3/maturin | https://www.maturin.rs/ |
| numpy | analysis | offline clustering of the nova image vectors in `scripts/cluster-image-standards.py`; spherical k-means is hand-rolled so no scikit-learn is pulled in | https://github.com/numpy/numpy | https://numpy.org/doc/stable/ |
| aws-xray-sdk | observability | aws x-ray tracing; optional — the Observer autodetects absence and no-ops, so ci and offline dev stay green without it | https://github.com/aws/aws-xray-sdk-python | https://docs.aws.amazon.com/xray/latest/devguide/xray-sdk-python.html |

## dev group

installed by default for local development (`uv sync` includes the dev group); excluded from production installs.

| package | what it does here | official repo | reference |
| --- | --- | --- | --- |
| pytest | test runner for the unit and integration suites under `tests/` | https://github.com/pytest-dev/pytest | https://docs.pytest.org/en/stable/ |
| ruff | linter run first in the local pre-push gate; dies in about one second on any lint error | https://github.com/astral-sh/ruff | https://docs.astral.sh/ruff/ |

## a note on system libraries

not every shaping dependency is a pip package. libraqm — the myanmar and devanagari conjunct shaper pillow calls through — is a system library added via `apt-get libraqm` in `infra/generate.Dockerfile`, not a python dependency. it will not appear in `pyproject.toml` or `uv.lock`.
