# System Requirements

## Business Objectives

QuoteWatch demonstrates real-time ML inference on market microstructure data:

- Showcase streaming feature engineering from L2 order book data
- Predict short-term quote stability for educational/research purposes
- Provide a visual dashboard for monitoring model performance
- Build a reusable pipeline for offline experimentation

## Functional Requirements

### Streaming

- [x] Connect to Coinbase WebSocket API (L2 channel)
- [x] Maintain in-memory order book with top-N levels
- [x] Handle reconnection with exponential backoff

### Feature Engineering

- [x] Extract features at configurable tick interval
- [x] Compute spread, mid-price, imbalance, volatility metrics
- [x] Buffer features for label alignment

### Labeling

- [x] Define quote-change label with configurable Δ (default 500ms)
- [x] Join features with delayed labels for training

### Model

- [x] Online inference with SGDClassifier
- [x] Incremental training via partial_fit()
- [x] Accuracy tracking with temporal alignment
- [ ] Support XGBoost (future)
- [ ] Hot-reload model artifacts without restart (future)

### Dashboard

- [x] Display live bid/ask prices
- [x] Show prediction probability with color gradient
- [x] Render OHLC candlestick chart
- [x] Poll backend at configurable interval (default 300ms)
- [x] Model Insights panel (training progress, accuracy, weights)
- [x] Mobile-responsive layout

### Storage

- [ ] Write features, labels, predictions to Parquet (future)
- [ ] Partition by date for efficient queries (future)

## Non-Functional Requirements

| Metric | Target | Status |
|--------|--------|--------|
| Feature tick latency | < 50ms p95 | ✓ |
| Inference latency | < 100ms p95 | ✓ |
| End-to-end latency | < 150ms p95 | ✓ |
| Dashboard refresh | 300ms | ✓ |
| Uptime (Cloud Run) | Best effort | ✓ |
| Data retention | 30 days | Pending |

## Out of Scope

- Real trading or order placement
- Multi-exchange support
- Sub-millisecond latency optimization
- Production-grade authentication/security
- Financial advice or signals

## Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Balanced accuracy | ≥ 0.55 | Tracking live |
| AUC-ROC | ≥ 0.58 | Future |
| Brier score | ≤ 0.25 | Future |
| Model reload time | < 5s | N/A (online learning) |
