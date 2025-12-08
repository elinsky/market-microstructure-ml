"""WebSocket client for Coinbase L2 order book data."""

import asyncio
import json
import logging
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from .order_book import OrderBook

logger = logging.getLogger(__name__)

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"


class CoinbaseWebSocketClient:
    """Async WebSocket client for Coinbase L2 channel.

    Connects to Coinbase, subscribes to L2 data, and updates an OrderBook.
    Includes basic reconnection logic on disconnect.
    """

    def __init__(
        self,
        order_book: OrderBook,
        symbol: str = "BTC-USD",
        on_update: Optional[Callable[[], None]] = None,
    ):
        """Initialize WebSocket client.

        Args:
            order_book: OrderBook instance to update with incoming data.
            symbol: Trading pair to subscribe to.
            on_update: Optional callback invoked after each update.
        """
        self.order_book = order_book
        self.symbol = symbol
        self.on_update = on_update
        self._running = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None

    async def start(self) -> None:
        """Start the WebSocket client with reconnection logic."""
        self._running = True
        retry_delay = 1.0
        max_retry_delay = 30.0

        while self._running:
            try:
                await self._connect_and_run()
                retry_delay = 1.0  # Reset on successful connection
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")

            if self._running:
                logger.info(f"Reconnecting in {retry_delay:.1f}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    async def stop(self) -> None:
        """Stop the WebSocket client."""
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _connect_and_run(self) -> None:
        """Connect to WebSocket and process messages."""
        # Coinbase L2 snapshots can be large (~1-2MB), increase limit
        async with websockets.connect(
            COINBASE_WS_URL, max_size=10 * 1024 * 1024
        ) as ws:
            self._ws = ws
            logger.info(f"Connected to {COINBASE_WS_URL}")

            # Subscribe to L2 channel
            subscribe_msg = {
                "type": "subscribe",
                "product_ids": [self.symbol],
                "channels": ["level2_batch"],
            }
            await ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to {self.symbol} L2 channel")

            # Process messages
            async for message in ws:
                await self._handle_message(message)

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message.

        Args:
            message: Raw JSON message from Coinbase.
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "snapshot":
                self.order_book.apply_snapshot(
                    bids=data.get("bids", []),
                    asks=data.get("asks", []),
                )
                logger.debug("Applied order book snapshot")

            elif msg_type == "l2update":
                self.order_book.apply_update(
                    changes=data.get("changes", []),
                    timestamp=data.get("time"),
                )

                if self.on_update:
                    self.on_update()

            elif msg_type == "subscriptions":
                logger.info(f"Subscription confirmed: {data.get('channels')}")

            elif msg_type == "error":
                logger.error(f"Coinbase error: {data.get('message')}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
