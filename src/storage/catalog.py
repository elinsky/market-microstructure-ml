"""Iceberg catalog configuration and factory function."""

import os

from pyiceberg.catalog.sql import SqlCatalog


def get_catalog(name: str = "default") -> SqlCatalog:
    """Load an Iceberg SQL catalog from environment variables.

    Environment variables:
        ICEBERG_CATALOG_URI: PostgreSQL connection string
            (e.g., postgresql+psycopg2://postgres:localdev@localhost:5432/iceberg)
        ICEBERG_WAREHOUSE: Warehouse path for table data
            (e.g., file://data/warehouse or gs://bucket/warehouse)

    Args:
        name: Catalog name identifier. Defaults to "default".

    Returns:
        Configured Iceberg SQL catalog.

    Raises:
        ValueError: If required environment variables are not set.
    """
    catalog_uri = os.environ.get("ICEBERG_CATALOG_URI")
    warehouse = os.environ.get("ICEBERG_WAREHOUSE")

    if not catalog_uri:
        raise ValueError("ICEBERG_CATALOG_URI environment variable is required")
    if not warehouse:
        raise ValueError("ICEBERG_WAREHOUSE environment variable is required")

    return SqlCatalog(
        name,
        uri=catalog_uri,
        warehouse=warehouse,
    )
