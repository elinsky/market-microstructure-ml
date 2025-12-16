"""Tests for FeatureExtractor."""

from decimal import Decimal

from src.features.extractor import FeatureExtractor
from src.ingest.order_book import OrderBookSnapshot


class TestFeatureExtractor:
    """Tests for FeatureExtractor class."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

    def make_snapshot(
        self,
        bids: list[tuple[str, str]] | None = None,
        asks: list[tuple[str, str]] | None = None,
        timestamp: str | None = None,
    ) -> OrderBookSnapshot:
        """Create an OrderBookSnapshot from string tuples."""
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

    def make_balanced_snapshot(self) -> OrderBookSnapshot:
        """Snapshot with equal bid/ask volumes (imbalance = 0)."""
        return self.make_snapshot(
            bids=[("100.00", "1.0")],
            asks=[("101.00", "1.0")],
        )

    def make_bid_heavy_snapshot(self) -> OrderBookSnapshot:
        """Snapshot with more bid volume (positive imbalance)."""
        return self.make_snapshot(
            bids=[("100.00", "2.0")],
            asks=[("101.00", "1.0")],
        )

    def make_ask_heavy_snapshot(self) -> OrderBookSnapshot:
        """Snapshot with more ask volume (negative imbalance)."""
        return self.make_snapshot(
            bids=[("100.00", "1.0")],
            asks=[("101.00", "2.0")],
        )

    def make_multi_level_snapshot(self) -> OrderBookSnapshot:
        """Snapshot with multiple price levels for depth calculation."""
        return self.make_snapshot(
            bids=[("100.00", "1.0"), ("99.00", "2.0")],
            asks=[("101.00", "1.5"), ("102.00", "2.5")],
        )

    # =========================================================================
    # Tests
    # =========================================================================

    def test_compute_returns_none_for_empty_snapshot(self):
        """Returns None when order book has no data."""
        # GIVEN an extractor and an empty snapshot
        extractor = FeatureExtractor()
        snapshot = self.make_snapshot()

        # WHEN we compute features
        result = extractor.compute(snapshot)

        # THEN result is None
        assert result is None

    def test_spread_bps_calculation(self):
        """Spread is computed correctly in basis points."""
        # GIVEN an extractor and a snapshot with bid=100, ask=101
        extractor = FeatureExtractor()
        snapshot = self.make_balanced_snapshot()
        # spread=1, mid=100.5, spread_bps = (1/100.5) * 10000 ≈ 99.5

        # WHEN we compute features
        result = extractor.compute(snapshot)

        # THEN spread_bps is approximately 99.5
        assert result is not None
        assert abs(result.spread_bps - 99.5) < 0.1

    def test_imbalance_zero_when_balanced(self):
        """Imbalance is 0 when bid and ask volumes are equal."""
        # GIVEN an extractor and a balanced snapshot
        extractor = FeatureExtractor()
        snapshot = self.make_balanced_snapshot()

        # WHEN we compute features
        result = extractor.compute(snapshot)

        # THEN imbalance is 0
        assert result is not None
        assert result.imbalance == 0.0

    def test_imbalance_positive_when_bid_heavy(self):
        """Positive imbalance when bid volume exceeds ask volume."""
        # GIVEN an extractor and a bid-heavy snapshot (2.0 bid, 1.0 ask)
        extractor = FeatureExtractor()
        snapshot = self.make_bid_heavy_snapshot()
        # imbalance = (2-1)/(2+1) = 0.333

        # WHEN we compute features
        result = extractor.compute(snapshot)

        # THEN imbalance is positive (~0.333)
        assert result is not None
        assert abs(result.imbalance - 0.333) < 0.01

    def test_imbalance_negative_when_ask_heavy(self):
        """Negative imbalance when ask volume exceeds bid volume."""
        # GIVEN an extractor and an ask-heavy snapshot (1.0 bid, 2.0 ask)
        extractor = FeatureExtractor()
        snapshot = self.make_ask_heavy_snapshot()
        # imbalance = (1-2)/(1+2) = -0.333

        # WHEN we compute features
        result = extractor.compute(snapshot)

        # THEN imbalance is negative (~-0.333)
        assert result is not None
        assert abs(result.imbalance + 0.333) < 0.01

    def test_depth_sums_all_volumes(self):
        """Depth is sum of all bid and ask volumes."""
        # GIVEN an extractor and a multi-level snapshot
        extractor = FeatureExtractor()
        snapshot = self.make_multi_level_snapshot()
        # Total: 1.0 + 2.0 + 1.5 + 2.5 = 7.0

        # WHEN we compute features
        result = extractor.compute(snapshot)

        # THEN depth equals total volume
        assert result is not None
        assert result.depth == 7.0

    def test_volatility_zero_with_single_price(self):
        """Volatility is 0 with only one price point."""
        # GIVEN an extractor and a single snapshot
        extractor = FeatureExtractor()
        snapshot = self.make_balanced_snapshot()

        # WHEN we compute features (first price point)
        result = extractor.compute(snapshot)

        # THEN volatility is 0 (need 2+ points for std)
        assert result is not None
        assert result.volatility == 0.0

    def test_volatility_increases_with_price_changes(self):
        """Volatility increases when prices change significantly."""
        # GIVEN an extractor with a small window
        extractor = FeatureExtractor(volatility_window=10)

        # WHEN we feed it prices that move around
        extractor.compute(
            self.make_snapshot(bids=[("100.00", "1.0")], asks=[("101.00", "1.0")])
        )
        extractor.compute(
            self.make_snapshot(bids=[("102.00", "1.0")], asks=[("103.00", "1.0")])
        )
        result = extractor.compute(
            self.make_snapshot(bids=[("100.00", "1.0")], asks=[("101.00", "1.0")])
        )

        # THEN volatility is greater than 0
        assert result is not None
        assert result.volatility > 0.0

    def test_timestamp_preserved_in_result(self):
        """Timestamp is passed through to FeatureSnapshot."""
        # GIVEN an extractor and a snapshot with a timestamp
        extractor = FeatureExtractor()
        snapshot = self.make_snapshot(
            bids=[("100.00", "1.0")],
            asks=[("101.00", "1.0")],
            timestamp="2024-01-01T00:00:00Z",
        )

        # WHEN we compute features
        result = extractor.compute(snapshot)

        # THEN timestamp is preserved
        assert result is not None
        assert result.timestamp == "2024-01-01T00:00:00Z"

    def test_timestamp_ms_preserved_in_result(self):
        """timestamp_ms is passed through to FeatureSnapshot."""
        # GIVEN an extractor and a snapshot with timestamp_ms
        extractor = FeatureExtractor()
        snapshot = OrderBookSnapshot(
            bids=[(Decimal("100.00"), Decimal("1.0"))],
            asks=[(Decimal("101.00"), Decimal("1.0"))],
            best_bid=Decimal("100.00"),
            best_ask=Decimal("101.00"),
            mid_price=Decimal("100.50"),
            spread=Decimal("1.00"),
            timestamp="2024-01-01T00:00:00Z",
            timestamp_ms=1704067200000,
        )

        # WHEN we compute features
        result = extractor.compute(snapshot)

        # THEN timestamp_ms is preserved
        assert result is not None
        assert result.timestamp_ms == 1704067200000
