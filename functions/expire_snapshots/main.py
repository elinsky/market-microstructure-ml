"""Cloud Function to expire old Iceberg snapshots.

Triggered weekly by Cloud Scheduler to prevent unbounded storage growth.
"""

import logging
import os
from datetime import UTC, datetime, timedelta

import functions_framework
from pyiceberg.catalog.sql import SqlCatalog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NAMESPACE = "quotewatch"
TABLE_NAMES = ["raw_orderbook", "raw_trades", "features", "predictions"]
RETENTION_DAYS = 30


def get_catalog() -> SqlCatalog:
    """Load Iceberg catalog from environment variables."""
    catalog_uri = os.environ.get("ICEBERG_CATALOG_URI")
    warehouse = os.environ.get("ICEBERG_WAREHOUSE")

    if not catalog_uri:
        raise ValueError("ICEBERG_CATALOG_URI environment variable is required")
    if not warehouse:
        raise ValueError("ICEBERG_WAREHOUSE environment variable is required")

    return SqlCatalog(
        "default",
        uri=catalog_uri,
        warehouse=warehouse,
    )


@functions_framework.http
def expire_snapshots(request):
    """HTTP Cloud Function to expire old Iceberg snapshots.

    Args:
        request: The request object (unused, but required by functions_framework).

    Returns:
        Tuple of (response body, status code).
    """
    logger.info(f"Starting snapshot expiration (retention: {RETENTION_DAYS} days)")

    try:
        catalog = get_catalog()
    except Exception as e:
        logger.error(f"Failed to connect to catalog: {e}")
        return f"Failed to connect to catalog: {e}", 500

    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    cutoff_ms = int(cutoff.timestamp() * 1000)

    results = {}

    for table_name in TABLE_NAMES:
        table_id = f"{NAMESPACE}.{table_name}"
        try:
            table = catalog.load_table(table_id)
        except Exception as e:
            logger.warning(f"Could not load table {table_id}: {e}")
            results[table_name] = {"status": "skipped", "reason": str(e)}
            continue

        # Count snapshots before expiration
        snapshots_before = list(table.metadata.snapshots)
        old_snapshots = [s for s in snapshots_before if s.timestamp_ms < cutoff_ms]

        if not old_snapshots:
            logger.info(f"{table_name}: No snapshots older than {RETENTION_DAYS} days")
            results[table_name] = {"status": "ok", "expired": 0}
            continue

        logger.info(
            f"{table_name}: Expiring {len(old_snapshots)} snapshots "
            f"older than {RETENTION_DAYS} days..."
        )

        try:
            table.manage_snapshots().expire_snapshots_older_than(cutoff_ms).commit()
            results[table_name] = {"status": "ok", "expired": len(old_snapshots)}
            logger.info(f"{table_name}: Expired {len(old_snapshots)} snapshots")
        except Exception as e:
            logger.error(f"{table_name}: Failed to expire snapshots: {e}")
            results[table_name] = {"status": "error", "reason": str(e)}

    total_expired = sum(
        r.get("expired", 0) for r in results.values() if isinstance(r, dict)
    )
    logger.info(f"Completed. Total snapshots expired: {total_expired}")

    return {"status": "ok", "results": results, "total_expired": total_expired}, 200
