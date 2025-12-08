# ML Design

Technical design document for the quote-stability prediction model.

## Problem Statement

Predict whether the mid-price will change by more than a threshold within the next $\Delta$ milliseconds.

## Label Definition

$$
y(t) = \begin{cases}
1 & \text{if } \left| \text{mid}(t + \Delta) - \text{mid}(t) \right| > \tau \\
0 & \text{otherwise}
\end{cases}
$$

Where:
- $\Delta = 500\text{ms}$ (prediction horizon)
- $\tau = 0.01\%$ of mid-price (threshold, configurable)

## Feature List

| Feature | Formula | Description |
|---------|---------|-------------|
| `spread` | $p_a^{(1)} - p_b^{(1)}$ | Best ask minus best bid |
| `spread_bps` | $\frac{\text{spread}}{\text{mid}} \times 10^4$ | Spread in basis points |
| `mid_price` | $\frac{p_b^{(1)} + p_a^{(1)}}{2}$ | Mid-price |
| `imbalance` | $\frac{V_b - V_a}{V_b + V_a}$ | Order book imbalance |
| `bid_depth_3` | $\sum_{i=1}^{3} v_b^{(i)}$ | Sum of top-3 bid volumes |
| `ask_depth_3` | $\sum_{i=1}^{3} v_a^{(i)}$ | Sum of top-3 ask volumes |
| `price_velocity` | $\frac{d(\text{mid})}{dt}$ | Mid-price change rate |
| `spread_volatility` | $\sigma(\text{spread})_n$ | Rolling std of spread |
| `trade_imbalance` | $\frac{V_{\text{buy}} - V_{\text{sell}}}{V_{\text{total}}}$ | Recent trade direction |

## Models

### Baseline: SGDClassifier

Stochastic Gradient Descent with log-loss:

$$
\mathcal{L}(\mathbf{w}) = -\frac{1}{N} \sum_{i=1}^{N} \left[ y_i \log(\hat{y}_i) + (1-y_i) \log(1-\hat{y}_i) \right] + \alpha \|\mathbf{w}\|_2^2
$$

- Online learning capable
- Fast inference (~1ms)
- Interpretable coefficients

### Production: XGBoost

Gradient boosted trees with:
- `max_depth` $= 4$
- `n_estimators` $= 100$
- `learning_rate` $= 0.1$

## Evaluation Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Balanced Accuracy | $\frac{1}{2}\left(\frac{TP}{P} + \frac{TN}{N}\right)$ | $\geq 0.55$ |
| AUC-ROC | $\int_0^1 \text{TPR}(t) \, d\text{FPR}(t)$ | $\geq 0.58$ |
| Brier Score | $\frac{1}{N}\sum_{i=1}^{N}(\hat{p}_i - y_i)^2$ | $\leq 0.25$ |

## Class Imbalance

Expected class distribution:
- $P(y=0) \approx 0.7$ (no change)
- $P(y=1) \approx 0.3$ (change)

Handled via:
- Class weights: $w_c = \frac{N}{2 \cdot N_c}$
- Balanced accuracy metric
- Stratified train/test splits

## Training Pipeline

1. Load features $\mathbf{X}$ and labels $\mathbf{y}$ from Parquet
2. Time-based split: $t < t_{\text{split}}$ for train
3. Fit scaler: $\tilde{x} = \frac{x - \mu}{\sigma}$
4. Train model with class weights
5. Evaluate on held-out test set
6. Deploy if metrics exceed threshold

## Model Artifacts

```
models/
  current.pkl          # Serialized model
  feature_spec.json    # Feature names + order
  scaler.pkl           # Fitted StandardScaler
  metrics.json         # Evaluation metrics
```

## Retraining Schedule

- **MVP**: Manual trigger
- **Future**: Daily cron with auto-deploy if $\text{AUC}_{\text{new}} > \text{AUC}_{\text{current}}$

## Inference Pipeline

1. Receive feature vector $\mathbf{x}(t)$ from tick buffer
2. Apply scaler: $\tilde{\mathbf{x}} = \frac{\mathbf{x} - \mu}{\sigma}$
3. Predict: $\hat{p} = P(y=1 | \tilde{\mathbf{x}})$
4. Publish to snapshot store
5. Log prediction to Parquet
