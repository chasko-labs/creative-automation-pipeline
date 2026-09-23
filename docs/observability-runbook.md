# observability runbook — X-Ray + CloudWatch, three paths side by side

> team-platform. how to see what the Kodiak creative pipeline is doing, across all three ways you might reach AWS: the MCP tools an agent uses, the `aws` CLI a human uses, and the AWS console click-path. every procedure below is the SAME operation expressed three ways so you can pick whichever surface you are in. the MCP column was proven live against account bryanchasko-kiro (946179428633) us-east-1 on 2026-09-03; the CLI column is the exact equivalent; the console column is the click-path that produces the same result.

## what emits what

- the app (`observability.Observer`) writes **structured JSON log lines to stdout**. in local execution environments those go to **CloudWatch Logs** automatically. locally they print to the terminal.
- the app opens **X-Ray subsegments** (`asset.add`, `s3.put_object`, `asset.select`) when the `observability` extra is installed and X-Ray is reachable; otherwise tracing no-ops and logging still works.
- infra (`infra/template.yaml`) provisions the CloudWatch log group `/kodiak/creative-pipeline` and the X-Ray sampling rule + IAM so traces + logs land somewhere the console can show them.

## account + region

- account: **bryanchasko-kiro (946179428633)**, region **us-east-1** (the asset store + pipeline region). always pass `--profile bryanchasko-kiro --region us-east-1` on the CLI; MCP calls pass `aws_profile="bryanchasko-kiro"` + `region_name="us-east-1"`.

---

## procedure 1 — list X-Ray sampling rules (confirm tracing config)

verified live: the account currently has only the `Default` rule (priority 10000, fixed rate 0.05, service `*`). our infra adds a `kodiak-creative` rule at higher priority.

| path        | how                                                                                                                                                                                            |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **MCP**     | `call_boto3(service_name="xray", operation_name="GetSamplingRules", region_name="us-east-1")` (aws_profile bryanchasko-kiro) — returns `SamplingRuleRecords[]`                                 |
| **CLI**     | `aws xray get-sampling-rules --profile bryanchasko-kiro --region us-east-1`                                                                                                                    |
| **console** | X-Ray console -> CloudWatch console (X-Ray is under CloudWatch now) -> left nav **Settings** -> **Sampling** tab -> the rules table lists Default + kodiak-creative with priority + fixed rate |

## procedure 2 — see recent traces (is the service being called?)

verified live: 0 traces in the last 30 min (clean slate before first deploy).

| path        | how                                                                                                                                                                                                         |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **MCP**     | `call_boto3(service_name="xray", operation_name="GetTraceSummaries", region_name="us-east-1", params={"StartTime": <dt>, "EndTime": <dt>})` — returns `TraceSummaries[]`                                    |
| **CLI**     | `aws xray get-trace-summaries --start-time $(date -d '30 min ago' +%s) --end-time $(date +%s) --profile bryanchasko-kiro --region us-east-1`                                                                |
| **console** | CloudWatch console -> **X-Ray traces** -> **Traces** -> set the time range to last 30 min -> the trace list shows each request; the **Service map** tab draws app -> S3 dependency edges with latency/error |

## procedure 3 — read a single trace end to end (why was this slow / what failed?)

| path        | how                                                                                                                                                                    |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **MCP**     | `call_boto3(service_name="xray", operation_name="BatchGetTraces", region_name="us-east-1", params={"TraceIds": ["<id>"]})` — returns full segment/subsegment tree      |
| **CLI**     | `aws xray batch-get-traces --trace-ids <id> --profile bryanchasko-kiro --region us-east-1`                                                                             |
| **console** | X-Ray traces -> click a trace id -> the **segments timeline** shows `asset.add` -> `s3.put_object` with durations; annotations (`kind`, `asset_id`) show in the detail |

## procedure 4 — query the structured logs (what happened to asset X?)

logs land in CloudWatch log group `/kodiak/creative-pipeline`. the JSON schema is stable (see below) so Logs Insights queries are reliable.

