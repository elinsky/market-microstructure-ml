"""Main entry point for QuoteWatch live system."""

import asyncio
import logging
import signal
import sys
import threading
from typing import Optional

from src.dashboard.app import create_app, update_shared_state
from src.ingest import CoinbaseWebSocketClient, OrderBook

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class QuoteWatchRunner:
    """Orchestrates WebSocket client, order book, and dashboard."""

    def __init__(self, symbol: str = "BTC-USD", dash_port: int = 8050):
        """Initialize the runner.

        Args:
            symbol: Trading pair to track.
            dash_port: Port for the Dash server.
        """
        self.symbol = symbol
        self.dash_port = dash_port

        self.order_book = OrderBook(depth=3)
        self.ws_client = CoinbaseWebSocketClient(
            order_book=self.order_book,
            symbol=symbol,
            on_update=self._on_order_book_update,
        )
        self.dash_app = create_app()
        self._dash_thread: Optional[threading.Thread] = None

    def _on_order_book_update(self) -> None:
        """Callback when order book is updated."""
        snapshot = self.order_book.get_snapshot()

        update_shared_state(
            best_bid=float(snapshot.best_bid) if snapshot.best_bid else None,
            best_ask=float(snapshot.best_ask) if snapshot.best_ask else None,
            mid_price=float(snapshot.mid_price) if snapshot.mid_price else None,
            spread=float(snapshot.spread) if snapshot.spread else None,
            timestamp=snapshot.timestamp,
        )

    def _run_dash_server(self) -> None:
        """Run Dash server in a separate thread."""
        # Suppress Werkzeug logs
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.WARNING)

        self.dash_app.run(
            host="0.0.0.0",
            port=self.dash_port,
            debug=False,
            use_reloader=False,
        )

    async def run(self) -> None:
        """Run the complete system."""
        # Start Dash in background thread
        self._dash_thread = threading.Thread(target=self._run_dash_server, daemon=True)
        self._dash_thread.start()
        logger.info(f"Dashboard running at http://localhost:{self.dash_port}")

        # Run WebSocket client (main async loop)
        logger.info(f"Starting WebSocket client for {self.symbol}...")
        await self.ws_client.start()

    async def stop(self) -> None:
        """Stop all components."""
        logger.info("Shutting down...")
        await self.ws_client.stop()


async def main() -> None:
    """Main async entry point."""
    runner = QuoteWatchRunner(symbol="BTC-USD")

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(runner.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await runner.run()
    except asyncio.CancelledError:
        pass
    finally:
        await runner.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
        sys.exit(0)
