# Milestones

## Week 1 - Core Infrastructure

- [x] Repo setup (simplified - no docker-compose/Redis for MVP)
- [x] Coinbase WS ingest + order book cache
- [x] Feature tick extraction (spread_bps, imbalance, depth, volatility)
- [x] Dash MVP (polling at 300ms)
- [x] Cloud Run deployment
- [x] Heuristic stability indicator
- [x] OHLC candlestick chart
- [ ] Labeler (Δ=500ms) - #26
- [ ] Baseline model (SGDClassifier) - #27
- [ ] Online inference pipeline - #29
- [ ] ML prediction display - #28

## Week 2 - Polish & Extend

- [ ] Balanced-accuracy metric tracking
- [ ] Offline training script
- [ ] Model hot-reload
- [ ] ETH-USD support
- [ ] Architecture docs polish
- [ ] Unit tests for core components - #30
- [ ] Parquet data persistence

## Future Ideas

- WebSocket-based dashboard (real-time push)
- Model registry (MLflow integration)
- Grafana metrics dashboard
- Multi-symbol tabs in UI
- Kubernetes deployment
- Backtesting framework
- Custom domain (GoDaddy DNS)
