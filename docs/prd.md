# QuoteWatch - Product Requirements

## What is this?

This doc describes where I want QuoteWatch to end up. It's a portfolio project to help me land a quant role (ML Engineer, Quant Dev, Quant Researcher, etc).

The point isn't to build a real trading system. It's to have something concrete to talk about in interviews that shows I can actually do the job.

---

## Skills I Want to Demonstrate

This is the checklist. The project should hit all of these:

| Skill | What it means |
|-------|---------------|
| Real-time systems | Streaming data, async, low-latency thinking |
| Feature engineering | Building useful features from raw data |
| Classical ML | Trees, linear models, online learning |
| Deep learning | Neural nets, PyTorch, Transformers |
| Reinforcement learning | Sequential decisions, policy optimization |
| Backtesting | Testing on historical data without cheating |
| MLOps / Deployment | Model versioning, retraining, cloud deploy |
| Software engineering | Clean code, tests, docs, CI/CD |
| Math rigor | Right metrics, statistical thinking |
| Domain knowledge | Market microstructure, how trading works |

---

## The Big Picture

QuoteWatch is a system that:

1. Pulls live order book data from Coinbase
2. Computes features and predicts price movements (classical ML + Transformer)
3. Has an RL agent that learns to trade based on those predictions
4. Shows everything on a live dashboard

Basically: **streaming data -> features -> predictions -> trading decisions -> dashboard**

---

## Current Status

- Coinbase WebSocket for L2 order book (only keeping top 3 levels)
- 4 basic features: spread_bps, imbalance, depth, volatility
- SGDClassifier that trains online
- Dash dashboard that polls every 300ms
- Running on Google Cloud Run
- Simple rolling accuracy tracking


---

## Target

### Data

| Want | Why |
|------|-----|
| More depth (10-20 levels, not 3) | Better features, more signal |
| Trade data (matches channel) | Trade flow imbalance, aggressor detection |
| Save data to disk (Parquet or DB) | Backtesting, retraining |
| Replay historical data | Test models on past data |
| Multi-symbol (BTC + ETH) | Shows it's not hardcoded |

### Features

| Want | Why |
|------|-----|
| Keep current 4 | They work |
| Add lag features (t-1, t-5, t-10) | Temporal patterns |
| Trade flow features | Volume imbalance tells you something |
| Raw LOB as tensor | Feed to Transformer directly |
| Feature store | Don't recompute everything every time |

### Prediction Models

| Want | Why |
|------|-----|
| Keep SGD as baseline | Simple, online, something to compare against |
| Add Transformer | Deep learning checkbox, modern architecture |
| Multiple horizons (100ms, 500ms, 1s) | More interesting prediction task |
| Model registry (MLflow or whatever) | Version models, track experiments |
| Batch retraining pipeline | Not just online learning |

### RL Agent

| Want | Why |
|------|-----|
| Market simulator | Replay data, simulate fills |
| Realistic costs | Slippage, fees, market impact |
| State = market features + predictions + position | Everything the agent needs |
| Actions = buy/sell/hold | Start simple |
| Reward = PnL - costs - inventory penalty | Standard setup |
| PPO or SAC | Modern, stable algorithms |
| Benchmark against TWAP, buy-and-hold | Need something to compare to |

### Evaluation

| Want | Why |
|------|-----|
| Walk-forward backtesting | Proper out-of-sample testing |
| Prediction metrics: AUC, Brier, calibration | Not just accuracy |
| Trading metrics: Sharpe, drawdown | Standard quant metrics |
| Feature importance (SHAP) | Explain what's driving predictions |

### Dashboard

| Want | Why |
|------|-----|
| Keep current views | They're fine |
| Add model comparison (SGD vs Transformer) | Show the difference |
| Add RL view (equity curve, position, actions) | See the agent work |
| Backtest results | Show historical performance |

### Infrastructure

| Want | Why |
|------|-----|
| Keep Cloud Run | It works |
| Add model registry | Track versions |
| Add retraining job | Keep model fresh |
| More tests | Confidence in changes |

---

## Diagram

```mermaid
flowchart TB
    subgraph Data["Data Layer"]
        WS[Coinbase WebSocket]
        L2[L2 Order Book]
        Trades[Trades]
        WS --> L2
        WS --> Trades
    end

    subgraph Features["Feature Layer"]
        Spread[spread_bps]
        Imbalance[imbalance]
        Lag[lag features]
        TradeFlow[trade flow]
    end

    subgraph Predictions["Prediction Layer"]
        SGD[SGD Classifier<br/>online baseline]
        Transformer[Transformer<br/>batch trained]
    end

    subgraph RL["RL Layer"]
        Agent[PPO/SAC Agent]
        Actions[buy / sell / hold]
        Agent --> Actions
    end

    subgraph Dashboard["Dashboard"]
        Prices[prices]
        Preds[predictions]
        Compare[model comparison]
        Equity[RL equity curve]
    end

    subgraph Infra["Infrastructure"]
        CloudRun[Cloud Run]
        MLflow[MLflow]
        Tests[Tests]
        CICD[CI/CD]
    end

    Data --> Features
    Features --> Predictions
    Predictions --> RL

    Data --> Dashboard
    Predictions --> Dashboard
    RL --> Dashboard
```

---

## Features

Prediction stuff:

- See live predictions updating in real-time
- See which features matter most
- Compare SGD vs Transformer side-by-side
- Backtest models on historical data
- Retrain models when needed

RL stuff:

- Train an agent on historical data
- See the agent's equity curve and actions
- Compare agent vs baselines (TWAP, buy-and-hold)
- Try different RL algorithms

General:
- Code is clean enough that an interviewer would be impressed

---

## Skills Checklist

| Skill | How |
|-------|-----|
| Real-time systems | WebSocket streaming, async, live updates |
| Feature engineering | LOB features, lag features, trade flow |
| Classical ML | SGD baseline |
| Deep learning | Transformer on LOB sequences |
| RL | PPO/SAC trading agent |
| Backtesting | Walk-forward validation |
| MLOps | Cloud Run, MLflow, retraining pipeline |
| Software engineering | Tests, docs, clean code |
| Math rigor | Proper metrics, statistical tests |
| Domain knowledge | Microstructure, order flow, trading costs |