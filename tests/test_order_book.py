"""Tests for OrderBook."""

from decimal import Decimal

from src.ingest.order_book import OrderBook


class TestOrderBook:
    """Tests for OrderBook class."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

    def make_empty_book(self, depth: int = 3) -> OrderBook:
        """Create an empty order book."""
        return OrderBook(depth=depth)

    def make_simple_bids(self) -> list[list[str]]:
        """Simple bid data: 3 levels at 100, 99, 98."""
        return [["100.00", "1.0"], ["99.00", "2.0"], ["98.00", "3.0"]]

    def make_simple_asks(self) -> list[list[str]]:
        """Simple ask data: 3 levels at 101, 102, 103."""
        return [["101.00", "1.5"], ["102.00", "2.5"], ["103.00", "3.5"]]

    def make_populated_book(self) -> OrderBook:
        """Create an order book populated with simple bids and asks."""
        book = self.make_empty_book()
        book.apply_snapshot(bids=self.make_simple_bids(), asks=self.make_simple_asks())
        return book

    # =========================================================================
    # Tests
    # =========================================================================

    def test_empty_book_returns_none_for_prices(self):
        """Empty order book returns None for all price fields."""
        # GIVEN an empty order book
        book = self.make_empty_book()

        # WHEN we get the snapshot
        snapshot = book.get_snapshot()

        # THEN all price fields are None and lists are empty
        assert snapshot.best_bid is None
        assert snapshot.best_ask is None
        assert snapshot.mid_price is None
        assert snapshot.spread is None
        assert snapshot.bids == []
        assert snapshot.asks == []

    def test_apply_snapshot_populates_book(self):
        """Applying snapshot populates order book with bids and asks."""
        # GIVEN an empty order book and bid/ask data
        book = self.make_empty_book()
        bids = self.make_simple_bids()
        asks = self.make_simple_asks()

        # WHEN we apply a snapshot
        book.apply_snapshot(bids=bids, asks=asks)

        # THEN the snapshot contains correct prices and levels
        snapshot = book.get_snapshot()
        assert snapshot.best_bid == Decimal("100.00")
        assert snapshot.best_ask == Decimal("101.00")
        assert snapshot.mid_price == Decimal("100.50")
        assert snapshot.spread == Decimal("1.00")
        assert len(snapshot.bids) == 3
        assert len(snapshot.asks) == 3

    def test_apply_update_adds_new_level(self):
        """Applying update with non-zero size adds a new price level."""
        # GIVEN a populated order book (bids at 100, 99, 98)
        book = self.make_populated_book()

        # WHEN we apply an update adding a new bid level at 97
        book.apply_update([["buy", "97.00", "4.0"]])

        # THEN the new level appears (but depth=3 limits visible levels)
        snapshot = book.get_snapshot()
        assert len(snapshot.bids) == 3
        assert snapshot.best_bid == Decimal("100.00")

    def test_apply_update_modifies_existing_level(self):
        """Applying update modifies size of existing price level."""
        # GIVEN a populated order book with bid at 100.00 = 1.0
        book = self.make_populated_book()

        # WHEN we apply an update changing the size at 100.00
        book.apply_update([["buy", "100.00", "5.0"]])

        # THEN the level is updated
        snapshot = book.get_snapshot()
        assert snapshot.bids[0] == (Decimal("100.00"), Decimal("5.0"))

    def test_apply_update_removes_level_when_size_zero(self):
        """Applying update with zero size removes the price level."""
        # GIVEN a populated order book with bid at 99.00
        book = self.make_populated_book()

        # WHEN we apply an update with zero size for that level
        book.apply_update([["buy", "99.00", "0"]])

        # THEN that level is removed
        snapshot = book.get_snapshot()
        assert len(snapshot.bids) == 2
        assert (Decimal("99.00"), Decimal("2.0")) not in snapshot.bids

    def test_snapshot_respects_depth_limit(self):
        """Order book respects configured depth limit."""
        # GIVEN an order book with depth=2 and 3 levels of data
        book = self.make_empty_book(depth=2)
        bids = self.make_simple_bids()  # 3 levels
        asks = self.make_simple_asks()  # 3 levels

        # WHEN we apply the snapshot
        book.apply_snapshot(bids=bids, asks=asks)

        # THEN only 2 levels are returned
        snapshot = book.get_snapshot()
        assert len(snapshot.bids) == 2
        assert len(snapshot.asks) == 2

    def test_apply_update_stores_timestamp(self):
        """Timestamp from update is stored in snapshot."""
        # GIVEN a populated order book
        book = self.make_populated_book()

        # WHEN we apply an update with a timestamp
        book.apply_update([["buy", "97.00", "1.0"]], timestamp="2024-01-01T00:00:00Z")

        # THEN the timestamp is stored in the snapshot
        snapshot = book.get_snapshot()
        assert snapshot.timestamp == "2024-01-01T00:00:00Z"
