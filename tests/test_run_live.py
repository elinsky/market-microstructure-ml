"""Tests for QuoteWatchRunner."""

import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.ingest.order_book import OrderBookSnapshot
from src.ingest.trade_buffer import Trade
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
        runner._writer = None
        runner._trade_buffer = None
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


class TestQuoteWatchRunnerPersistence:
    """Tests for QuoteWatchRunner persistence functionality."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

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

    def make_trade(self) -> Trade:
        """Create a test trade."""
        return Trade(
            trade_id="123",
            timestamp_ms=1704067200000,
            price=Decimal("100.50"),
            size=Decimal("0.5"),
            side="buy",
        )

    # =========================================================================
    # Tests - Persistence Disabled (default)
    # =========================================================================

    def test_runner_has_no_writer_when_persistence_disabled(self):
        """Runner has no DataWriter when ENABLE_PERSISTENCE is not set."""
        # GIVEN ENABLE_PERSISTENCE is not set
        env = os.environ.copy()
        env.pop("ENABLE_PERSISTENCE", None)

        with patch.dict(os.environ, env, clear=True):
            # WHEN we create a runner
            runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
            runner._init_components("BTC-USD")

            # THEN writer is None
            assert runner._writer is None

    def test_runner_has_no_trade_buffer_when_persistence_disabled(self):
        """Runner has no TradeBuffer when ENABLE_PERSISTENCE is not set."""
        # GIVEN ENABLE_PERSISTENCE is not set
        env = os.environ.copy()
        env.pop("ENABLE_PERSISTENCE", None)

        with patch.dict(os.environ, env, clear=True):
            # WHEN we create a runner
            runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
            runner._init_components("BTC-USD")

            # THEN trade_buffer is None
            assert runner._trade_buffer is None

    # =========================================================================
    # Tests - Persistence Enabled
    # =========================================================================

    def test_runner_has_trade_buffer_when_persistence_enabled(self):
        """Runner has TradeBuffer when ENABLE_PERSISTENCE=true."""
        # GIVEN ENABLE_PERSISTENCE=true and catalog env vars set
        env = {
            "ENABLE_PERSISTENCE": "true",
            "ICEBERG_CATALOG_URI": "postgresql+psycopg2://localhost/test",
            "ICEBERG_WAREHOUSE": "file:///tmp/warehouse",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("src.run_live.get_catalog") as mock_get_catalog:
                with patch("src.run_live.create_tables"):
                    with patch("src.run_live.DataWriter"):
                        mock_get_catalog.return_value = MagicMock()

                        # WHEN we create a runner
                        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
                        runner._init_components("BTC-USD")

                        # THEN trade_buffer is initialized
                        assert runner._trade_buffer is not None

    def test_runner_creates_tables_on_init_when_persistence_enabled(self):
        """Runner calls create_tables when ENABLE_PERSISTENCE=true."""
        # GIVEN ENABLE_PERSISTENCE=true
        env = {
            "ENABLE_PERSISTENCE": "true",
            "ICEBERG_CATALOG_URI": "postgresql+psycopg2://localhost/test",
            "ICEBERG_WAREHOUSE": "file:///tmp/warehouse",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("src.run_live.get_catalog") as mock_get_catalog:
                with patch("src.run_live.create_tables") as mock_create_tables:
                    with patch("src.run_live.DataWriter"):
                        mock_catalog = MagicMock()
                        mock_get_catalog.return_value = mock_catalog

                        # WHEN we create a runner
                        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
                        runner._init_components("BTC-USD")

                        # THEN create_tables was called
                        mock_create_tables.assert_called_once_with(mock_catalog)

    def test_runner_has_writer_when_persistence_enabled(self):
        """Runner has DataWriter when ENABLE_PERSISTENCE=true."""
        # GIVEN ENABLE_PERSISTENCE=true
        env = {
            "ENABLE_PERSISTENCE": "true",
            "ICEBERG_CATALOG_URI": "postgresql+psycopg2://localhost/test",
            "ICEBERG_WAREHOUSE": "file:///tmp/warehouse",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("src.run_live.get_catalog") as mock_get_catalog:
                with patch("src.run_live.create_tables"):
                    with patch("src.run_live.DataWriter") as mock_writer_class:
                        mock_catalog = MagicMock()
                        mock_get_catalog.return_value = mock_catalog
                        mock_writer = MagicMock()
                        mock_writer_class.return_value = mock_writer

                        # WHEN we create a runner
                        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
                        runner._init_components("BTC-USD")

                        # THEN writer is initialized
                        assert runner._writer is mock_writer
                        mock_writer_class.assert_called_once_with(
                            catalog=mock_catalog, symbol="BTC-USD"
                        )

    # =========================================================================
    # Tests - Write Operations
    # =========================================================================

    def test_process_snapshot_writes_orderbook_when_persistence_enabled(self):
        """process_snapshot calls write_orderbook when persistence is enabled."""
        # GIVEN a runner with a mock writer
        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
        from src.features import FeatureExtractor, Labeler, StabilityScorer
        from src.ingest import OrderBook
        from src.model import OnlineClassifier

        runner.symbol = "BTC-USD"
        runner.order_book = OrderBook(depth=3)
        runner.feature_extractor = FeatureExtractor(volatility_window=50)
        runner.stability_scorer = StabilityScorer()
        runner.labeler = Labeler(delta_ms=500, threshold_pct=0.01)
        runner.classifier = OnlineClassifier(learning_rate=0.01)
        runner._writer = MagicMock()
        runner._trade_buffer = None

        snapshot = self.make_snapshot()

        # WHEN we process the snapshot
        runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN write_orderbook was called
        runner._writer.write_orderbook.assert_called_once_with(snapshot)

    def test_process_snapshot_writes_features_when_persistence_enabled(self):
        """process_snapshot calls write_features when persistence is enabled."""
        # GIVEN a runner with a mock writer
        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
        from src.features import FeatureExtractor, Labeler, StabilityScorer
        from src.ingest import OrderBook
        from src.model import OnlineClassifier

        runner.symbol = "BTC-USD"
        runner.order_book = OrderBook(depth=3)
        runner.feature_extractor = FeatureExtractor(volatility_window=50)
        runner.stability_scorer = StabilityScorer()
        runner.labeler = Labeler(delta_ms=500, threshold_pct=0.01)
        runner.classifier = OnlineClassifier(learning_rate=0.01)
        runner._writer = MagicMock()
        runner._trade_buffer = None

        snapshot = self.make_snapshot()

        # WHEN we process the snapshot
        runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN write_features was called
        runner._writer.write_features.assert_called_once()
        written_features = runner._writer.write_features.call_args[0][0]
        assert written_features.spread_bps > 0

    def test_process_snapshot_does_not_write_when_persistence_disabled(self):
        """process_snapshot does not write when persistence is disabled."""
        # GIVEN a runner without a writer
        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
        from src.features import FeatureExtractor, Labeler, StabilityScorer
        from src.ingest import OrderBook
        from src.model import OnlineClassifier

        runner.symbol = "BTC-USD"
        runner.order_book = OrderBook(depth=3)
        runner.feature_extractor = FeatureExtractor(volatility_window=50)
        runner.stability_scorer = StabilityScorer()
        runner.labeler = Labeler(delta_ms=500, threshold_pct=0.01)
        runner.classifier = OnlineClassifier(learning_rate=0.01)
        runner._writer = None
        runner._trade_buffer = None

        snapshot = self.make_snapshot()

        # WHEN we process the snapshot (should not raise)
        result = runner.process_snapshot(snapshot, timestamp_ms=1000.0)

        # THEN result is still valid
        assert result.features is not None

    def test_on_trade_writes_trade_when_persistence_enabled(self):
        """_on_trade callback writes trade to DataWriter."""
        # GIVEN a runner with a mock writer
        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
        runner._writer = MagicMock()

        trade = self.make_trade()

        # WHEN _on_trade is called
        runner._on_trade(trade)

        # THEN write_trade was called
        runner._writer.write_trade.assert_called_once_with(trade)

    def test_on_trade_does_nothing_when_persistence_disabled(self):
        """_on_trade does nothing when persistence is disabled."""
        # GIVEN a runner without a writer
        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
        runner._writer = None

        trade = self.make_trade()

        # WHEN _on_trade is called (should not raise)
        runner._on_trade(trade)

        # THEN no exception is raised (implicit pass)

    # =========================================================================
    # Tests - Graceful Shutdown
    # =========================================================================

    def test_stop_flushes_writer_when_persistence_enabled(self):
        """stop() calls writer.close() for graceful shutdown."""
        # GIVEN a runner with a mock writer
        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
        runner._writer = MagicMock()
        runner._loop = None
        runner.ws_client = MagicMock()

        # WHEN we call stop
        runner.stop()

        # THEN writer.close() was called
        runner._writer.close.assert_called_once()

    def test_stop_works_when_persistence_disabled(self):
        """stop() works without error when persistence is disabled."""
        # GIVEN a runner without a writer
        runner = QuoteWatchRunner.__new__(QuoteWatchRunner)
        runner._writer = None
        runner._loop = None
        runner.ws_client = MagicMock()

        # WHEN we call stop (should not raise)
        runner.stop()

        # THEN no exception is raised (implicit pass)
