# Changelog

human-readable release notes for the Kodiak creative-automation-pipeline. the full commit-by-commit history
is preserved on `main` (we merge with merge-commits, not squash, so `git log` is the exhaustive record).
this file curates the notable milestones.

## 0.1.016 — 2026-09-06 — sprint: art-director + ingest + DAM + localize, UI redesign, code atomization

merged via PR #142 (merge-commit `92d04f0`). one sprint, six tracks plus a front-page redesign and a
code-hygiene atomization pass.

### backend + data

- **art-director voice** — asset-directed generation voice (dark default, gated by
  `KODIAK_ARTDIRECTOR_ENABLED`).
- **asset ingest** — `/library/assets` ingest path: sha256 exact-dedup + Nova embedding + write to S3
  Vectors, driven by an S3 event. no DynamoDB this sprint.
- **DAM browser** — `/assets/library` browse tab over the digital asset library.
- **localize endpoint** — `/localize` route. currently returns `source=mock` (offline dictionary); live
  Amazon Translate / Bedrock path is a tracked follow-up.
- **path dispatcher fix** — the generate Lambda was path-blind (ran the generate ladder for every path).
  added request-path routing so `/localize`, `/assets/library`, and `/library/assets` stop returning hero
  images.
- **safety blocklist** — resolves via `CAP_DATA_ROOT` inside the Lambda image.
- **input intelligence** — regex pattern recognition on the prompt field + defensive upload/parse error
  handling.
- **perf** — page-lifecycle state survival, leak teardown, content-visibility DOM slimming.

### infrastructure

- **S3 Vectors** — CDK-provisioned bucket `kodiak-vectors` + index `kodiak-assets`, with Lambda grants.
- CloudFront `E3GEX8LSRX6OYS` behaviors for `/generate*`, `/localize*`, `/assets/library*`,
  `/library/assets*` (hand-managed — moving these to CDK is a tracked follow-up).

### frontend redesign

- **Output Preview** — renamed from "Output"; shows 3 previewed ratios + a blog row, 4 generated.
- **Generate Campaign** — post-Create section with 3 scopes (nationwide, nationwide + full localization,
  localized to the prompt's area — the default, made prominent and no-scroll).
- **Campaign Assets** — carousel of generated assets after Create.
- **Download Preview Pack** — fixed to export all preview ratios (was exporting one image), renamed from
  "Download Asset Pack".
- Park City resting-state localization preview (es + de), forest-silhouette CSS divider, 100%-width header,
  unified location control, product carousel in the SKU picker.

### code hygiene — the atomization

- `index.html` **3761 -> 296 lines**. inline JS extracted into 10 `js/` classic-script siblings; the
  731-line inline `<style>` block extracted to hand-authored `design/components.css`.
- classic `<script src>` (not ES modules) to preserve the shared global scope; data stays inline for
  offline-first `file://`. see `docs/frontend-architecture.md` for the full rationale.
- zero visual/behavior change — pure structural refactor.

### notes

- version string is a build-metadata stamp (`v<semver>-<gitshort>-<date>`), not a semver release gate.
- open follow-ups tracked in PR #142: `/localize` mock fallback, 44MB orphan JSONL not yet migrated to S3
  Vectors, CloudFront behaviors hand-managed, `details.html` not yet atomized.
