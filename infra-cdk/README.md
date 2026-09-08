# kodiak-creatives infra-cdk

AWS CDK (TypeScript) app for the Kodiak creative-automation-pipeline. Proposed
alongside the existing `../infra` (Terraform + CloudFormation/SAM); the old IaC
is left in place, this is not a same-PR replacement of it.

account `946179428633` (bryanchasko-kiro), primary region `us-east-1`, one
cross-region concern in `us-west-2`.

## stacks

| stack id                             | region    | contents                                                      |
| ------------------------------------ | --------- | ------------------------------------------------------------- |
| KodiakCreativesData                  | us-east-1 | DAM S3 bucket + 2 DynamoDB tables (all RETAIN)                |
| KodiakCreativesObservability         | us-east-1 | app log group + X-Ray sampling rule + write managed policy    |
| KodiakCreativesGenerate              | us-east-1 | container-image lambda + public function url + bedrock/S3 IAM |
| KodiakCreativesBedrockLoggingUsEast1 | us-east-1 | bedrock invocation log group + role + singleton enable        |
| KodiakCreativesBedrockLoggingUsWest2 | us-west-2 | same, cross-region (FIX 2) for the art-director model         |
| kodiak-creatives-hosting             | us-east-1 | frontier site bucket + CloudFront distro + OAC + DNS alias (#202, all RETAIN) |

## two observability fixes carried by this app

- FIX 1 (GenerateStack): X-Ray was `PassThrough` with `AWS_XRAY_SDK_ENABLED=false`.
  Now `Tracing.ACTIVE`, `AWS_XRAY_SDK_ENABLED=true`, and the role gets
  `xray:PutTraceSegments` + `xray:PutTelemetryRecords`. Populates the run-ledger
  `trace_id`.
- FIX 2 (BedrockLoggingStack, us-west-2 instance): model-invocation logging is an
  account+region singleton. The original IaC configured only us-east-1 and its
  role was scoped to the us-east-1 log group ARN, so the us-west-2 art-director
  model's invocations were never logged. The second stack instance provisions a
  us-west-2 log group + a us-west-2-scoped role and enables the singleton there.

## prerequisites

```
npm install
```

CDK toolkit is pinned as a dev dependency; use `npx cdk ...` or `npm run synth`.

## bootstrap (once per account+region)

```
npx cdk bootstrap aws://946179428633/us-east-1 --profile bryanchasko-kiro
npx cdk bootstrap aws://946179428633/us-west-2 --profile bryanchasko-kiro
```

us-west-2 bootstrap is required because KodiakCreativesBedrockLoggingUsWest2
deploys there.

## GenerateStack prerequisite: build + push the container image to ECR

GenerateStack references a pre-built image by ECR repo name + tag (default repo
`kodiak-creatives-generate`, tag `latest`). Build + push BEFORE deploying it:

```
ACCOUNT=946179428633
REGION=us-east-1
REPO=kodiak-creatives-generate
TAG=latest
ECR=${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com

aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" --profile bryanchasko-kiro \
  || aws ecr create-repository --repository-name "$REPO" --region "$REGION" --profile bryanchasko-kiro

aws ecr get-login-password --region "$REGION" --profile bryanchasko-kiro \
  | docker login --username AWS --password-stdin "$ECR"

# build context is the repo root; Dockerfile lives at infra/generate.Dockerfile
docker build -f ../infra/generate.Dockerfile -t "$REPO:$TAG" ..
docker tag "$REPO:$TAG" "$ECR/$REPO:$TAG"
docker push "$ECR/$REPO:$TAG"
```

override repo/tag at deploy time with context:

```
npx cdk deploy KodiakCreativesGenerate -c generateEcrRepo=kodiak-creatives-generate -c generateImageTag=latest
```

## adopting the LIVE resources with `cdk import` (zero-destroy)

The DAM bucket and the two DynamoDB tables already exist and hold production
data. Do NOT `cdk deploy` DataStack against a live environment before importing
-- a plain deploy would try to CREATE resources whose names already exist and
fail (bucket) or collide (tables). Every resource in DataStack is
`RemovalPolicy.RETAIN`, so import is safe and reversible.

```
# 1. synth first so the template is on disk
npm run synth

# 2. import the live resources into DataStack. cdk prompts for each resource's
#    physical id; supply the live names below.
npx cdk import KodiakCreativesData --profile bryanchasko-kiro
```

physical ids to supply when prompted:

| construct path          | physical id (live)                         |
| ----------------------- | ------------------------------------------ |
| StyleLibraryBucket      | chasko-creative-dam-946179428633-us-east-1 |
| LocalizationMemoryTable | kodiak-creatives-localization-memory       |
| RetailNetworkTable      | kodiak-creatives-retail-network            |

after import, a normal `cdk diff` / `cdk deploy` will manage tags, lifecycle, and
the TLS-only bucket policy without replacing the resource.

the app log group `/kodiak/creative-pipeline` and the bedrock log groups may also
already exist. If so, import them the same way before deploying their stacks:

```
npx cdk import KodiakCreativesObservability --profile bryanchasko-kiro
# CreativePipelineLogGroup -> /kodiak/creative-pipeline

npx cdk import KodiakCreativesBedrockLoggingUsEast1 --profile bryanchasko-kiro
# BedrockLoggingLogGroup -> /aws/bedrock/kodiak-model-invocations
```

for a FRESH environment (new account/region with none of these live) skip import
and `cdk deploy` directly.

## adopting the LIVE site hosting with `cdk import` (#202, zero-destroy)

The site bucket (`frontier-bryanchasko-com`) and the CloudFront distribution
(`E3GEX8LSRX6OYS`) are hand-made and serve production traffic. Do NOT
`cdk deploy` HostingStack before importing -- a plain deploy would try to
CREATE a duplicate bucket and fail. The stack mirrors the live config
(L2 bucket; L1 distribution because the live default behavior uses legacy
ForwardedValues, which L2 cannot render -- it always injects a CachePolicyId),
so import is a no-op. Every resource in the stack is `RemovalPolicy.RETAIN`
and the stack has terminationProtection.

Two resources need special handling:

- `FrontierOriginAccessControl` is NEW (provisioned, not attached). Import
  creates it with no traffic impact. Attaching it (origin swap to S3 REST +
  bucket-policy rewrite) is a reviewed follow-up, not part of adoption.
- `KodiakAliasRecord` CANNOT ride along: CloudFormation refuses to import
  `AWS::Route53::RecordSet` at all. Import with the record gated out, then
  adopt DNS in a second pass (delete the live `kodiak` A alias, deploy to
  recreate it identically -- seconds of resolver-cache cover).

```
# 1. synth first so the template is on disk
npm run synth

# 2. import bucket + distro (+ new OAC), record gated out
npx cdk import kodiak-creatives-hosting -c hostingIncludeDnsRecord=false --profile bryanchasko-kiro
```

physical ids to supply when prompted:

| construct path           | physical id (live)        |
| ------------------------ | ------------------------- |
| FrontierSiteBucket       | frontier-bryanchasko-com  |
| FrontierDistribution     | E3GEX8LSRX6OYS            |

```
# 3. confirm clean, then adopt DNS (once): delete the live kodiak A alias in
#    the bryanchasko.com zone (aerospaceug-admin Z09216723VDB0N04DM9LL), deploy
#    to recreate it, verify with dig.
npx cdk diff kodiak-creatives-hosting -c hostingIncludeDnsRecord=false --profile bryanchasko-kiro  # clean
# ... delete live record ...
npx cdk deploy kodiak-creatives-hosting --profile bryanchasko-kiro
dig +short kodiak.bryanchasko.com  # CloudFront IPs
```

content publishing is NOT part of this stack -- `scripts/deploy-frontier.sh`
keeps the s3 sync + invalidation job. The `kodiak-generate-api` second origin
and the cf-logs bucket are referenced by string only (owned elsewhere).

## deploy order

```
npx cdk deploy KodiakCreativesData             --profile bryanchasko-kiro   # import first if live
npx cdk deploy KodiakCreativesObservability    --profile bryanchasko-kiro
npx cdk deploy KodiakCreativesGenerate         --profile bryanchasko-kiro   # after ECR push
npx cdk deploy KodiakCreativesBedrockLoggingUsEast1 --profile bryanchasko-kiro
npx cdk deploy KodiakCreativesBedrockLoggingUsWest2 --profile bryanchasko-kiro
npx cdk deploy kodiak-creatives-hosting             --profile bryanchasko-kiro   # import first if live, see #202 section above
```

or all at once: `npx cdk deploy --all --profile bryanchasko-kiro`.

named-IAM roles (kodiak-bedrock-logging-role\*) require the CDK deploy to run with
named-IAM capability; the CDK CLI adds this automatically.

## post-deploy: verify Bedrock model-invocation logging (BOTH regions)

Each BedrockLoggingStack enables the account+region singleton at deploy time via
an AwsCustomResource. If you need to re-apply or verify by hand, each stack emits
the exact CLI as the `EnableLoggingCommand` output. Run for BOTH regions:

```
# us-east-1
aws bedrock put-model-invocation-logging-configuration \
  --region us-east-1 --profile bryanchasko-kiro \
  --logging-config '{"cloudWatchConfig":{"logGroupName":"/aws/bedrock/kodiak-model-invocations","roleArn":"<KodiakCreativesBedrockLoggingUsEast1.BedrockLoggingRoleArn>"},"textDataDeliveryEnabled":true,"imageDataDeliveryEnabled":true,"embeddingDataDeliveryEnabled":true,"videoDataDeliveryEnabled":true}'

# us-west-2 (FIX 2)
aws bedrock put-model-invocation-logging-configuration \
  --region us-west-2 --profile bryanchasko-kiro \
  --logging-config '{"cloudWatchConfig":{"logGroupName":"/aws/bedrock/kodiak-model-invocations","roleArn":"<KodiakCreativesBedrockLoggingUsWest2.BedrockLoggingRoleArn>"},"textDataDeliveryEnabled":true,"imageDataDeliveryEnabled":true,"embeddingDataDeliveryEnabled":true,"videoDataDeliveryEnabled":true}'

# verify each
aws bedrock get-model-invocation-logging-configuration --region us-east-1 --profile bryanchasko-kiro
aws bedrock get-model-invocation-logging-configuration --region us-west-2 --profile bryanchasko-kiro
```

substitute the real role ARNs from the stack outputs. The custom resource does
NOT disable logging on stack delete (the singleton is account-level and may be
shared), so a delete leaves logging enabled -- disable by hand if intended.

## notes / discrepancies flagged during porting

- The DAM bucket SSE is `aws:kms` (KMS-managed default key) with
  `bucketKeyEnabled`, NOT plain SSE-S3. Ported from the live `template.yaml` /
  `import-dam.yaml`; the `s3-dam.tf` default was `aws:kms` too. If the task brief
  said SSE-S3, the live truth is KMS-managed -- ported live truth to keep import
  drift-free.
- CodeBuild CI project + CI role from `../infra/template.yaml` were NOT ported --
  CI is out of scope for this IaC app and is owned separately (ghost-orin-ci-cd).
  Flag, not guess.
- `../infra/browser-observability.yaml` was not read/ported -- not in the
  enumerated port list. Flag for a follow-up if it should move to CDK.
