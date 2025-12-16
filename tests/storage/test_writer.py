"""Tests for DataWriter class.

Unit tests use mocks for the Iceberg catalog.
Integration tests (marked with pytest.mark.integration) require Postgres.
"""

import os
import threading
import time
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.ingest.order_book import OrderBookSnapshot
from src.ingest.trade_buffer import Trade
from src.storage.writer import DataWriter


class TestDataWriterInit:
    """Tests for DataWriter initialization."""

    def test_init_sets_default_values(self):
        """DataWriter initializes with default batch_size and flush_interval."""
        # GIVEN a mock catalog
        catalog = MagicMock()

        # WHEN we create a DataWriter
        writer = DataWriter(catalog)

        # THEN default values are set
        assert writer._batch_size == 1000
        assert writer._flush_interval_sec == 10.0
        assert writer._symbol == "BTC-USD"

    def test_init_accepts_custom_values(self):
        """DataWriter accepts custom batch_size, flush_interval, and symbol."""
        # GIVEN a mock catalog
        catalog = MagicMock()

        # WHEN we create a DataWriter with custom values
        writer = DataWriter(
            catalog,
            symbol="ETH-USD",
            batch_size=500,
            flush_interval_sec=5.0,
        )

        # THEN custom values are set
        assert writer._batch_size == 500
        assert writer._flush_interval_sec == 5.0
        assert writer._symbol == "ETH-USD"

    def test_init_creates_empty_buffers(self):
        """DataWriter initializes with empty buffers."""
        # GIVEN a mock catalog
        catalog = MagicMock()

        # WHEN we create a DataWriter
        writer = DataWriter(catalog)

        # THEN buffers are empty
        assert writer._orderbook_buffer == []
        assert writer._trades_buffer == []


class TestWriteOrderbook:
    """Tests for write_orderbook method."""

    def _make_snapshot(
        self,
        timestamp_ms: int = 1704110400000,
        num_levels: int = 3,
    ) -> OrderBookSnapshot:
        """Create a test OrderBookSnapshot."""
        bids = [
            (Decimal(f"{100 - i}.00"), Decimal(f"{i + 1}.0")) for i in range(num_levels)
        ]
        asks = [
            (Decimal(f"{101 + i}.00"), Decimal(f"{i + 1}.5")) for i in range(num_levels)
        ]
        return OrderBookSnapshot(
            best_bid=bids[0][0] if bids else None,
            best_ask=asks[0][0] if asks else None,
            mid_price=Decimal("100.50"),
            spread=Decimal("1.00"),
            bids=bids,
            asks=asks,
            timestamp="2024-01-01T12:00:00Z",
            timestamp_ms=timestamp_ms,
        )

    def test_write_orderbook_adds_to_buffer(self):
        """write_orderbook adds snapshot to buffer."""
        # GIVEN a DataWriter
        catalog = MagicMock()
        writer = DataWriter(catalog, batch_size=1000)

        # WHEN we write a snapshot
        snapshot = self._make_snapshot()
        writer.write_orderbook(snapshot)

        # THEN the buffer has one item
        assert len(writer._orderbook_buffer) == 1

    def test_write_orderbook_maps_snapshot_to_dict(self):
        """write_orderbook correctly maps snapshot fields to dict."""
        # GIVEN a DataWriter
        catalog = MagicMock()
        writer = DataWriter(catalog, symbol="BTC-USD", batch_size=1000)

        # WHEN we write a snapshot
        snapshot = self._make_snapshot(timestamp_ms=1704110400123, num_levels=2)
        writer.write_orderbook(snapshot)

        # THEN the dict has correct fields
        row = writer._orderbook_buffer[0]
        assert row["timestamp_ms"] == 1704110400123
        assert row["symbol"] == "BTC-USD"
        assert row["bid_0_price"] == Decimal("100.00")
        assert row["bid_0_size"] == Decimal("1.0")
        assert row["bid_1_price"] == Decimal("99.00")
        assert row["bid_1_size"] == Decimal("2.0")
        assert row["ask_0_price"] == Decimal("101.00")
        assert row["ask_0_size"] == Decimal("1.5")
        assert row["ask_1_price"] == Decimal("102.00")
        assert row["ask_1_size"] == Decimal("2.5")
        assert "received_at" in row

    def test_write_orderbook_pads_missing_levels_with_none(self):
        """write_orderbook fills missing levels with None."""
        # GIVEN a DataWriter
        catalog = MagicMock()
        writer = DataWriter(catalog, batch_size=1000)

        # WHEN we write a snapshot with only 2 levels
        snapshot = self._make_snapshot(num_levels=2)
        writer.write_orderbook(snapshot)

        # THEN levels 2-9 are None
        row = writer._orderbook_buffer[0]
        for i in range(2, 10):
            assert row[f"bid_{i}_price"] is None
            assert row[f"bid_{i}_size"] is None
            assert row[f"ask_{i}_price"] is None
            assert row[f"ask_{i}_size"] is None

    def test_write_orderbook_requires_timestamp_ms(self):
        """write_orderbook raises ValueError if timestamp_ms is None."""
        # GIVEN a DataWriter and snapshot without timestamp_ms
        catalog = MagicMock()
        writer = DataWriter(catalog)
        snapshot = OrderBookSnapshot(
            best_bid=Decimal("100"),
            best_ask=Decimal("101"),
            mid_price=Decimal("100.50"),
            spread=Decimal("1"),
            bids=[(Decimal("100"), Decimal("1"))],
            asks=[(Decimal("101"), Decimal("1"))],
            timestamp_ms=None,
        )

        # WHEN/THEN we get ValueError
        with pytest.raises(ValueError, match="timestamp_ms"):
            writer.write_orderbook(snapshot)


