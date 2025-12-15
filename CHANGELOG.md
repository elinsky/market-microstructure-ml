# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2024-12-07

### Added
- Live BTC-USD order book stream from Coinbase WebSocket API
- Order book cache maintaining top-3 bid/ask levels
- Feature extraction: spread_bps, imbalance, depth, volatility
- Labeler with configurable Δ (500ms) and τ (0.01%) for price change labels
- OnlineClassifier using SGDClassifier with partial_fit for online learning
- Accuracy tracking with temporal alignment (predictions at T matched with labels at T+Δ)
- Plotly Dash dashboard with:
  - Price change probability indicator (color-coded)
  - Best bid/ask/mid price display
  - OHLC candlestick chart
  - Model Insights panel (training progress, class balance, accuracy, feature weights)
- Mobile-responsive CSS layout
- Cloud Run deployment
- Health check endpoint (/health)

### Technical Details
- SGDClassifier with log_loss, constant learning rate (0.01)
- StandardScaler for online feature normalization
- 100 samples per class minimum before model is "ready"
- Rolling accuracy over last 100 predictions
- Dashboard polls at 300ms interval

## [Unreleased]

### Changed
- Order book depth increased from 3 to 10 levels for richer market microstructure data

### Planned
- Unit tests for core components
- ETH-USD support
- Offline training pipeline
- Model hot-reload
- Parquet data persistence
- Balanced accuracy metric tracking
