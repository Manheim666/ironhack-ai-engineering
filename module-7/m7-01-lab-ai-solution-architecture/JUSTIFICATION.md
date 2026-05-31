# Justification — Scenario A: Real-Time Fraud Scoring

## Which serving pattern and why

**Online synchronous inference.**

The scenario specifies p95 latency ≤ 80 ms end-to-end with ~300 transactions/second at peak, and the three downstream actions (block / allow / step-up-auth) must be delivered before the user sees the payment confirmation screen. That eliminates batch entirely — a Monday-morning churn list can tolerate a two-day-old score; a payment cannot. Streaming (async event-driven) would reduce coupling but adds an irreducible message-queue round-trip of 10–50 ms, consuming most of the 80 ms budget before the model even runs. Online synchronous is the only pattern that fits within the latency envelope while delivering a decision in the same HTTP response as the transaction request.

Specific lines from the scenario that force this choice:
- "score every transaction **before** the user sees confirmation" → result must be synchronous with the request.
- "p95 latency budget 80 ms end-to-end" → no room for async round-trips.
- "Block / allow / step-up-auth are the three downstream actions" → each action is time-coupled to a specific transaction.

## Where inference runs and why

**Cloud inference, no edge.** The model requires two enrichment signals — account history and device fingerprint — that live in a backend feature store. Replicating a full account-history feature store to edge devices is impractical and a compliance risk. The model binary itself is likely 50–200 MB (gradient-boosted tree or shallow neural net), which is edge-feasible in isolation, but without the features it cannot run meaningfully. Cloud inference with a globally distributed Redis cluster for the feature store keeps the feature lookup under 5 ms from any major region, leaving ~70 ms for network + model + decision logic — achievable with an ONNX-optimized model on a CPU inference fleet.

## Latency, throughput, and cost targets

**Optimize for:** p95 latency ≤ 80 ms (hard SLA — budget constraint) and **throughput ≥ 300 TPS sustained** (business requirement — the system must not drop transactions at peak).

**Accept as secondary:** cost. Fraud prevention has a clear ROI: one prevented fraudulent transaction typically covers the inference cost of thousands of legitimate ones. Over-provisioning the inference fleet is cheaper than missed fraud or degraded user experience from latency spikes.

Concrete targets:
- **p99 latency ≤ 120 ms** (allow headroom above p95 budget for tail spikes).
- **Feature store p99 read ≤ 5 ms** (Redis Cluster, single-digit-ms SLA).
- **ONNX model inference ≤ 20 ms** on CPU (gradient-boosted tree or shallow net; GPU is wasteful at this batch size of 1).
- **Throughput:** autoscale inference pods to handle 300 TPS with ≥ 30% headroom.

## Fallback when the model is unavailable or wrong

**Unavailable (serving outage):** Fall back to a deterministic rule-based engine: velocity checks (> 5 transactions from one account in 60 seconds → step-up-auth; > 15 → block), known-bad BIN list, and geolocation mismatch flag. This covers ~85% of obvious fraud patterns with zero ML dependency. The rule engine runs in the same Fraud Scoring API process, so there is no additional network hop.

**Wrong (false positive / false negative):** The Decision Engine applies a three-tier threshold rather than a binary cut. Scores between 0.4 and 0.75 route to step-up-auth (soft challenge) rather than hard block. This converts uncertain model outputs into a recoverable human interaction instead of a binary loss event. Chargebacks and customer-reported false blocks feed outcome labels back to the Data Warehouse within 24 hours, closing the retraining loop.
