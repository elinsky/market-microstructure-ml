"""WebSocket client for Coinbase L2 order book and trade data."""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

import websockets
from websockets.exceptions import ConnectionClosed

from .order_book import OrderBook
from .trade_buffer import Trade, TradeBuffer

logger = logging.getLogger(__name__)

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"


class CoinbaseWebSocketClient:
    """Async WebSocket client for Coinbase L2 and matches channels.

    Connects to Coinbase, subscribes to L2 data and trades, and updates
    an OrderBook and optional TradeBuffer. Includes reconnection logic.
    """

    def __init__(
        self,
        order_book: OrderBook,
        trade_buffer: TradeBuffer | None = None,
        symbol: str = "BTC-USD",
        on_update: Callable[[], None] | None = None,
        on_trade: Callable[[Trade], None] | None = None,
    ):
        """Initialize WebSocket client.

        Args:
            order_book: OrderBook instance to update with incoming data.
            trade_buffer: Optional TradeBuffer for storing trades from matches.
            symbol: Trading pair to subscribe to.
            on_update: Optional callback invoked after each L2 update.
            on_trade: Optional callback invoked after each trade.
        """
        self.order_book = order_book
        self.trade_buffer = trade_buffer
        self.symbol = symbol
        self.on_update = on_update
        self.on_trade = on_trade
        self._running = False
        self._ws: websockets.ClientConnection | None = None

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
        async with websockets.connect(COINBASE_WS_URL, max_size=10 * 1024 * 1024) as ws:
            self._ws = ws
            logger.info(f"Connected to {COINBASE_WS_URL}")

            # Build channel list - always include L2, optionally matches
            channels = ["level2_batch"]
            if self.trade_buffer is not None:
                channels.append("matches")

            # Subscribe to channels
            subscribe_msg = {
                "type": "subscribe",
                "product_ids": [self.symbol],
                "channels": channels,
            }
            await ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to {self.symbol} channels: {channels}")

            # Process messages
            async for message in ws:
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                self.process_message(message)

    def process_message(self, message: str) -> None:
        """Process a raw JSON message from Coinbase.

        Parses the message and updates the order book accordingly.
        Handles snapshot, l2update, match, subscriptions, and error messages.

        Args:
            message: Raw JSON message string from Coinbase WebSocket.
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

            elif msg_type == "match":
                self._handle_match(data)

            elif msg_type == "subscriptions":
                logger.info(f"Subscription confirmed: {data.get('channels')}")

            elif msg_type == "error":
                logger.error(f"Coinbase error: {data.get('message')}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _handle_match(self, data: dict) -> None:
        """Handle a match (trade) message from Coinbase.

        Args:
            data: Parsed match message data.
        """
        if self.trade_buffer is None:
            return

        # Parse timestamp from ISO8601 to epoch milliseconds
        time_str = data.get("time", "")
        timestamp_ms = self._parse_timestamp_ms(time_str)

        # Create Trade object
        trade = Trade(
            trade_id=str(data.get("trade_id", "")),
            timestamp_ms=timestamp_ms,
            price=Decimal(data.get("price", "0")),
            size=Decimal(data.get("size", "0")),
            side=data.get("side", ""),
        )

        # Add to buffer
        self.trade_buffer.add_trade(trade)

        # Invoke callback if provided
        if self.on_trade:
            self.on_trade(trade)

    @staticmethod
    def _parse_timestamp_ms(iso_timestamp: str) -> int:
        """Parse ISO8601 timestamp to milliseconds since epoch.

        Args:
            iso_timestamp: ISO8601 timestamp string
                (e.g., "2024-01-01T12:00:00.123456Z").

        Returns:
            Milliseconds since Unix epoch.
        """
        if not iso_timestamp:
            return 0
        # Handle microsecond precision - truncate to milliseconds
        # Format: 2024-01-01T12:00:00.123456Z
        try:
            # Parse with microseconds
            dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            return 0
