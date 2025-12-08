# System Requirements

## Business Objectives

QuoteWatch demonstrates real-time ML inference on market microstructure data:

- Showcase streaming feature engineering from L2 order book data
- Predict short-term quote stability for educational/research purposes
- Provide a visual dashboard for monitoring model performance
- Build a reusable pipeline for offline experimentation

## Functional Requirements

### Streaming

- [ ] Connect to Coinbase WebSocket API (L2 channel)
- [ ] Maintain in-memory order book with top-N levels
- [ ] Handle reconnection with exponential backoff

### Feature Engineering

- [ ] Extract features at configurable tick interval (default 100ms)
- [ ] Compute spread, mid-price, imbalance, volatility metrics
- [ ] Buffer features for label alignment

### Labeling

- [ ] Define quote-change label with configurable Δ (default 500ms)
- [ ] Join features with delayed labels for training

### Model

- [ ] Online inference with pre-trained model
- [ ] Support SGDClassifier and XGBoost
- [ ] Hot-reload model artifacts without restart

### Dashboard

- [ ] Display live bid/ask prices
- [ ] Show prediction probability and confidence
- [ ] Render sparkline of recent predictions
- [ ] Poll backend at configurable interval (default 300ms)

### Storage

- [ ] Write features, labels, predictions to Parquet
- [ ] Partition by date for efficient queries

## Non-Functional Requirements

| Metric | Target |
|--------|--------|
| Feature tick latency | < 50ms p95 |
| Inference latency | < 100ms p95 |
| End-to-end latency | < 150ms p95 |
| Dashboard refresh | 300ms |
| Uptime (local) | Best effort |
| Data retention | 30 days |

## Out of Scope

- Real trading or order placement
- Multi-exchange support
- Sub-millisecond latency optimization
- Production-grade authentication/security
- Financial advice or signals

## Success Metrics

| Metric | Target |
|--------|--------|
| Balanced accuracy | ≥ 0.55 |
| AUC-ROC | ≥ 0.58 |
| Brier score | ≤ 0.25 |
| Model reload time | < 5s |
