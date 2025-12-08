# QuoteWatch

Real-time quote-stability model powered by Coinbase WebSocket data and Plotly Dash.

## Features

- Live stream from Coinbase L2 order book
- Feature extraction + Δ=500ms quote-change prediction
- Online model training (SGD/XGBoost)
- Real-time dashboard (Dash)
- Parquet data lake + daily retrain pipeline

## Quick Start

```bash
docker-compose up -d
python -m src.run_live --symbol BTC-USD
open http://localhost:8050
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
