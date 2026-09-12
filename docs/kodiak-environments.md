# kodiak deployment environments

## operator deployment contract

The deployment target is explicit, then checked against the current named local git branch before any cloud call:

| branch | target | hostname | behavior |
| --- | --- | --- | --- |
| `main` | `prod` | `kodiak.bryanchasko.com` | production deployment after approved changes are merged |
| any other named branch | `dev` | `kodiak-dev.bryanchasko.com` | shared development environment; the latest successful branch deployment wins |

The deployment script accepts exactly `prod` or `dev`. It reads the current branch with `git symbolic-ref`, rejects detached checkouts, permits `prod` only from `main`, and permits `dev` only from every other named branch

A named development branch will run the deterministic local gates, then an operator will run:

```bash
AWS_PROFILE=<local-profile> ./scripts/deploy-frontier.sh dev
```

All named development branches share `kodiak-dev.bryanchasko.com`. The latest successful branch deployment wins on that hostname. A git push alone does not deploy a site

After approved changes merge to `main`, the operator will use a clean `main` checkout, run the same deterministic local gates, then run:

```bash
AWS_PROFILE=<local-profile> ./scripts/deploy-frontier.sh prod
```

Production remains an explicit operator action

The local deployment requires an explicit `AWS_PROFILE`, uses the fixed website region, protects against a dirty worktree by default, supports `DRY_RUN=1` for a no-mutation preview, exports `WEB_SRC`, and verifies the selected hostname in its final output

## separate resources

Development requires a separate resource set from production:

- separate S3 bucket for the development site
- separate CloudFront distribution for the development site
- Route 53 alias for `kodiak-dev.bryanchasko.com`
- certificate coverage for the development hostname, separate from production coverage unless an approved certificate covers both names
- access logging for the development bucket and CloudFront distribution, retained under the environment logging policy

The deployment script consumes only the development bucket, distribution, and hostname. It requires these environment variables and fails closed when any is absent:

```text
KODIAK_DEV_BUCKET
KODIAK_DEV_DISTRO
KODIAK_DEV_HOSTNAME
```

No development identifier, certificate, hosted-zone value, or logging destination will be guessed in repository code

## live AWS inventory and provisioning blocker

Before provisioning development resources, the live AWS inventory must discover the resource identifiers and certificate coverage. That inventory includes the development S3 bucket, CloudFront distribution, Route 53 hosted zone and alias state, certificate coverage, and logging destinations. No guessed identifier will enter `infra-cdk`, the deployment script, or environment configuration

This repository-side process does not provision resources, call AWS APIs, upload content, invalidate CloudFront, or change DNS. AWS inventory and provisioning will occur as a separate specialist task after the AWS transport is healthy

## production controls and rollback

Production deployment requires approval before the merge to `main` is published. The deployment record will include the approved commit, branch, selected target, gate results, S3 bucket, CloudFront distribution, hostname, invalidation identifier, and final verification result

A rollback will republish a known-good commit through the same target-aware operator process. Development deployments will not be treated as production approval or audit evidence
