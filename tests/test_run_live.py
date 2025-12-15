"""Tests for QuoteWatchRunner."""

from decimal import Decimal

from src.ingest.order_book import OrderBookSnapshot
from src.run_live import PipelineResult, QuoteWatchRunner


class TestQuoteWatchRunner:
    """Tests for QuoteWatchRunner.process_snapshot."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

    def make_runner(self) -> QuoteWatchRunner:
        """Create a QuoteWatchRunner without starting the websocket."""
        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
        # Initialize components manually to avoid websocket setup
        from src.features import FeatureExtractor, Labeler, StabilityScorer
        from src.ingest import OrderBook
        from src.model import OnlineClassifier

        runner.symbol = "BTC-USD"
        runner.order_book = OrderBook(depth=3)
        runner.feature_extractor = FeatureExtractor(volatility_window=50)
        runner.stability_scorer = StabilityScorer()
        runner.labeler = Labeler(delta_ms=500, threshold_pct=0.01)
        runner.classifier = OnlineClassifier(learning_rate=0.01)
        return runner

    def make_empty_snapshot(self) -> OrderBookSnapshot:
        """Create an empty order book snapshot."""
        return OrderBookSnapshot(
            bids=[],
            asks=[],
            best_bid=None,
            best_ask=None,
            mid_price=None,
            spread=None,
            timestamp=None,
        )

    def make_snapshot(
        self,
        best_bid: str = "100.00",
        best_ask: str = "101.00",
        timestamp: str | None = "2024-01-01T00:00:00Z",
    ) -> OrderBookSnapshot:
        """Create a populated order book snapshot."""
        bid = Decimal(best_bid)
        ask = Decimal(best_ask)
        return OrderBookSnapshot(
            bids=[(bid, Decimal("1.0"))],
            asks=[(ask, Decimal("1.0"))],
            best_bid=bid,
            best_ask=ask,
            mid_price=(bid + ask) / 2,
            spread=ask - bid,
            timestamp=timestamp,
        )

    # =========================================================================
    # Tests - Empty Snapshot
    # =========================================================================

    def test_empty_snapshot_returns_none_features(self):
        """Empty snapshot produces None features."""
        # GIVEN a runner and an empty snapshot
        runner = self.make_runner()
        snapshot = self.make_empty_snapshot()

        # WHEN we process the snapshot
        result = runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN features are None
        assert result.features is None

    def test_empty_snapshot_returns_none_stability(self):
        """Empty snapshot produces None stability."""
        # GIVEN a runner and an empty snapshot
        runner = self.make_runner()
        snapshot = self.make_empty_snapshot()

        # WHEN we process the snapshot
        result = runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN stability is None
        assert result.stability is None

    # =========================================================================
    # Tests - Valid Snapshot
    # =========================================================================

    def test_valid_snapshot_extracts_features(self):
        """Valid snapshot produces features with spread, imbalance, depth."""
        # GIVEN a runner and a valid snapshot
        runner = self.make_runner()
        snapshot = self.make_snapshot()

        # WHEN we process the snapshot
        result = runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN features are populated
        assert result.features is not None
        assert result.features.spread_bps > 0
        assert result.features.depth > 0

    def test_valid_snapshot_computes_stability(self):
        """Valid snapshot produces stability score."""
        # GIVEN a runner and a valid snapshot
        runner = self.make_runner()
        snapshot = self.make_snapshot()

        # WHEN we process the snapshot
        result = runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN stability is computed
        assert result.stability is not None
        assert 0 <= result.stability.score <= 100
        assert result.stability.category in ["STABLE", "MODERATE", "UNSTABLE"]

    def test_valid_snapshot_returns_prediction_proba(self):
        """Valid snapshot produces prediction probability."""
        # GIVEN a runner and a valid snapshot
        runner = self.make_runner()
        snapshot = self.make_snapshot()

        # WHEN we process the snapshot
        result = runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN prediction probability is returned
        assert result.prediction_proba is not None
        assert 0.0 <= result.prediction_proba <= 1.0

    def test_valid_snapshot_returns_model_stats(self):
        """Valid snapshot returns model statistics."""
        # GIVEN a runner and a valid snapshot
        runner = self.make_runner()
        snapshot = self.make_snapshot()

        # WHEN we process the snapshot
        result = runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN model stats are returned
        assert result.model_stats is not None
        assert result.model_stats.samples_total >= 0

    # =========================================================================
    # Tests - Pipeline Result Structure
    # =========================================================================

    def test_process_snapshot_returns_pipeline_result(self):
        """process_snapshot returns a PipelineResult dataclass."""
        # GIVEN a runner and a snapshot
        runner = self.make_runner()
        snapshot = self.make_snapshot()

        # WHEN we process the snapshot
        result = runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN result is a PipelineResult
        assert isinstance(result, PipelineResult)

    # =========================================================================
    # Tests - ML Pipeline Behavior
    # =========================================================================

    def test_multiple_snapshots_accumulate_samples(self):
        """Processing multiple snapshots adds samples to labeler."""
        # GIVEN a runner
        runner = self.make_runner()

        # WHEN we process multiple snapshots over time
        for i in range(5):
            snapshot = self.make_snapshot()
            runner.process_snapshot(snapshot, timestamp_ms=1000.0 + i * 100)

        # THEN samples are buffered in labeler
        assert runner.labeler.buffer_size > 0

    def test_labeled_sample_trains_classifier(self):
        """When labeler emits a sample, classifier is trained."""
        # GIVEN a runner with delta_ms=500
        runner = self.make_runner()
        snapshot = self.make_snapshot()

        # WHEN we process snapshots spanning delta time
        runner.process_snapshot(snapshot, timestamp_ms=1000.0)
        runner.process_snapshot(snapshot, timestamp_ms=1600.0)  # 600ms later

        # THEN classifier has received training samples
        assert runner.classifier.sample_count >= 1
