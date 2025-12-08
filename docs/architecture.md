# Architecture

This document describes the system architecture for QuoteWatch, a real-time market microstructure ML system.

## Context & Goals

QuoteWatch predicts short-term price changes (Δ=500ms) using L2 order book data from Coinbase. The system:

- Ingests real-time WebSocket data
- Extracts features from order book snapshots
- Trains an online ML model from live data
- Displays predictions via a polling dashboard
- Runs on Google Cloud Run

## 1. System Context

High-level view of system boundaries and external interactions.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         QuoteWatch System                            │
│                                                                      │
│  ┌──────────┐    ┌───────────┐    ┌─────────┐    ┌──────────────┐  │
│  │ WS Client │───►│Order Book │───►│Features │───►│   Labeler    │  │
│  └──────────┘    └───────────┘    │Extractor│    │  (Δ=500ms)   │  │
│       ▲                           └─────────┘    └──────┬───────┘  │
│       │                                │                 │          │
│       │                                ▼                 ▼          │
│       │                          ┌──────────┐    ┌──────────────┐  │
│       │                          │ Classifier│◄───│partial_fit() │  │
│       │                          │(SGD+Scaler)│   └──────────────┘  │
│       │                          └─────┬────┘                       │
│       │                                │                            │
│       │                                ▼                            │
│  ┌────┴─────┐                    ┌──────────┐    ┌──────────────┐  │
│  │ Coinbase │                    │  Shared  │◄───│   Dashboard  │◄──┤ User
│  │ WS API   │                    │  State   │    │  (Dash app)  │  │
│  └──────────┘                    └──────────┘    └──────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. Component Diagram

Internal modules and their responsibilities.

```
src/
├── ingest/
│   ├── websocket_client.py   # Coinbase WS connection, reconnection logic
│   └── order_book.py         # Thread-safe order book cache (top-3 levels)
│
├── features/
│   ├── extractor.py          # Computes spread_bps, imbalance, depth, volatility
│   ├── labeler.py            # Buffers samples, emits labels after Δ=500ms
│   └── stability.py          # Heuristic stability scorer (legacy fallback)
│
├── model/
│   └── classifier.py         # OnlineClassifier: SGDClassifier + StandardScaler
│                              # - partial_fit() for online learning
│                              # - record_prediction() for accuracy tracking
│
├── dashboard/
│   └── app.py                # Plotly Dash app
│                              # - Polls shared state at 300ms
│                              # - Renders prices, charts, model insights
│
└── run_live.py               # Main entry point / orchestrator
                               # - QuoteWatchRunner class
                               # - Wires all components together
```

## 3. Data Flow

Live tick to prediction and dashboard flow.

```
1. Coinbase WS sends L2 update
        │
        ▼
2. Order Book applies changes, updates top-3 bids/asks
        │
        ▼
3. Feature Extractor computes:
   - spread_bps: (ask - bid) / mid * 10000
   - imbalance: (bid_vol - ask_vol) / total_vol
   - depth: sum of bid + ask volumes
   - volatility: rolling std of mid-price changes
        │
        ▼
4. Classifier predicts P(price_change) for current features
        │
        ▼
5. Labeler buffers (timestamp, mid_price, features, prediction)
        │
        ▼
6. After Δ=500ms, Labeler emits LabeledSample with:
   - features from time T
   - label: 1 if |mid(T+Δ) - mid(T)| > τ, else 0
   - prediction_at_t: prediction made at time T
        │
        ▼
7. Classifier.partial_fit() updates model with new sample
        │
        ▼
8. Classifier.record_prediction() tracks accuracy
        │
        ▼
9. Shared state updated with prices, features, prediction, model stats
        │
        ▼
10. Dashboard polls every 300ms, renders latest state
```

## 4. ML Pipeline Details

### Label Definition

```
y(t) = 1 if |mid(t + Δ) - mid(t)| > τ
       0 otherwise

Where:
- Δ = 500ms (prediction horizon)
- τ = 0.01% of mid-price (threshold)
```

### Online Learning

The model trains continuously from live data:

1. **Feature vector**: `[spread_bps, imbalance, depth, volatility]`
2. **Scaler**: StandardScaler updated via `partial_fit()`
3. **Classifier**: SGDClassifier with `loss='log_loss'`
4. **Readiness**: Model "ready" after 100 samples of each class

### Accuracy Tracking

Predictions are temporally aligned with labels:
- At time T: make prediction, store with features
- At time T+Δ: label arrives, match with stored prediction
- Calculate rolling accuracy over last 100 predictions

## 5. Deployment

### Cloud Run (Current)

```
┌─────────────────────────────────────────┐
│           Google Cloud Run               │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │     Container: quotewatch           │ │
│  │                                     │ │
│  │  ┌─────────────┐  ┌──────────────┐ │ │
│  │  │ Gunicorn    │  │ WS Client    │ │ │
│  │  │ (Dash app)  │  │ (background) │ │ │
│  │  └─────────────┘  └──────────────┘ │ │
│  │         │                 │         │ │
│  │         └────────┬────────┘         │ │
│  │                  │                  │ │
│  │         ┌────────▼────────┐         │ │
│  │         │  Shared Memory  │         │ │
│  │         │  (in-process)   │         │ │
│  │         └─────────────────┘         │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
         │
         │ HTTPS
         ▼
    ┌─────────┐
    │  User   │
    │ Browser │
    └─────────┘
```

### Environment Variables

- `PORT`: HTTP port (default 8050, Cloud Run sets this)

### Deployment Command

```bash
gcloud run deploy quotewatch \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

## 6. State Machine

WebSocket client connection resilience.

```
[Init] ──start()──► [Connecting]
                         │
           ┌─────────────┼─────────────┐
           │             │             │
      onError/       onOpen +      timeout
      timeout        subscribe
           │             │             │
           ▼             ▼             │
      [Backoff] ◄── [Subscribed] ──────┘
           │             │
    delay elapsed   onMessage (l2update)
           │             │
           └──────► [Subscribed]
                         │
                      stop()
                         │
                         ▼
                      [Done]
```

## Future Improvements

- WebSocket-based dashboard (replace polling with push)
- Multi-symbol support (ETH-USD, SOL-USD)
- Parquet data persistence
- Offline training pipeline
- Model hot-reload
- Kubernetes deployment for horizontal scaling
