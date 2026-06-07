![logo_ironhack_blue 7](https://user-images.githubusercontent.com/23629340/40541063-a07a0a8a-601a-11e8-91b5-2f13e4e6b441.png)

# Personalized In-App Recommendations — MLOps Design Dossier

> Scenario X (B2C retail). This repo is the design hand-off: everything another team would
> need to start building on Monday. No training, no notebooks — just the system and how we run it.

## Executive summary

We serve personalized product recommendations on every home-screen load of a mobile retail app.
A request comes in with a `user_id`, we pull that user's recent activity from a low-latency feature
store, retrieve a few hundred candidate products with an approximate-nearest-neighbour index, and a
small **ranking model** (we call it `ranker`) scores them. We return the top-N. The whole thing has
to stay under a **120 ms p95** budget while handling **~800 RPS at peak**. Cold-start users (no
history) fall back to a popularity/segment model so they still get something reasonable, and because
the product team A/B tests constantly, the model version is carried end-to-end on every response so
we can attribute experiment results correctly.

The ranking model is **baked into the container image** rather than mounted at runtime — that single
decision drives most of the CI/CD, rollback, and registry design, so it's written up as
[ADR-0001](architecture/adr/0001-bake-model-into-image.md).

## Architecture

See [architecture/architecture.md](architecture/architecture.md) for the full diagram and component
notes. The short version: stateless serving pods behind an ingress/load balancer, a Redis feature
store for per-user features, a vector index for candidate retrieval, and the ranker running on CPU
inside each pod.

## Key numbers

| Thing | Value | Where it's pinned |
|---|---|---|
| Target throughput (peak) | 800 RPS | [capacity-plan](serving/capacity-plan.md), [slos.yaml](serving/slos.yaml) |
| Latency objective | p95 ≤ 120 ms end-to-end | [slos.yaml](serving/slos.yaml) |
| Availability objective | 99.9% (30-day) | [slos.yaml](serving/slos.yaml) |
| Error-rate objective | < 0.5% 5xx | [slos.yaml](serving/slos.yaml) |
| Model size (ranker) | ~180 MB (baked into image) | [container/README.md](container/README.md) |
| Image size (final) | ~480 MB | [container/README.md](container/README.md) |
| Serving hardware | CPU pods, 4 vCPU / 8 GB | [capacity-plan](serving/capacity-plan.md) |
| Replicas at peak | ~18 (HPA 12–24) | [capacity-plan](serving/capacity-plan.md) |
| Monthly cost estimate | ~$3.5k (serving + Redis + index) | [capacity-plan](serving/capacity-plan.md) |

## Navigation

| Area | Primary artifact |
|---|---|
| Architecture | [architecture/architecture.md](architecture/architecture.md) · [JUSTIFICATION](architecture/JUSTIFICATION.md) · [ADRs](architecture/adr/) |
| Lifecycle & registry | [lifecycle/lifecycle.md](lifecycle/lifecycle.md) · [model-registry.yaml](lifecycle/model-registry.yaml) |
| Container | [container/Dockerfile](container/Dockerfile) · [container/README.md](container/README.md) |
| API contract | [api/openapi.yaml](api/openapi.yaml) · [examples/](api/examples/) |
| Capacity & SLOs | [serving/capacity-plan.md](serving/capacity-plan.md) · [slos.yaml](serving/slos.yaml) · [load-test-plan.md](serving/load-test-plan.md) |
| CI/CD | [cicd/.github/workflows/deploy-model.yml](cicd/.github/workflows/deploy-model.yml) |
| Monitoring | [monitoring/alerts.yaml](monitoring/alerts.yaml) |
| Rollback | [runbooks/rollback.md](runbooks/rollback.md) |

## Open questions (things I'd confirm Monday)

1. **Is 800 RPS really the ceiling, or just today's peak?** The replica math has headroom to ~24
   pods, but if marketing is planning a push-notification campaign that spikes home-screen loads,
   I'd want the projected peak before we commit the HPA max and the cost number.
2. **What's the actual feature freshness requirement?** I've assumed "last 30 days" can tolerate a
   feature store that's refreshed every few minutes. If recommendations must reflect a purchase from
   *seconds* ago, the feature pipeline (and the cost) changes shape.
3. **Who owns the cold-start fallback model, and how often does it retrain?** I've treated it as a
   separate, slower-moving artifact, but the team may want it folded into the same release train.
