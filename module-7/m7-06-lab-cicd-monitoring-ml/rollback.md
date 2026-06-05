# Runbook — Rollback: vision-moderation

On-call checklist. Fits one phone screen. Roll back first, diagnose after.

## When to roll back (any one = roll back)
- [ ] 5xx error rate > 1% for 5 min, OR `AvailabilityBurnFast` paging
- [ ] p99 latency > 1s for 5 min (`LatencyP99High`)
- [ ] `ModelVersionMismatch` paging after a deploy
- [ ] Quality proxy: moderation block-rate shifts > 3σ from 7-day baseline
- [ ] Smoke/canary-verify failed but rollout continued

## How to roll back
- [ ] Find last-good SHA: `gh run list --workflow=deploy-model.yml --branch main`
- [ ] Trigger rollback workflow:
      `gh workflow run rollback.yml -f target_env=production -f sha=<LAST_GOOD_SHA>`
      (or run `./scripts/rollback.sh` with `TARGET_ENV=production IMAGE_TAG=ghcr.io/<repo>:<LAST_GOOD_SHA>`)
- [ ] Confirm traffic on old version: registry `active_model_version` == last-good

## What to verify (must return green)
- [ ] `AvailabilityBurnFast` / `AvailabilityBurnSlow` cleared
- [ ] `LatencyP99High` cleared; p95 ≤ 250 ms on the latency dashboard
- [ ] `ModelVersionMismatch` count == 0
- [ ] 5xx rate back < 0.1%

## Who to notify
- [ ] `#incident-vision-moderation` (Slack) — declare + post status
- [ ] Page IC if not already engaged (PagerDuty: vision-moderation)
- [ ] If SLA risk (partner refund line), notify Partner Success lead

## What NOT to do
- [ ] Do NOT roll *forward* with a hotfix before root cause is known
- [ ] Do NOT clear/silence alerts before metrics actually recover
- [ ] Do NOT skip canary on the re-deploy
- [ ] Do NOT delete the bad image — keep it for postmortem

## When to roll forward
- [ ] Root cause identified AND fix has passing unit + contract + smoke
- [ ] Canary at 10% verifies clean for ≥ 15 min
- [ ] Error budget has recovered enough to absorb a new deploy
