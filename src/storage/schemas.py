"""Iceberg table schema definitions for market data storage.

Schema conventions:
- Price/size columns use decimal(18,8) to match Coinbase string precision
- Timestamps use bigint (milliseconds since epoch) from exchange
- received_at uses timestamp for when we received the data
- Order book levels are flattened: bid_0_price, bid_0_size, bid_1_price, etc.
"""

from pyiceberg.catalog import Catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    DecimalType,
    FloatType,
    IntegerType,
    LongType,
    NestedField,
    StringType,
    TimestampType,
)

NAMESPACE = "quotewatch"
ORDER_BOOK_DEPTH = 10


def _build_orderbook_fields() -> list[NestedField]:
    """Build flattened order book schema fields for 10 levels of bids and asks."""
    fields: list[NestedField] = [
        NestedField(
            field_id=1, name="timestamp_ms", field_type=LongType(), required=True
        ),
        NestedField(field_id=2, name="symbol", field_type=StringType(), required=True),
    ]

    field_id = 3
    # Bid levels: bid_0_price, bid_0_size, bid_1_price, bid_1_size, ...
    for i in range(ORDER_BOOK_DEPTH):
        fields.append(
            NestedField(
                field_id=field_id,
                name=f"bid_{i}_price",
                field_type=DecimalType(precision=18, scale=8),
                required=False,
            )
        )
        field_id += 1
        fields.append(
            NestedField(
                field_id=field_id,
                name=f"bid_{i}_size",
                field_type=DecimalType(precision=18, scale=8),
                required=False,
            )
        )
        field_id += 1

    # Ask levels: ask_0_price, ask_0_size, ask_1_price, ask_1_size, ...
    for i in range(ORDER_BOOK_DEPTH):
        fields.append(
            NestedField(
                field_id=field_id,
                name=f"ask_{i}_price",
                field_type=DecimalType(precision=18, scale=8),
                required=False,
            )
        )
        field_id += 1
        fields.append(
            NestedField(
                field_id=field_id,
                name=f"ask_{i}_size",
                field_type=DecimalType(precision=18, scale=8),
                required=False,
            )
        )
        field_id += 1

    fields.append(
        NestedField(
            field_id=field_id,
            name="received_at",
            field_type=TimestampType(),
            required=True,
        )
    )

    return fields


RAW_ORDERBOOK_SCHEMA = Schema(*_build_orderbook_fields())

RAW_TRADES_SCHEMA = Schema(
    NestedField(field_id=1, name="trade_id", field_type=StringType(), required=True),
    NestedField(field_id=2, name="timestamp_ms", field_type=LongType(), required=True),
    NestedField(field_id=3, name="symbol", field_type=StringType(), required=True),
    NestedField(
        field_id=4,
        name="price",
        field_type=DecimalType(precision=18, scale=8),
        required=True,
    ),
    NestedField(
        field_id=5,
        name="size",
        field_type=DecimalType(precision=18, scale=8),
        required=True,
    ),
    NestedField(field_id=6, name="side", field_type=StringType(), required=True),
    NestedField(
        field_id=7, name="received_at", field_type=TimestampType(), required=True
    ),
)

FEATURES_SCHEMA = Schema(
    NestedField(field_id=1, name="timestamp_ms", field_type=LongType(), required=True),
    NestedField(field_id=2, name="symbol", field_type=StringType(), required=True),
    NestedField(field_id=3, name="spread_bps", field_type=FloatType(), required=False),
    NestedField(field_id=4, name="imbalance", field_type=FloatType(), required=False),
    NestedField(field_id=5, name="depth", field_type=FloatType(), required=False),
    NestedField(field_id=6, name="volatility", field_type=FloatType(), required=False),
    NestedField(
        field_id=7, name="trade_imbalance", field_type=FloatType(), required=False
    ),
)

PREDICTIONS_SCHEMA = Schema(
    NestedField(field_id=1, name="timestamp_ms", field_type=LongType(), required=True),
    NestedField(field_id=2, name="symbol", field_type=StringType(), required=True),
    NestedField(field_id=3, name="model_id", field_type=StringType(), required=True),
    NestedField(field_id=4, name="prediction", field_type=IntegerType(), required=True),
    NestedField(field_id=5, name="probability", field_type=FloatType(), required=True),
    NestedField(field_id=6, name="label", field_type=IntegerType(), required=False),
    NestedField(
        field_id=7, name="labeled_at_ms", field_type=LongType(), required=False
    ),
)


def create_tables(catalog: Catalog) -> None:
    """Create all Iceberg tables in the catalog.

    This function is idempotent - it will not fail if tables already exist.

    Args:
        catalog: Iceberg catalog to create tables in.
    """
    # Create namespace if it doesn't exist
    try:
        catalog.create_namespace(NAMESPACE)
    except Exception:
        # Namespace already exists
        pass

    table_schemas = {
        "raw_orderbook": RAW_ORDERBOOK_SCHEMA,
        "raw_trades": RAW_TRADES_SCHEMA,
        "features": FEATURES_SCHEMA,
        "predictions": PREDICTIONS_SCHEMA,
    }

    for table_name, schema in table_schemas.items():
        identifier = f"{NAMESPACE}.{table_name}"
        try:
            catalog.create_table(identifier=identifier, schema=schema)
        except Exception:
            # Table already exists
            pass
