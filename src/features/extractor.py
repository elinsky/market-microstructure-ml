"""Feature extraction from order book snapshots."""

import threading
from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from src.ingest.order_book import OrderBookSnapshot


@dataclass
class FeatureSnapshot:
    """Computed features from order book state."""

    spread_bps: float  # Spread in basis points
    imbalance: float  # Bid-ask volume imbalance (-1 to 1)
    depth: float  # Total volume at top levels (in base currency)
    volatility: float  # Rolling std of mid-price changes (in bps)
    timestamp: str | None = None


class FeatureExtractor:
    """Extracts market microstructure features from order book snapshots.

    Thread-safe implementation with rolling window for volatility calculation.
    """

    def __init__(self, volatility_window: int = 50):
        """Initialize the feature extractor.

        Args:
            volatility_window: Number of ticks to use for volatility calculation.
        """
        self._volatility_window = volatility_window
        self._mid_prices: deque[Decimal] = deque(maxlen=volatility_window)
        self._lock = threading.RLock()

    def compute(self, snapshot: OrderBookSnapshot) -> FeatureSnapshot | None:
        """Compute features from an order book snapshot.

        Args:
            snapshot: Current order book state.

        Returns:
            FeatureSnapshot with computed metrics, or None if insufficient data.
        """
        if snapshot.mid_price is None or snapshot.spread is None:
            return None

        with self._lock:
            # Store mid price for volatility calculation
            self._mid_prices.append(snapshot.mid_price)

            # Compute spread in basis points
            spread_bps = self._compute_spread_bps(snapshot)

            # Compute bid-ask volume imbalance
            imbalance = self._compute_imbalance(snapshot)

            # Compute total depth
            depth = self._compute_depth(snapshot)

            # Compute volatility
            volatility = self._compute_volatility(snapshot.mid_price)

            return FeatureSnapshot(
                spread_bps=spread_bps,
                imbalance=imbalance,
                depth=depth,
                volatility=volatility,
                timestamp=snapshot.timestamp,
            )

    def _compute_spread_bps(self, snapshot: OrderBookSnapshot) -> float:
        """Compute spread in basis points.

        spread_bps = (ask - bid) / mid * 10000
        """
        if snapshot.spread is None or snapshot.mid_price is None:
            return 0.0

        if snapshot.mid_price == 0:
            return 0.0

        return float(snapshot.spread / snapshot.mid_price * 10000)

    def _compute_imbalance(self, snapshot: OrderBookSnapshot) -> float:
        """Compute bid-ask volume imbalance at top level.

        imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)

        Returns value in [-1, 1]:
          +1 = all buying pressure (bids only)
          -1 = all selling pressure (asks only)
           0 = balanced
        """
        if not snapshot.bids or not snapshot.asks:
            return 0.0

        # Get top level volumes
        bid_vol = float(snapshot.bids[0][1])
        ask_vol = float(snapshot.asks[0][1])

        total = bid_vol + ask_vol
        if total == 0:
            return 0.0

        return (bid_vol - ask_vol) / total

    def _compute_depth(self, snapshot: OrderBookSnapshot) -> float:
        """Compute total volume at all tracked levels.

        Returns total volume in base currency (e.g., BTC).
        """
        bid_depth = sum(float(size) for _, size in snapshot.bids)
        ask_depth = sum(float(size) for _, size in snapshot.asks)
        return bid_depth + ask_depth

    def _compute_volatility(self, current_mid: Decimal) -> float:
        """Compute rolling volatility of mid-price changes in basis points.

        Uses standard deviation of percentage changes over the window.
        """
        if len(self._mid_prices) < 2:
            return 0.0

        # Compute percentage changes
        changes = []
        prices = list(self._mid_prices)
        for i in range(1, len(prices)):
            if prices[i - 1] != 0:
                pct_change = float((prices[i] - prices[i - 1]) / prices[i - 1] * 10000)
                changes.append(pct_change)

        if not changes:
            return 0.0

        # Compute standard deviation
        mean = sum(changes) / len(changes)
        variance = sum((x - mean) ** 2 for x in changes) / len(changes)
        return variance**0.5
