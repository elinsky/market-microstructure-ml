"""Tests for DataReader class.

Unit tests use mocks for the Iceberg catalog.
Integration tests (marked with pytest.mark.integration) require Postgres.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pyarrow as pa
import pytest

from src.features.extractor import FeatureSnapshot
from src.ingest.order_book import OrderBookSnapshot
from src.ingest.trade_buffer import Trade
from src.model.classifier import Prediction
from src.storage.reader import DataReader


class TestDataReaderInit:
    """Tests for DataReader initialization."""

    def test_init_stores_catalog(self):
        """DataReader stores the catalog reference."""
        # GIVEN a mock catalog
        catalog = MagicMock()

        # WHEN we create a DataReader
        reader = DataReader(catalog)

        # THEN the catalog is stored
        assert reader._catalog is catalog


class TestReadFeatures:
    """Tests for read_features method."""

    def _make_mock_table(self, rows: list[dict]) -> MagicMock:
        """Create a mock Iceberg table that returns the given rows."""
        # Convert rows to PyArrow table
        if rows:
            arrow_table = pa.Table.from_pylist(rows)
        else:
            # Empty table with schema
            arrow_table = pa.table(
                {
                    "timestamp_ms": pa.array([], type=pa.int64()),
                    "symbol": pa.array([], type=pa.string()),
                    "spread_bps": pa.array([], type=pa.float32()),
                    "imbalance": pa.array([], type=pa.float32()),
                    "depth": pa.array([], type=pa.float32()),
                    "volatility": pa.array([], type=pa.float32()),
                    "trade_imbalance": pa.array([], type=pa.float32()),
                }
            )

        mock_table = MagicMock()
        mock_scan = MagicMock()
        mock_scan.to_arrow.return_value = arrow_table
        mock_table.scan.return_value = mock_scan
        return mock_table

    def test_read_features_returns_iterator(self):
        """read_features returns an iterator."""
        # GIVEN a DataReader with mock catalog
        catalog = MagicMock()
        catalog.load_table.return_value = self._make_mock_table([])
        reader = DataReader(catalog)

        # WHEN we call read_features
        result = reader.read_features(date(2024, 1, 1), date(2024, 1, 2))

        # THEN we get an iterator
        assert hasattr(result, "__iter__")
        assert hasattr(result, "__next__")

    def test_read_features_yields_feature_snapshots(self):
        """read_features yields FeatureSnapshot objects."""
        # GIVEN a DataReader with mock data
        catalog = MagicMock()
        rows = [
            {
                "timestamp_ms": 1704110400000,
                "symbol": "BTC-USD",
                "spread_bps": 10.5,
                "imbalance": 0.25,
                "depth": 5.0,
                "volatility": 1.2,
                "trade_imbalance": None,
            }
        ]
        catalog.load_table.return_value = self._make_mock_table(rows)
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_features(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get FeatureSnapshot objects
        assert len(results) == 1
        assert isinstance(results[0], FeatureSnapshot)
        assert results[0].timestamp_ms == 1704110400000
        assert results[0].spread_bps == 10.5
        assert results[0].imbalance == 0.25
        assert results[0].depth == 5.0
        assert results[0].volatility == 1.2

    def test_read_features_filters_by_symbol(self):
        """read_features passes symbol filter to scan."""
        # GIVEN a DataReader with mock catalog
        catalog = MagicMock()
        mock_table = self._make_mock_table([])
        catalog.load_table.return_value = mock_table
        reader = DataReader(catalog)

        # WHEN we call read_features with a symbol
        list(reader.read_features(date(2024, 1, 1), date(2024, 1, 2), symbol="ETH-USD"))

        # THEN the scan is called (filter verification happens at integration level)
        mock_table.scan.assert_called_once()

    def test_read_features_empty_table_returns_empty_iterator(self):
        """read_features with no data returns empty iterator."""
        # GIVEN a DataReader with empty table
        catalog = MagicMock()
        catalog.load_table.return_value = self._make_mock_table([])
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_features(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get empty list
        assert results == []

    def test_read_features_multiple_rows_in_order(self):
        """read_features yields multiple rows in timestamp order."""
        # GIVEN a DataReader with multiple rows (already sorted)
        catalog = MagicMock()
        rows = [
            {
                "timestamp_ms": 1704110400000,
                "symbol": "BTC-USD",
                "spread_bps": 10.0,
                "imbalance": 0.1,
                "depth": 5.0,
                "volatility": 1.0,
                "trade_imbalance": None,
            },
            {
                "timestamp_ms": 1704110401000,
                "symbol": "BTC-USD",
                "spread_bps": 11.0,
                "imbalance": 0.2,
                "depth": 6.0,
                "volatility": 1.1,
                "trade_imbalance": None,
            },
        ]
        catalog.load_table.return_value = self._make_mock_table(rows)
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_features(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get rows in order
        assert len(results) == 2
        assert results[0].timestamp_ms == 1704110400000
        assert results[1].timestamp_ms == 1704110401000


class TestReadTrades:
    """Tests for read_trades method."""

    def _make_mock_table(self, rows: list[dict]) -> MagicMock:
        """Create a mock Iceberg table that returns the given rows."""
        if rows:
            arrow_table = pa.Table.from_pylist(rows)
        else:
            arrow_table = pa.table(
                {
                    "trade_id": pa.array([], type=pa.string()),
                    "timestamp_ms": pa.array([], type=pa.int64()),
                    "symbol": pa.array([], type=pa.string()),
                    "price": pa.array([], type=pa.decimal128(18, 8)),
                    "size": pa.array([], type=pa.decimal128(18, 8)),
                    "side": pa.array([], type=pa.string()),
                    "received_at": pa.array([], type=pa.timestamp("us")),
                }
            )

        mock_table = MagicMock()
        mock_scan = MagicMock()
        mock_scan.to_arrow.return_value = arrow_table
        mock_table.scan.return_value = mock_scan
        return mock_table

    def test_read_trades_returns_iterator(self):
        """read_trades returns an iterator."""
        # GIVEN a DataReader with mock catalog
        catalog = MagicMock()
        catalog.load_table.return_value = self._make_mock_table([])
        reader = DataReader(catalog)

        # WHEN we call read_trades
        result = reader.read_trades(date(2024, 1, 1), date(2024, 1, 2))

        # THEN we get an iterator
        assert hasattr(result, "__iter__")
        assert hasattr(result, "__next__")

    def test_read_trades_yields_trade_objects(self):
        """read_trades yields Trade objects."""
        # GIVEN a DataReader with mock data
        catalog = MagicMock()
        rows = [
            {
                "trade_id": "abc123",
                "timestamp_ms": 1704110400000,
                "symbol": "BTC-USD",
                "price": Decimal("100.50"),
                "size": Decimal("0.5"),
                "side": "buy",
                "received_at": None,
            }
        ]
        catalog.load_table.return_value = self._make_mock_table(rows)
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_trades(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get Trade objects
        assert len(results) == 1
        assert isinstance(results[0], Trade)
        assert results[0].trade_id == "abc123"
        assert results[0].timestamp_ms == 1704110400000
        assert results[0].price == Decimal("100.50")
        assert results[0].size == Decimal("0.5")
        assert results[0].side == "buy"

    def test_read_trades_empty_table_returns_empty_iterator(self):
        """read_trades with no data returns empty iterator."""
        # GIVEN a DataReader with empty table
        catalog = MagicMock()
        catalog.load_table.return_value = self._make_mock_table([])
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_trades(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get empty list
        assert results == []


class TestReadOrderbook:
    """Tests for read_orderbook method."""

    def _make_mock_table(self, rows: list[dict]) -> MagicMock:
        """Create a mock Iceberg table that returns the given rows."""
        if rows:
            arrow_table = pa.Table.from_pylist(rows)
        else:
            # Build empty schema with all orderbook columns
            schema_dict = {
                "timestamp_ms": pa.array([], type=pa.int64()),
                "symbol": pa.array([], type=pa.string()),
            }
            for i in range(10):
                schema_dict[f"bid_{i}_price"] = pa.array([], type=pa.decimal128(18, 8))
                schema_dict[f"bid_{i}_size"] = pa.array([], type=pa.decimal128(18, 8))
                schema_dict[f"ask_{i}_price"] = pa.array([], type=pa.decimal128(18, 8))
                schema_dict[f"ask_{i}_size"] = pa.array([], type=pa.decimal128(18, 8))
            schema_dict["received_at"] = pa.array([], type=pa.timestamp("us"))
            arrow_table = pa.table(schema_dict)

        mock_table = MagicMock()
        mock_scan = MagicMock()
        mock_scan.to_arrow.return_value = arrow_table
        mock_table.scan.return_value = mock_scan
        return mock_table

    def _make_orderbook_row(
        self,
        timestamp_ms: int = 1704110400000,
        num_levels: int = 3,
    ) -> dict:
        """Create a test orderbook row with flattened columns."""
        row = {
            "timestamp_ms": timestamp_ms,
            "symbol": "BTC-USD",
            "received_at": None,
        }
        # Add bid levels
        for i in range(10):
            if i < num_levels:
                row[f"bid_{i}_price"] = Decimal(f"{100 - i}.00")
                row[f"bid_{i}_size"] = Decimal(f"{i + 1}.0")
            else:
                row[f"bid_{i}_price"] = None
                row[f"bid_{i}_size"] = None
        # Add ask levels
        for i in range(10):
            if i < num_levels:
                row[f"ask_{i}_price"] = Decimal(f"{101 + i}.00")
                row[f"ask_{i}_size"] = Decimal(f"{i + 1}.5")
            else:
                row[f"ask_{i}_price"] = None
                row[f"ask_{i}_size"] = None
        return row

    def test_read_orderbook_returns_iterator(self):
        """read_orderbook returns an iterator."""
        # GIVEN a DataReader with mock catalog
        catalog = MagicMock()
        catalog.load_table.return_value = self._make_mock_table([])
        reader = DataReader(catalog)

        # WHEN we call read_orderbook
        result = reader.read_orderbook(date(2024, 1, 1), date(2024, 1, 2))

        # THEN we get an iterator
        assert hasattr(result, "__iter__")
        assert hasattr(result, "__next__")

    def test_read_orderbook_yields_order_book_snapshots(self):
        """read_orderbook yields OrderBookSnapshot objects."""
        # GIVEN a DataReader with mock data
        catalog = MagicMock()
        rows = [self._make_orderbook_row(timestamp_ms=1704110400000, num_levels=2)]
        catalog.load_table.return_value = self._make_mock_table(rows)
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_orderbook(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get OrderBookSnapshot objects
        assert len(results) == 1
        assert isinstance(results[0], OrderBookSnapshot)
        assert results[0].timestamp_ms == 1704110400000

    def test_read_orderbook_reconstructs_bids_asks_lists(self):
        """read_orderbook reconstructs bids and asks from flattened columns."""
        # GIVEN a DataReader with mock data
        catalog = MagicMock()
        rows = [self._make_orderbook_row(num_levels=2)]
        catalog.load_table.return_value = self._make_mock_table(rows)
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_orderbook(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN bids and asks are reconstructed
        snapshot = results[0]
        assert len(snapshot.bids) == 2
        assert len(snapshot.asks) == 2
        assert snapshot.bids[0] == (Decimal("100.00"), Decimal("1.0"))
        assert snapshot.bids[1] == (Decimal("99.00"), Decimal("2.0"))
        assert snapshot.asks[0] == (Decimal("101.00"), Decimal("1.5"))
        assert snapshot.asks[1] == (Decimal("102.00"), Decimal("2.5"))

    def test_read_orderbook_computes_derived_fields(self):
        """read_orderbook computes best_bid, best_ask, mid_price, spread."""
        # GIVEN a DataReader with mock data
        catalog = MagicMock()
        rows = [self._make_orderbook_row(num_levels=2)]
        catalog.load_table.return_value = self._make_mock_table(rows)
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_orderbook(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN derived fields are computed
        snapshot = results[0]
        assert snapshot.best_bid == Decimal("100.00")
        assert snapshot.best_ask == Decimal("101.00")
        assert snapshot.mid_price == Decimal("100.50")
        assert snapshot.spread == Decimal("1.00")

    def test_read_orderbook_skips_none_levels(self):
        """read_orderbook only includes non-None levels in bids/asks."""
        # GIVEN a DataReader with partial levels (only 2 out of 10)
        catalog = MagicMock()
        rows = [self._make_orderbook_row(num_levels=2)]
        catalog.load_table.return_value = self._make_mock_table(rows)
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_orderbook(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN only non-None levels are included
        snapshot = results[0]
        assert len(snapshot.bids) == 2
        assert len(snapshot.asks) == 2

    def test_read_orderbook_empty_table_returns_empty_iterator(self):
        """read_orderbook with no data returns empty iterator."""
        # GIVEN a DataReader with empty table
        catalog = MagicMock()
        catalog.load_table.return_value = self._make_mock_table([])
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_orderbook(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get empty list
        assert results == []


class TestReadPredictions:
    """Tests for read_predictions method."""

    def _make_mock_table(self, rows: list[dict]) -> MagicMock:
        """Create a mock Iceberg table that returns the given rows."""
        if rows:
            arrow_table = pa.Table.from_pylist(rows)
        else:
            arrow_table = pa.table(
                {
                    "timestamp_ms": pa.array([], type=pa.int64()),
                    "symbol": pa.array([], type=pa.string()),
                    "model_id": pa.array([], type=pa.string()),
                    "prediction": pa.array([], type=pa.int32()),
                    "probability": pa.array([], type=pa.float32()),
                    "label": pa.array([], type=pa.int32()),
                    "labeled_at_ms": pa.array([], type=pa.int64()),
                }
            )

        mock_table = MagicMock()
        mock_scan = MagicMock()
        mock_scan.to_arrow.return_value = arrow_table
        mock_table.scan.return_value = mock_scan
        return mock_table

    def test_read_predictions_returns_iterator(self):
        """read_predictions returns an iterator."""
        # GIVEN a DataReader with mock catalog
        catalog = MagicMock()
        catalog.load_table.return_value = self._make_mock_table([])
        reader = DataReader(catalog)

        # WHEN we call read_predictions
        result = reader.read_predictions(date(2024, 1, 1), date(2024, 1, 2))

        # THEN we get an iterator
        assert hasattr(result, "__iter__")
        assert hasattr(result, "__next__")

    def test_read_predictions_yields_prediction_objects(self):
        """read_predictions yields Prediction objects."""
        # GIVEN a DataReader with mock data
        catalog = MagicMock()
        rows = [
            {
                "timestamp_ms": 1704110400000,
                "symbol": "BTC-USD",
                "model_id": "sgd-v1",
                "prediction": 1,
                "probability": 0.75,
                "label": 1,
                "labeled_at_ms": 1704110400500,
            }
        ]
        catalog.load_table.return_value = self._make_mock_table(rows)
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_predictions(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get Prediction objects
        assert len(results) == 1
        assert isinstance(results[0], Prediction)
        assert results[0].timestamp_ms == 1704110400000
        assert results[0].prediction == 1
        assert results[0].probability == 0.75
        assert results[0].label == 1
        assert results[0].labeled_at_ms == 1704110400500

    def test_read_predictions_handles_null_label(self):
        """read_predictions handles null label field."""
        # GIVEN a DataReader with prediction that has no label yet
        catalog = MagicMock()
        rows = [
            {
                "timestamp_ms": 1704110400000,
                "symbol": "BTC-USD",
                "model_id": "sgd-v1",
                "prediction": 1,
                "probability": 0.75,
                "label": None,
                "labeled_at_ms": None,
            }
        ]
        catalog.load_table.return_value = self._make_mock_table(rows)
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_predictions(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get Prediction with None values
        assert len(results) == 1
        assert results[0].label is None
        assert results[0].labeled_at_ms is None

    def test_read_predictions_empty_table_returns_empty_iterator(self):
        """read_predictions with no data returns empty iterator."""
        # GIVEN a DataReader with empty table
        catalog = MagicMock()
        catalog.load_table.return_value = self._make_mock_table([])
        reader = DataReader(catalog)

        # WHEN we iterate
        results = list(reader.read_predictions(date(2024, 1, 1), date(2024, 1, 2)))

        # THEN we get empty list
        assert results == []


class TestDateFiltering:
    """Tests for date range filtering logic."""

    def _make_mock_table(self, rows: list[dict]) -> MagicMock:
        """Create a mock Iceberg table."""
        if rows:
            arrow_table = pa.Table.from_pylist(rows)
        else:
            arrow_table = pa.table(
                {
                    "timestamp_ms": pa.array([], type=pa.int64()),
                    "symbol": pa.array([], type=pa.string()),
                    "spread_bps": pa.array([], type=pa.float32()),
                    "imbalance": pa.array([], type=pa.float32()),
                    "depth": pa.array([], type=pa.float32()),
                    "volatility": pa.array([], type=pa.float32()),
                    "trade_imbalance": pa.array([], type=pa.float32()),
                }
            )

        mock_table = MagicMock()
        mock_scan = MagicMock()
        mock_scan.to_arrow.return_value = arrow_table
        mock_table.scan.return_value = mock_scan
        return mock_table

    def test_date_to_timestamp_ms_start_of_day(self):
        """_date_to_timestamp_ms_start converts date to start of day."""
        # GIVEN a DataReader
        catalog = MagicMock()
        reader = DataReader(catalog)

        # WHEN we convert a date
        ts = reader._date_to_timestamp_ms_start(date(2024, 1, 1))

        # THEN we get start of day (midnight UTC)
        # 2024-01-01 00:00:00 UTC = 1704067200000 ms
        assert ts == 1704067200000

    def test_date_to_timestamp_ms_end_of_day(self):
        """_date_to_timestamp_ms_end converts date to end of day."""
        # GIVEN a DataReader
        catalog = MagicMock()
        reader = DataReader(catalog)

        # WHEN we convert a date
        ts = reader._date_to_timestamp_ms_end(date(2024, 1, 1))

        # THEN we get end of day (23:59:59.999 UTC)
        # 2024-01-01 23:59:59.999 UTC = 1704153599999 ms
        assert ts == 1704153599999


# =============================================================================
# Integration Tests (require Postgres)
# =============================================================================


@pytest.fixture(scope="module")
def catalog():
    """Provide catalog fixture, skip if Postgres not available."""
    import os

    if not os.environ.get("ICEBERG_CATALOG_URI"):
        pytest.skip("ICEBERG_CATALOG_URI not set - skipping integration tests")

    from src.storage.catalog import get_catalog
    from src.storage.schemas import create_tables

    cat = get_catalog("test_reader")
    create_tables(cat)
    return cat


@pytest.fixture(scope="module")
def seeded_catalog(catalog):
    """Seed the catalog with test data for reading."""
    from src.storage.writer import DataWriter

    writer = DataWriter(catalog, symbol="BTC-USD", model_id="sgd-v1", batch_size=100)

    # Write some test data with known timestamps
    # Use timestamp for 2024-01-15 12:00:00 UTC = 1705320000000
    base_ts = 1705320000000

    # Write orderbook snapshots
    for i in range(5):
        from src.ingest.order_book import OrderBookSnapshot

        snapshot = OrderBookSnapshot(
            best_bid=Decimal("100.00"),
            best_ask=Decimal("101.00"),
            mid_price=Decimal("100.50"),
            spread=Decimal("1.00"),
            bids=[(Decimal("100.00"), Decimal("1.0"))],
            asks=[(Decimal("101.00"), Decimal("1.5"))],
            timestamp_ms=base_ts + i * 1000,
        )
        writer.write_orderbook(snapshot)

    # Write trades
    for i in range(5):
        from src.ingest.trade_buffer import Trade

        trade = Trade(
            trade_id=f"integration_read_{i}",
            timestamp_ms=base_ts + i * 1000,
            price=Decimal("100.50"),
            size=Decimal("0.5"),
            side="buy" if i % 2 == 0 else "sell",
        )
        writer.write_trade(trade)

    # Write features
    for i in range(5):
        from src.features.extractor import FeatureSnapshot

        features = FeatureSnapshot(
            spread_bps=10.0 + i,
            imbalance=0.1 * i,
            depth=5.0 + i,
            volatility=1.0 + i * 0.1,
            timestamp_ms=base_ts + i * 1000,
        )
        writer.write_features(features)

    # Write predictions
    for i in range(5):
        from src.model.classifier import Prediction

        pred = Prediction(
            timestamp_ms=base_ts + i * 1000,
            prediction=i % 2,
            probability=0.5 + i * 0.05,
            label=i % 2,
            labeled_at_ms=base_ts + i * 1000 + 500,
        )
        writer.write_prediction(pred)

    writer.flush()

    return catalog


class TestDataReaderIntegration:
    """Integration tests for DataReader with real Iceberg tables."""

    def test_read_features_from_iceberg(self, seeded_catalog):
        """DataReader successfully reads features from Iceberg."""
        # GIVEN a DataReader with real catalog
        reader = DataReader(seeded_catalog)

        # WHEN we read features for the date range containing our test data
        results = list(
            reader.read_features(date(2024, 1, 15), date(2024, 1, 15), symbol="BTC-USD")
        )

        # THEN we get FeatureSnapshot objects
        assert len(results) >= 5
        assert all(isinstance(r, FeatureSnapshot) for r in results)
        # Results should be in chronological order
        timestamps = [r.timestamp_ms for r in results]
        assert timestamps == sorted(timestamps)

    def test_read_trades_from_iceberg(self, seeded_catalog):
        """DataReader successfully reads trades from Iceberg."""
        # GIVEN a DataReader with real catalog
        reader = DataReader(seeded_catalog)

        # WHEN we read trades
        results = list(
            reader.read_trades(date(2024, 1, 15), date(2024, 1, 15), symbol="BTC-USD")
        )

        # THEN we get Trade objects
        assert len(results) >= 5
        assert all(isinstance(r, Trade) for r in results)

    def test_read_orderbook_from_iceberg(self, seeded_catalog):
        """DataReader successfully reads orderbook from Iceberg."""
        # GIVEN a DataReader with real catalog
        reader = DataReader(seeded_catalog)

        # WHEN we read orderbook
        results = list(
            reader.read_orderbook(
                date(2024, 1, 15), date(2024, 1, 15), symbol="BTC-USD"
            )
        )

        # THEN we get OrderBookSnapshot objects with computed fields
        assert len(results) >= 5
        assert all(isinstance(r, OrderBookSnapshot) for r in results)
        # Check that derived fields are computed
        for r in results:
            assert r.best_bid is not None
            assert r.best_ask is not None
            assert r.mid_price is not None
            assert r.spread is not None

    def test_read_predictions_from_iceberg(self, seeded_catalog):
        """DataReader successfully reads predictions from Iceberg."""
        # GIVEN a DataReader with real catalog
        reader = DataReader(seeded_catalog)

        # WHEN we read predictions
        results = list(
            reader.read_predictions(
                date(2024, 1, 15), date(2024, 1, 15), symbol="BTC-USD"
            )
        )

        # THEN we get Prediction objects
        assert len(results) >= 5
        assert all(isinstance(r, Prediction) for r in results)

    def test_read_features_filters_by_date_range(self, seeded_catalog):
        """DataReader filters by date range correctly."""
        # GIVEN a DataReader with real catalog
        reader = DataReader(seeded_catalog)

        # WHEN we read with a date range that excludes our test data
        results = list(
            reader.read_features(date(2023, 1, 1), date(2023, 1, 2), symbol="BTC-USD")
        )

        # THEN we get no results (test data is from 2024-01-15)
        assert len(results) == 0

    def test_read_features_filters_by_symbol(self, seeded_catalog):
        """DataReader filters by symbol correctly."""
        # GIVEN a DataReader with real catalog
        reader = DataReader(seeded_catalog)

        # WHEN we read with a symbol that doesn't exist
        results = list(
            reader.read_features(
                date(2024, 1, 15), date(2024, 1, 15), symbol="DOGE-USD"
            )
        )

        # THEN we get no results
        assert len(results) == 0
