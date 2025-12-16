"""DataWriter for buffering and persisting market data to Iceberg tables."""

import threading
import time
from datetime import UTC, datetime

import pyarrow as pa
from pyiceberg.catalog import Catalog

from src.features.extractor import FeatureSnapshot
from src.ingest.order_book import OrderBookSnapshot
from src.ingest.trade_buffer import Trade
from src.model.classifier import Prediction
from src.storage.schemas import NAMESPACE, ORDER_BOOK_DEPTH


class DataWriter:
    """Batched writer for persisting market data to Iceberg tables.

    Buffers order book snapshots and trades, flushing to Iceberg when either:
    - Buffer reaches batch_size
    - Time since last flush exceeds flush_interval_sec

    Thread-safe: all public methods can be called from multiple threads.
    """

    def __init__(
        self,
        catalog: Catalog,
        symbol: str = "BTC-USD",
        model_id: str = "sgd-v1",
        batch_size: int = 1000,
        flush_interval_sec: float = 10.0,
    ):
        """Initialize DataWriter.

        Args:
            catalog: Iceberg catalog for table access.
            symbol: Trading pair symbol (e.g., "BTC-USD").
            model_id: Model identifier for predictions (e.g., "sgd-v1").
            batch_size: Number of records before triggering flush.
            flush_interval_sec: Seconds between time-based flushes.
        """
        self._catalog = catalog
        self._symbol = symbol
        self._model_id = model_id
        self._batch_size = batch_size
        self._flush_interval_sec = flush_interval_sec

        self._orderbook_buffer: list[dict] = []
        self._trades_buffer: list[dict] = []
        self._features_buffer: list[dict] = []
        self._predictions_buffer: list[dict] = []
        self._last_flush = time.time()
        self._lock = threading.RLock()

    def write_orderbook(self, snapshot: OrderBookSnapshot) -> None:
        """Buffer an order book snapshot for writing.

        Args:
            snapshot: Order book snapshot to write.

        Raises:
            ValueError: If snapshot.timestamp_ms is None.
        """
        if snapshot.timestamp_ms is None:
            raise ValueError("snapshot.timestamp_ms is required for persistence")

        row = self._snapshot_to_dict(snapshot)

        with self._lock:
            self._orderbook_buffer.append(row)
            self._maybe_flush()

    def write_trade(self, trade: Trade) -> None:
        """Buffer a trade for writing.

        Args:
            trade: Trade to write.
        """
        row = self._trade_to_dict(trade)

        with self._lock:
            self._trades_buffer.append(row)
            self._maybe_flush()

    def write_features(self, features: FeatureSnapshot) -> None:
        """Buffer features for writing.

        Args:
            features: Feature snapshot to write.

        Raises:
            ValueError: If features.timestamp_ms is None.
        """
        if features.timestamp_ms is None:
            raise ValueError("features.timestamp_ms is required for persistence")

        row = self._features_to_dict(features)

        with self._lock:
            self._features_buffer.append(row)
            self._maybe_flush()

    def write_prediction(self, prediction: Prediction) -> None:
        """Buffer a prediction for writing.

        Args:
            prediction: Prediction to write.
        """
        row = self._prediction_to_dict(prediction)

        with self._lock:
            self._predictions_buffer.append(row)
            self._maybe_flush()

    def flush(self) -> None:
        """Force flush all buffers to Iceberg tables."""
        with self._lock:
            self._flush()

    def close(self) -> None:
        """Flush remaining data and clean up resources."""
        self.flush()

    def _maybe_flush(self) -> None:
        """Flush if batch_size reached or time interval exceeded.

        Must be called while holding self._lock.
        """
        # Check batch size trigger
        max_buffer_size = max(
            len(self._orderbook_buffer),
            len(self._trades_buffer),
            len(self._features_buffer),
            len(self._predictions_buffer),
        )
        if max_buffer_size >= self._batch_size:
            self._flush()
            return

        # Check time interval trigger
        elapsed = time.time() - self._last_flush
        if elapsed >= self._flush_interval_sec:
            has_data = (
                self._orderbook_buffer
                or self._trades_buffer
                or self._features_buffer
                or self._predictions_buffer
            )
            if has_data:
                self._flush()

    def _flush(self) -> None:
        """Actually write buffered data to Iceberg tables.

        Must be called while holding self._lock.
        """
        # Write orderbook data
        if self._orderbook_buffer:
            self._write_to_table("raw_orderbook", self._orderbook_buffer)
            self._orderbook_buffer = []

        # Write trades data
        if self._trades_buffer:
            self._write_to_table("raw_trades", self._trades_buffer)
            self._trades_buffer = []

        # Write features data
        if self._features_buffer:
            self._write_to_table("features", self._features_buffer)
            self._features_buffer = []

        # Write predictions data
        if self._predictions_buffer:
            self._write_to_table("predictions", self._predictions_buffer)
            self._predictions_buffer = []

        self._last_flush = time.time()

    def _write_to_table(self, table_name: str, rows: list[dict]) -> None:
        """Write rows to an Iceberg table.

        Args:
            table_name: Name of the table (without namespace).
            rows: List of row dictionaries to write.
        """
        table = self._catalog.load_table(f"{NAMESPACE}.{table_name}")

        # Convert to PyArrow table
        arrow_table = pa.Table.from_pylist(rows, schema=table.schema().as_arrow())

        # Append to Iceberg table
        table.append(arrow_table)

    def _snapshot_to_dict(self, snapshot: OrderBookSnapshot) -> dict:
        """Convert OrderBookSnapshot to flattened dict for Iceberg.

        Args:
            snapshot: Order book snapshot.

        Returns:
            Dict with flattened columns (bid_0_price, bid_0_size, etc.).
        """
        row: dict = {
            "timestamp_ms": snapshot.timestamp_ms,
            "symbol": self._symbol,
            "received_at": datetime.now(UTC),
        }

        # Add bid levels (pad with None if fewer than ORDER_BOOK_DEPTH)
        for i in range(ORDER_BOOK_DEPTH):
            if i < len(snapshot.bids):
                price, size = snapshot.bids[i]
                row[f"bid_{i}_price"] = price
                row[f"bid_{i}_size"] = size
            else:
                row[f"bid_{i}_price"] = None
                row[f"bid_{i}_size"] = None

        # Add ask levels (pad with None if fewer than ORDER_BOOK_DEPTH)
        for i in range(ORDER_BOOK_DEPTH):
            if i < len(snapshot.asks):
                price, size = snapshot.asks[i]
                row[f"ask_{i}_price"] = price
                row[f"ask_{i}_size"] = size
            else:
                row[f"ask_{i}_price"] = None
                row[f"ask_{i}_size"] = None

        return row

    def _trade_to_dict(self, trade: Trade) -> dict:
        """Convert Trade to dict for Iceberg.

        Args:
            trade: Trade object.

        Returns:
            Dict matching raw_trades schema.
        """
        return {
            "trade_id": trade.trade_id,
            "timestamp_ms": trade.timestamp_ms,
            "symbol": self._symbol,
            "price": trade.price,
            "size": trade.size,
            "side": trade.side,
            "received_at": datetime.now(UTC),
        }

    def _features_to_dict(self, features: FeatureSnapshot) -> dict:
        """Convert FeatureSnapshot to dict for Iceberg.

        Args:
            features: Feature snapshot.

        Returns:
            Dict matching features schema.
        """
        return {
            "timestamp_ms": features.timestamp_ms,
            "symbol": self._symbol,
            "spread_bps": features.spread_bps,
            "imbalance": features.imbalance,
            "depth": features.depth,
            "volatility": features.volatility,
            "trade_imbalance": None,  # Not implemented yet
        }

    def _prediction_to_dict(self, prediction: Prediction) -> dict:
        """Convert Prediction to dict for Iceberg.

        Args:
            prediction: Prediction object.

        Returns:
            Dict matching predictions schema.
        """
        return {
            "timestamp_ms": prediction.timestamp_ms,
            "symbol": self._symbol,
            "model_id": self._model_id,
            "prediction": prediction.prediction,
            "probability": prediction.probability,
            "label": prediction.label,
            "labeled_at_ms": prediction.labeled_at_ms,
        }