class TestWriteTrade:
    """Tests for write_trade method."""

    def _make_trade(
        self,
        trade_id: str = "12345",
        timestamp_ms: int = 1704110400000,
    ) -> Trade:
        """Create a test Trade."""
        return Trade(
            trade_id=trade_id,
            timestamp_ms=timestamp_ms,
            price=Decimal("100.50"),
            size=Decimal("0.5"),
            side="buy",
        )

    def test_write_trade_adds_to_buffer(self):
        """write_trade adds trade to buffer."""
        # GIVEN a DataWriter
        catalog = MagicMock()
        writer = DataWriter(catalog, batch_size=1000)

        # WHEN we write a trade
        trade = self._make_trade()
        writer.write_trade(trade)

        # THEN the buffer has one item
        assert len(writer._trades_buffer) == 1

    def test_write_trade_maps_trade_to_dict(self):
        """write_trade correctly maps trade fields to dict."""
        # GIVEN a DataWriter
        catalog = MagicMock()
        writer = DataWriter(catalog, symbol="BTC-USD", batch_size=1000)

        # WHEN we write a trade
        trade = self._make_trade(trade_id="abc123", timestamp_ms=1704110400456)
        writer.write_trade(trade)

        # THEN the dict has correct fields
        row = writer._trades_buffer[0]
        assert row["trade_id"] == "abc123"
        assert row["timestamp_ms"] == 1704110400456
        assert row["symbol"] == "BTC-USD"
        assert row["price"] == Decimal("100.50")
        assert row["size"] == Decimal("0.5")
        assert row["side"] == "buy"
        assert "received_at" in row


class TestFlushTriggers:
    """Tests for flush trigger logic."""

    def test_flush_triggered_by_batch_size(self):
        """Flush is triggered when batch_size is reached."""
        # GIVEN a DataWriter with batch_size=2
        catalog = MagicMock()
        writer = DataWriter(catalog, batch_size=2)

        # Mock the _flush method to track calls
        writer._flush = MagicMock()

        # WHEN we write 2 snapshots
        snapshot = TestWriteOrderbook()._make_snapshot()
        writer.write_orderbook(snapshot)
        assert writer._flush.call_count == 0  # Not yet

        writer.write_orderbook(snapshot)

        # THEN flush is called
        assert writer._flush.call_count == 1

    def test_flush_triggered_by_time_interval(self):
        """Flush is triggered when time interval is exceeded."""
        # GIVEN a DataWriter with short flush interval
        catalog = MagicMock()
        writer = DataWriter(catalog, batch_size=1000, flush_interval_sec=0.1)

        # Mock the _flush method
        writer._flush = MagicMock()

        # Write first snapshot
        snapshot = TestWriteOrderbook()._make_snapshot()
        writer.write_orderbook(snapshot)
        assert writer._flush.call_count == 0

        # WHEN we wait and write again
        time.sleep(0.15)
        writer.write_orderbook(snapshot)

        # THEN flush is triggered by time
        assert writer._flush.call_count == 1

    def test_flush_not_triggered_before_interval(self):
        """Flush is not triggered before time interval elapses."""
        # GIVEN a DataWriter with longer flush interval
        catalog = MagicMock()
        writer = DataWriter(catalog, batch_size=1000, flush_interval_sec=10.0)

        # Mock the _flush method
        writer._flush = MagicMock()

        # WHEN we write multiple snapshots quickly
        snapshot = TestWriteOrderbook()._make_snapshot()
        writer.write_orderbook(snapshot)
        writer.write_orderbook(snapshot)
        writer.write_orderbook(snapshot)

        # THEN flush is not called (batch_size=1000 not reached, time not elapsed)
        assert writer._flush.call_count == 0


