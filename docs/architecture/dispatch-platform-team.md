# dispatch — infra + data-platform team

This repository keeps infrastructure source, data synchronization, and local check governance in the platform lane. The project does not use a server-side continuous integration service

## orientation

- repository: `chasko-labs/creative-automation-pipeline`
- local checks: `scripts/hooks/pre-push` and `scripts/hooks/full-check.sh`
- local browser evidence: `scripts/browser-check.py` and `tests/browser/`
- infrastructure source: `infra/` and `infra-cdk/`
- data synchronization: `scripts/sync-dam.sh` and related manual commands

Read `docs/architecture/team-lanes.md` and `docs/architecture/dispatch-guideline.md` before editing platform-owned files

## platform boundaries

- local gates must use repository-owned tools and committed fixtures
- browser testing remains local Playwright or deterministic pixel and markup checking
- campaign generation remains an explicit manual command, never a gate
- data synchronization remains an explicit manual command and may use `AWS_PROFILE=bryanchasko-kiro` when cloud storage access is required
- secrets remain in AWS Systems Manager Parameter Store; no local secret files
- infrastructure changes require local template validation before any separately authorized deployment

## manual data commands

```bash
AWS_PROFILE=bryanchasko-kiro ./scripts/sync-dam.sh pull
AWS_PROFILE=bryanchasko-kiro uv run python scripts/embed-social-corpus.py --out data/vectors
```

These commands are not part of the pre-push hook or full local gate

## local check commands

```bash
scripts/hooks/pre-push
scripts/hooks/full-check.sh
npm run test:browser
uv run python scripts/browser-check.py --all --out /tmp/browser-report.json
```

The repository keeps the former server-side gate only as migration history in `docs/archive/buildspec-retired.md`. It is not an executable build definition
