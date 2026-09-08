# Runbook: kodiak.bryanchasko.com 403 from S3 origin

Site: `https://kodiak.bryanchasko.com/` (alias) + `https://d37333alc7ojpl.cloudfront.net/`
(distribution `E3GEX8LSRX6OYS`, account 946179428633).
Bucket: `frontier-bryanchasko-com`. Design intent (infra-cdk/lib/hosting-stack.ts):
public-read website bucket (`publicReadAccess: true`, `blockPublicPolicy: false`).

## Symptom

Both hosts return `403 Forbidden`, `x-amz-error-code: AccessDenied`,
`server: AmazonS3`, `x-cache: Error from cloudfront`. Twice observed
2026-09-08 (~19:33 and ~20:0x UTC), both while hosting-stack CDK work was in
flight in another session.

## Diagnose (profile: bryanchasko-kiro)

```bash
export AWS_PROFILE=bryanchasko-kiro
curl -sI "https://kodiak.bryanchasko.com/" | head -6
aws s3 ls s3://frontier-bryanchasko-com/ --recursive | wc -l   # content present?
aws s3api get-bucket-policy --bucket frontier-bryanchasko-com  # NoSuchBucketPolicy = this runbook
aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=frontier-bryanchasko-com \
  --max-items 5 --query "Events[*].[EventTime,EventName,Username]" --output text
```

Known cause (2x): `DeleteBucketPolicy` on the site bucket during tag-restore /
converge deploy activity strips the public-read policy. Content is untouched
(53 objects) — this is permissions, not missing files. Do NOT re-upload the site.

## Restore (stopgap, seconds)

Re-apply the CDK-intended public-read policy:

```bash
export AWS_PROFILE=bryanchasko-kiro
aws s3api put-bucket-policy --bucket frontier-bryanchasko-com --policy \
  '{"Version":"2012-10-17","Statement":[{"Sid":"PublicReadGetObject","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::frontier-bryanchasko-com/*"}]}'
sleep 5
curl -s -o /dev/null -w "site:%{http_code}\n" "https://kodiak.bryanchasko.com/"
```

## Verify the real render (not just the status)

```bash
python3 - <<'EOF'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1440,"height":900})
    pg.goto("https://kodiak.bryanchasko.com/?cakes=1", timeout=30000)
    pg.wait_for_timeout(4000)
    print("stamp:", (pg.text_content("#buildStamp") or "").strip())
    print("gated:", pg.get_attribute("#generateCampaignSection", "data-gated"))
    pg.screenshot(path="/tmp/k-restore-check.png")
    pg.close(); b.close()
EOF
```

Open `/tmp/k-restore-check.png` and look at it: setup card, market chips,
Create button, no gate overlay.

## Lesson learned

The stopgap gets clobbered again on the next converge deploy that manages the
bucket policy — it has, twice. The durable fix is the hosting-stack OAC
convergence (other team, in flight): CloudFront OAC + bucket policy owned by
CDK, so no session can strip it by hand. Until that lands: restore the stopgap,
then tell the hosting-stack owner before touching anything else. Never fight an
in-flight deploy — check `LastModifiedTime` on the distribution first.
