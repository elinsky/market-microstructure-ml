"""Plotly Dash application for live price display."""

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

from dash import Dash, Input, Output, dcc, html

# Shared state updated by the WebSocket client
_shared_state: Dict[str, Any] = {
    "best_bid": None,
    "best_ask": None,
    "mid_price": None,
    "spread": None,
    "timestamp": None,
    # Feature state
    "spread_bps": None,
    "imbalance": None,
    "depth": None,
    "volatility": None,
    # Stability state
    "stability_score": None,
    "stability_category": None,
    "stability_color": None,
}


@dataclass
class OHLCCandle:
    """Single OHLC candle aggregating multiple ticks."""

    open: float
    high: float
    low: float
    close: float
    tick_count: int = 1


# OHLC candle history (each candle = 10 ticks)
TICKS_PER_CANDLE = 10
MAX_CANDLES = 50
_candle_history: Deque[OHLCCandle] = deque(maxlen=MAX_CANDLES)
_current_candle: Optional[OHLCCandle] = None
_tick_count: int = 0


def update_shared_state(
    best_bid: Optional[float],
    best_ask: Optional[float],
    mid_price: Optional[float],
    spread: Optional[float],
    timestamp: Optional[str],
    spread_bps: Optional[float] = None,
    imbalance: Optional[float] = None,
    depth: Optional[float] = None,
    volatility: Optional[float] = None,
    stability_score: Optional[float] = None,
    stability_category: Optional[str] = None,
    stability_color: Optional[str] = None,
) -> None:
    """Update shared state from WebSocket client.

    Args:
        best_bid: Current best bid price.
        best_ask: Current best ask price.
        mid_price: Current mid price.
        spread: Current spread.
        timestamp: Timestamp of the update.
        spread_bps: Spread in basis points.
        imbalance: Bid-ask volume imbalance (-1 to 1).
        depth: Total order book depth.
        volatility: Price volatility.
        stability_score: Overall stability score (0-100).
        stability_category: STABLE, MODERATE, or UNSTABLE.
        stability_color: green, yellow, or red.
    """
    _shared_state["best_bid"] = best_bid
    _shared_state["best_ask"] = best_ask
    _shared_state["mid_price"] = mid_price
    _shared_state["spread"] = spread
    _shared_state["timestamp"] = timestamp
    _shared_state["spread_bps"] = spread_bps
    _shared_state["imbalance"] = imbalance
    _shared_state["depth"] = depth
    _shared_state["volatility"] = volatility
    _shared_state["stability_score"] = stability_score
    _shared_state["stability_category"] = stability_category
    _shared_state["stability_color"] = stability_color

    # Build OHLC candles from mid prices
    if mid_price is not None:
        _update_candles(mid_price)


def _update_candles(price: float) -> None:
    """Update OHLC candle history with new price tick."""
    global _current_candle, _tick_count

    if _current_candle is None:
        # Start new candle
        _current_candle = OHLCCandle(open=price, high=price, low=price, close=price)
        _tick_count = 1
    else:
        # Update current candle
        _current_candle.high = max(_current_candle.high, price)
        _current_candle.low = min(_current_candle.low, price)
        _current_candle.close = price
        _current_candle.tick_count += 1
        _tick_count += 1

    # Close candle after TICKS_PER_CANDLE ticks
    if _tick_count >= TICKS_PER_CANDLE:
        _candle_history.append(_current_candle)
        _current_candle = None
        _tick_count = 0


