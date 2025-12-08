# QuoteWatch

Real-time quote-stability model powered by Coinbase WebSocket data and Plotly Dash.

**Live Demo:** https://quotewatch-b2ny4jhbrq-uc.a.run.app

## Features

- Live stream from Coinbase L2 order book
- Feature extraction + Δ=500ms quote-change prediction
- Online model training (SGD/XGBoost)
- Real-time dashboard (Dash)
- Parquet data lake + daily retrain pipeline

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
  ingest/       # WS client + order book cache
  features/     # 100ms tick feature extraction
  labels/       # Δ=500ms quote-change labeling
  models/       # inference + trainer
  dashboard/    # Dash app
data/           # parquet outputs
ops/            # infra & compose files
docs/           # architecture, requirements, design docs
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for detailed system diagrams including:
- System context
- Component boundaries
- Data flow (live + offline)
- Deployment topology

## License

MIT License - see [LICENSE](LICENSE) for details.
