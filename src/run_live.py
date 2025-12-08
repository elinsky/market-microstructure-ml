"""Main entry point for QuoteWatch live system."""

import asyncio
import logging
import os
import signal
import sys
import threading
from typing import Optional

from src.dashboard.app import create_app, update_shared_state
from src.features import FeatureExtractor, StabilityScorer
from src.ingest import CoinbaseWebSocketClient, OrderBook

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class QuoteWatchRunner:
    """Orchestrates WebSocket client, order book, features, and dashboard."""

    def __init__(self, symbol: str = "BTC-USD"):
        """Initialize the runner.

        Args:
            symbol: Trading pair to track.
        """
        self.symbol = symbol
        self.order_book = OrderBook(depth=3)
        self.feature_extractor = FeatureExtractor(volatility_window=50)
        self.stability_scorer = StabilityScorer()
        self.ws_client = CoinbaseWebSocketClient(
            order_book=self.order_book,
            symbol=symbol,
            on_update=self._on_order_book_update,
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def _on_order_book_update(self) -> None:
        """Callback when order book is updated."""
        snapshot = self.order_book.get_snapshot()

        # Extract features
        features = self.feature_extractor.compute(snapshot)

        # Compute stability score
        stability = None
        if features is not None:
            stability = self.stability_scorer.score(features)

        # Update dashboard state
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
            # Stability data
            stability_score=stability.score if stability else None,
            stability_category=stability.category if stability else None,
            stability_color=stability.color if stability else None,
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
        """Stop the WebSocket client."""
        logger.info("Shutting down WebSocket client...")
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.ws_client.stop(), self._loop)


# Create Dash app
dash_app = create_app()

# Expose Flask server for Gunicorn
server = dash_app.server

# Global runner instance
_runner: Optional[QuoteWatchRunner] = None


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
