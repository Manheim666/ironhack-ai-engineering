# ADR-0002: Serve on CPU, synchronously, rather than GPU or async

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** Asif Habilov

## Context

We have a 120 ms p95 budget at 800 RPS. The ranker scores a few hundred candidates per request. Two sub-questions:

1. **CPU or GPU** for inference?
2. **Synchronous** request/response, or push the work onto an **async queue**?

## Decision

**CPU, synchronous.** The ranker is small enough to score \~300 candidates in \~40 ms on CPU. Home-screen recommendations are inherently a synchronous, user-blocking call — the app is waiting to render — so a queue would just add latency and complexity for no benefit.

We still expose **batch and async endpoints in the API** (see [openapi.yaml](../../api/openapi.yaml)), but those serve *different* use cases (offline scoring, large jobs), not the home-screen hot path.

## Consequences

**Gains**

- **Cheaper and simpler scaling.** CPU pods autoscale cleanly on CPU/RPS, no GPU node pools, no driver or CUDA-runtime baggage in the image, no GPU scheduling constraints.
- **The latency budget closes on CPU.** 40 ms inference fits, with the retrieve step capping the work the ranker has to do.
- **Synchronous path is the simplest correct thing** for a blocking UI call — fewer failure modes, easier to reason about, trivial to trace end-to-end.

**Costs**

- **Ceiling on model size.** A much heavier ranker (large transformer) might not fit 40 ms on CPU. If we go there, this ADR gets revisited and GPU re-enters.
- **No free batching efficiency.** GPUs love big batches; per-request CPU inference doesn't get that. Fine here — requests are independent and latency-sensitive, not throughput-bound on a single box.

## Alternatives rejected

- **GPU serving:** over-provisioned for a small ranker, more expensive, more operationally heavy. Re-open if the model grows.
- **Async/queue for the home-screen call:** adds latency to a call the user is actively waiting on. Wrong tool for a blocking render. (Async *is* the right tool for the bulk endpoints, which is why the API offers it there.)

## Relationship to ADR-0001

Independent but compatible: baking the model in (0001) plus CPU pods (0002) gives us cheap, stateless, fast-to-roll-back replicas. The two together are what make the capacity plan and rollback runbook as simple as they are.