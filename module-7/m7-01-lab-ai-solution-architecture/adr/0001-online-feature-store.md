# ADR 0001: Pre-materialise features in an online store rather than computing them at request time

## Context

The fraud model requires two enrichment signals — rolling account transaction history (last 30 days) and device fingerprint profile — that are not available in the raw transaction payload. These must be retrieved in the 80 ms end-to-end budget that includes network, feature lookup, inference, and decision logic.

## Decision

Maintain a dedicated online feature store (Redis Cluster) that is written to by an hourly batch ETL pipeline reading from the Data Warehouse. At request time, the Fraud Scoring API performs a single multi-key GET on account_id and device_id and receives pre-aggregated feature vectors in under 5 ms. The feature pipeline, not the serving path, handles all joins, window aggregations, and normalisation.

## Alternatives rejected

- **Compute features on the fly in the request path** — real-time aggregation over 30 days of account history from a transactional DB at 300 TPS would require a low-latency OLAP store (e.g., ClickHouse) with sub-10 ms query SLAs. Achievable in isolation, but adds a second network dependency in the critical path and a significantly more complex serving component. Latency variance is too high for the 80 ms budget.
- **Embed feature computation in the model server** — moves complexity into the model artefact, making retraining, feature versioning, and A/B testing harder. Feature logic becomes a training/serving skew risk. Rejected: coupling model binary to feature engineering is an operational anti-pattern.
- **Stream-computed features via Kafka + Flink** — would give fresher features (seconds-old rather than up-to-an-hour-old), but streaming infrastructure is operationally heavy for a team that needs to ship quickly. Account history features at hourly granularity are sufficient: fraud velocity patterns manifest over minutes, and device fingerprints change rarely. Not worth the operational cost for marginal freshness gain.

## Consequences

- Feature freshness is bounded by the ETL cadence: up to 1 hour stale. Fraud signals that emerge within the last hour of an account's history may be missed by the model (mitigated by the rule-based fallback catching velocity patterns in real time).
- The online feature store becomes a new availability dependency. Redis Cluster failure degrades to the rule-based fallback — acceptable, but must be monitored separately from model serving.
- Training pipeline must read features from the same feature store snapshots it wrote, or re-compute from the DW with the same logic, to avoid training/serving skew. Requires explicit snapshot versioning in the feature pipeline.

## Revisit if

The business requires fraud detection latency under 20 ms end-to-end (e.g., to compete with card-network-level scoring), which would make a 5 ms Redis lookup too expensive relative to the remaining budget and would force a fully embedded, in-process feature lookup with no network hop.
