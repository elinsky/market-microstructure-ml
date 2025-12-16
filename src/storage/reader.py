"""DataReader for reading historical market data from Iceberg tables."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal

from pyiceberg.catalog import Catalog
from pyiceberg.expressions import And, EqualTo, GreaterThanOrEqual, LessThanOrEqual

from src.features.extractor import FeatureSnapshot
from src.ingest.order_book import OrderBookSnapshot
from src.ingest.trade_buffer import Trade
from src.model.classifier import Prediction
from src.storage.schemas import NAMESPACE, ORDER_BOOK_DEPTH


class DataReader:
    """Reader for historical market data from Iceberg tables.

    Provides iterator-based access to stored order book snapshots, trades,
    features, and predictions. All results are returned in chronological order.
    """

    def __init__(self, catalog: Catalog):
        """Initialize DataReader.

        Args:
            catalog: Iceberg catalog for table access.
        """
        self._catalog = catalog

    def read_features(
        self,
        start_date: date,
        end_date: date,
        symbol: str = "BTC-USD",
    ) -> Iterator[FeatureSnapshot]:
        """Read feature snapshots from storage.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
            symbol: Trading pair symbol to filter by.

        Yields:
            FeatureSnapshot objects in chronological order.
        """
        table = self._catalog.load_table(f"{NAMESPACE}.features")

        # Build filter expression
        row_filter = self._build_filter(start_date, end_date, symbol)

        # Scan and convert to Arrow table, then sort
        scan = table.scan(row_filter=row_filter)
        arrow_table = scan.to_arrow()

        # Sort by timestamp_ms
        if len(arrow_table) > 0:
            indices = arrow_table.column("timestamp_ms").to_pylist()
            sorted_indices = sorted(range(len(indices)), key=lambda i: indices[i])

            for idx in sorted_indices:
                row = {
                    col: arrow_table.column(col)[idx].as_py()
                    for col in arrow_table.column_names
                }
                yield self._row_to_feature_snapshot(row)

    def read_trades(
        self,
        start_date: date,
        end_date: date,
        symbol: str = "BTC-USD",
    ) -> Iterator[Trade]:
        """Read trades from storage.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
            symbol: Trading pair symbol to filter by.

        Yields:
            Trade objects in chronological order.
        """
        table = self._catalog.load_table(f"{NAMESPACE}.raw_trades")

        # Build filter expression
        row_filter = self._build_filter(start_date, end_date, symbol)

        # Scan and convert to Arrow table
        scan = table.scan(row_filter=row_filter)
        arrow_table = scan.to_arrow()

        # Sort by timestamp_ms
        if len(arrow_table) > 0:
            indices = arrow_table.column("timestamp_ms").to_pylist()
            sorted_indices = sorted(range(len(indices)), key=lambda i: indices[i])

            for idx in sorted_indices:
                row = {
                    col: arrow_table.column(col)[idx].as_py()
                    for col in arrow_table.column_names
                }
                yield self._row_to_trade(row)

    def read_orderbook(
        self,
        start_date: date,
        end_date: date,
        symbol: str = "BTC-USD",
    ) -> Iterator[OrderBookSnapshot]:
        """Read order book snapshots from storage.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
            symbol: Trading pair symbol to filter by.

        Yields:
            OrderBookSnapshot objects in chronological order.
        """
        table = self._catalog.load_table(f"{NAMESPACE}.raw_orderbook")

        # Build filter expression
        row_filter = self._build_filter(start_date, end_date, symbol)

        # Scan and convert to Arrow table
        scan = table.scan(row_filter=row_filter)
        arrow_table = scan.to_arrow()

        # Sort by timestamp_ms
        if len(arrow_table) > 0:
            indices = arrow_table.column("timestamp_ms").to_pylist()
            sorted_indices = sorted(range(len(indices)), key=lambda i: indices[i])

            for idx in sorted_indices:
                row = {
                    col: arrow_table.column(col)[idx].as_py()
                    for col in arrow_table.column_names
                }
                yield self._row_to_orderbook_snapshot(row)

    def read_predictions(
        self,
        start_date: date,
        end_date: date,
        symbol: str = "BTC-USD",
    ) -> Iterator[Prediction]:
        """Read predictions from storage.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
            symbol: Trading pair symbol to filter by.

        Yields:
            Prediction objects in chronological order.
        """
        table = self._catalog.load_table(f"{NAMESPACE}.predictions")

        # Build filter expression
        row_filter = self._build_filter(start_date, end_date, symbol)

        # Scan and convert to Arrow table
        scan = table.scan(row_filter=row_filter)
        arrow_table = scan.to_arrow()

        # Sort by timestamp_ms
        if len(arrow_table) > 0:
            indices = arrow_table.column("timestamp_ms").to_pylist()
            sorted_indices = sorted(range(len(indices)), key=lambda i: indices[i])

            for idx in sorted_indices:
                row = {
                    col: arrow_table.column(col)[idx].as_py()
                    for col in arrow_table.column_names
                }
                yield self._row_to_prediction(row)

    def _build_filter(self, start_date: date, end_date: date, symbol: str):
        """Build Iceberg filter expression for date range and symbol.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
            symbol: Symbol to filter by.

        Returns:
            Iceberg filter expression.
        """
        start_ts = self._date_to_timestamp_ms_start(start_date)
        end_ts = self._date_to_timestamp_ms_end(end_date)

        return And(
            And(
                GreaterThanOrEqual("timestamp_ms", start_ts),
                LessThanOrEqual("timestamp_ms", end_ts),
            ),
            EqualTo("symbol", symbol),
        )

    def _date_to_timestamp_ms_start(self, d: date) -> int:
        """Convert date to timestamp at start of day (00:00:00 UTC).

        Args:
            d: Date to convert.

        Returns:
            Milliseconds since Unix epoch for start of day.
        """
        dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=UTC)
        return int(dt.timestamp() * 1000)

    def _date_to_timestamp_ms_end(self, d: date) -> int:
        """Convert date to timestamp at end of day (23:59:59.999 UTC).

        Args:
            d: Date to convert.

        Returns:
            Milliseconds since Unix epoch for end of day.
        """
        dt = datetime(d.year, d.month, d.day, 23, 59, 59, 999000, tzinfo=UTC)
        return int(dt.timestamp() * 1000)

    def _row_to_feature_snapshot(self, row: dict) -> FeatureSnapshot:
        """Convert a row dict to FeatureSnapshot.

        Args:
            row: Dict with feature columns.

        Returns:
            FeatureSnapshot object.
        """
        return FeatureSnapshot(
            spread_bps=row["spread_bps"],
            imbalance=row["imbalance"],
            depth=row["depth"],
            volatility=row["volatility"],
            timestamp_ms=row["timestamp_ms"],
        )

    def _row_to_trade(self, row: dict) -> Trade:
        """Convert a row dict to Trade.

        Args:
            row: Dict with trade columns.

        Returns:
            Trade object.
        """
        return Trade(
            trade_id=row["trade_id"],
            timestamp_ms=row["timestamp_ms"],
            price=(
                Decimal(str(row["price"])) if row["price"] is not None else Decimal(0)
            ),
            size=Decimal(str(row["size"])) if row["size"] is not None else Decimal(0),
            side=row["side"],
        )

    def _row_to_orderbook_snapshot(self, row: dict) -> OrderBookSnapshot:
        """Convert a row dict to OrderBookSnapshot.

        Reconstructs bids/asks lists from flattened columns and computes
        derived fields (best_bid, best_ask, mid_price, spread).

        Args:
            row: Dict with flattened orderbook columns.

        Returns:
            OrderBookSnapshot object with computed fields.
        """
        # Reconstruct bids list from flattened columns
        bids: list[tuple[Decimal, Decimal]] = []
        for i in range(ORDER_BOOK_DEPTH):
            price = row.get(f"bid_{i}_price")
            size = row.get(f"bid_{i}_size")
            if price is not None and size is not None:
                bids.append((Decimal(str(price)), Decimal(str(size))))

        # Reconstruct asks list from flattened columns
        asks: list[tuple[Decimal, Decimal]] = []
        for i in range(ORDER_BOOK_DEPTH):
            price = row.get(f"ask_{i}_price")
            size = row.get(f"ask_{i}_size")
            if price is not None and size is not None:
                asks.append((Decimal(str(price)), Decimal(str(size))))

        # Compute derived fields
        best_bid = bids[0][0] if bids else None
        best_ask = asks[0][0] if asks else None

        mid_price = None
        spread = None
        if best_bid is not None and best_ask is not None:
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid

        return OrderBookSnapshot(
            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=mid_price,
            spread=spread,
            bids=bids,
            asks=asks,
            timestamp_ms=row["timestamp_ms"],
        )

    def _row_to_prediction(self, row: dict) -> Prediction:
        """Convert a row dict to Prediction.

        Args:
            row: Dict with prediction columns.

        Returns:
            Prediction object.
        """
        return Prediction(
            timestamp_ms=row["timestamp_ms"],
            prediction=row["prediction"],
            probability=row["probability"],
            label=row["label"],
            labeled_at_ms=row["labeled_at_ms"],
        )
