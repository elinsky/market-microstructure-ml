# Architecture

This document describes the system architecture for QuoteWatch, a real-time market microstructure ML system.

## Context & Goals

QuoteWatch predicts short-term quote stability (Δ=500ms) using L2 order book data from Coinbase. The system:

- Ingests real-time WebSocket data
- Extracts features at 100ms intervals
- Runs online inference with hot-reloadable models
- Displays predictions via a polling dashboard
- Persists all data to a Parquet lake for offline analysis

## 1. System Context

High-level view of system boundaries and external interactions.

```plantuml
@startuml
title QuoteWatch – System Context

actor User as U
rectangle "Coinbase WebSocket API" as EX_API
node "QuoteWatch System" as SYS {
  [WS Ingestor] as ING
  [Order Book Cache] as BOOK
  [Feature Tick / Labeler] as FL
  [Online Inference] as INF
  [Snapshot Publisher] as PUB
  [Dash UI] as UI
  database "Parquet Lake\n(raw / features / labels / predictions)" as LAKE
  [Offline Trainer] as TRN
  [Model Registry\n(artifact store)] as REG
}

U --> UI : View live dashboard\n(HTTP)
EX_API --> ING : L2 updates & trades (WS)
ING --> BOOK : normalized updates
BOOK --> FL : top-3 snapshots (100ms)
FL --> INF : x(t), labels (delayed)
INF --> PUB : p(change), metrics
PUB --> UI : latest snapshot (poll 300ms)
FL --> LAKE : write features/labels
INF --> LAKE : write predictions
LAKE --> TRN : batch training
TRN --> REG : model.pkl + metrics
REG --> INF : hot reload model

@enduml
```

## 2. Component Diagram

Internal boundaries and module responsibilities.

```plantuml
@startuml
title QuoteWatch – Component View

package "Ingestion" {
  [WS Client]
  [Normalizer]
  [Order Book Cache]
}

package "Feature & Label" {
  [Feature Tick]
  [Labeler (Δ=500ms)]
  [Feature Buffer]
}

package "Inference Service" {
  [Scaler]
  [Classifier (LR/XGB)]
  [Hot Reload Watcher]
  [Snapshot Publisher (Redis/HTTP)]
}

package "Storage" {
  database "Parquet Lake"
  [Model Registry (MLflow/S3 path)]
}

package "Presentation" {
  [Dash App]
}

' Connections
[WS Client] --> [Normalizer]
[Normalizer] --> [Order Book Cache]
[Order Book Cache] --> [Feature Tick]
[Feature Tick] --> [Feature Buffer]
[Order Book Cache] --> [Labeler (Δ=500ms)]
[Labeler (Δ=500ms)] --> [Feature Buffer] : join x(t-Δ)↔y(t-Δ)

[Feature Buffer] --> [Scaler]
[Scaler] --> [Classifier (LR/XGB)]
[Classifier (LR/XGB)] --> [Snapshot Publisher (Redis/HTTP)]
[Snapshot Publisher (Redis/HTTP)] --> [Dash App]

[Feature Tick] --> "Parquet Lake"
[Labeler (Δ=500ms)] --> "Parquet Lake"
[Classifier (LR/XGB)] --> "Parquet Lake" : predictions
[Model Registry (MLflow/S3 path)] --> [Hot Reload Watcher]
[Hot Reload Watcher] --> [Classifier (LR/XGB)]

@enduml
```

## 3. Sequence Diagram

Live tick to prediction and dashboard flow.

```plantuml
@startuml
title Live Tick → Prediction → Dashboard (Polling)

participant "Coinbase WS" as CB
participant "WS Client" as WS
participant "Book Cache" as BK
participant "Feature Tick" as FT
participant "Labeler Δ=500ms" as LB
participant "Inference" as INF
participant "Snapshot Publisher" as PUB
participant "Dash App (poll 300ms)" as UI

CB -> WS : l2update (WS)
WS -> BK : apply changes
FT -> BK : read top-3 (every 100ms)
BK --> FT : snapshot
FT -> FT : compute features x(t)
FT -> LB : enqueue (t, bid, ask)
LB -> LB : when t is Δ old, emit y(t)
LB --> INF : (x(t), y(t)) batch (optional online train)
FT --> INF : x(now)
INF -> INF : scale + predict p(change)
INF -> PUB : publish {prices, features*, p, metrics}
UI -> PUB : GET /latest (every 300ms)
PUB --> UI : JSON snapshot
UI -> UI : render KPI + sparkline

@enduml
```

## 4. Deployment Diagram

MVP single-host Docker Compose setup.

```plantuml
@startuml
title Deployment – MVP (single host)

node "Host (Linux/macOS)" {
  node "Docker" {
    node "container: redis:7" as REDIS

    node "container: inference" as INFER {
      component "WS Ingestor"
      component "Book Cache"
      component "Feature/Label"
      component "Model Inference"
      component "Publisher (Redis/HTTP)"
      folder "/data/lake" as DATA
    }

    node "container: dash-ui" as DASH {
      component "Plotly Dash Server"
    }
  }
}

cloud "Coinbase WS API" as CB

CB --> INFER : WebSocket
INFER --> REDIS : set latest snapshot
DASH --> REDIS : get latest snapshot
INFER --> DATA : write Parquet
note right of INFER
ENV:
  SYMBOLS=BTC-USD
  DELTA_MS=500
  TICK_MS=100
  MODEL_URI=/models/current.pkl
end note
@enduml
```

## 5. Activity Diagram

Offline training and hot reload workflow.

```plantuml
@startuml
title Offline Training & Hot Reload

start
:Load /features and /labels Parquet;
:Time-based split (train/test);
:Train baseline (LR) + XGB(d=4);
:Evaluate (balanced acc, AUC, Brier);
if (Metrics ≥ threshold?) then (yes)
  :Package artifact (model.pkl, feature_spec.json, metrics.json);
  :Upload to Model Registry (S3/MLflow);
  :Emit new version tag (qs-0.2.1);
  :Notify Inference (file watcher / REST ping);
  :Inference downloads artifact;
  :Warm-up sanity check (shadow eval optional);
  :Switch active model;
else (no)
  :Keep current model; log regression;
endif
stop
@enduml
```

## 6. State Machine

WebSocket client connection resilience.

```plantuml
@startuml
title WS Client – Connection States

[*] --> Init
Init --> Connecting : start()
Connecting --> Subscribed : onOpen + subscribe
Connecting --> Backoff : onError / timeout
Subscribed --> Subscribed : onMessage (l2update)
Subscribed --> Reconnecting : onClose / ping timeout
Reconnecting --> Backoff : fail connect
Backoff --> Connecting : jitter delay elapsed
Reconnecting --> Subscribed : onOpen + resubscribe
Subscribed --> [*] : stop()

@enduml
```

## Future Improvements

- WebSocket-based dashboard (replace polling with push)
- Multi-symbol support (ETH-USD, SOL-USD)
- Model registry integration (MLflow)
- Grafana metrics dashboard
- Kubernetes deployment for horizontal scaling
