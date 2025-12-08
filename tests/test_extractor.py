"""Tests for FeatureExtractor."""

from decimal import Decimal

import pytest

from src.features.extractor import FeatureExtractor
from src.ingest.order_book import OrderBookSnapshot


class TestFeatureExtractor:
    """Tests for FeatureExtractor class."""

    def _make_snapshot(
        self,
        bids: list[tuple[str, str]] | None = None,
        asks: list[tuple[str, str]] | None = None,
        timestamp: str | None = None,
    ) -> OrderBookSnapshot:
        """Helper to create an OrderBookSnapshot."""
        bid_list = [(Decimal(p), Decimal(s)) for p, s in (bids or [])]
        ask_list = [(Decimal(p), Decimal(s)) for p, s in (asks or [])]

        best_bid = bid_list[0][0] if bid_list else None
        best_ask = ask_list[0][0] if ask_list else None

        mid_price = None
        spread = None
        if best_bid is not None and best_ask is not None:
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid

        return OrderBookSnapshot(
            bids=bid_list,
            asks=ask_list,
            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=mid_price,
            spread=spread,
            timestamp=timestamp,
        )

    def test_empty_snapshot_returns_none(self):
        """Returns None for empty order book."""
        extractor = FeatureExtractor()
        snapshot = self._make_snapshot()

        result = extractor.compute(snapshot)

        assert result is None

    def test_spread_bps_calculation(self):
        """Spread is computed correctly in basis points."""
        extractor = FeatureExtractor()
        # bid=100, ask=101, mid=100.5, spread=1
        # spread_bps = (1 / 100.5) * 10000 ≈ 99.5
        snapshot = self._make_snapshot(
            bids=[("100.00", "1.0")],
            asks=[("101.00", "1.0")],
        )

        result = extractor.compute(snapshot)

        assert result is not None
        assert abs(result.spread_bps - 99.5) < 0.1

    def test_imbalance_balanced(self):
        """Imbalance is 0 when bid and ask volumes are equal."""
        extractor = FeatureExtractor()
        snapshot = self._make_snapshot(
            bids=[("100.00", "1.0")],
            asks=[("101.00", "1.0")],
        )

        result = extractor.compute(snapshot)

        assert result is not None
        assert result.imbalance == 0.0

    def test_imbalance_bid_heavy(self):
        """Positive imbalance when bid volume exceeds ask volume."""
        extractor = FeatureExtractor()
        # bid_vol=2.0, ask_vol=1.0 -> imbalance = (2-1)/(2+1) = 0.333
        snapshot = self._make_snapshot(
            bids=[("100.00", "2.0")],
            asks=[("101.00", "1.0")],
        )

        result = extractor.compute(snapshot)

        assert result is not None
        assert abs(result.imbalance - 0.333) < 0.01

    def test_imbalance_ask_heavy(self):
        """Negative imbalance when ask volume exceeds bid volume."""
        extractor = FeatureExtractor()
        # bid_vol=1.0, ask_vol=2.0 -> imbalance = (1-2)/(1+2) = -0.333
        snapshot = self._make_snapshot(
            bids=[("100.00", "1.0")],
            asks=[("101.00", "2.0")],
        )

        result = extractor.compute(snapshot)

        assert result is not None
        assert abs(result.imbalance + 0.333) < 0.01

    def test_depth_calculation(self):
        """Depth is sum of all bid and ask volumes."""
        extractor = FeatureExtractor()
        # Total: 1.0 + 2.0 + 1.5 + 2.5 = 7.0
        snapshot = self._make_snapshot(
            bids=[("100.00", "1.0"), ("99.00", "2.0")],
            asks=[("101.00", "1.5"), ("102.00", "2.5")],
        )

        result = extractor.compute(snapshot)

        assert result is not None
        assert result.depth == 7.0

    def test_volatility_initial_zero(self):
        """Volatility is 0 with only one price point."""
        extractor = FeatureExtractor()
        snapshot = self._make_snapshot(
            bids=[("100.00", "1.0")],
            asks=[("101.00", "1.0")],
        )

        result = extractor.compute(snapshot)

        assert result is not None
        assert result.volatility == 0.0

    def test_volatility_increases_with_price_changes(self):
        """Volatility increases when prices change."""
        extractor = FeatureExtractor(volatility_window=10)

        # First snapshot - volatility 0 (only 1 point)
        result1 = extractor.compute(
            self._make_snapshot(bids=[("100.00", "1.0")], asks=[("101.00", "1.0")])
        )
        assert result1 is not None
        assert result1.volatility == 0.0

        # Second snapshot - volatility 0 (std of single change is 0)
        result2 = extractor.compute(
            self._make_snapshot(bids=[("102.00", "1.0")], asks=[("103.00", "1.0")])
        )
        assert result2 is not None
        # With only 2 prices, we have 1 change, std of 1 value is 0

        # Third snapshot with different magnitude change - now volatility > 0
        result3 = extractor.compute(
            self._make_snapshot(bids=[("100.00", "1.0")], asks=[("101.00", "1.0")])
        )
        assert result3 is not None
        assert result3.volatility > 0.0

    def test_timestamp_preserved(self):
        """Timestamp is passed through to FeatureSnapshot."""
        extractor = FeatureExtractor()
        snapshot = self._make_snapshot(
            bids=[("100.00", "1.0")],
            asks=[("101.00", "1.0")],
            timestamp="2024-01-01T00:00:00Z",
        )

        result = extractor.compute(snapshot)

        assert result is not None
        assert result.timestamp == "2024-01-01T00:00:00Z"