class TestFlushAndClose:
    """Tests for flush and close methods."""

    def test_flush_clears_buffers(self):
        """flush() clears all buffers after writing."""
        # GIVEN a DataWriter with data in buffers
        catalog = MagicMock()
        writer = DataWriter(catalog, batch_size=1000)

        # Mock _write_to_table to avoid Iceberg interaction
        writer._write_to_table = MagicMock()

        snapshot = TestWriteOrderbook()._make_snapshot()
        trade = TestWriteTrade()._make_trade()
        writer.write_orderbook(snapshot)
        writer.write_trade(trade)

        # WHEN we flush
        writer.flush()

        # THEN buffers are empty
        assert writer._orderbook_buffer == []
        assert writer._trades_buffer == []

    def test_flush_updates_last_flush_time(self):
        """flush() updates the last flush timestamp."""
        # GIVEN a DataWriter
        catalog = MagicMock()
        writer = DataWriter(catalog, batch_size=1000)

        # Mock _write_to_table to avoid Iceberg interaction
        writer._write_to_table = MagicMock()

        old_flush_time = writer._last_flush

        # Small delay to ensure time difference
        time.sleep(0.01)

        # WHEN we flush
        snapshot = TestWriteOrderbook()._make_snapshot()
        writer.write_orderbook(snapshot)
        writer.flush()

        # THEN last_flush is updated
        assert writer._last_flush > old_flush_time

    def test_flush_does_nothing_when_buffers_empty(self):
        """flush() does not write when buffers are empty."""
        # GIVEN a DataWriter with empty buffers
        catalog = MagicMock()
        writer = DataWriter(catalog)

        # Mock _write_to_table to track calls
        writer._write_to_table = MagicMock()

        # WHEN we flush
        writer.flush()

        # THEN no write operations are called
        writer._write_to_table.assert_not_called()

    def test_close_flushes_remaining_data(self):
        """close() flushes any remaining buffered data."""
        # GIVEN a DataWriter with data in buffer
        catalog = MagicMock()
        writer = DataWriter(catalog, batch_size=1000)

        # Mock _write_to_table to track calls
        writer._write_to_table = MagicMock()

        snapshot = TestWriteOrderbook()._make_snapshot()
        writer.write_orderbook(snapshot)

        # WHEN we close
        writer.close()

        # THEN data is flushed
        assert writer._orderbook_buffer == []
        writer._write_to_table.assert_called()


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_writes_are_safe(self):
        """Concurrent writes from multiple threads don't corrupt data."""
        # GIVEN a DataWriter
        catalog = MagicMock()
        mock_table = MagicMock()
        catalog.load_table.return_value = mock_table

        writer = DataWriter(catalog, batch_size=10000)  # High batch to avoid flushes
        errors: list[Exception] = []
        write_count = 100

        def write_snapshots():
            try:
                for i in range(write_count):
                    snapshot = TestWriteOrderbook()._make_snapshot(
                        timestamp_ms=1704110400000 + i
                    )
                    writer.write_orderbook(snapshot)
            except Exception as e:
                errors.append(e)

        def write_trades():
            try:
                for i in range(write_count):
                    trade = TestWriteTrade()._make_trade(
                        trade_id=str(i), timestamp_ms=1704110400000 + i
                    )
                    writer.write_trade(trade)
            except Exception as e:
                errors.append(e)

        # WHEN we run concurrent writes
        threads = [
            threading.Thread(target=write_snapshots),
            threading.Thread(target=write_trades),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # THEN no errors and all data is in buffers
        assert errors == []
        assert len(writer._orderbook_buffer) == write_count
        assert len(writer._trades_buffer) == write_count


# =============================================================================
# Integration Tests (require Postgres)
# =============================================================================


@pytest.fixture(scope="module")
def catalog():
    """Provide catalog fixture, skip if Postgres not available."""
    if not os.environ.get("ICEBERG_CATALOG_URI"):
        pytest.skip("ICEBERG_CATALOG_URI not set - skipping integration tests")

    from src.storage.catalog import get_catalog
    from src.storage.schemas import create_tables

    cat = get_catalog("test_writer")
    create_tables(cat)
    return cat


class TestDataWriterIntegration:
    """Integration tests for DataWriter with real Iceberg tables."""

    def _make_snapshot(self, timestamp_ms: int = 1704110400000) -> OrderBookSnapshot:
        """Create a test OrderBookSnapshot."""
        bids = [(Decimal("100.00"), Decimal("1.0")), (Decimal("99.00"), Decimal("2.0"))]
        asks = [
            (Decimal("101.00"), Decimal("1.5")),
            (Decimal("102.00"), Decimal("2.5")),
        ]
        return OrderBookSnapshot(
            best_bid=bids[0][0],
            best_ask=asks[0][0],
            mid_price=Decimal("100.50"),
            spread=Decimal("1.00"),
            bids=bids,
            asks=asks,
            timestamp="2024-01-01T12:00:00Z",
            timestamp_ms=timestamp_ms,
        )

    def _make_trade(
        self, trade_id: str = "test123", timestamp_ms: int = 1704110400000
    ) -> Trade:
        """Create a test Trade."""
        return Trade(
            trade_id=trade_id,
            timestamp_ms=timestamp_ms,
            price=Decimal("100.50"),
            size=Decimal("0.5"),
            side="buy",
        )

    def test_write_orderbook_to_iceberg(self, catalog):
        """DataWriter successfully writes order book data to Iceberg."""
        # GIVEN a DataWriter with real catalog
        writer = DataWriter(catalog, symbol="BTC-USD", batch_size=1000)

        # WHEN we write and flush a snapshot
        snapshot = self._make_snapshot(timestamp_ms=1704110400001)
        writer.write_orderbook(snapshot)
        writer.flush()

        # THEN data exists in the table
        from src.storage.schemas import NAMESPACE

        table = catalog.load_table(f"{NAMESPACE}.raw_orderbook")
        df = table.scan().to_pandas()

        # Find our row by timestamp
        row = df[df["timestamp_ms"] == 1704110400001]
        assert len(row) >= 1
        assert row.iloc[0]["symbol"] == "BTC-USD"
        assert row.iloc[0]["bid_0_price"] == Decimal("100.00")

    def test_write_trade_to_iceberg(self, catalog):
        """DataWriter successfully writes trade data to Iceberg."""
        # GIVEN a DataWriter with real catalog
        writer = DataWriter(catalog, symbol="BTC-USD", batch_size=1000)

        # WHEN we write and flush a trade
        trade = self._make_trade(
            trade_id="integration_test_001", timestamp_ms=1704110400002
        )
        writer.write_trade(trade)
        writer.flush()

        # THEN data exists in the table
        from src.storage.schemas import NAMESPACE

        table = catalog.load_table(f"{NAMESPACE}.raw_trades")
        df = table.scan().to_pandas()

        # Find our row by trade_id
        row = df[df["trade_id"] == "integration_test_001"]
        assert len(row) >= 1
        assert row.iloc[0]["symbol"] == "BTC-USD"
        assert row.iloc[0]["price"] == Decimal("100.50")
        assert row.iloc[0]["side"] == "buy"

    def test_batch_flush_writes_multiple_rows(self, catalog):
        """DataWriter batch flush writes multiple rows at once."""
        # GIVEN a DataWriter with small batch size
        writer = DataWriter(catalog, symbol="BTC-USD", batch_size=3)

        # WHEN we write 3 snapshots (triggers flush)
        base_ts = 1704110500000
        for i in range(3):
            snapshot = self._make_snapshot(timestamp_ms=base_ts + i)
            writer.write_orderbook(snapshot)

        # THEN all 3 rows exist in table
        from src.storage.schemas import NAMESPACE

        table = catalog.load_table(f"{NAMESPACE}.raw_orderbook")
        df = table.scan().to_pandas()

        for i in range(3):
            assert (df["timestamp_ms"] == base_ts + i).any()
