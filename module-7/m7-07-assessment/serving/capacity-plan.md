# Capacity plan

How many pods, on what hardware, and why — for **800 RPS peak** at **120 ms p95**. These two numbers
are the same ones in [slos.yaml](slos.yaml) and the [architecture latency budget](../architecture/architecture.md);
the whole plan hangs off them.

## Hardware

CPU pods, **4 vCPU / 8 GB** each. CPU because the ranker is small and fits the budget on CPU
([ADR-0002](../architecture/adr/0002-cpu-synchronous-serving.md)). 8 GB comfortably holds the baked
~180 MB model plus the venv and per-worker overhead. Pods are stateless and interchangeable
(model is baked in, [ADR-0001](../architecture/adr/0001-bake-model-into-image.md)), so scaling is just
adding/removing identical pods.

## Latency budget (per request, p95)

Repeated here so the replica math is grounded in it:

| Stage | p95 |
|---|---|
| Ingress + network in | 15 ms |
| Feature fetch (Redis) | 20 ms |
| Candidate retrieval (ANN) | 25 ms |
| Ranking inference (CPU) | 40 ms |
| Serialize + network out | 20 ms |
| **Total** | **120 ms** |

Of that 120 ms wall time, the **CPU-bound** part is roughly the 40 ms inference + ~10 ms serialize =
**~50 ms of CPU per request**. The 45 ms of Redis/ANN is I/O wait — the worker isn't burning CPU then,
which is why async workers let a pod handle more than 4 concurrent requests.

## Replica math (two ways, they should bracket each other)

**Method A — CPU throughput (sizing for steady peak).**
A 4 vCPU pod has 4000 ms of CPU per wall-second. Target utilization **65%** (headroom for GC pauses,
tail latency, and not running hot) → 2600 ms usable CPU/sec per pod.
At ~50 ms CPU per request: `2600 / 50 ≈ 52 RPS per pod`.
For 800 RPS: `800 / 52 ≈ 15.4` → **16 pods**, plus one for N+1 resilience → **~18 pods at peak**.

**Method B — concurrency ceiling (sanity check, upper bound).**
In-flight requests at peak (Little's law): `800 RPS × 0.120 s = 96 concurrent`. That's the system-wide
concurrency we must absorb. 18 pods × ~6 effective concurrent slots each ≈ 108 > 96 ✓ — and it lines
up with the HPA max below.

So: **18 pods at peak**, and the two methods agree that ~16–24 is the sane band.

## Autoscaling

HPA on CPU utilization, target 65%, **min 12 / max 24**.

- **min 12** keeps enough warm capacity for off-peak (~600 RPS) without cold-start latency spikes, and
  survives a zone loss.
- **max 24** gives ~50% surge headroom over the 18-pod peak — covers a campaign spike or a slow model
  before we'd need to intervene. (24 pods × ~52 RPS ≈ 1250 RPS.)
- Scale-up is aggressive, scale-down is slow (stabilization window) so we don't flap during normal
  traffic waves.

This `max 24` is the same number the open question in the root README flags: if marketing plans a push
campaign, confirm the projected peak before trusting it.

## Dependencies (not pods, but they have to keep up)

- **Redis feature store:** managed, HA, a few GB hot working set. Sized for ~800 reads/sec with
  pipelined keys, p99 read < 5 ms. ~$400/mo.
- **Vector index (ANN):** hosted, holds product embeddings, ~800 queries/sec. ~$500/mo.
- Both are read-only on the hot path, so they scale with read load, not write load.

## Monthly cost estimate

Rough, on-demand-ish pricing, averaged over the day (we're not at peak 24/7 — average ~14 pods):

| Item | Est. / mo |
|---|---|
| Serving pods (avg ~14 × 4 vCPU/8 GB) | ~$1,900 |
| Redis feature store (HA) | ~$400 |
| Vector index host | ~$500 |
| Load balancer + egress + observability | ~$600 |
| **Total** | **~$3,400 / mo** |

Rounded to **~$3.5k/mo** in the root README. Biggest lever if we need to cut: committed-use/spot for
the steady baseline pods. Biggest risk to the number: a higher real peak (see open question 1).
