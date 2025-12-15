"""Trade buffer for storing recent trades from Coinbase matches channel."""

import threading
from collections import deque
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Trade:
    """A single trade execution from the matches channel.

    Attributes:
        trade_id: Unique identifier for the trade.
        timestamp_ms: Trade execution time in milliseconds since epoch.
        price: Execution price.
        size: Trade size (quantity).
        side: Taker side - "buy" (buyer lifted ask) or "sell" (seller hit bid).
    """

    trade_id: str
    timestamp_ms: int
    price: Decimal
    size: Decimal
    side: str


class TradeBuffer:
    """Thread-safe buffer for recent trades.

    Stores trades in a fixed-size deque, dropping oldest trades when full.
    All methods are thread-safe via RLock.
    """

    def __init__(self, max_trades: int = 1000):
        """Initialize trade buffer.

        Args:
            max_trades: Maximum number of trades to store. Oldest dropped when exceeded.
        """
        self.max_trades = max_trades
        self._trades: deque[Trade] = deque(maxlen=max_trades)
        self._lock = threading.RLock()

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to the buffer.

        Args:
            trade: Trade to add. If buffer is full, oldest trade is dropped.
        """
        with self._lock:
            self._trades.append(trade)

    def get_recent(self, n: int = 100) -> list[Trade]:
        """Get the N most recent trades.

        Args:
            n: Number of trades to return.

        Returns:
            List of trades, most recent first.
        """
        with self._lock:
            # deque stores oldest first, so reverse and take first n
            trades = list(self._trades)
            trades.reverse()
            return trades[:n]

    def get_trades_since(self, timestamp_ms: int) -> list[Trade]:
        """Get all trades since a given timestamp.

        Args:
            timestamp_ms: Timestamp in milliseconds. Returns trades with
                timestamp > timestamp_ms (exclusive).

        Returns:
            List of trades after the timestamp, most recent first.
        """
        with self._lock:
            trades = [t for t in self._trades if t.timestamp_ms > timestamp_ms]
            trades.reverse()
            return trades

    def clear(self) -> None:
        """Clear all trades from the buffer."""
        with self._lock:
            self._trades.clear()
