"""Integration tests for Iceberg catalog and table schemas.

These tests require a running Postgres instance. In CI, this is provided
by the GitHub Actions service container. Locally, run:
    docker-compose up -d
"""

import os

import pytest

from src.storage.catalog import get_catalog
from src.storage.schemas import (
    NAMESPACE,
    ORDER_BOOK_DEPTH,
    create_tables,
)


@pytest.fixture(scope="module")
def catalog():
    """Provide catalog fixture, skip if Postgres not available."""
    if not os.environ.get("ICEBERG_CATALOG_URI"):
        pytest.skip("ICEBERG_CATALOG_URI not set - skipping integration tests")
    return get_catalog("test")


class TestGetCatalog:
    """Tests for the get_catalog factory function."""

    def test_get_catalog_raises_without_uri(self, monkeypatch):
        """get_catalog raises ValueError when ICEBERG_CATALOG_URI is not set."""
        # GIVEN environment without ICEBERG_CATALOG_URI
        monkeypatch.delenv("ICEBERG_CATALOG_URI", raising=False)
        monkeypatch.setenv("ICEBERG_WAREHOUSE", "file:///tmp/warehouse")

        # WHEN we call get_catalog
        # THEN it raises ValueError
        with pytest.raises(ValueError, match="ICEBERG_CATALOG_URI"):
            get_catalog()

    def test_get_catalog_raises_without_warehouse(self, monkeypatch):
        """get_catalog raises ValueError when ICEBERG_WAREHOUSE is not set."""
        # GIVEN environment without ICEBERG_WAREHOUSE
        monkeypatch.setenv(
            "ICEBERG_CATALOG_URI",
            "postgresql+psycopg2://postgres:localdev@localhost:5432/iceberg",
        )
        monkeypatch.delenv("ICEBERG_WAREHOUSE", raising=False)

        # WHEN we call get_catalog
        # THEN it raises ValueError
        with pytest.raises(ValueError, match="ICEBERG_WAREHOUSE"):
            get_catalog()

    def test_get_catalog_connects_to_postgres(self, catalog):
        """get_catalog successfully connects to Postgres."""
        # GIVEN a configured catalog
        # WHEN we list namespaces
        namespaces = catalog.list_namespaces()

        # THEN it returns a list (possibly empty)
        assert isinstance(namespaces, list)


class TestCreateTables:
    """Tests for table creation."""

    def test_create_tables_creates_namespace(self, catalog):
        """create_tables creates the quotewatch namespace."""
        # GIVEN a catalog
        # WHEN we create tables
        create_tables(catalog)

        # THEN the namespace exists
        namespaces = catalog.list_namespaces()
        assert (NAMESPACE,) in namespaces

    def test_create_tables_creates_all_four_tables(self, catalog):
        """create_tables creates raw_orderbook, raw_trades, features, predictions."""
        # GIVEN a catalog with tables created
        create_tables(catalog)

        # WHEN we list tables
        tables = catalog.list_tables(NAMESPACE)

        # THEN all four tables exist
        table_names = {t[1] for t in tables}
        assert "raw_orderbook" in table_names
        assert "raw_trades" in table_names
        assert "features" in table_names
        assert "predictions" in table_names

    def test_create_tables_is_idempotent(self, catalog):
        """create_tables can be called multiple times without error."""
        # GIVEN a catalog
        # WHEN we create tables twice
        create_tables(catalog)
        create_tables(catalog)

        # THEN no exception is raised and tables still exist
        tables = catalog.list_tables(NAMESPACE)
        assert len(tables) == 4


