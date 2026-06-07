# Why this architecture

The pattern is **synchronous online inference with retrieve-then-rank**. Below is why that beats the obvious alternatives for *this* scenario, and the trade-offs I'm accepting.

## The forcing constraints

- 120 ms p95, end-to-end, on every home-screen load.
- \~800 RPS at peak.
- Personalization needs the user's last 30 days of activity.
- Cold-start users still need a reasonable answer.
- Continuous A/B testing on the model.

Two of these pull hardest: the latency budget rules out scoring the whole catalog per request, and the A/B requirement means model identity has to be a first-class, traceable thing.

## Alternatives I considered

**1. Fully precomputed recommendations (batch, cached per user)**.Compute top-N for every user overnight, stash in a cache, serve a lookup at request time. Tempting because it makes the hot path trivially fast. Rejected because: it can't reflect *today's* browsing, which is the whole point of "last 30 days including recent activity"; and it explodes for cold-start and for users who weren't in last night's batch. We keep a *cache-friendly* design (the feature store, the candidate index) but the final ranking is computed live so it reflects current context.

**2. Score the entire catalog online per request**.Maximum personalization quality, no retrieval step. Rejected because: ranking tens of thousands of products per request inside a 40 ms inference budget isn't realistic on CPU, and it scales with catalog size rather than with what the user might plausibly want. Retrieve-then-rank caps the ranker's work at a few hundred candidates regardless of catalog size — that's what keeps inference at a predictable \~40 ms.

**3. GPU serving**.Rejected for now (see ADR-0002). The ranker is small enough that CPU comfortably hits the budget, and CPU pods are cheaper, simpler to autoscale, and don't drag in GPU node pools and driver/runtime baggage. If the model grows into something heavier (e.g. a transformer ranker), revisit.

## The pattern I chose

Retrieve-then-rank, served synchronously online:

1. Fetch user features from Redis (fast, side-effect-free read).
2. Retrieve a few hundred candidates from the ANN index.
3. Rank them with the baked `ranker` (or the fallback for cold start).
4. Return top-N with the model version attached.

Everything that's expensive or slow (computing features, building embeddings, training) is pushed **off the request path** into the offline tier. The hot path only does cheap reads and one bounded inference. That's the core idea.

## Trade-offs I'm accepting

- **Feature freshness is bounded by the pipeline cadence, not real-time.** If the business needs recommendations to reflect an action from seconds ago, this design needs a streaming feature path bolted on. 
- **Baking the model into the image** (ADR-0001) means a model update requires an image build and redeploy — slower than hot-swapping a mounted artifact. I'm trading update latency for reproducibility, atomic rollback, and a dead-simple "what version is running" story. For a system under continuous A/B testing, knowing *exactly* what shipped is worth more than shaving minutes off a model update.
- **Retrieve-then-rank can miss a great item that ANN didn't surface.** Recall is bounded by the retrieval step. Acceptable: tuning candidate count trades latency for recall, and we'd rather ship a fast good answer than a slow perfect one on a home screen.
- **CPU inference** caps how heavy the ranker can get. Accepted until the model demands otherwise.

## How this stays coherent with the rest of the repo

- The 120 ms budget here is the same one in [slos.yaml](../serving/slos.yaml) and the [capacity plan](../serving/capacity-plan.md).
- "Baked, not mounted" here is ADR-0001, and it's the assumption the [Dockerfile](../container/Dockerfile)and CI pipeline are built on.
- The `X-Model-Version` header is defined in [openapi.yaml](../api/openapi.yaml) and consumed by the [version-mismatch alert](../monitoring/alerts.yaml).