| path        | how                                                                                                                                                                                                                                                                                              |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **MCP**     | list groups: `call_boto3(service_name="logs", operation_name="DescribeLogGroups", region_name="us-east-1", params={"logGroupNamePrefix": "/kodiak"})`. run a query: `call_boto3(service_name="logs", operation_name="StartQuery", params={...})` then `GetQueryResults`                          |
| **CLI**     | `aws logs describe-log-groups --log-group-name-prefix /kodiak --profile bryanchasko-kiro --region us-east-1` ; `aws logs start-query --log-group-name /kodiak/creative-pipeline --start-time <e> --end-time <e> --query-string 'fields @timestamp, event, asset_id \| filter event="asset.add"'` |
| **console** | CloudWatch console -> **Logs** -> **Logs Insights** -> select `/kodiak/creative-pipeline` -> paste `fields @timestamp, event, asset_id, kind \| filter event = "asset.add" \| sort @timestamp desc` -> **Run query**                                                                             |

## procedure 5 — live tail during a deploy / manual run

| path        | how                                                                                                                                              |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **MCP**     | `call_boto3(service_name="logs", operation_name="StartLiveTail", params={"logGroupIdentifiers": [<arn>]})` (streaming; MCP auto-caps output)     |
| **CLI**     | `aws logs tail /kodiak/creative-pipeline --follow --profile bryanchasko-kiro --region us-east-1`                                                 |
| **console** | CloudWatch console -> Logs -> log group `/kodiak/creative-pipeline` -> **Live tail** button -> events stream as they arrive                      |
| **app**     | in-process, no AWS round-trip: `GET /library/report` returns the last 50 events from the Observer ring buffer — the fastest "what just happened" |

## procedure 6 — create/update the kodiak X-Ray sampling rule (infra, one-time)

the sampling rule ships in `infra/template.yaml` (see the `AWS::XRay::SamplingRule` resource). deploy it with the stack; these are the manual equivalents for verification / emergency.

| path        | how                                                                                                                                                                                                                                                 |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **MCP**     | `call_boto3(service_name="xray", operation_name="CreateSamplingRule", region_name="us-east-1", params={"SamplingRule": {...}})`                                                                                                                     |
| **CLI**     | `aws xray create-sampling-rule --cli-input-json file://kodiak-sampling-rule.json --profile bryanchasko-kiro --region us-east-1`                                                                                                                     |
| **console** | CloudWatch -> Settings -> Sampling -> **Create sampling rule** -> name `kodiak-creative`, priority 9000, reservoir 1, fixed rate 0.10, service name `kodiak-creative*` (matches the app service name `kodiak-creative`), resource ARN `*` -> Create |

---

## the structured log schema (parse against this)

every line is one JSON object. stable keys:

```json
{
  "ts": "2026-09-03T21:14:07.412Z",
  "service": "kodiak-creative",
  "event": "asset.add",
  "level": "info",
  "asset_id": "01J...",
  "kind": "raster",
  "filename": "wasatch-dawn.png",
  "size_bytes": 184320,
  "sha256": "9f2c...",
  "source": "user-upload"
}
```

event vocabulary: `asset.add`, `asset.dedup_hit`, `asset.list`, `asset.select`, `asset.reject`, plus pipeline events as they adopt the Observer. `level` in {info, warn, error}. unknown fields are additive — consumers read by key, never by position.

## X-Ray annotations (filterable in console)

subsegments carry indexed annotations so you can filter the trace list:

- `kind` — raster | vector | doc | copy
- `asset_id` — the ulid
- `source` — user-upload | pipeline | import

console filter example: in X-Ray traces, filter expression `annotation.kind = "raster"` shows only raster-asset operations.

## graceful degradation (offline-first, matches the codebase)

- no `aws-xray-sdk` installed, or no X-Ray reachable -> `Observer.trace()` is a no-op context manager; logging still emits to stdout. CI and offline dev stay green.
- no CloudWatch (local run) -> logs print to terminal; `GET /library/report` still works (ring buffer is in-process).
- the app never raises because observability is unavailable. observability is a lens, never a dependency of the work.

## the rule in one sentence

every observation is reachable three ways — MCP for agents, `aws` CLI for humans, the CloudWatch/X-Ray console click-path for eyes — over the same stable JSON log schema + X-Ray annotations, and the app degrades to stdout-only logging when AWS is out of reach so the pipeline never blocks on being watched
