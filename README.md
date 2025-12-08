# QuoteWatch

Real-time market microstructure ML system powered by Coinbase WebSocket data and Plotly Dash.

**Live Demo:** https://quotewatch-275631345026.us-central1.run.app

## Features

- Live BTC-USD order book stream from Coinbase WebSocket API
- Real-time feature extraction (spread, imbalance, depth, volatility)
- Online ML training with SGDClassifier (learns from live data)
- Price change prediction (Δ=500ms horizon, τ=0.01% threshold)
- Mobile-responsive dashboard with:
  - Price change probability indicator
  - OHLC candlestick chart
  - Model Insights panel (training progress, accuracy, feature weights)
- Cloud Run deployment

## Quick Start

```bash
# Create virtual environment
pyenv virtualenv 3.11 quotewatch
pyenv local quotewatch

# Install package
pip install -e .

# Run live dashboard
python -m src.run_live
open http://localhost:8050
```

## Development Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Linting/formatting
black .
ruff check .
mypy src/

# Tests
pytest -v
```

## Repo Layout

```
src/
  ingest/       # WebSocket client + order book cache
  features/     # Feature extraction + labeling
  model/        # OnlineClassifier (SGDClassifier)
  dashboard/    # Plotly Dash app
docs/           # Architecture, requirements, design docs
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for system diagrams.

**Data Flow:**
```
Coinbase WS → Order Book → Feature Extractor → Labeler (Δ=500ms) → SGDClassifier → Dashboard
                                                    ↓
                                          Feature Buffer (joins x_t with y_{t+Δ})
```

## ML Pipeline

The system uses online learning - the model trains continuously from live data:

1. **Feature Extraction**: Computes spread_bps, imbalance, depth, volatility from order book
2. **Labeling**: After 500ms, determines if mid-price changed >0.01%
3. **Training**: SGDClassifier.partial_fit() updates model incrementally
4. **Prediction**: Outputs probability of price change for current features
5. **Accuracy Tracking**: Predictions at time T matched with labels at T+500ms

## License

MIT License - see [LICENSE](LICENSE) for details.
