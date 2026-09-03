# asset library + observability — design + seam announcement

> team-platform design for two coupled capabilities: (1) an asset-library ingest + browse/select service so a user can add a source file (png/svg/jpg/jpeg/pdf/copy) to the DAM and later browse the library to build or riff a campaign off a chosen asset, and (2) structured logging + AWS X-Ray tracing across the infra so results are visible in the AWS console. UI is out of scope here — this defines the backend hooks the frontend/api teams consume, plus a webmcp surface and docs. built typed + object-oriented, self-reviewed, shipped by PR.

## why these two ship together

the asset-library service is the first new write-path into the DAM. it is also the first place we want end-to-end visibility (a user adds a file -> it lands in S3 -> it becomes selectable -> a campaign is built off it). so the observability layer is designed as the substrate the asset-library service is the first consumer of. every asset-library operation emits a structured log record and opens an X-Ray subsegment. that gives the frontend/api teams a reporting surface from day one instead of bolting it on later.

## lane + seam boundaries (read before touching)

per `team-lanes.md`:

- team-platform (this work) OWNS: the DAM bucket layout + prefixes, the S3 storage contract, the observability substrate, the IAM/infra for logs + traces. that is `infra/`, the new prefix, `observability.py`, and the storage-facing service.
- team-pipeline OWNS: `src/creative_automation/*.py` engine core, and the act of a campaign CONSUMING a chosen asset (pipeline/compose/generate). we do NOT write engine internals.
- the seam: the asset-library service produces a stable **AssetRef** contract (below). the pipeline consumes an AssetRef when a user picks an asset to build/riff. the frontend consumes the browse/select API + the AssetRef. changing AssetRef fields is a seam event — announce it.

### where the code lives (seam-respecting placement)

- `src/creative_automation/asset_library.py` — the AssetLibrary service class. this sits in the engine package because it is imported by both the api layer and (later) the pipeline, but its LOGIC is storage + metadata only (platform-owned concern). team-pipeline is the anchor of the package directory, so this addition is announced to them as a seam event; it does not touch their existing modules and imports `naming.py` + `dam.py` rather than duplicating them.
- `src/creative_automation/observability.py` — the observability substrate (platform-owned, engine-wide utility).
- `src/creative_automation/asset_api.py` — the FastAPI + MCP surface for browse/select/add, mirroring `reference_api.py`'s pattern (platform-owned API for the asset library specifically, kept separate from the pipeline's `api.py`).
- `infra/template.yaml` — CloudWatch log group + X-Ray + IAM (platform).

this placement was chosen over a separate top-level package to keep imports simple (`from .naming import build_iso_name`, `from .dam import ...`) and to match the existing `reference_api.py` precedent of a capability-scoped api module in the same package.

## capability 1 — asset library

### storage contract (platform-owned)

new DAM prefix, collision-free against the 12 existing prefixes (heroes/, logos/, renders/, references/, vectors/, ...):

```
s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/library/<asset_id>/<original_filename>
s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/library/<asset_id>/asset.json   (metadata sidecar)
```

- `library/` is user-contributed SOURCE assets a campaign is built or riffed off. distinct from `renders/` (pipeline output) and `references/` (training corpus).
- `asset_id` is a stable ulid/uuid4 hex — never derived from filename (filenames collide, ulids sort by time).
- the metadata sidecar `asset.json` is the durable record. it is also mirrored to DynamoDB later if query volume warrants; v1 is S3-sidecar only (list = ListObjectsV2 on the prefix, read = GetObject the sidecar).

### accepted asset kinds

`dam.py` today accepts only `{.png, .jpg, .jpeg, .webp}` for hero lookup. the library accepts a wider set because a user can add reference material to riff off, not just heroes:

| kind   | extensions            | notes                                                              |
| ------ | --------------------- | ------------------------------------------------------------------ |
| raster | .png .jpg .jpeg .webp | directly usable as a hero / composite source                       |
| vector | .svg                  | logo / mark source; rasterized on demand by the pipeline, not here |
| doc    | .pdf                  | brand guide / brief reference; first page thumbnailed later        |
| copy   | .txt .md              | reference copy / voice sample a campaign can riff off              |

kind is derived from extension by a single `AssetKind` enum classifier — one place, imported everywhere (same discipline as `naming.ISO_NAME_RE`). unknown extension -> rejected with a typed error, never silently stored.

