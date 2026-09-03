# Working together on the Kodiak creative pipeline

This guide is for anyone who helps build the pipeline — designers, marketers, and engineers — and it keeps the whole system in one connected place.

## How we work in plain language

We keep everything together. One cloud setup, one photo and style library, one growing table that remembers what worked per place. Nothing is split across hidden accounts.

### One cloud setup that holds it all

We describe the whole system in a single cloud formation file at `infra/template.yaml`. That file creates:

- the cloud storage buckets where style and photos live
- the versioned style library (tokens, logos, photo directions)
- the regional knowledge base (places, audiences, messages)
- the table that remembers what worked per place

But our current live bucket was built with the earlier style library template at `infra/s3-dam.tf` — that template already created `chasko-creative-dam-946179428633-us-east-1` in us-east-1 with versioning, blocked public access, and lifecycle rules. The new single file at `infra/template.yaml` wraps that plus the tables and knowledge base so future deploys stay one file.

### How we test before we ship

Every change must pass these checks:

1. **Quick local checks** — from the project folder:

   ```
   uv run pytest -q
   uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out /tmp/verify-kodiak
   uv run python scripts/nova-act-check.py --preview /tmp/verify-kodiak/preview.html --out /tmp/nova.json
   ```

   All should say pass.

2. **End to end through the cloud** — with `AWS_PROFILE=bryanchasko-kiro` and `DAM_S3_BUCKET` set:

   ```
   ./scripts/sync-dam.sh pull
   DAM_S3_BUCKET=chasko-creative-dam-946179428633-us-east-1 uv run python -m creative_automation.cli --brief briefs/kodiak-on-the-go.yaml --assets input_assets --out output_kodiak-on-the-go
   ./scripts/sync-dam.sh push-renders output_kodiak-on-the-go
   ```

   Then check the style library loaded from cloud, not just your laptop.

3. **Cloud formation safety** before any deploy:
   ```
   cfn-lint infra/template.yaml
   cfn-guard validate --template infra/template.yaml --rules cfn-guard-rules/
   aws cloudformation create-change-set --stack-name kodiak-creatives --template-body file://infra/template.yaml --capabilities CAPABILITY_NAMED_IAM
   aws cloudformation describe-events --stack-name kodiak-creatives --filters FailedEvents=true --region us-east-1
   ```

### How to add something new — dispatched development

When you want to add a new channel (for example, a diner menu board or a subscription email) or a new region (for example, Las Cruces green chile):

1. Add a one-page brief at `briefs/kodiak-your-idea.yaml` with at least two products, a place, an audience, and one line of message. Write it in human words — no short forms.
2. Add a row to `data/localization/localization-training-data.jsonl` and `data/localization/localization-table-seed.json` for that place, or let the pipeline add it automatically after the first run succeeds.
3. Add your test to `tests/` that proves the new brief produces three sizes, shows the line, and passes the bear and color check.
4. Run the quick local checks above. If your change touched cloud storage, run the cloud end to end.
5. Open a small pull request with just those files. Keep it under 500 lines so marketing can review the words and engineering can review the logic.

### What we expect in every pull request

- Human description: who is this for (Maya the brand manager, Diego the field ambassador, Priya the paid media lead), what place and store does it serve, and what will marketing see?
- No short forms in docs or code comments — write "cloud storage," "photo library," "style tokens" instead of initials.
- Updated human docs if you changed the experience: `docs/ux-persona-kodiak.md`, `docs/kodiak-brand-explained.md`, or `docs/regional-cultural-database.md`.
- Screenshots of `preview.html` for the new campaign (one per size) attached to the pull request — the reviewer should not need to run the code to see the result.

### Daily flow

- Work on the main branch is continuous — we commit small and push often to the private repository at https://github.com/chasko-labs/creative-automation-pipeline .
- The cloud bucket `chasko-creative-dam-946179428633-us-east-1` always holds the latest approved style tokens, references, and renders under `brands/kodiak/`. Pull before you branch, push after your change is approved.
- worktrees: three teams share one clone — see [docs/architecture/worktree-workflow.md](docs/architecture/worktree-workflow.md)

### Need help?

Open an issue with the place, store group, and the line you want to try. Label it with the persona it serves (brand, field, media).
