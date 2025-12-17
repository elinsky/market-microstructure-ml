#!/usr/bin/env python3
"""Expire old Iceberg snapshots to reclaim storage.

This script expires snapshots older than a threshold and removes orphan files.
Run periodically (e.g., weekly via Cloud Scheduler) to prevent unbounded storage growth.

Usage:
    python scripts/expire_snapshots.py [--days 7] [--dry-run]

Environment variables:
    ICEBERG_CATALOG_URI: PostgreSQL connection string for Iceberg catalog
    ICEBERG_WAREHOUSE: Warehouse path (gs://... or file://...)
"""

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta

from src.storage.catalog import get_catalog
from src.storage.schemas import NAMESPACE

TABLE_NAMES = ["raw_orderbook", "raw_trades", "features", "predictions"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def expire_snapshots(days: int = 7, dry_run: bool = False) -> dict[str, int]:
    """Expire snapshots older than the specified number of days.

    Args:
        days: Number of days to retain snapshots. Older snapshots are expired.
        dry_run: If True, only log what would be done without making changes.

    Returns:
        Dictionary mapping table names to number of snapshots expired.
    """
    catalog = get_catalog()
    cutoff = datetime.now(UTC) - timedelta(days=days)
    cutoff_ms = int(cutoff.timestamp() * 1000)

    results = {}

    for table_name in TABLE_NAMES:
        table_id = f"{NAMESPACE}.{table_name}"
        try:
            table = catalog.load_table(table_id)
        except Exception as e:
            logger.warning(f"Could not load table {table_id}: {e}")
            results[table_name] = 0
            continue

        # Count snapshots before expiration
        snapshots_before = list(table.metadata.snapshots)
        old_snapshots = [s for s in snapshots_before if s.timestamp_ms < cutoff_ms]

        if not old_snapshots:
            logger.info(f"{table_name}: No snapshots older than {days} days")
            results[table_name] = 0
            continue

        if dry_run:
            logger.info(
                f"{table_name}: Would expire {len(old_snapshots)} snapshots "
                f"(keeping {len(snapshots_before) - len(old_snapshots)})"
            )
            results[table_name] = len(old_snapshots)
            continue

        # Expire old snapshots
        logger.info(
            f"{table_name}: Expiring {len(old_snapshots)} snapshots "
            f"older than {days} days..."
        )

        try:
            # PyIceberg's expire_snapshots API
            table.manage_snapshots().expire_snapshots_older_than(cutoff_ms).commit()
            results[table_name] = len(old_snapshots)
            logger.info(f"{table_name}: Expired {len(old_snapshots)} snapshots")
        except Exception as e:
            logger.error(f"{table_name}: Failed to expire snapshots: {e}")
            results[table_name] = 0

    return results


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Expire old Iceberg snapshots to reclaim storage."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to retain snapshots (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only log what would be done, don't make changes",
    )
    args = parser.parse_args()

    logger.info(f"Expiring snapshots older than {args.days} days")
    if args.dry_run:
        logger.info("DRY RUN MODE - no changes will be made")

    try:
        results = expire_snapshots(days=args.days, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Failed to expire snapshots: {e}")
        return 1

    total_expired = sum(results.values())
    logger.info(f"Total snapshots expired: {total_expired}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
