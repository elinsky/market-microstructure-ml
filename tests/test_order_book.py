"""Tests for OrderBook."""

from decimal import Decimal

import pytest

from src.ingest.order_book import OrderBook


class TestOrderBook:
    """Tests for OrderBook class."""

    def test_empty_book(self):
        """Empty order book returns None for prices."""
        book = OrderBook(depth=3)
        snapshot = book.get_snapshot()

        assert snapshot.best_bid is None
        assert snapshot.best_ask is None
        assert snapshot.mid_price is None
        assert snapshot.spread is None
        assert snapshot.bids == []
        assert snapshot.asks == []

    def test_apply_snapshot(self):
        """Applying snapshot populates order book."""
        book = OrderBook(depth=3)
        book.apply_snapshot(
            bids=[["100.00", "1.0"], ["99.00", "2.0"], ["98.00", "3.0"]],
            asks=[["101.00", "1.5"], ["102.00", "2.5"], ["103.00", "3.5"]],
        )
        snapshot = book.get_snapshot()

        assert snapshot.best_bid == Decimal("100.00")
        assert snapshot.best_ask == Decimal("101.00")
        assert snapshot.mid_price == Decimal("100.50")
        assert snapshot.spread == Decimal("1.00")
        assert len(snapshot.bids) == 3
        assert len(snapshot.asks) == 3

    def test_apply_update_add(self):
        """Applying update adds new levels."""
        book = OrderBook(depth=3)
        book.apply_snapshot(
            bids=[["100.00", "1.0"]],
            asks=[["101.00", "1.0"]],
        )
        book.apply_update([["buy", "99.00", "2.0"]])
        snapshot = book.get_snapshot()

        assert len(snapshot.bids) == 2
        assert snapshot.bids[1] == (Decimal("99.00"), Decimal("2.0"))

    def test_apply_update_remove(self):
        """Applying update with zero size removes level."""
        book = OrderBook(depth=3)
        book.apply_snapshot(
            bids=[["100.00", "1.0"], ["99.00", "2.0"]],
            asks=[["101.00", "1.0"]],
        )
        book.apply_update([["buy", "99.00", "0"]])
        snapshot = book.get_snapshot()

        assert len(snapshot.bids) == 1
        assert snapshot.best_bid == Decimal("100.00")

    def test_depth_limit(self):
        """Order book respects depth limit."""
        book = OrderBook(depth=2)
        book.apply_snapshot(
            bids=[["100.00", "1.0"], ["99.00", "2.0"], ["98.00", "3.0"]],
            asks=[["101.00", "1.0"], ["102.00", "2.0"], ["103.00", "3.0"]],
        )
        snapshot = book.get_snapshot()

        assert len(snapshot.bids) == 2
        assert len(snapshot.asks) == 2

    def test_timestamp_stored(self):
        """Timestamp from update is stored."""
        book = OrderBook(depth=3)
        book.apply_snapshot(
            bids=[["100.00", "1.0"]],
            asks=[["101.00", "1.0"]],
        )
        book.apply_update([["buy", "99.00", "1.0"]], timestamp="2024-01-01T00:00:00Z")
        snapshot = book.get_snapshot()

        assert snapshot.timestamp == "2024-01-01T00:00:00Z"