def create_app() -> Dash:
    """Create and configure the Dash application.

    Returns:
        Configured Dash app instance.
    """
    app = Dash(__name__)

    # Add health check endpoint to underlying Flask server
    @app.server.route("/health")
    def health():
        return "OK", 200

    app.layout = html.Div(
        [
            html.H1("QuoteWatch - BTC-USD Live", style={"textAlign": "center"}),
            # Stability Indicator (prominent)
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                id="stability-score",
                                children="--",
                                style={
                                    "fontSize": "48px",
                                    "fontWeight": "bold",
                                    "lineHeight": "1",
                                },
                            ),
                            html.Div(
                                id="stability-category",
                                children="LOADING",
                                style={
                                    "fontSize": "18px",
                                    "marginTop": "5px",
                                    "fontWeight": "500",
                                },
                            ),
                        ],
                        id="stability-indicator",
                        style={
                            "width": "140px",
                            "height": "140px",
                            "borderRadius": "50%",
                            "backgroundColor": "#333",
                            "display": "flex",
                            "flexDirection": "column",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "margin": "0 auto",
                            "border": "4px solid #444",
                        },
                    ),
                    html.Div(
                        "Quote Stability",
                        style={
                            "textAlign": "center",
                            "marginTop": "10px",
                            "fontSize": "14px",
                            "color": "#888",
                        },
                    ),
                ],
                style={
                    "padding": "20px",
                    "marginBottom": "20px",
                },
            ),
            # Market Microstructure Metrics
            html.Div(
                [
                    html.H4(
                        "Market Microstructure",
                        style={"textAlign": "center", "marginBottom": "15px"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        "Spread", style={"fontSize": "12px", "color": "#888"}
                                    ),
                                    html.Div(
                                        id="metric-spread",
                                        children="--",
                                        style={"fontSize": "18px", "fontWeight": "bold"},
                                    ),
                                ],
                                style={"flex": "1", "textAlign": "center"},
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Imbalance",
                                        style={"fontSize": "12px", "color": "#888"},
                                    ),
                                    html.Div(
                                        id="metric-imbalance",
                                        children="--",
                                        style={"fontSize": "18px", "fontWeight": "bold"},
                                    ),
                                ],
                                style={"flex": "1", "textAlign": "center"},
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Depth", style={"fontSize": "12px", "color": "#888"}
                                    ),
                                    html.Div(
                                        id="metric-depth",
                                        children="--",
                                        style={"fontSize": "18px", "fontWeight": "bold"},
                                    ),
                                ],
                                style={"flex": "1", "textAlign": "center"},
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Volatility",
                                        style={"fontSize": "12px", "color": "#888"},
                                    ),
                                    html.Div(
                                        id="metric-volatility",
                                        children="--",
                                        style={"fontSize": "18px", "fontWeight": "bold"},
                                    ),
                                ],
                                style={"flex": "1", "textAlign": "center"},
                            ),
                        ],
                        style={"display": "flex", "justifyContent": "space-around"},
                    ),
                ],
                style={
                    "padding": "15px",
                    "backgroundColor": "#16213e",
                    "borderRadius": "10px",
                    "margin": "0 20px 20px 20px",
                },
            ),
            # Price cards
            html.Div(
                [
                    html.Div(
                        [
                            html.H3("Best Bid", style={"color": "#28a745"}),
                            html.H2(id="bid-price", children="--"),
                        ],
                        style={
                            "flex": "1",
                            "textAlign": "center",
                            "padding": "20px",
                            "backgroundColor": "#1a1a2e",
                            "borderRadius": "10px",
                            "margin": "10px",
                        },
                    ),
                    html.Div(
                        [
                            html.H3("Mid Price", style={"color": "#ffc107"}),
                            html.H2(id="mid-price", children="--"),
                        ],
                        style={
                            "flex": "1",
                            "textAlign": "center",
                            "padding": "20px",
                            "backgroundColor": "#1a1a2e",
                            "borderRadius": "10px",
                            "margin": "10px",
                        },
                    ),
                    html.Div(
                        [
                            html.H3("Best Ask", style={"color": "#dc3545"}),
                            html.H2(id="ask-price", children="--"),
                        ],
                        style={
                            "flex": "1",
                            "textAlign": "center",
                            "padding": "20px",
                            "backgroundColor": "#1a1a2e",
                            "borderRadius": "10px",
                            "margin": "10px",
                        },
                    ),
                ],
                style={"display": "flex", "justifyContent": "center"},
            ),
            # Spread display
            html.Div(
                [
                    html.H4("Spread"),
                    html.H3(id="spread-value", children="--"),
                ],
                style={
                    "textAlign": "center",
                    "padding": "15px",
                    "backgroundColor": "#16213e",
                    "borderRadius": "10px",
                    "margin": "20px auto",
                    "maxWidth": "300px",
                },
            ),
            # Price history candlestick chart
            html.Div(
                [
                    html.H4("Price History (OHLC - 10 ticks per candle)"),
                    dcc.Graph(
                        id="price-chart",
                        config={"displayModeBar": False},
                        style={"height": "250px"},
                    ),
                ],
                style={
                    "padding": "20px",
                    "backgroundColor": "#1a1a2e",
                    "borderRadius": "10px",
                    "margin": "20px",
                },
            ),
            # Timestamp
            html.Div(
                id="timestamp",
                style={"textAlign": "center", "color": "#666", "marginTop": "20px"},
            ),
            # Auto-refresh interval (300ms)
            dcc.Interval(id="interval-component", interval=300, n_intervals=0),
        ],
        style={
            "fontFamily": "Arial, sans-serif",
            "backgroundColor": "#0f0f23",
            "color": "white",
            "minHeight": "100vh",
            "padding": "20px",
        },
    )

    @app.callback(
        [
            Output("bid-price", "children"),
            Output("mid-price", "children"),
            Output("ask-price", "children"),
            Output("spread-value", "children"),
            Output("timestamp", "children"),
            Output("price-chart", "figure"),
            Output("stability-score", "children"),
            Output("stability-category", "children"),
            Output("stability-indicator", "style"),
            Output("metric-spread", "children"),
            Output("metric-imbalance", "children"),
            Output("metric-imbalance", "style"),
            Output("metric-depth", "children"),
            Output("metric-volatility", "children"),
        ],
        [Input("interval-component", "n_intervals")],
    )
    def update_display(_n: int):
        """Update all display elements."""
        bid = _shared_state["best_bid"]
        ask = _shared_state["best_ask"]
        mid = _shared_state["mid_price"]
        spread = _shared_state["spread"]
        ts = _shared_state["timestamp"]

        bid_str = f"${bid:,.2f}" if bid else "--"
        ask_str = f"${ask:,.2f}" if ask else "--"
        mid_str = f"${mid:,.2f}" if mid else "--"
        spread_str = f"${spread:.2f}" if spread else "--"
        ts_str = f"Last update: {ts}" if ts else "Waiting for data..."

        # Build OHLC candlestick chart
        candles = list(_candle_history)
        # Include current in-progress candle if exists
        if _current_candle is not None:
            candles = candles + [_current_candle]

        if candles:
            opens = [c.open for c in candles]
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]
            closes = [c.close for c in candles]
            x_vals = list(range(len(candles)))

            # Calculate y-axis range with padding
            all_prices = highs + lows
            y_min = min(all_prices)
            y_max = max(all_prices)
            y_padding = (y_max - y_min) * 0.1 if y_max > y_min else 10
            y_range = [y_min - y_padding, y_max + y_padding]
        else:
            opens = highs = lows = closes = x_vals = []
            y_range = None

        price_chart = {
            "data": [
                {
                    "type": "candlestick",
                    "x": x_vals,
                    "open": opens,
                    "high": highs,
                    "low": lows,
                    "close": closes,
                    "increasing": {"line": {"color": "#28a745"}},
                    "decreasing": {"line": {"color": "#dc3545"}},
                }
            ],
            "layout": {
                "margin": {"l": 60, "r": 20, "t": 10, "b": 30},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "xaxis": {
                    "showgrid": False,
                    "showticklabels": False,
                    "rangeslider": {"visible": False},
                },
                "yaxis": {
                    "showgrid": True,
                    "gridcolor": "rgba(255,255,255,0.1)",
                    "tickformat": "$,.0f",
                    "tickfont": {"color": "#666"},
                    "range": y_range,
                    "autorange": False if y_range else True,
                },
            },
        }

        # Stability indicator
        stability_score = _shared_state["stability_score"]
        stability_category = _shared_state["stability_category"]
        stability_color = _shared_state["stability_color"]

        score_str = f"{stability_score:.0f}" if stability_score is not None else "--"
        category_str = stability_category if stability_category else "LOADING"

        # Map color names to actual colors
        color_map = {
            "green": "#28a745",
            "yellow": "#ffc107",
            "red": "#dc3545",
        }
        border_color = color_map.get(stability_color, "#444")
        bg_color = (
            f"rgba({int(border_color[1:3], 16)}, {int(border_color[3:5], 16)}, {int(border_color[5:7], 16)}, 0.2)"
            if stability_color in color_map
            else "#333"
        )

        indicator_style = {
            "width": "140px",
            "height": "140px",
            "borderRadius": "50%",
            "backgroundColor": bg_color,
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "margin": "0 auto",
            "border": f"4px solid {border_color}",
        }

        # Metrics
        spread_bps = _shared_state["spread_bps"]
        imbalance = _shared_state["imbalance"]
        depth = _shared_state["depth"]
        volatility = _shared_state["volatility"]

        spread_bps_str = f"{spread_bps:.2f} bps" if spread_bps is not None else "--"
        imbalance_str = f"{imbalance:+.2f}" if imbalance is not None else "--"
        depth_str = f"{depth:.2f}" if depth is not None else "--"
        volatility_str = f"{volatility:.2f} bps" if volatility is not None else "--"

        # Color imbalance based on direction
        imbalance_style = {"fontSize": "18px", "fontWeight": "bold"}
        if imbalance is not None:
            if imbalance > 0.1:
                imbalance_style["color"] = "#28a745"  # Green for buying pressure
            elif imbalance < -0.1:
                imbalance_style["color"] = "#dc3545"  # Red for selling pressure
            else:
                imbalance_style["color"] = "white"

        return (
            bid_str,
            mid_str,
            ask_str,
            spread_str,
            ts_str,
            price_chart,
            score_str,
            category_str,
            indicator_style,
            spread_bps_str,
            imbalance_str,
            imbalance_style,
            depth_str,
            volatility_str,
        )

    return app
