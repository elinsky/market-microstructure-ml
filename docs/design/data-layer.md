# Data Layer Enhancement - Design Doc

Epic: [#35](https://github.com/elinsky/market-microstructure-ml/issues/35)

## Overview

This doc covers the design for enhancing the data layer to:
- Add trade data (matches channel)
- Increase order book depth
- Persist data to Iceberg/Parquet
- Enable replay for backtesting and training

---

## 1. Current State Architecture

```mermaid
flowchart TB
    subgraph Coinbase["Coinbase Exchange"]
        WSFeed[WebSocket Feed]
    end

    subgraph Ingestion["Ingestion Layer"]
        WSClient[WebSocketClient]
        OB[OrderBook<br/>depth=10]
    end

    subgraph Features["Feature Layer"]
        FE[FeatureExtractor]
        Labeler[Labeler<br/>delta=500ms]
    end

    subgraph Model["Model Layer"]
        Classifier[OnlineClassifier<br/>SGDClassifier]
    end

    subgraph Presentation["Presentation Layer"]
        State[Shared State]
        Dashboard[Dash App]
    end

    WSFeed -->|level2_batch| WSClient
    WSClient -->|snapshot/update| OB
    OB -->|OrderBookSnapshot| FE
    FE -->|Features| Labeler
    FE -->|Features| Classifier
    Labeler -->|LabeledSample| Classifier
    Classifier -->|prediction, stats| State
    FE -->|features| State
    OB -->|prices| State
    State -->|poll 300ms| Dashboard
```

**Limitations:**
- Only L2 data, no trades
- Only top 10 levels kept
- All data in-memory, lost on restart
- No historical replay capability

---

## 2. Target State Architecture

```mermaid
flowchart TB
    subgraph Coinbase["Coinbase Exchange"]
        WSFeed[WebSocket Feed]
    end

    subgraph Ingestion["Ingestion Layer"]
        WSClient[WebSocketClient]
        OB[OrderBook<br/>depth=20]
        TB[TradeBuffer]
    end

    subgraph Persistence["Persistence Layer"]
        Writer[DataWriter<br/>batched]
        Iceberg[(Iceberg Tables<br/>Parquet)]
    end

    subgraph Features["Feature Layer"]
        FE[FeatureExtractor]
        Labeler[Labeler]
    end

    subgraph Model["Model Layer"]
        Classifier[OnlineClassifier]
    end

    subgraph Presentation["Presentation Layer"]
        State[Shared State]
        Dashboard[Dash App]
    end

    subgraph Replay["Replay Layer"]
        Reader[DataReader]
    end

    WSFeed -->|level2_batch| WSClient
    WSFeed -->|matches| WSClient
    WSClient -->|snapshot/update| OB
    WSClient -->|trade| TB

    OB -->|OrderBookSnapshot| Writer
    TB -->|Trade| Writer
    Writer -->|append| Iceberg

    OB -->|OrderBookSnapshot| FE
    TB -->|trades| FE
    FE -->|Features| Writer
    FE -->|Features| Labeler
    FE -->|Features| Classifier
    Labeler -->|LabeledSample| Classifier
    Labeler -->|LabeledSample| Writer

    Classifier -->|prediction, stats| State
    FE -->|features| State
    OB -->|prices| State
    State -->|poll 300ms| Dashboard

    Iceberg -->|read| Reader
    Reader -->|Iterator| FE
```

**What's new:**

- `matches` channel for trade data
- `TradeBuffer` to hold recent trades
- `DataWriter` for batched persistence
- Iceberg tables for storage
- `DataReader` for replay

---

## 3. Data Flow - Live Ingestion

Sequence of events when a message arrives:

```mermaid
sequenceDiagram
    participant CB as Coinbase WS
    participant WS as WebSocketClient
    participant OB as OrderBook
    participant TB as TradeBuffer
    participant FE as FeatureExtractor
    participant DW as DataWriter
    participant ICE as Iceberg

    CB->>WS: l2update message
    WS->>OB: apply_update()
    OB->>OB: update bids/asks
    WS->>FE: on_update callback
    FE->>OB: get_snapshot()
    OB-->>FE: OrderBookSnapshot
    FE->>FE: compute features
    FE->>DW: buffer(snapshot, features)

    Note over DW: Buffer fills up...

    DW->>ICE: append batch

    CB->>WS: match message
    WS->>TB: add_trade()
    WS->>DW: buffer(trade)
```

---

## 4. Data Flow - Replay

How replay works for backtesting:

```mermaid
sequenceDiagram
    participant DR as DataReader
    participant ICE as Iceberg
    participant FE as FeatureExtractor
    participant Model as Classifier
    participant Eval as Evaluator

    DR->>ICE: read_table("features")
    ICE-->>DR: Iterator[FeatureRow]

    loop For each row
        DR->>FE: yield features
        FE->>Model: predict(features)
        Model-->>Eval: prediction
        DR->>Eval: actual label
        Eval->>Eval: record accuracy
    end

    Eval-->>Eval: compute metrics
```

---

## 5. Data Model

### 5.1 Iceberg Tables

```mermaid
erDiagram
    RAW_ORDERBOOK {
        timestamp_ms bigint PK
        symbol string
        bids array
        asks array
        received_at timestamp
    }

    RAW_TRADES {
        trade_id string PK
        timestamp_ms bigint
        symbol string
        price decimal
        size decimal
        side string
        received_at timestamp
    }

    FEATURES {
        timestamp_ms bigint PK
        symbol string
        spread_bps float
        imbalance float
        depth float
        volatility float
        trade_imbalance float
    }

    PREDICTIONS {
        timestamp_ms bigint PK
        symbol string
        model_id string
        prediction int
        probability float
        label int
        labeled_at_ms bigint
    }
```

### 5.2 Table Details

**`raw_orderbook`**
| Column | Type | Description |
|--------|------|-------------|
| timestamp_ms | bigint | Exchange timestamp (ms since epoch) |
| symbol | string | Trading pair (e.g., "BTC-USD") |
| bids | array<struct<price: decimal, size: decimal>> | Top N bid levels |
| asks | array<struct<price: decimal, size: decimal>> | Top N ask levels |
| received_at | timestamp | When we received this update |

**`raw_trades`**
| Column | Type | Description |
|--------|------|-------------|
| trade_id | string | Coinbase trade ID |
| timestamp_ms | bigint | Trade execution time |
| symbol | string | Trading pair |
| price | decimal(18,8) | Execution price |
| size | decimal(18,8) | Trade size |
| side | string | "buy" or "sell" (taker side) |
| received_at | timestamp | When we received this |

**`features`**
| Column | Type | Description |
|--------|------|-------------|
| timestamp_ms | bigint | Feature computation time |
| symbol | string | Trading pair |
| spread_bps | float | Spread in basis points |
| imbalance | float | Bid/ask volume imbalance [-1, 1] |
| depth | float | Total volume top N levels |
| volatility | float | Rolling mid-price volatility |
| trade_imbalance | float | Buy vs sell volume imbalance |

**`predictions`**
| Column | Type | Description |
|--------|------|-------------|
| timestamp_ms | bigint | When prediction was made |
| symbol | string | Trading pair |
| model_id | string | Model version identifier |
| prediction | int | 0 or 1 |
| probability | float | P(price_change) |
| label | int | Actual outcome (filled later) |
| labeled_at_ms | bigint | When label was determined |

### 5.3 Partitioning

All tables partitioned by date:
```
data/
├── raw_orderbook/
│   ├── dt=2025-12-14/
│   │   └── *.parquet
│   └── dt=2025-12-15/
├── raw_trades/
│   └── ...
├── features/
│   └── ...
└── predictions/
    └── ...
```

---

## 6. Component Design

### 6.1 TradeBuffer

New class to hold recent trades (similar to OrderBook for L2):

```python
@dataclass
class Trade:
    trade_id: str
    timestamp_ms: int
    price: Decimal
    size: Decimal
    side: str  # "buy" or "sell"

class TradeBuffer:
    def __init__(self, max_trades: int = 1000):
        self._trades: deque[Trade] = deque(maxlen=max_trades)
        self._lock = threading.RLock()

    def add_trade(self, trade: Trade) -> None: ...
    def get_recent(self, n: int = 100) -> List[Trade]: ...
    def get_volume_imbalance(self, window_ms: int = 1000) -> float: ...
```

### 6.2 DataWriter

Batched writer with configurable flush triggers:

```python
class DataWriter:
    def __init__(
        self,
        catalog: Catalog,
        batch_size: int = 1000,
        flush_interval_sec: float = 10.0,
    ):
        self._buffers: Dict[str, List[dict]] = {
            "raw_orderbook": [],
            "raw_trades": [],
            "features": [],
            "predictions": [],
        }
        self._last_flush = time.time()
        self._lock = threading.RLock()

    def write_orderbook(self, snapshot: OrderBookSnapshot) -> None: ...
    def write_trade(self, trade: Trade) -> None: ...
    def write_features(self, features: Features, timestamp_ms: int) -> None: ...
    def write_prediction(self, pred: Prediction) -> None: ...

    def _maybe_flush(self) -> None:
        """Flush if batch_size reached or flush_interval elapsed."""
        ...

    def flush(self) -> None:
        """Force flush all buffers to Iceberg."""
        ...
```

### 6.3 DataReader

Simple iterator for replay:

```python
class DataReader:
    def __init__(self, catalog: Catalog):
        self._catalog = catalog

    def read_features(
        self,
        start_date: date,
        end_date: date,
        symbol: str = "BTC-USD",
    ) -> Iterator[FeatureRow]:
        """Yield feature rows in chronological order."""
        ...

    def read_orderbook(
        self,
        start_date: date,
        end_date: date,
        symbol: str = "BTC-USD",
    ) -> Iterator[OrderBookSnapshot]:
        """Yield order book snapshots in chronological order."""
        ...
```

---

## 7. Storage Configuration

We use **Postgres for the Iceberg catalog** in both dev and prod for consistency.

### 7.1 Local (Development)

Run Postgres via Docker:

```bash
docker run -d --name quotewatch-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=localdev \
  -e POSTGRES_DB=iceberg \
  postgres:16
```

```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog(
    "local",
    **{
        "type": "sql",
        "uri": "postgresql+psycopg2://postgres:localdev@localhost:5432/iceberg",
        "warehouse": "file://data/warehouse",
    }
)
```

### 7.2 GCS (Production)

```python
catalog = load_catalog(
    "prod",
    **{
        "type": "sql",
        "uri": "postgresql+psycopg2://user:pass@cloud-sql-host:5432/iceberg",
        "warehouse": "gs://quotewatch-data/warehouse",
    }
)
```

Configuration is driven by environment variables (`ICEBERG_CATALOG_URI`, `ICEBERG_WAREHOUSE`).

---

## 8. Open Questions

1. ~~**Exact depth?**~~ **Resolved:** 10 levels to start
2. **Retention policy?** How long to keep data? (Maybe 30 days to start)
3. **GCS bucket setup?** Need to create bucket, set up auth for Cloud Run
4. ~~**Catalog in prod?**~~ **Resolved:** Postgres everywhere (Docker locally, Cloud SQL in prod)

---

## 9. Implementation Order

**Note: We use TDD. Write tests first for each component.**

```
1. CI/CD foundation (GitHub Actions, pre-commit, branch protection)
2. Get test coverage to 90%+
3. Set up Iceberg catalog + table schemas (all 4 tables)
4. Increase order book depth to 10
5. Add matches channel + TradeBuffer
6. Implement DataWriter (raw_orderbook + raw_trades)
7. Implement DataWriter (features + predictions)
8. Wire writer into runner
9. Implement DataReader
10. Add GCS backend for prod
11. Update docs
```

### Rationale

| Step | Risk Mitigated | Value Delivered |
|------|----------------|-----------------|
| 1 | Broken code merging to main | Automated quality gates |
| 2 | Regressions, untested code paths | Confidence to refactor |
| 3 | Schema design issues caught early | Test fixtures, data model locked |
| 4-5 | Low risk changes | Richer data available for features |
| 6-7 | Writer bugs | Can persist all data types |
| 8 | Integration issues | Live data collection working |
| 9 | Reader bugs | Replay capability for backtesting |
| 10 | Cloud config issues | Production ready |

**Why CI/CD first?**
- Ensures all new code is automatically linted and tested
- Branch protection prevents merging broken code
- Coverage tracking keeps quality high as we add features

**Why schemas before implementation?**
- PyIceberg has quirks - validate catalog setup before building components that depend on it
- If schema is wrong (missing fields, wrong types), better to find out before implementing 5 components
- Enables writing integration tests against real schemas before implementing the writer

---

## 10. Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/ingest/trade_buffer.py` | Create | New TradeBuffer class |
| `src/ingest/websocket_client.py` | Modify | Add matches subscription |
| `src/ingest/order_book.py` | Modify | Increase depth parameter |
| `src/storage/__init__.py` | Create | New storage package |
| `src/storage/writer.py` | Create | DataWriter class |
| `src/storage/reader.py` | Create | DataReader class |
| `src/storage/catalog.py` | Create | Iceberg catalog setup |
| `src/storage/schemas.py` | Create | Table schema definitions |
| `src/run_live.py` | Modify | Wire up persistence |
| `tests/test_trade_buffer.py` | Create | Tests |
| `tests/test_writer.py` | Create | Tests |
| `tests/test_reader.py` | Create | Tests |

---

## 11. Implementation Progress

### Step 3: Iceberg Catalog + Table Schemas (Issue #41)

**Status:** Complete

**What was implemented:**

1. **Docker setup** (`docker-compose.yml`)
   - Postgres 16 container for Iceberg catalog
   - Health checks for reliable startup
   - Persistent volume for data

2. **Dependencies** (`pyproject.toml`)
   - `pyiceberg[sql-postgres]>=0.7.0`
   - `psycopg2-binary>=2.9`

3. **Storage package** (`src/storage/`)
   - `catalog.py`: Factory function loading from `ICEBERG_CATALOG_URI` and `ICEBERG_WAREHOUSE` env vars
   - `schemas.py`: All 4 table schemas with flattened column naming

4. **Table schemas implemented:**
   - `raw_orderbook`: 10 levels of bids/asks with `bid_N_price`, `bid_N_size` naming
   - `raw_trades`: trade_id, price, size, side with decimal(18,8) precision
   - `features`: spread_bps, imbalance, depth, volatility, trade_imbalance
   - `predictions`: model_id, prediction, probability, label, labeled_at_ms

5. **CI/CD** (`.github/workflows/ci.yml`)
   - Postgres 16 service container
   - Environment variables for catalog connection

6. **Integration tests** (`tests/storage/test_catalog.py`)
   - Catalog connectivity
   - Table creation and idempotency
   - Schema validation for all 4 tables

### Step 4: Increase Order Book Depth to 10 (Issue #44)

**Status:** Complete (PR #45)

**What was implemented:**

1. Changed default depth from 3 to 10 in `OrderBook.__init__()`
2. Updated `QuoteWatchRunner` to use `depth=10`
3. Updated all documentation referencing "top-3" to "top-10"

### Step 5: Add Matches Channel + TradeBuffer (Issue #46)

**Status:** Complete (PR #55)

**What was implemented:**

1. **Trade dataclass** (`src/ingest/trade_buffer.py`)
   - `trade_id`, `timestamp_ms`, `price`, `size`, `side`
   - Decimal precision for price/size

2. **TradeBuffer class** (`src/ingest/trade_buffer.py`)
   - Thread-safe deque with configurable `max_trades` (default 1000)
   - `add_trade()`, `get_recent()`, `get_trades_since()`, `clear()`
   - RLock for thread safety

3. **WebSocket client changes** (`src/ingest/websocket_client.py`)
   - Optional `trade_buffer` parameter
   - Optional `on_trade` callback
   - Subscribes to `matches` channel when trade_buffer is provided
   - Handles `match` message type
   - ISO8601 timestamp parsing to epoch milliseconds

4. **Exports** (`src/ingest/__init__.py`)
   - `Trade` and `TradeBuffer` now exported

5. **Tests**
   - 15 tests for TradeBuffer (add, get_recent, get_trades_since, max_trades, thread safety)
   - 6 tests for WebSocket match handling
