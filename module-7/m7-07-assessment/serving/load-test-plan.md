# Load test plan

The point of this test isn't "can it survive a flood" — it's to **confirm the assumptions the capacity
plan rests on** before we trust them in production. Specifically: does a 4 vCPU pod really sustain
~50 RPS at p95 ≤ 120 ms, and does the fleet hold the budget at 800 RPS?

## What we're validating

1. **Per-pod throughput.** The replica math says ~52 RPS/pod at 65% CPU. Measure the real number.
2. **Fleet at peak.** 800 RPS across the autoscaled fleet stays under p95 120 ms, error rate < 0.5%.
3. **Autoscaling behaves.** HPA scales 12 → up toward 18–24 under rising load without latency blowing
   past budget during the scale-up, and scales back down without flapping.
4. **The 40 ms inference assumption.** Isolate it — it's the single number the whole budget pivots on.
5. **Cold-start path.** Fallback model requests stay within the same budget (no surprise slow path).

## Workload model

Traffic is single-user `POST /v1/recommendations` (the home-screen hot path) — that's >95% of real
load, so the test mirrors it. A small slice exercises the batch endpoint separately (it has its own,
looser expectations).

- **Request mix:** 90% known users (ranker), 10% cold-start (fallback). Roughly matches expected
  cold-start share; tune once we see real numbers.
- **Payloads:** drawn from a pool of realistic `user_id`s so feature-store cache hit rates are
  realistic — hitting one hot user would lie to us about Redis latency.
- **`num_results`:** mostly 10–20.

## Stages

Run these in order; each answers a specific question.

| Stage | Load | Duration | Looking for |
|---|---|---|---|
| 0. Smoke | 5 RPS | 2 min | Correctness, no errors, baseline latency. |
| 1. Single-pod | ramp to find the knee, **pinned to 1 pod** (HPA disabled) | ~15 min | The real per-pod RPS at p95 = 120 ms. Validates Method A. |
| 2. Steady peak | 800 RPS, HPA on | 30 min | p95 ≤ 120 ms, 5xx < 0.5%, fleet settles ~16–18 pods. |
| 3. Surge | ramp 800 → 1200 RPS over 5 min, hold 10 min | 15 min | HPA reaches toward max 24, budget holds during scale-up. |
| 4. Soak | 600 RPS | 2 h | No latency creep, no memory leak, stable over time. |
| 5. Dependency stress | 800 RPS while injecting +30 ms Redis latency | 10 min | Graceful degradation, readiness behaves, no cascading errors. |

## Pass / fail criteria

These are the [SLO](slos.yaml) numbers — the test passes only if production targets would hold:

- **p95 latency ≤ 120 ms** at 800 RPS (stage 2). Hard gate.
- **Error rate < 0.5%** 5xx across stages 2–4.
- **Per-pod RPS ≥ ~50** at the p95 knee (stage 1). If it's materially lower, the replica count and the
  cost estimate are both wrong and get revised before launch.
- **HPA** scales up before p95 degrades and scales down without flapping (stages 3–4).
- **Cold-start requests** stay within the same 120 ms budget.

## Tooling & method

- **k6** (or Locust) driving the synchronous endpoint, run from outside the cluster so ingress and
  network-in are in the measurement.
- Latency measured **server-side at ingress** *and* **client-side** — the gap is the network tax,
  which the budget allots 15 + 20 ms to.
- Grafana dashboards on the same Prometheus metrics the [alerts](../monitoring/alerts.yaml) use, so the
  test and production look at identical signals.
- Run against a staging fleet sized like production. Never the first load test in prod.

## Out of scope

Model *quality* (NDCG/recall) — that's offline eval (Gate 1 in the [lifecycle](../lifecycle/lifecycle.md)),
not a load test. This test only cares about latency, throughput, and stability.
