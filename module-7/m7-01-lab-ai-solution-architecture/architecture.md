# Architecture — Scenario A: Real-Time Fraud Scoring

**Serving pattern:** Online synchronous inference, p95 ≤ 80 ms end-to-end.

```mermaid
flowchart TD
    subgraph Online["⚡ Online — p95 ≤ 80 ms request path"]
        PG[Payment Gateway]
        FSS[Fraud Scoring API\nREST, Go/Java]
        OFS[Online Feature Store\nRedis Cluster]
        MS[Model Server\nONNX Runtime]
        DE[Decision Engine\nthreshold rules]
    end

    subgraph Consumers["Downstream Consumers"]
        PP[Payment Processor]
        SA[Step-Up Auth Service]
    end

    subgraph Offline["Offline / Batch"]
        DW[(Data Warehouse\nraw transactions + labels)]
        FP[Feature Pipeline\nbatch ETL — hourly]
        TP[Training Pipeline\nscheduled]
        MR[Model Registry\nMLflow]
        MON[Monitoring & Drift Detector\nEvidentlyAI]
    end

    PG -->|"transaction request"| FSS
    FSS -->|"lookup: account_id, device_id"| OFS
    OFS -->|"account_history, device_fingerprint"| FSS
    FSS -->|"feature vector"| MS
    MS -->|"fraud_score: float [0,1]"| FSS
    FSS -->|"score + transaction_id"| DE
    DE -->|"allow → proceed"| PP
    DE -->|"step-up-auth signal"| SA
    DE -->|"block response"| PG

    DW -->|"raw event batch"| FP
    FP -->|"feature writes (hourly)"| OFS
    DW -->|"labeled dataset (fraud outcomes)"| TP
    TP -->|"model artifact + eval metrics"| MR
    MR -->|"promoted model binary"| MS
    MS -->|"inference logs (score, latency)"| DW
    PP -->|"outcome label (chargeback / cleared)"| DW
    MS -->|"score distribution samples"| MON
    MON -->|"drift signal → retrain trigger"| TP
```

## Serving Boundary

| Layer | What runs there |
|---|---|
| **Online** | Fraud Scoring API, Online Feature Store (Redis), Model Server (ONNX), Decision Engine |
| **Batch / Offline** | Feature ETL pipeline, Training pipeline, Model Registry, Monitoring |

## Feedback Loop

1. Payment Processor writes chargeback/cleared **outcome labels** back to the Data Warehouse.
2. Model Server streams **score distribution samples** to the Drift Detector.
3. Monitoring detects feature drift (PSI > 0.2) or label drift → emits **retrain trigger** to Training Pipeline.
4. Training Pipeline reads fresh labeled dataset from DW, trains, pushes artifact to Registry.
5. Registry promotes model → Model Server hot-reloads the binary without restart.
