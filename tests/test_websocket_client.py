"""Tests for CoinbaseWebSocketClient."""

import json

from src.ingest.order_book import OrderBook
from src.ingest.websocket_client import CoinbaseWebSocketClient


class TestCoinbaseWebSocketClient:
    """Tests for CoinbaseWebSocketClient.process_message."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

    def make_order_book(self, depth: int = 3) -> OrderBook:
        """Create an empty order book."""
        return OrderBook(depth=depth)

    def make_client(
        self, order_book: OrderBook | None = None, on_update=None
    ) -> CoinbaseWebSocketClient:
        """Create a WebSocket client with the given order book."""
        book = order_book or self.make_order_book()
        return CoinbaseWebSocketClient(book, symbol="BTC-USD", on_update=on_update)

    def make_snapshot_message(
        self,
        bids: list[list[str]] | None = None,
        asks: list[list[str]] | None = None,
    ) -> str:
        """Create a Coinbase snapshot message."""
        return json.dumps(
            {
                "type": "snapshot",
                "product_id": "BTC-USD",
                "bids": bids or [["100.00", "1.0"], ["99.00", "2.0"]],
                "asks": asks or [["101.00", "1.5"], ["102.00", "2.5"]],
            }
        )

    def make_l2update_message(
        self,
        changes: list[list[str]] | None = None,
        timestamp: str = "2024-01-01T00:00:00.000000Z",
    ) -> str:
        """Create a Coinbase l2update message."""
        return json.dumps(
            {
                "type": "l2update",
                "product_id": "BTC-USD",
                "time": timestamp,
                "changes": changes or [["buy", "100.00", "5.0"]],
            }
        )

    def make_subscriptions_message(self) -> str:
        """Create a Coinbase subscriptions confirmation message."""
        return json.dumps(
            {
                "type": "subscriptions",
                "channels": [{"name": "level2_batch", "product_ids": ["BTC-USD"]}],
            }
        )

    def make_error_message(self, error_msg: str = "Test error") -> str:
        """Create a Coinbase error message."""
        return json.dumps({"type": "error", "message": error_msg})

    # =========================================================================
    # Tests - Snapshot Messages
    # =========================================================================

    def test_snapshot_updates_order_book(self):
        """Snapshot message populates order book with bids and asks."""
        # GIVEN a client with an empty order book
        book = self.make_order_book()
        client = self.make_client(order_book=book)
        message = self.make_snapshot_message(
            bids=[["100.00", "1.0"]],
            asks=[["101.00", "2.0"]],
        )

        # WHEN we process a snapshot message
        client.process_message(message)

        # THEN order book is populated
        snapshot = book.get_snapshot()
        assert snapshot.best_bid is not None
        assert float(snapshot.best_bid) == 100.0
        assert float(snapshot.best_ask) == 101.0

    def test_snapshot_does_not_trigger_on_update(self):
        """Snapshot messages do not trigger the on_update callback."""
        # GIVEN a client with a callback tracker
        callback_count = {"count": 0}

        def on_update():
            callback_count["count"] += 1

        client = self.make_client(on_update=on_update)
        message = self.make_snapshot_message()

        # WHEN we process a snapshot message
        client.process_message(message)

        # THEN callback is not invoked
        assert callback_count["count"] == 0

    # =========================================================================
    # Tests - L2 Update Messages
    # =========================================================================

    def test_l2update_modifies_order_book(self):
        """L2 update message modifies existing order book."""
        # GIVEN a client with a populated order book
        book = self.make_order_book()
        client = self.make_client(order_book=book)
        client.process_message(self.make_snapshot_message(bids=[["100.00", "1.0"]]))

        # WHEN we process an l2update that changes the bid
        update_msg = self.make_l2update_message(changes=[["buy", "100.00", "5.0"]])
        client.process_message(update_msg)

        # THEN order book reflects the update
        snapshot = book.get_snapshot()
        assert snapshot.bids[0][1] == 5.0  # Size updated

    def test_l2update_triggers_on_update_callback(self):
        """L2 update messages trigger the on_update callback."""
        # GIVEN a client with a callback tracker
        callback_count = {"count": 0}

        def on_update():
            callback_count["count"] += 1

        client = self.make_client(on_update=on_update)
        message = self.make_l2update_message()

        # WHEN we process an l2update message
        client.process_message(message)

        # THEN callback is invoked
        assert callback_count["count"] == 1

    def test_l2update_stores_timestamp(self):
        """L2 update message stores timestamp in order book."""
        # GIVEN a client with an order book
        book = self.make_order_book()
        client = self.make_client(order_book=book)
        timestamp = "2024-01-15T12:30:45.123456Z"
        message = self.make_l2update_message(timestamp=timestamp)

        # WHEN we process an l2update message
        client.process_message(message)

        # THEN timestamp is stored
        snapshot = book.get_snapshot()
        assert snapshot.timestamp == timestamp

    # =========================================================================
    # Tests - Other Message Types
    # =========================================================================

    def test_subscriptions_message_is_handled(self):
        """Subscriptions message is handled without error."""
        # GIVEN a client
        client = self.make_client()
        message = self.make_subscriptions_message()

        # WHEN we process a subscriptions message
        client.process_message(message)

        # THEN no exception is raised (implicit assertion)

    def test_error_message_is_handled(self):
        """Error message is handled without raising exception."""
        # GIVEN a client
        client = self.make_client()
        message = self.make_error_message("Something went wrong")

        # WHEN we process an error message
        client.process_message(message)

        # THEN no exception is raised (implicit assertion)

    def test_unknown_message_type_is_ignored(self):
        """Unknown message types are silently ignored."""
        # GIVEN a client
        client = self.make_client()
        message = json.dumps({"type": "unknown_type", "data": "whatever"})

        # WHEN we process an unknown message type
        client.process_message(message)

        # THEN no exception is raised (implicit assertion)

    # =========================================================================
    # Tests - Error Handling
    # =========================================================================

    def test_invalid_json_is_handled(self):
        """Invalid JSON does not raise exception."""
        # GIVEN a client
        client = self.make_client()

        # WHEN we process invalid JSON
        client.process_message("not valid json {{{")

        # THEN no exception is raised (implicit assertion)

    def test_missing_fields_are_handled(self):
        """Messages with missing fields are handled gracefully."""
        # GIVEN a client
        client = self.make_client()
        message = json.dumps({"type": "snapshot"})  # Missing bids/asks

        # WHEN we process a message with missing fields
        client.process_message(message)

        # THEN no exception is raised (implicit assertion)