### the AssetRef contract (the seam — pydantic model)

this is what browse/select returns and what the pipeline consumes. stable field set:

```
AssetRef:
  asset_id:      str            # stable ulid
  kind:          AssetKind      # raster | vector | doc | copy
  filename:      str            # original filename as uploaded
  s3_uri:        str            # s3://.../library/<asset_id>/<filename>
  s3_key:        str            # brands/kodiak/library/<asset_id>/<filename>
  content_type:  str            # detected MIME
  size_bytes:    int
  sha256:        str            # content hash for dedup + integrity
  added_at:      str            # ISO 8601 UTC
  added_by:      str            # opaque user/agent id, default "anonymous"
  tags:          list[str]      # free-form, user-supplied, default []
  width:         int | None     # raster only
  height:        int | None     # raster only
  source:        str            # "user-upload" | "pipeline" | "import"
```

changing/removing a field here is a seam event -> announce to team-frontend + team-pipeline. adding an optional field is safe.

### the AssetLibrary service (typed, OO)

single class, dependency-injected S3 client + observability, so it is unit-testable offline (inject a fake client) and degrades gracefully when boto3/creds are absent (mirrors `dam.py`'s `_s3_enabled()` pattern).

```
class AssetLibrary:
    def __init__(self, bucket: str, prefix: str = "brands/kodiak/library/",
                 s3_client=None, obs: Observer | None = None) -> None: ...

    # --- add-asset ingest hook (the "inherently add to library when added to the tool" path) ---
    def add_asset(self, *, data: bytes, filename: str,
                  added_by: str = "anonymous", tags: list[str] | None = None,
                  source: str = "user-upload") -> AssetRef:
        """Classify -> validate kind -> hash -> dedup-check -> put object + sidecar -> emit log + trace.
        Raises UnsupportedAssetKind on unknown extension. Idempotent on identical sha256
        (returns the existing AssetRef instead of a duplicate object)."""

    def add_asset_from_path(self, path: Path, **kw) -> AssetRef:
        """Convenience wrapper: read bytes from a local path, infer filename, delegate to add_asset."""

    # --- browse / select ---
    def list_assets(self, *, kind: AssetKind | None = None,
                    limit: int = 100, cursor: str | None = None) -> AssetPage:
        """Paginated browse. Filter by kind. Returns AssetPage(items: list[AssetRef], next_cursor)."""

    def get_asset(self, asset_id: str) -> AssetRef | None:
        """Read a single AssetRef from its sidecar. None if absent."""

    def select_for_campaign(self, asset_id: str) -> AssetRef:
        """Resolve + validate an asset is campaign-usable (kind in {raster,vector}) and return the
        AssetRef the pipeline will build/riff off. Raises AssetNotSelectable for doc/copy kinds
        (those are reference-only until the pipeline grows a rasterizer). Emits a select event."""
```

design decisions:

- **dedup by sha256**: the same file added twice returns the first AssetRef, no duplicate S3 object. cheap integrity + storage discipline.
- **ingest is the "add to tool = add to library" hook**: `add_asset` IS the hook. whatever surface the user uses to attach a file (frontend upload, api, cli) calls `add_asset` and the asset is in the library as a side effect — no separate "publish" step. that satisfies "it should inherently do when they add it to the tool."
- **naming**: user-library assets keep their original filename under the ulid dir (source material, not ISO-named renders). the ISO `naming.py` pattern applies to pipeline RENDER output, not user source uploads, so we do not force-rename uploads. `naming.slugify` is still used for tag normalization so we import the module and never re-implement slug logic.
- **no width/height without pillow**: raster dims are read via pillow if available (already a dependency), else left None — graceful degrade.

### the asset api surface (`asset_api.py`, mirrors reference_api.py)

FastAPI, `HAS_FASTAPI` graceful degrade, also exposed as MCP for agents:

```
POST /library/assets            multipart file upload -> add_asset -> 201 {AssetRef}
GET  /library/assets            ?kind=&limit=&cursor=  -> {items: [AssetRef], next_cursor}
GET  /library/assets/{id}       -> AssetRef | 404
POST /library/assets/{id}/select -> AssetRef (campaign-usable) | 409 AssetNotSelectable
GET  /library/health            -> {ok, bucket, prefix, count, s3_enabled}
```

these are the **hooks the frontend team consumes**. UI (upload widget, library browser, "build off this" button) is dispatched to team-frontend as a separate issue referencing this contract.

## capability 2 — observability substrate

### goals

- every meaningful operation emits a **structured JSON log line** to stdout (CloudWatch-friendly) with a stable schema.
- AWS **X-Ray** traces the request -> service -> S3 call chain so it is visible as a service map in the console.
- **degrades gracefully**: no X-Ray daemon / no creds -> tracing becomes a no-op, logging still works. offline-first, same as the rest of the codebase.
- exposes a **reporting surface** the frontend/api teams + webmcp can read (recent events, counts).

### the Observer (typed, OO, one substrate)

```
class Observer:
    def __init__(self, service: str, *, xray_enabled: bool | None = None) -> None:
        """xray_enabled defaults to autodetect: True only if aws-xray-sdk importable AND
        AWS_XRAY_SDK_ENABLED != 'false' AND creds resolvable. Never raises on absence."""

    def log_event(self, event: str, **fields) -> LogRecord:
        """Emit a structured JSON line: {ts, service, event, level, **fields}. Returns the record
        so callers/tests can assert on it. Also appends to an in-process ring buffer for /report."""

    @contextmanager
    def trace(self, name: str, **annotations):
        """Open an X-Ray subsegment (no-op if disabled). Annotations become X-Ray annotations
        (indexed, filterable in console). Exceptions are recorded on the segment and re-raised."""

    def recent(self, limit: int = 50) -> list[LogRecord]:
        """Return the last N events from the ring buffer — powers the /report endpoint + webmcp."""
```

- **structured log schema** (stable, documented so frontend/api can parse): `ts` (ISO8601 UTC), `service`, `event`, `level`, plus event-specific fields. asset-library events: `asset.add`, `asset.dedup_hit`, `asset.list`, `asset.select`, `asset.reject`. each carries `asset_id`, `kind`, `size_bytes`, `sha256` where relevant.
- **X-Ray**: subsegments named `asset.add`, `s3.put_object`, `asset.select`. annotations: `kind`, `asset_id`, `source`. this makes the console service map show the S3 dependency and let you filter traces by asset kind.
- **ring buffer**: an in-process deque(maxlen=500) of recent LogRecords so a `/report` endpoint + webmcp island can show "what just happened" without a CloudWatch Logs Insights round-trip. CloudWatch remains the durable store; the buffer is a live tail.

### reporting surface exposed to frontend/api + webmcp

```
GET /library/report            -> {service, recent: [LogRecord], counts: {event: n}}
```

- webmcp island (dispatched to frontend): a `data-mcp="library.report"` selector that fetches `/library/report` so the console/agents can see recent asset + campaign activity.
- README + docs document the log schema and the X-Ray annotations so the api team can build dashboards / Logs Insights queries against a known shape.

## dependency additions (coordinate — pyproject seam)

`pyproject.toml` is a team-pipeline-anchored shared-venv seam. this work needs:

- `aws-xray-sdk>=2.12` — added as an OPTIONAL extra `observability = ["aws-xray-sdk>=2.12"]`, NOT a core dep, so CI + offline stay green without it (Observer autodetects and no-ops when absent). announce the extra to all teams before `uv add`.

no other new deps — pillow (raster dims), boto3 (S3), pydantic (models), fastapi (api) are already present.

## testing

- `tests/test_asset_library.py` — inject a fake in-memory S3 client; assert add/list/get/select, dedup by sha256, unsupported-kind rejection, AssetRef shape, offline degrade (no boto3).
- `tests/test_observability.py` — assert log schema, ring buffer, trace no-op when X-Ray disabled, annotation passthrough.
- both run in the fast per-push gate (no aws calls, fake client). the X-Ray-enabled path is exercised only in the RUN_SLOW nightly path against real creds.

## the rule in one sentence

the asset-library service is the first DAM write-path and the first observability consumer: add_asset is the "add to tool = add to library" hook, browse/select returns the stable AssetRef the pipeline builds off, and every op emits a structured log + X-Ray subsegment so results are visible in the console — all platform-owned, seam-announced to pipeline + frontend, UI dispatched separately.