class TestRawOrderbookSchema:
    """Tests for raw_orderbook table schema."""

    def test_raw_orderbook_has_timestamp_ms(self, catalog):
        """raw_orderbook has timestamp_ms bigint column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.raw_orderbook")

        # THEN timestamp_ms field exists and is required
        field = table.schema().find_field("timestamp_ms")
        assert field is not None
        assert field.required is True
        assert str(field.field_type) == "long"

    def test_raw_orderbook_has_symbol(self, catalog):
        """raw_orderbook has symbol string column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.raw_orderbook")

        # THEN symbol field exists
        field = table.schema().find_field("symbol")
        assert field is not None
        assert str(field.field_type) == "string"

    def test_raw_orderbook_has_10_bid_levels(self, catalog):
        """raw_orderbook has bid_0 through bid_9 price and size columns."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.raw_orderbook")

        # THEN all 10 bid levels exist with decimal(18,8) type
        for i in range(ORDER_BOOK_DEPTH):
            price_field = table.schema().find_field(f"bid_{i}_price")
            size_field = table.schema().find_field(f"bid_{i}_size")
            assert price_field is not None, f"bid_{i}_price not found"
            assert size_field is not None, f"bid_{i}_size not found"
            assert "decimal(18, 8)" in str(price_field.field_type)
            assert "decimal(18, 8)" in str(size_field.field_type)

    def test_raw_orderbook_has_10_ask_levels(self, catalog):
        """raw_orderbook has ask_0 through ask_9 price and size columns."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.raw_orderbook")

        # THEN all 10 ask levels exist with decimal(18,8) type
        for i in range(ORDER_BOOK_DEPTH):
            price_field = table.schema().find_field(f"ask_{i}_price")
            size_field = table.schema().find_field(f"ask_{i}_size")
            assert price_field is not None, f"ask_{i}_price not found"
            assert size_field is not None, f"ask_{i}_size not found"
            assert "decimal(18, 8)" in str(price_field.field_type)
            assert "decimal(18, 8)" in str(size_field.field_type)

    def test_raw_orderbook_has_received_at(self, catalog):
        """raw_orderbook has received_at timestamp column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.raw_orderbook")

        # THEN received_at field exists
        field = table.schema().find_field("received_at")
        assert field is not None
        assert "timestamp" in str(field.field_type).lower()


class TestRawTradesSchema:
    """Tests for raw_trades table schema."""

    def test_raw_trades_has_trade_id(self, catalog):
        """raw_trades has trade_id string column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.raw_trades")

        # THEN trade_id field exists
        field = table.schema().find_field("trade_id")
        assert field is not None
        assert str(field.field_type) == "string"

    def test_raw_trades_has_price_decimal(self, catalog):
        """raw_trades has price decimal(18,8) column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.raw_trades")

        # THEN price field is decimal(18,8)
        field = table.schema().find_field("price")
        assert field is not None
        assert "decimal(18, 8)" in str(field.field_type)

    def test_raw_trades_has_size_decimal(self, catalog):
        """raw_trades has size decimal(18,8) column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.raw_trades")

        # THEN size field is decimal(18,8)
        field = table.schema().find_field("size")
        assert field is not None
        assert "decimal(18, 8)" in str(field.field_type)

    def test_raw_trades_has_side(self, catalog):
        """raw_trades has side string column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.raw_trades")

        # THEN side field exists
        field = table.schema().find_field("side")
        assert field is not None
        assert str(field.field_type) == "string"


class TestFeaturesSchema:
    """Tests for features table schema."""

    def test_features_has_all_feature_columns(self, catalog):
        """features has spread_bps, imbalance, depth, volatility, trade_imbalance."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.features")

        # THEN all feature columns exist as float
        for col in [
            "spread_bps",
            "imbalance",
            "depth",
            "volatility",
            "trade_imbalance",
        ]:
            field = table.schema().find_field(col)
            assert field is not None, f"{col} not found"
            assert str(field.field_type) == "float"


class TestPredictionsSchema:
    """Tests for predictions table schema."""

    def test_predictions_has_model_id(self, catalog):
        """predictions has model_id string column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.predictions")

        # THEN model_id field exists
        field = table.schema().find_field("model_id")
        assert field is not None
        assert str(field.field_type) == "string"

    def test_predictions_has_prediction_int(self, catalog):
        """predictions has prediction integer column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.predictions")

        # THEN prediction field is int
        field = table.schema().find_field("prediction")
        assert field is not None
        assert str(field.field_type) == "int"

    def test_predictions_has_probability_float(self, catalog):
        """predictions has probability float column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.predictions")

        # THEN probability field is float
        field = table.schema().find_field("probability")
        assert field is not None
        assert str(field.field_type) == "float"

    def test_predictions_has_label_nullable(self, catalog):
        """predictions has label as nullable integer."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.predictions")

        # THEN label field is optional
        field = table.schema().find_field("label")
        assert field is not None
        assert field.required is False

    def test_predictions_has_labeled_at_ms(self, catalog):
        """predictions has labeled_at_ms bigint column."""
        # GIVEN tables are created
        create_tables(catalog)

        # WHEN we load the table
        table = catalog.load_table(f"{NAMESPACE}.predictions")

        # THEN labeled_at_ms field exists
        field = table.schema().find_field("labeled_at_ms")
        assert field is not None
        assert str(field.field_type) == "long"
