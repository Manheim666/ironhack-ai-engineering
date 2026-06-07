# Runbook: Roll back the ranker

For the tired on-call at 3am. If a deploy went bad, this gets you back to the last known-good model
fast. Rolling back = deploying the previous image tag, because the model is baked into the image
([ADR-0001](../architecture/adr/0001-bake-model-into-image.md)). No mounted artifacts to untangle.

**Estimated time to safe: ~5 minutes.**

## Roll back when ANY of these fire

These are the [alerts](../monitoring/alerts.yaml) — same thresholds as the [SLOs](../serving/slos.yaml):

- [ ] `ErrorBudgetFastBurn` — 5xx burning the budget ~14.4x (page).
- [ ] `LatencyFastBurn` — p95 over 120 ms, burning fast (page).
- [ ] `ModelVersionMismatch` — pods serving a version ≠ registry champion (page).
- [ ] `ColdStartRateSpike` — >25% cold-start (page) **and** it started with the last deploy.
- [ ] Error rate **> 0.5%** sustained 5 min, OR p95 **> 120 ms** sustained 5 min, and it lines up with
      a recent rollout.

If it's a slow-burn/ticket alert and traffic is fine, **don't** roll back reflexively — investigate first.

## Before you touch anything (10 seconds)

- [ ] Confirm a deploy happened recently. Check the [pipeline](../cicd/.github/workflows/deploy-model.yml)
      run history — is the timing of the alert ≈ the rollout?
- [ ] Note the **currently-serving tag** and the **previous known-good tag**:
      ```
      kubectl -n recsys get deploy ranker -o=jsonpath='{.spec.template.spec.containers[0].image}'
      kubectl -n recsys rollout history deploy/ranker
      ```
- [ ] Drop a line in the incident channel: "rolling back ranker from `<bad-tag>` to `<good-tag>`".

## Roll back

- [ ] Roll back to the previous revision:
      ```
      kubectl -n recsys rollout undo deploy/ranker
      ```
      (or pin an explicit known-good tag if you need a specific one:)
      ```
      kubectl -n recsys set image deploy/ranker ranker=ghcr.io/example/ranker:1.4.2-9f3a1c2d
      ```
- [ ] Watch it land:
      ```
      kubectl -n recsys rollout status deploy/ranker --timeout=120s
      ```

## Verify you're actually safe (don't skip)

- [ ] **Version is right:** new responses report the expected `X-Model-Version` (e.g. `ranker-1.4.2`),
      and `ModelVersionMismatch` clears within ~10 min.
      ```
      curl -s -D - https://api.example.com/v1/recommendations -d '{"user_id":"u_8812734"}' | grep -i x-model-version
      ```
- [ ] **Latency recovered:** p95 back under 120 ms on the dashboard.
- [ ] **Errors recovered:** 5xx back under 0.5%.
- [ ] **Cold-start normal:** back near ~10%.
- [ ] The page clears.

## If rollback DOESN'T fix it

Then the model probably wasn't the cause. In rough order:

- [ ] **Feature store:** is Redis healthy/reachable? A `ColdStartRateSpike` that survives rollback
      points here, not at the model. (`/readyz` failing on pods = a dependency is down.)
- [ ] **Vector index (ANN):** up and within latency? Retrieval stalls show as latency burn.
- [ ] **Traffic surge:** is RPS above the ~1250 the fleet can hold (HPA at max 24)? If so it's capacity,
      not a bad model — bump HPA max / scale the node pool (see [capacity plan](../serving/capacity-plan.md)).
- [ ] **Escalate** to the serving on-call lead if none of the above and the page is still active.

## After (when it's quiet)

- [ ] Mark the bad version `archived` in the [registry](../lifecycle/model-registry.yaml) so it can't
      be promoted again by accident.
- [ ] Open a follow-up: why did it clear the canary gate but fail in prod? File it; fix the gate.
- [ ] Short write-up in the incident doc. Five sentences is fine.
