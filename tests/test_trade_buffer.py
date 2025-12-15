"""Unit tests for Trade dataclass and TradeBuffer class."""

import threading
from decimal import Decimal

from src.ingest.trade_buffer import Trade, TradeBuffer


def _make_trade(
    trade_id: str = "123",
    timestamp_ms: int = 1000,
    price: str = "50000.00",
    size: str = "0.01",
    side: str = "buy",
) -> Trade:
    """Helper to create a Trade with defaults."""
    return Trade(
        trade_id=trade_id,
        timestamp_ms=timestamp_ms,
        price=Decimal(price),
        size=Decimal(size),
        side=side,
    )


class TestTrade:
    """Tests for Trade dataclass."""

    def test_trade_stores_all_fields(self):
        """Trade stores trade_id, timestamp_ms, price, size, side."""
        # GIVEN trade data
        # WHEN we create a Trade
        trade = Trade(
            trade_id="abc123",
            timestamp_ms=1702656000000,
            price=Decimal("50000.50"),
            size=Decimal("0.025"),
            side="buy",
        )

        # THEN all fields are stored correctly
        assert trade.trade_id == "abc123"
        assert trade.timestamp_ms == 1702656000000
        assert trade.price == Decimal("50000.50")
        assert trade.size == Decimal("0.025")
        assert trade.side == "buy"

    def test_trade_side_can_be_sell(self):
        """Trade side can be 'sell'."""
        # GIVEN a sell trade
        trade = _make_trade(side="sell")

        # THEN side is stored as sell
        assert trade.side == "sell"


class TestTradeBufferAddTrade:
    """Tests for TradeBuffer.add_trade()."""

    def test_add_trade_stores_trade(self):
        """add_trade stores a trade in the buffer."""
        # GIVEN an empty buffer
        buffer = TradeBuffer()

        # WHEN we add a trade
        trade = _make_trade()
        buffer.add_trade(trade)

        # THEN the trade is stored
        trades = buffer.get_recent(1)
        assert len(trades) == 1
        assert trades[0] == trade

    def test_add_trade_maintains_order(self):
        """add_trade maintains insertion order (oldest first)."""
        # GIVEN a buffer with trades
        buffer = TradeBuffer()
        trade1 = _make_trade(trade_id="1", timestamp_ms=1000)
        trade2 = _make_trade(trade_id="2", timestamp_ms=2000)
        trade3 = _make_trade(trade_id="3", timestamp_ms=3000)

        # WHEN we add trades in order
        buffer.add_trade(trade1)
        buffer.add_trade(trade2)
        buffer.add_trade(trade3)

        # THEN get_recent returns most recent first
        trades = buffer.get_recent(3)
        assert trades[0] == trade3
        assert trades[1] == trade2
        assert trades[2] == trade1


class TestTradeBufferMaxTrades:
    """Tests for TradeBuffer max_trades limit."""

    def test_max_trades_drops_oldest(self):
        """Buffer drops oldest trades when max_trades exceeded."""
        # GIVEN a buffer with max_trades=2
        buffer = TradeBuffer(max_trades=2)
        trade1 = _make_trade(trade_id="1")
        trade2 = _make_trade(trade_id="2")
        trade3 = _make_trade(trade_id="3")

        # WHEN we add 3 trades
        buffer.add_trade(trade1)
        buffer.add_trade(trade2)
        buffer.add_trade(trade3)

        # THEN only the 2 most recent remain
        trades = buffer.get_recent(10)
        assert len(trades) == 2
        assert trades[0].trade_id == "3"
        assert trades[1].trade_id == "2"

    def test_default_max_trades_is_1000(self):
        """Default max_trades is 1000."""
        # GIVEN a buffer with default max_trades
        buffer = TradeBuffer()

        # THEN max_trades is 1000
        assert buffer.max_trades == 1000


