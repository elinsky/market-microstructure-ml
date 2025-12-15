"""Tests for CoinbaseWebSocketClient."""

import json
from decimal import Decimal

from src.ingest.order_book import OrderBook
from src.ingest.trade_buffer import Trade, TradeBuffer
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


class TestCoinbaseWebSocketClientMatches:
    """Tests for CoinbaseWebSocketClient match message handling."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

    def make_client_with_trade_buffer(
        self,
        trade_buffer: TradeBuffer | None = None,
        on_trade=None,
    ) -> CoinbaseWebSocketClient:
        """Create a WebSocket client with a trade buffer."""
        book = OrderBook(depth=3)
        buffer = trade_buffer or TradeBuffer()
        return CoinbaseWebSocketClient(
            order_book=book,
            trade_buffer=buffer,
            symbol="BTC-USD",
            on_trade=on_trade,
        )

    def make_match_message(
        self,
        trade_id: str = "123456789",
        time: str = "2024-01-01T12:00:00.000000Z",
        price: str = "50000.00",
        size: str = "0.01",
        side: str = "buy",
    ) -> str:
        """Create a Coinbase match message."""
        return json.dumps(
            {
                "type": "match",
                "trade_id": trade_id,
                "sequence": 50,
                "maker_order_id": "abc-123",
                "taker_order_id": "def-456",
                "time": time,
                "product_id": "BTC-USD",
                "size": size,
                "price": price,
                "side": side,
            }
        )

    # =========================================================================
    # Tests - Match Message Processing
    # =========================================================================

    def test_match_message_adds_trade_to_buffer(self):
        """Match message adds a trade to the trade buffer."""
        # GIVEN a client with a trade buffer
        buffer = TradeBuffer()
        client = self.make_client_with_trade_buffer(trade_buffer=buffer)
        message = self.make_match_message(
            trade_id="999",
            price="51000.50",
            size="0.025",
            side="sell",
        )

        # WHEN we process a match message
        client.process_message(message)

        # THEN trade is added to buffer
        trades = buffer.get_recent(1)
        assert len(trades) == 1
        assert trades[0].trade_id == "999"
        assert trades[0].price == Decimal("51000.50")
        assert trades[0].size == Decimal("0.025")
        assert trades[0].side == "sell"

    def test_match_message_parses_timestamp_to_ms(self):
        """Match message parses ISO timestamp to milliseconds."""
        # GIVEN a client with a trade buffer
        buffer = TradeBuffer()
        client = self.make_client_with_trade_buffer(trade_buffer=buffer)
        # 2024-01-01T12:00:00.123456Z -> epoch ms
        message = self.make_match_message(time="2024-01-01T12:00:00.123456Z")

        # WHEN we process a match message
        client.process_message(message)

        # THEN timestamp is in milliseconds
        trades = buffer.get_recent(1)
        assert trades[0].timestamp_ms == 1704110400123

    def test_match_message_triggers_on_trade_callback(self):
        """Match message triggers on_trade callback with Trade object."""
        # GIVEN a client with an on_trade callback
        received_trades: list[Trade] = []

        def on_trade(trade: Trade):
            received_trades.append(trade)

        client = self.make_client_with_trade_buffer(on_trade=on_trade)
        message = self.make_match_message(trade_id="callback-test")

        # WHEN we process a match message
        client.process_message(message)

        # THEN callback receives the Trade object
        assert len(received_trades) == 1
        assert received_trades[0].trade_id == "callback-test"

    def test_match_message_without_trade_buffer_is_ignored(self):
        """Match message is ignored if no trade buffer configured."""
        # GIVEN a client without a trade buffer
        book = OrderBook(depth=3)
        client = CoinbaseWebSocketClient(order_book=book, symbol="BTC-USD")
        message = self.make_match_message()

        # WHEN we process a match message
        client.process_message(message)

        # THEN no exception is raised (implicit assertion)

    def test_match_message_does_not_trigger_on_update(self):
        """Match messages do not trigger the on_update callback."""
        # GIVEN a client with both callbacks
        update_count = {"count": 0}
        trade_count = {"count": 0}

        def on_update():
            update_count["count"] += 1

        def on_trade(trade: Trade):
            trade_count["count"] += 1

        book = OrderBook(depth=3)
        buffer = TradeBuffer()
        client = CoinbaseWebSocketClient(
            order_book=book,
            trade_buffer=buffer,
            symbol="BTC-USD",
            on_update=on_update,
            on_trade=on_trade,
        )
        message = self.make_match_message()

        # WHEN we process a match message
        client.process_message(message)

        # THEN only on_trade is called, not on_update
        assert update_count["count"] == 0
        assert trade_count["count"] == 1

    def test_match_message_with_integer_trade_id(self):
        """Match message handles trade_id as integer (Coinbase sends both)."""
        # GIVEN a message with integer trade_id
        buffer = TradeBuffer()
        client = self.make_client_with_trade_buffer(trade_buffer=buffer)
        message = json.dumps(
            {
                "type": "match",
                "trade_id": 123456789,  # Integer, not string
                "time": "2024-01-01T12:00:00.000000Z",
                "product_id": "BTC-USD",
                "size": "0.01",
                "price": "50000.00",
                "side": "buy",
            }
        )

        # WHEN we process the message
        client.process_message(message)

        # THEN trade_id is stored as string
        trades = buffer.get_recent(1)
        assert trades[0].trade_id == "123456789"
