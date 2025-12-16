"""Order book cache maintaining top-10 bid/ask levels."""

import threading
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class OrderBookSnapshot:
    """Snapshot of current order book state."""

    best_bid: Decimal | None
    best_ask: Decimal | None
    mid_price: Decimal | None
    spread: Decimal | None
    bids: list[tuple[Decimal, Decimal]]  # [(price, size), ...]
    asks: list[tuple[Decimal, Decimal]]  # [(price, size), ...]
    timestamp: str | None = None
    timestamp_ms: int | None = None


class OrderBook:
    """Thread-safe order book maintaining top-N levels.

    Processes Coinbase L2 snapshot and update messages.
    """

    def __init__(self, depth: int = 10):
        """Initialize order book.

        Args:
            depth: Number of price levels to maintain on each side.
        """
        self.depth = depth
        self._bids: dict[Decimal, Decimal] = {}  # price -> size
        self._asks: dict[Decimal, Decimal] = {}  # price -> size
        self._lock = threading.RLock()
        self._last_timestamp: str | None = None

    def apply_snapshot(self, bids: list[list[str]], asks: list[list[str]]) -> None:
        """Apply full order book snapshot.

        Args:
            bids: List of [price, size] strings from Coinbase.
            asks: List of [price, size] strings from Coinbase.
        """
        with self._lock:
            self._bids.clear()
            self._asks.clear()

            for price_str, size_str in bids:
                price = Decimal(price_str)
                size = Decimal(size_str)
                if size > 0:
                    self._bids[price] = size

            for price_str, size_str in asks:
                price = Decimal(price_str)
                size = Decimal(size_str)
                if size > 0:
                    self._asks[price] = size

    def apply_update(
        self, changes: list[list[str]], timestamp: str | None = None
    ) -> None:
        """Apply incremental L2 update.

        Args:
            changes: List of [side, price, size] strings from Coinbase.
            timestamp: Optional timestamp from the update message.
        """
        with self._lock:
            self._last_timestamp = timestamp

            for change in changes:
                side, price_str, size_str = change
                price = Decimal(price_str)
                size = Decimal(size_str)

                book = self._bids if side == "buy" else self._asks

                if size == 0:
                    book.pop(price, None)
                else:
                    book[price] = size

    def get_snapshot(self) -> OrderBookSnapshot:
        """Get current order book snapshot.

        Returns:
            OrderBookSnapshot with top-N levels and derived metrics.
        """
        with self._lock:
            # Sort and take top N levels
            sorted_bids = sorted(self._bids.items(), key=lambda x: x[0], reverse=True)[
                : self.depth
            ]
            sorted_asks = sorted(self._asks.items(), key=lambda x: x[0])[: self.depth]

            best_bid = sorted_bids[0][0] if sorted_bids else None
            best_ask = sorted_asks[0][0] if sorted_asks else None

            mid_price = None
            spread = None

            if best_bid is not None and best_ask is not None:
                mid_price = (best_bid + best_ask) / 2
                spread = best_ask - best_bid

            # Parse timestamp to milliseconds
            timestamp_ms = self._parse_timestamp_ms(self._last_timestamp)

            return OrderBookSnapshot(
                best_bid=best_bid,
                best_ask=best_ask,
                mid_price=mid_price,
                spread=spread,
                bids=sorted_bids,
                asks=sorted_asks,
                timestamp=self._last_timestamp,
                timestamp_ms=timestamp_ms,
            )

    @staticmethod
    def _parse_timestamp_ms(iso_timestamp: str | None) -> int | None:
        """Parse ISO8601 timestamp to milliseconds since epoch.

        Args:
            iso_timestamp: ISO8601 timestamp string
                (e.g., "2024-01-01T12:00:00.123456Z").

        Returns:
            Milliseconds since Unix epoch, or None if parsing fails.
        """
        if not iso_timestamp:
            return None
        try:
            dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            return None
