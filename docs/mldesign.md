# ML Design

Technical design document for the price change prediction model.

## Problem Statement

Predict whether the mid-price will change by more than a threshold within the next Δ milliseconds.

## Label Definition

```
y(t) = 1 if |mid(t + Δ) - mid(t)| > τ
       0 otherwise
```

Where:
- Δ = 500ms (prediction horizon)
- τ = 0.01% of mid-price (threshold)

## Feature List (Current Implementation)

| Feature | Formula | Description |
|---------|---------|-------------|
| `spread_bps` | `(ask - bid) / mid × 10000` | Spread in basis points |
| `imbalance` | `(bid_vol - ask_vol) / (bid_vol + ask_vol)` | Order book imbalance at top level (-1 to 1) |
| `depth` | `Σ bid_vol + Σ ask_vol` | Total volume at top-3 levels |
| `volatility` | `std(mid_price_changes)` | Rolling volatility of mid-price (bps) |

### Future Features (Not Yet Implemented)

| Feature | Description |
|---------|-------------|
| `price_velocity` | Mid-price change rate |
| `spread_volatility` | Rolling std of spread |
| `trade_imbalance` | Recent trade direction |

## Model

### Current: SGDClassifier (Online Learning)

Stochastic Gradient Descent with log-loss for online learning:

```python
SGDClassifier(
    loss="log_loss",
    learning_rate="constant",
    eta0=0.01,
    warm_start=True,
    random_state=42,
)
```

**Properties:**
- Online learning via `partial_fit()`
- Fast inference (~1ms)
- Interpretable coefficients (shown in dashboard)
- Trains continuously from live data

### Scaler: StandardScaler (Online)

Features are normalized using incremental StandardScaler:
- Updated via `partial_fit()` alongside model
- Maintains running mean and variance

### Model Readiness

Model is considered "ready" after:
- 100 samples of class 0 (no change)
- 100 samples of class 1 (price changed)

Before ready, model outputs 0.5 probability (uncertain).

## Accuracy Tracking

### Temporal Alignment Problem

Predictions are made at time T, but labels are only known at time T+Δ. Solution:

1. At time T: Make prediction, store it with features in Labeler buffer
2. At time T+Δ: Label computed, matched with stored prediction
3. Call `record_prediction(predicted, actual)` to track accuracy

### Rolling Accuracy

- Tracks last 100 (prediction, actual) pairs
- Accuracy = correct predictions / total predictions
- Displayed in Model Insights panel

## Evaluation Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Accuracy | > 50% (better than random) | Live tracking |
| Balanced Accuracy | ≥ 0.55 | Future |
| AUC-ROC | ≥ 0.58 | Future |
| Brier Score | ≤ 0.25 | Future |

## Class Balance

The Labeler naturally produces imbalanced classes:
- More "no change" (0) samples than "change" (1)
- Dashboard shows live class counts
- Future: class weights for SGDClassifier

## Training Pipeline (Current)

**Online Training** (no batch training needed):

1. WebSocket update arrives
2. Feature Extractor computes features from order book
3. Classifier predicts P(change) for current features
4. Labeler buffers sample with prediction
5. After Δ=500ms, Labeler emits labeled sample
6. Classifier.partial_fit() updates model
7. Classifier.record_prediction() tracks accuracy

## Future Improvements

- XGBoost for offline batch training
- Parquet data persistence for replay
- Balanced accuracy metric
- Class weights
- Model hot-reload from artifacts
- Feature importance analysis
