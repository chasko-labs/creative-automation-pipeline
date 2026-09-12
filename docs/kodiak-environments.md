# kodiak deployment environments

## branch and hostname contract

The deployment target is explicit, then checked against the branch before any AWS call:

| branch | target | hostname | behavior |
| --- | --- | --- | --- |
| `main` | `prod` | `kodiak.bryanchasko.com` | production deployment with approval and audit evidence |
| any other named branch | `dev` | `kodiak-dev.bryanchasko.com` | shared development environment; the latest successful branch deployment wins |

A non-main branch cannot target production. A detached checkout cannot deploy. Local deployment uses the checked-out branch; CodeBuild uses `CODEBUILD_WEBHOOK_HEAD_REF` as the branch source

Development branches share one development hostname. Multiple branches therefore follow latest-wins behavior rather than receiving separate live hosts. Promotion happens by merging the approved change to `main`. Rollback happens by republishing a known-good commit through the same target-aware process

## separate resources

Development requires a separate resource set from production:

- S3 bucket for the development site
- CloudFront distribution for the development site
- Route 53 alias for `kodiak-dev.bryanchasko.com`
- ACM certificate coverage for the development hostname, separate from production coverage unless an approved certificate explicitly covers both names
- access logging for the development bucket and CloudFront distribution, retained under the environment's logging policy

The deploy script consumes only the development bucket, distribution, and hostname. It requires these environment variables and fails closed when any is absent:

```text
KODIAK_DEV_BUCKET
KODIAK_DEV_DISTRO
KODIAK_DEV_HOSTNAME
```

No development identifier, certificate, hosted-zone value, or logging destination will be guessed in repository code

## CodeBuild contract

The repository-owned `buildspec.yml` defines the CodeBuild execution contract. The CodeBuild project will run in `us-west-2`; the website S3, CloudFront, Route 53, and ACM resources will use `us-east-1`

Required project and webhook configuration:

- enable a repository webhook on the CodeBuild project
- configure the webhook to provide `CODEBUILD_WEBHOOK_HEAD_REF`
- run the project from a clean source checkout
- provide an execution role with only the approved deployment and read permissions
- use role credentials in CodeBuild; do not configure `AWS_PROFILE`, access keys, or secret values in the buildspec
- configure `KODIAK_DEV_BUCKET`, `KODIAK_DEV_DISTRO`, and `KODIAK_DEV_HOSTNAME` as CodeBuild environment values after inventory approval
- leave `ALLOW_DIRTY_WORKTREE` unset; the deploy script rejects dirty worktrees by default

The buildspec derives `prod` for `main`, `dev` for every other named branch, runs the repository's non-Nova deterministic gates, then invokes `scripts/deploy-frontier.sh` with that target. A target and branch mismatch remains a hard failure inside the script

For local operation, `AWS_PROFILE` may select an existing profile. `DRY_RUN=1` preserves the no-mutation preview. The controlled emergency override `ALLOW_DIRTY_WORKTREE=1` remains off by default and will not be used by CodeBuild

## live infrastructure blocker

Before provisioning development resources, the live inventory must discover the resource identifiers and certificate coverage. That inventory includes the development S3 bucket, CloudFront distribution, Route 53 hosted zone and alias state, ACM certificate coverage, and logging destinations. No guessed identifier will enter `infra-cdk`, the buildspec, the deployment script, or environment configuration

This repository-side process does not provision resources, call AWS APIs, upload content, invalidate CloudFront, or change DNS. AWS inventory and provisioning will occur as a separate specialist task after the AWS transport is healthy

## production controls

Production deployment requires approval before the merge to `main` is published. The deployment record will include the approved commit, branch, selected target, CodeBuild build identifier, gate results, S3 bucket, CloudFront distribution, hostname, invalidation identifier, and final verification result

A production rollback will republish a known-good commit after approval. Development deployments will not be treated as production approval or audit evidence
