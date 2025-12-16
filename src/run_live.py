"""Main entry point for QuoteWatch live system."""

import asyncio
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass

from src.dashboard.app import create_app, update_shared_state
from src.features import FeatureExtractor, FeatureSnapshot, Labeler, StabilityScorer
from src.features.stability import StabilityScore
from src.ingest import CoinbaseWebSocketClient, OrderBook
from src.ingest.order_book import OrderBookSnapshot
from src.ingest.trade_buffer import Trade, TradeBuffer
from src.model import OnlineClassifier, Prediction
from src.model.classifier import ModelStats
from src.storage import DataWriter, create_tables, get_catalog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of processing an order book snapshot through the ML pipeline."""

    features: FeatureSnapshot | None
    stability: StabilityScore | None
    prediction_proba: float | None
    model_stats: ModelStats | None


class QuoteWatchRunner:
    """Orchestrates WebSocket client, order book, features, ML model, and dashboard."""

    def __init__(self, symbol: str = "BTC-USD"):
        """Initialize the runner.

        Args:
            symbol: Trading pair to track.
        """
        self._init_components(symbol)
        self._init_websocket(symbol)

    def _init_components(self, symbol: str) -> None:
        """Initialize pipeline components.

        Separated for testability - allows tests to mock persistence setup.

        Args:
            symbol: Trading pair to track.
        """
        self.symbol = symbol
        self.order_book = OrderBook(depth=10)
        self.feature_extractor = FeatureExtractor(volatility_window=50)
        self.stability_scorer = StabilityScorer()  # Keep as fallback

        # ML pipeline components
        self.labeler = Labeler(delta_ms=500, threshold_pct=0.01)
        self.classifier = OnlineClassifier(learning_rate=0.01)

        # Persistence components (optional)
        self._writer: DataWriter | None = None
        self._trade_buffer: TradeBuffer | None = None

        if os.environ.get("ENABLE_PERSISTENCE", "").lower() == "true":
            self._init_persistence(symbol)

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None

    def _init_persistence(self, symbol: str) -> None:
        """Initialize persistence layer (catalog, tables, writer).

        Args:
            symbol: Trading pair to track.
        """
        logger.info("Initializing persistence layer...")
        try:
            catalog = get_catalog()
            create_tables(catalog)
            self._writer = DataWriter(catalog=catalog, symbol=symbol)
            self._trade_buffer = TradeBuffer()
            logger.info("Persistence layer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize persistence: {e}")
            logger.warning("Continuing without persistence")
            self._writer = None
            self._trade_buffer = None

    def _init_websocket(self, symbol: str) -> None:
        """Initialize WebSocket client.

        Args:
            symbol: Trading pair to track.
        """
        self.ws_client = CoinbaseWebSocketClient(
            order_book=self.order_book,
            trade_buffer=self._trade_buffer,
            symbol=symbol,
            on_update=self._on_order_book_update,
            on_trade=self._on_trade if self._writer else None,
        )

    def process_snapshot(
        self, snapshot: OrderBookSnapshot, timestamp_ms: float
    ) -> PipelineResult:
        """Process an order book snapshot through the ML pipeline.

        Extracts features, computes stability score, runs ML prediction,
        and trains the model if a labeled sample is available.

        Args:
            snapshot: Current order book snapshot.
            timestamp_ms: Current timestamp in milliseconds.

        Returns:
            PipelineResult containing features, stability, prediction, and model stats.
        """
        # Write order book to persistence (if enabled)
        if self._writer is not None:
            self._writer.write_orderbook(snapshot)

        # Extract features
        features = self.feature_extractor.compute(snapshot)

        # Compute stability score (heuristic fallback)
        stability = None
        if features is not None:
            stability = self.stability_scorer.score(features)

        # ML pipeline: labeling and training
        prediction_proba = None
        model_stats = None

        if features is not None and snapshot.mid_price is not None:
            mid_price = float(snapshot.mid_price)

            # Get prediction for current features (before adding sample)
            prediction_proba = self.classifier.predict_proba(features)
            current_prediction = self.classifier.predict(features)

            # Write features to persistence (if enabled)
            if self._writer is not None:
                self._writer.write_features(features)

            # Add sample to labeler with current prediction and probability
            labeled_sample = self.labeler.add_sample(
                timestamp_ms,
                mid_price,
                features,
                prediction=current_prediction,
                probability=prediction_proba,
            )

            # If we got a labeled sample, train the model and record accuracy
            if labeled_sample is not None:
                self.classifier.partial_fit(
                    labeled_sample.features, labeled_sample.label
                )

                # Record prediction accuracy if we had a prediction at time t
                if labeled_sample.prediction_at_t is not None:
                    self.classifier.record_prediction(
                        labeled_sample.prediction_at_t, labeled_sample.label
                    )

                # Write prediction with label to persistence (if enabled)
                if self._writer is not None:
                    prediction = Prediction(
                        timestamp_ms=int(labeled_sample.features.timestamp_ms or 0),
                        prediction=labeled_sample.prediction_at_t or 0,
                        probability=labeled_sample.probability_at_t or 0.5,
                        label=labeled_sample.label,
                        labeled_at_ms=int(timestamp_ms),
                    )
                    self._writer.write_prediction(prediction)

            # Get model statistics
            model_stats = self.classifier.get_stats()

        return PipelineResult(
            features=features,
            stability=stability,
            prediction_proba=prediction_proba,
            model_stats=model_stats,
        )

    def _on_trade(self, trade: Trade) -> None:
        """Callback when a trade is received.

        Args:
            trade: The trade that was received.
        """
        if self._writer is not None:
            self._writer.write_trade(trade)

    def _on_order_book_update(self) -> None:
        """Callback when order book is updated."""
        snapshot = self.order_book.get_snapshot()
        timestamp_ms = time.time() * 1000

        # Run ML pipeline
        result = self.process_snapshot(snapshot, timestamp_ms)

        # Update dashboard state
        features = result.features
        stability = result.stability
        model_stats = result.model_stats

        update_shared_state(
            best_bid=float(snapshot.best_bid) if snapshot.best_bid else None,
            best_ask=float(snapshot.best_ask) if snapshot.best_ask else None,
            mid_price=float(snapshot.mid_price) if snapshot.mid_price else None,
            spread=float(snapshot.spread) if snapshot.spread else None,
            timestamp=snapshot.timestamp,
            # Feature data
            spread_bps=features.spread_bps if features else None,
            imbalance=features.imbalance if features else None,
            depth=features.depth if features else None,
            volatility=features.volatility if features else None,
            # Stability data (heuristic)
            stability_score=stability.score if stability else None,
            stability_category=stability.category if stability else None,
            stability_color=stability.color if stability else None,
            # ML prediction data
            prediction_proba=result.prediction_proba,
            model_ready=model_stats.is_ready if model_stats else False,
            model_samples_total=model_stats.samples_total if model_stats else 0,
            model_samples_no_change=model_stats.samples_no_change if model_stats else 0,
            model_samples_change=model_stats.samples_change if model_stats else 0,
            model_ready_pct=model_stats.ready_pct if model_stats else 0.0,
            model_accuracy=model_stats.accuracy_recent if model_stats else None,
            model_weights=model_stats.weights if model_stats else None,
        )

    def _run_async_loop(self) -> None:
        """Run the async event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self.ws_client.start())
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self._loop.close()

    def start_background(self) -> None:
        """Start WebSocket client in background thread."""
        logger.info(f"Starting WebSocket client for {self.symbol} in background...")
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the WebSocket client and flush persistence."""
        logger.info("Shutting down...")

        # Flush and close DataWriter (if enabled)
        if self._writer is not None:
            logger.info("Flushing data writer...")
            self._writer.close()

        # Stop WebSocket client
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.ws_client.stop(), self._loop)


# Create Dash app
dash_app = create_app()

# Expose Flask server for Gunicorn
server = dash_app.server

# Global runner instance
_runner: QuoteWatchRunner | None = None


def start_websocket_client() -> None:
    """Start the WebSocket client (called once on app startup)."""
    global _runner
    if _runner is None:
        _runner = QuoteWatchRunner(symbol="BTC-USD")
        _runner.start_background()


# Start WebSocket client when module is imported (for Gunicorn)
start_websocket_client()


def handle_shutdown(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    if _runner:
        _runner.stop()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


async def main() -> None:
    """Main async entry point for local development."""
    port = int(os.environ.get("PORT", 8050))

    # Suppress Werkzeug logs
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    logger.info(f"Dashboard running at http://localhost:{port}")

    # Run Dash dev server (WebSocket already started via module import)
    dash_app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
        sys.exit(0)