class TestTradeBufferGetRecent:
    """Tests for TradeBuffer.get_recent()."""

    def test_get_recent_returns_n_trades(self):
        """get_recent returns the N most recent trades."""
        # GIVEN a buffer with 5 trades
        buffer = TradeBuffer()
        for i in range(5):
            buffer.add_trade(_make_trade(trade_id=str(i), timestamp_ms=i * 1000))

        # WHEN we get 3 recent trades
        trades = buffer.get_recent(3)

        # THEN we get the 3 most recent (newest first)
        assert len(trades) == 3
        assert trades[0].trade_id == "4"
        assert trades[1].trade_id == "3"
        assert trades[2].trade_id == "2"

    def test_get_recent_returns_all_if_n_exceeds_count(self):
        """get_recent returns all trades if n exceeds buffer size."""
        # GIVEN a buffer with 2 trades
        buffer = TradeBuffer()
        buffer.add_trade(_make_trade(trade_id="1"))
        buffer.add_trade(_make_trade(trade_id="2"))

        # WHEN we request 10 trades
        trades = buffer.get_recent(10)

        # THEN we get all 2 trades
        assert len(trades) == 2

    def test_get_recent_empty_buffer_returns_empty_list(self):
        """get_recent on empty buffer returns empty list."""
        # GIVEN an empty buffer
        buffer = TradeBuffer()

        # WHEN we get recent trades
        trades = buffer.get_recent(10)

        # THEN we get an empty list
        assert trades == []

    def test_get_recent_default_is_100(self):
        """get_recent default n is 100."""
        # GIVEN a buffer with 150 trades
        buffer = TradeBuffer()
        for i in range(150):
            buffer.add_trade(_make_trade(trade_id=str(i)))

        # WHEN we call get_recent without n
        trades = buffer.get_recent()

        # THEN we get 100 trades
        assert len(trades) == 100


class TestTradeBufferGetTradesSince:
    """Tests for TradeBuffer.get_trades_since()."""

    def test_get_trades_since_filters_by_timestamp(self):
        """get_trades_since returns trades after given timestamp."""
        # GIVEN a buffer with trades at different timestamps
        buffer = TradeBuffer()
        buffer.add_trade(_make_trade(trade_id="1", timestamp_ms=1000))
        buffer.add_trade(_make_trade(trade_id="2", timestamp_ms=2000))
        buffer.add_trade(_make_trade(trade_id="3", timestamp_ms=3000))
        buffer.add_trade(_make_trade(trade_id="4", timestamp_ms=4000))

        # WHEN we get trades since 2000
        trades = buffer.get_trades_since(2000)

        # THEN we get trades with timestamp > 2000 (newest first)
        assert len(trades) == 2
        assert trades[0].trade_id == "4"
        assert trades[1].trade_id == "3"

    def test_get_trades_since_excludes_exact_timestamp(self):
        """get_trades_since excludes trades at exactly the given timestamp."""
        # GIVEN a buffer with a trade at exactly 2000
        buffer = TradeBuffer()
        buffer.add_trade(_make_trade(trade_id="1", timestamp_ms=2000))
        buffer.add_trade(_make_trade(trade_id="2", timestamp_ms=3000))

        # WHEN we get trades since 2000
        trades = buffer.get_trades_since(2000)

        # THEN the trade at 2000 is excluded
        assert len(trades) == 1
        assert trades[0].trade_id == "2"

    def test_get_trades_since_returns_empty_if_none_match(self):
        """get_trades_since returns empty list if no trades after timestamp."""
        # GIVEN a buffer with trades before the cutoff
        buffer = TradeBuffer()
        buffer.add_trade(_make_trade(timestamp_ms=1000))
        buffer.add_trade(_make_trade(timestamp_ms=2000))

        # WHEN we get trades since 5000
        trades = buffer.get_trades_since(5000)

        # THEN we get an empty list
        assert trades == []


class TestTradeBufferClear:
    """Tests for TradeBuffer.clear()."""

    def test_clear_removes_all_trades(self):
        """clear removes all trades from buffer."""
        # GIVEN a buffer with trades
        buffer = TradeBuffer()
        buffer.add_trade(_make_trade(trade_id="1"))
        buffer.add_trade(_make_trade(trade_id="2"))

        # WHEN we clear
        buffer.clear()

        # THEN buffer is empty
        assert buffer.get_recent(10) == []


class TestTradeBufferThreadSafety:
    """Tests for TradeBuffer thread safety."""

    def test_concurrent_add_and_read(self):
        """Buffer handles concurrent adds and reads safely."""
        # GIVEN a buffer
        buffer = TradeBuffer(max_trades=1000)
        errors = []

        def add_trades():
            try:
                for i in range(100):
                    buffer.add_trade(_make_trade(trade_id=str(i), timestamp_ms=i))
            except Exception as e:
                errors.append(e)

        def read_trades():
            try:
                for _ in range(100):
                    buffer.get_recent(50)
                    buffer.get_trades_since(50)
            except Exception as e:
                errors.append(e)

        # WHEN we run concurrent adds and reads
        threads = [
            threading.Thread(target=add_trades),
            threading.Thread(target=add_trades),
            threading.Thread(target=read_trades),
            threading.Thread(target=read_trades),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # THEN no errors occurred
        assert errors == []
