# Fleet build + deploy defaults

Two process notes the next fleet inherits. Both were learned the hard way;
neither is optional.

## Docker builds: provenance + SBOM on by default

Every image build (local or CodeBuild) records provenance and SBOM:

```bash
docker buildx build --provenance=true --sbom=true -t <name>:<tag> .
```

In CodeBuild buildspecs set them as defaults so no project opts out by
forgetting:

```yaml
env:
  variables:
    DOCKER_BUILDKIT: "1"
    BUILDX_PROVENANCE: "true"
    BUILDX_SBOM: "true"
```

Why: provenance ties a deployed image to its source commit; SBOM gives the
next audit something to read instead of something to reconstruct.

## Frontier deploys: 3-minute edge settle

`scripts/deploy-frontier.sh` waits for the `/*` invalidation to reach
`Completed` before it prints the verify line (typically ~3 min). Do not
take a live receipt before the settle: pre-settle reads mix old and new
objects across edge POPs, and a mixed read looks exactly like a bad deploy.

If you bypass the script with a manual sync + invalidate, replicate the
settle yourself:

```bash
aws cloudfront wait invalidation-completed \
  --distribution-id E3GEX8LSRX6OYS --id "$INV_ID" \
  --profile bryanchasko-kiro --region us-east-1
```

Then receipt both hosts plus the version stamp before calling it live:

```bash
curl -s -o /dev/null -w 'kodiak:%{http_code}\n' https://kodiak.bryanchasko.com/
curl -s -o /dev/null -w 'cf:%{http_code}\n' https://d37333alc7ojpl.cloudfront.net/
curl -s https://kodiak.bryanchasko.com/index.html | grep -o '0\.1\.0[0-9]*-[0-9a-f]*-[0-9]*' | head -1
```
