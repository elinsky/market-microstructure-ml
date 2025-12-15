# ML Design

Technical design document for the price change prediction model.

## Problem Statement

Predict whether the mid-price will change by more than a threshold within the next $\Delta$ milliseconds.

## Label Definition

$$
y(t) = \begin{cases}
1 & \text{if } \left| p_{\text{mid}}(t + \Delta) - p_{\text{mid}}(t) \right| > \tau \\
0 & \text{otherwise}
\end{cases}
$$

Where:
- $\Delta = 500\text{ms}$ (prediction horizon)
- $\tau = 0.0001 \cdot p_{\text{mid}}$ (0.01% threshold)

## Feature List (Current Implementation)

| Feature | Formula | Description |
|---------|---------|-------------|
| `spread_bps` | $\frac{p_{\text{ask}} - p_{\text{bid}}}{p_{\text{mid}}} \times 10000$ | Spread in basis points |
| `imbalance` | $\frac{V_{\text{bid}} - V_{\text{ask}}}{V_{\text{bid}} + V_{\text{ask}}}$ | Order book imbalance at top level $\in [-1, 1]$ |
| `depth` | $\sum_{i=1}^{10} V_{\text{bid},i} + \sum_{i=1}^{10} V_{\text{ask},i}$ | Total volume at top-10 levels |
| `volatility` | $\sigma\left(\frac{\Delta p_{\text{mid}}}{p_{\text{mid}}}\right)$ | Rolling std of mid-price changes (bps) |

### Future Features (Not Yet Implemented)

| Feature | Description |
|---------|-------------|
| `price_velocity` | Mid-price change rate |
| `spread_volatility` | Rolling std of spread |
| `trade_imbalance` | Recent trade direction |

## Model

### Current: SGDClassifier (Online Learning)

Stochastic Gradient Descent with log-loss for online learning. The model minimizes:

$$
\mathcal{L}(\theta) = -\frac{1}{n} \sum_{i=1}^{n} \left[ y_i \log(\hat{y}_i) + (1 - y_i) \log(1 - \hat{y}_i) \right] + \alpha \|\theta\|_2^2
$$

Where $\hat{y}_i = \sigma(\theta^\top x_i)$ and $\sigma$ is the sigmoid function.

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

$$
x'_j = \frac{x_j - \mu_j}{\sigma_j}
$$

- Updated via `partial_fit()` alongside model
- Maintains running mean $\mu$ and variance $\sigma^2$

### Model Readiness

Model is considered "ready" after:
- $n_0 \geq 100$ samples of class 0 (no change)
- $n_1 \geq 100$ samples of class 1 (price changed)

Before the first training sample, model outputs $P(y=1) = 0.5$ (maximum uncertainty). After fitting begins, predictions are made even before reaching the readiness threshold.

## Accuracy Tracking

### Temporal Alignment Problem

Predictions are made at time $t$, but labels are only known at time $t + \Delta$. Solution:

1. At time $t$: Make prediction $\hat{y}(t)$, store it with features in Labeler buffer
2. At time $t + \Delta$: Label $y(t)$ computed, matched with stored prediction
3. Call `record_prediction(predicted, actual)` to track accuracy

### Rolling Accuracy

$$
\text{Accuracy} = \frac{1}{N} \sum_{i=1}^{N} \mathbf{1}[\hat{y}_i = y_i]
$$

- Tracks last $N = 100$ (prediction, actual) pairs
- Displayed in Model Insights panel

## Evaluation Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Accuracy | $> 0.50$ (better than random) | Live tracking |
| Balanced Accuracy | $\geq 0.55$ | Future |
| AUC-ROC | $\geq 0.58$ | Future |
| Brier Score | $\leq 0.25$ | Future |

## Class Balance

The Labeler naturally produces imbalanced classes:
- More "no change" (0) samples than "change" (1)
- Dashboard shows live class counts
- Future: class weights $w_c$ for SGDClassifier

## Training Pipeline (Current)

**Online Training** (no batch training needed):

1. WebSocket update arrives
2. Feature Extractor computes $x_t$ from order book
3. Classifier predicts $P(y=1 | x_t)$
4. Labeler buffers sample with prediction
5. After $\Delta = 500\text{ms}$, Labeler emits labeled sample $(x_t, y_t)$
6. `Classifier.partial_fit()` updates $\theta$
7. `Classifier.record_prediction()` tracks accuracy

## Future Improvements

- XGBoost for offline batch training
- Parquet data persistence for replay
- Balanced accuracy metric
- Class weights
- Model hot-reload from artifacts
- Feature importance analysis
