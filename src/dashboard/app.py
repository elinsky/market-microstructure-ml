"""Plotly Dash application for live price display."""

from collections import deque
from typing import Any, Deque, Dict, Optional

from dash import Dash, Input, Output, dcc, html

# Shared state updated by the WebSocket client
_shared_state: Dict[str, Any] = {
    "best_bid": None,
    "best_ask": None,
    "mid_price": None,
    "spread": None,
    "timestamp": None,
}

# Price history for sparkline
_price_history: Deque[float] = deque(maxlen=100)


def update_shared_state(
    best_bid: Optional[float],
    best_ask: Optional[float],
    mid_price: Optional[float],
    spread: Optional[float],
    timestamp: Optional[str],
) -> None:
    """Update shared state from WebSocket client.

    Args:
        best_bid: Current best bid price.
        best_ask: Current best ask price.
        mid_price: Current mid price.
        spread: Current spread.
        timestamp: Timestamp of the update.
    """
    _shared_state["best_bid"] = best_bid
    _shared_state["best_ask"] = best_ask
    _shared_state["mid_price"] = mid_price
    _shared_state["spread"] = spread
    _shared_state["timestamp"] = timestamp

    if mid_price is not None:
        _price_history.append(mid_price)


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
            # Price history sparkline
            html.Div(
                [
                    html.H4("Price History (last 100 ticks)"),
                    dcc.Graph(
                        id="price-sparkline",
                        config={"displayModeBar": False},
                        style={"height": "150px"},
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
            Output("price-sparkline", "figure"),
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

        # Sparkline figure
        prices = list(_price_history)
        sparkline = {
            "data": [
                {
                    "y": prices,
                    "type": "scatter",
                    "mode": "lines",
                    "line": {"color": "#ffc107", "width": 2},
                    "fill": "tozeroy",
                    "fillcolor": "rgba(255, 193, 7, 0.1)",
                }
            ],
            "layout": {
                "margin": {"l": 40, "r": 20, "t": 10, "b": 30},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "xaxis": {"showgrid": False, "showticklabels": False},
                "yaxis": {
                    "showgrid": True,
                    "gridcolor": "rgba(255,255,255,0.1)",
                    "tickformat": "$,.0f",
                    "tickfont": {"color": "#666"},
                },
            },
        }

        return bid_str, mid_str, ask_str, spread_str, ts_str, sparkline

    return app
