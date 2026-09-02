# Linda Mohamed AI Film Crew — applied to KODIAK Posts

Reference: https://builder.aws.com/content/3FuJ4dTDxJ6HQefCYfpqxOFmpQa/how-i-built-an-ai-film-crew-on-aws

## Why it matters for KODIAK
Linda's pipeline proves the bottleneck is not shooting — it's turning hours of raw into publishable cuts.
Our CPG client has the same bottleneck at static scale: hundreds of localized social variants from a handful of brown-box heroes.

## Mapping to KODIAK Posts for Today's Frontier

| Linda layer | KODIAK equivalent | What we institutionalized |
|---|---|---|
| Intake (MediaConvert validation, codec/container/duration) | `dam.find_hero_asset` + `brief` validation + `enhance_hero` histogram normalize | Validates hero exists, readable, RGB, auto-contrast cutoff 0.5 before any grade |
| Analysis — parallel (Rekognition per-frame labels, Transcribe word timestamps, BDA video understanding) | `enhance_hero` analysis: histogram, kraft texture 6%, vignette 0.06 radial | Contrast 1.08 / brightness 1.02 / sharpness 1.12 / color 1.04 — gentle, product-safe |
| Creative — 8-agent CrewAI Film Crew → VariantSpec (16:9, 9:16, 1:1) | `suggest_variants` + `pipeline.run_pipeline` across 1x1/9x16/16x9 | One hero → 3 variants, compliance PASS gate, human-named `KODIAK-CAKES-{product}-suggested-{ratio}-{YYYYMMDD}-v01.png` |
| MediaConvert 3 outputs (960x540 proxy + AAC audio + JPEG every 2s) | `compose_creative` outputs 1080×1080, 1080×1920, 1920×1080 with same Wasatch cover + scrim | Blurred cover + 0.18 darken, contain, message bar 32% at 68%, slab 56/64/72, orange 8px bar |
| Step Functions orchestration (Task/Choice/Wait/Parallel, health check) | `pipeline.py` + `api.py` (`POST /pipeline/run`, `POST /suggest/run`, `POST /enhance/hero`) | Visible flow, retry-safe, no synthetic fallback |
| FSxN enterprise archive (source on NAS, derivatives in S3) | `input_assets` stays local (offline), `_work` + `output` derivatives mirror to `s3://chasko-creative-dam-.../brands/kodiak/` | No migration needed to remix — existing heroes stay put |
| 6 validation layers (FileSanitizer → Clip → Timestamp → FactCheck → QualityCheck → VariantSpec schema) | `compliance.py` (`run_all_checks`) — dimensions, brand marks, slogan, color, scrim, legality | `overall_passed` per creative, `compliance_pass_rate` in report.json |
| Observability (Step Functions console + CloudWatch + AgentCore tail) | `report.json` + `report.jsonl` + `preview.html` per run | One glance PASS/FAIL, no log hunting |

## New in this release

- **Suggested posts** — `src/creative_automation/suggest.py` scans `input_assets/*/hero.*`, enhances (contrast/texture/vignette), composes ×3 ratios, writes `report.json`/`preview.html`. Offline JS mirror in `web/kodiak-posts-for-todays-frontier/index.html` `#suggestedPreview`. Live: `POST /suggest/run`.
- **Institutional grading** — `src/creative_automation/enhance.py` (Pillow-only, offline): autocontrast, ImageEnhance chain, kraft hairlines 6%, vignette 0.06, double border (1px Stone #D9CFC6 + 6px Bear Brown #3B2316 + 2px Blaze Orange hairline), Bear watermark at 24,24. Pipeline applies by default (`dam+enhanced`). Toggleable via `POST /enhance/hero`.
- **Cost note** — Linda: ~€0.34/video at 10k/mo. KODIAK still images are cheaper: Pillow enhance + compose is local CPU, Nova Canvas only when missing hero (~$0.04/image). Suggest remixing 4 heroes ×3 = 12 creatives is free locally.

## YouTube deep as KODIAK story
`data/raw-ingest/kodiakcakes/youtube-deep/4sGNHT3cwtw.en.srt` + `4sGNHT3cwtw.json` — Zac Efron "Going All In" (3:44) transcript via yt-dlp auto-captions fallback (whisper large-v3-turbo image rebuild in progress on rocm-aibox). Themes extracted: Keep It Wild, Feeding Epic Days & Wilder Lives, grizzly habitat, getting outside, pushing boundaries. Available as suggested-post messages.
