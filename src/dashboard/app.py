"""Plotly Dash application for live price display."""

from collections import deque
from dataclasses import dataclass
from typing import Any

from dash import Dash, Input, Output, dcc, html

# Shared state updated by the WebSocket client
_shared_state: dict[str, Any] = {
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
    # Stability state (heuristic - will be replaced by ML)
    "stability_score": None,
    "stability_category": None,
    "stability_color": None,
    # ML prediction state
    "prediction_proba": None,  # 0.0 to 1.0
    "model_ready": False,
    "model_samples_total": 0,
    "model_samples_no_change": 0,
    "model_samples_change": 0,
    "model_ready_pct": 0.0,
    "model_accuracy": None,
    "model_weights": None,  # Dict of feature -> weight
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
_candle_history: deque[OHLCCandle] = deque(maxlen=MAX_CANDLES)
_current_candle: OHLCCandle | None = None
_tick_count: int = 0


def update_shared_state(
    best_bid: float | None,
    best_ask: float | None,
    mid_price: float | None,
    spread: float | None,
    timestamp: str | None,
    spread_bps: float | None = None,
    imbalance: float | None = None,
    depth: float | None = None,
    volatility: float | None = None,
    stability_score: float | None = None,
    stability_category: str | None = None,
    stability_color: str | None = None,
    # ML prediction fields
    prediction_proba: float | None = None,
    model_ready: bool = False,
    model_samples_total: int = 0,
    model_samples_no_change: int = 0,
    model_samples_change: int = 0,
    model_ready_pct: float = 0.0,
    model_accuracy: float | None = None,
    model_weights: dict[str, float] | None = None,
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
        prediction_proba: ML prediction probability (0.0 to 1.0).
        model_ready: Whether model has enough training data.
        model_samples_total: Total training samples seen.
        model_samples_no_change: Samples with label 0.
        model_samples_change: Samples with label 1.
        model_ready_pct: Percentage to ready state (0-100).
        model_accuracy: Recent prediction accuracy.
        model_weights: Feature weights from model.
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

    # ML prediction state
    _shared_state["prediction_proba"] = prediction_proba
    _shared_state["model_ready"] = model_ready
    _shared_state["model_samples_total"] = model_samples_total
    _shared_state["model_samples_no_change"] = model_samples_no_change
    _shared_state["model_samples_change"] = model_samples_change
    _shared_state["model_ready_pct"] = model_ready_pct
    _shared_state["model_accuracy"] = model_accuracy
    _shared_state["model_weights"] = model_weights

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

    # Mobile-responsive CSS
    app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            /* Mobile-responsive styles */
            @media (max-width: 768px) {
                .price-cards {
                    flex-direction: column !important;
                }
                .price-cards > div {
                    margin: 5px 10px !important;
                }
                .metrics-row {
                    flex-wrap: wrap !important;
                }
                .metrics-row > div {
                    flex: 1 1 45% !important;
                    margin-bottom: 10px !important;
                }
                .model-insights-row {
                    flex-direction: column !important;
                }
                .model-insights-row > div {
                    border-left: none !important;
                    border-right: none !important;
                    border-bottom: 1px solid #333 !important;
                    padding: 10px 0 !important;
                    margin-bottom: 10px !important;
                }
                .model-insights-row > div:last-child {
                    border-bottom: none !important;
                }
                h1 {
                    font-size: 1.5rem !important;
                }
                h2 {
                    font-size: 1.2rem !important;
                }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

    app.layout = html.Div(
        [
            html.H1("QuoteWatch - BTC-USD Live", style={"textAlign": "center"}),
            # ML Prediction Indicator (prominent)
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                id="prediction-value",
                                children="--",
                                style={
                                    "fontSize": "42px",
                                    "fontWeight": "bold",
                                    "lineHeight": "1",
                                },
                            ),
                            html.Div(
                                id="prediction-label",
                                children="Loading...",
                                style={
                                    "fontSize": "14px",
                                    "marginTop": "5px",
                                    "fontWeight": "500",
                                },
                            ),
                        ],
                        id="prediction-indicator",
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
                        id="prediction-subtitle",
                        children="Price Change Probability",
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
                                        "Spread",
                                        style={"fontSize": "12px", "color": "#888"},
                                    ),
                                    html.Div(
                                        id="metric-spread",
                                        children="--",
                                        style={
                                            "fontSize": "18px",
                                            "fontWeight": "bold",
                                        },
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
                                        style={
                                            "fontSize": "18px",
                                            "fontWeight": "bold",
                                        },
                                    ),
                                ],
                                style={"flex": "1", "textAlign": "center"},
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Depth",
                                        style={"fontSize": "12px", "color": "#888"},
                                    ),
                                    html.Div(
                                        id="metric-depth",
                                        children="--",
                                        style={
                                            "fontSize": "18px",
                                            "fontWeight": "bold",
                                        },
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
                                        style={
                                            "fontSize": "18px",
                                            "fontWeight": "bold",
                                        },
                                    ),
                                ],
                                style={"flex": "1", "textAlign": "center"},
                            ),
                        ],
                        className="metrics-row",
                        style={"display": "flex", "justifyContent": "space-around"},
                    ),
                ],
                style={
                    "padding": "15px",
                    "backgroundColor": "#16213e",
                    "borderRadius": "10px",
                    "margin": "0 10px 20px 10px",
                },
            ),
            # Price cards
            html.Div(
                [
                    html.Div(
                        [
                            html.H3(
                                "Best Bid",
                                style={
                                    "color": "#28a745",
                                    "fontSize": "1rem",
                                    "margin": "0 0 5px 0",
                                },
                            ),
                            html.H2(
                                id="bid-price",
                                children="--",
                                style={"margin": "0", "fontSize": "1.3rem"},
                            ),
                        ],
                        style={
                            "flex": "1",
                            "textAlign": "center",
                            "padding": "15px",
                            "backgroundColor": "#1a1a2e",
                            "borderRadius": "10px",
                            "margin": "5px",
                            "minWidth": "100px",
                        },
                    ),
                    html.Div(
                        [
                            html.H3(
                                "Mid Price",
                                style={
                                    "color": "#ffc107",
                                    "fontSize": "1rem",
                                    "margin": "0 0 5px 0",
                                },
                            ),
                            html.H2(
                                id="mid-price",
                                children="--",
                                style={"margin": "0", "fontSize": "1.3rem"},
                            ),
                        ],
                        style={
                            "flex": "1",
                            "textAlign": "center",
                            "padding": "15px",
                            "backgroundColor": "#1a1a2e",
                            "borderRadius": "10px",
                            "margin": "5px",
                            "minWidth": "100px",
                        },
                    ),
                    html.Div(
                        [
                            html.H3(
                                "Best Ask",
                                style={
                                    "color": "#dc3545",
                                    "fontSize": "1rem",
                                    "margin": "0 0 5px 0",
                                },
                            ),
                            html.H2(
                                id="ask-price",
                                children="--",
                                style={"margin": "0", "fontSize": "1.3rem"},
                            ),
                        ],
                        style={
                            "flex": "1",
                            "textAlign": "center",
                            "padding": "15px",
                            "backgroundColor": "#1a1a2e",
                            "borderRadius": "10px",
                            "margin": "5px",
                            "minWidth": "100px",
                        },
                    ),
                ],
                className="price-cards",
                style={
                    "display": "flex",
                    "justifyContent": "center",
                    "flexWrap": "wrap",
                    "margin": "0 5px",
                },
            ),
            # Spread display
            html.Div(
                [
                    html.H4("Spread", style={"margin": "0 0 5px 0"}),
                    html.H3(id="spread-value", children="--", style={"margin": "0"}),
                ],
                style={
                    "textAlign": "center",
                    "padding": "10px 15px",
                    "backgroundColor": "#16213e",
                    "borderRadius": "10px",
                    "margin": "10px auto",
                    "maxWidth": "200px",
                },
            ),
            # Price history candlestick chart
            html.Div(
                [
                    html.H4(
                        "Price History (OHLC)",
                        style={"margin": "0 0 10px 0", "fontSize": "0.9rem"},
                    ),
                    dcc.Graph(
                        id="price-chart",
                        config={"displayModeBar": False},
                        style={"height": "200px"},
                    ),
                ],
                style={
                    "padding": "15px",
                    "backgroundColor": "#1a1a2e",
                    "borderRadius": "10px",
                    "margin": "10px",
                },
            ),
            # Model Insights Panel
            html.Div(
                [
                    html.H4(
                        "Model Insights",
                        style={"textAlign": "center", "marginBottom": "15px"},
                    ),
                    html.Div(
                        [
                            # Training Progress
                            html.Div(
                                [
                                    html.Div(
                                        "Training Progress",
                                        style={
                                            "fontSize": "12px",
                                            "color": "#888",
                                            "marginBottom": "8px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                id="training-progress-bar",
                                                style={
                                                    "height": "8px",
                                                    "backgroundColor": "#17a2b8",
                                                    "borderRadius": "4px",
                                                    "width": "0%",
                                                },
                                            ),
                                        ],
                                        style={
                                            "width": "100%",
                                            "backgroundColor": "#333",
                                            "borderRadius": "4px",
                                            "marginBottom": "5px",
                                        },
                                    ),
                                    html.Div(
                                        id="training-stats",
                                        children="Waiting for data...",
                                        style={"fontSize": "11px", "color": "#aaa"},
                                    ),
                                ],
                                style={"flex": "1", "padding": "0 15px"},
                            ),
                            # Accuracy
                            html.Div(
                                [
                                    html.Div(
                                        "Accuracy (last 100)",
                                        style={
                                            "fontSize": "12px",
                                            "color": "#888",
                                            "marginBottom": "8px",
                                        },
                                    ),
                                    html.Div(
                                        id="accuracy-value",
                                        children="--",
                                        style={
                                            "fontSize": "24px",
                                            "fontWeight": "bold",
                                        },
                                    ),
                                ],
                                style={
                                    "flex": "1",
                                    "textAlign": "center",
                                    "borderLeft": "1px solid #333",
                                    "borderRight": "1px solid #333",
                                    "padding": "0 15px",
                                },
                            ),
                            # Feature Weights
                            html.Div(
                                [
                                    html.Div(
                                        "Feature Weights",
                                        style={
                                            "fontSize": "12px",
                                            "color": "#888",
                                            "marginBottom": "8px",
                                        },
                                    ),
                                    dcc.Graph(
                                        id="weights-chart",
                                        config={"displayModeBar": False},
                                        style={"height": "80px"},
                                    ),
                                ],
                                style={
                                    "flex": "2",
                                    "padding": "0 15px",
                                    "minWidth": "200px",
                                },
                            ),
                        ],
                        className="model-insights-row",
                        style={
                            "display": "flex",
                            "alignItems": "flex-start",
                            "flexWrap": "wrap",
                        },
                    ),
                ],
                style={
                    "padding": "15px",
                    "backgroundColor": "#16213e",
                    "borderRadius": "10px",
                    "margin": "10px",
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
            "padding": "10px",
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
            Output("prediction-value", "children"),
            Output("prediction-label", "children"),
            Output("prediction-indicator", "style"),
            Output("prediction-subtitle", "children"),
            Output("metric-spread", "children"),
            Output("metric-imbalance", "children"),
            Output("metric-imbalance", "style"),
            Output("metric-depth", "children"),
            Output("metric-volatility", "children"),
            # Model Insights outputs
            Output("training-progress-bar", "style"),
            Output("training-stats", "children"),
            Output("accuracy-value", "children"),
            Output("accuracy-value", "style"),
            Output("weights-chart", "figure"),
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

        opens: list[float] = []
        highs: list[float] = []
        lows: list[float] = []
        closes: list[float] = []
        x_vals: list[int] = []
        y_range: list[float] | None = None

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

        # ML Prediction indicator
        prediction_proba = _shared_state["prediction_proba"]
        model_ready = _shared_state["model_ready"]
        model_samples = _shared_state["model_samples_total"]
        model_ready_pct = _shared_state["model_ready_pct"]

        # Determine what to display
        if model_ready and prediction_proba is not None:
            # Model is ready - show prediction percentage
            pred_pct = prediction_proba * 100
            prediction_value_str = f"{pred_pct:.0f}%"
            prediction_label_str = "Price Move"
            subtitle_str = "in next 500ms"

            # Color based on probability: low=green, medium=yellow, high=red
            if pred_pct < 30:
                border_color = "#28a745"  # Green - low probability
            elif pred_pct < 60:
                border_color = "#ffc107"  # Yellow - medium
            else:
                border_color = "#dc3545"  # Red - high probability
        elif model_samples > 0:
            # Model is training - show progress
            prediction_value_str = f"{model_ready_pct:.0f}%"
            prediction_label_str = "Training..."
            subtitle_str = f"{model_samples} samples"
            border_color = "#17a2b8"  # Blue - training
        else:
            # No data yet
            prediction_value_str = "--"
            prediction_label_str = "Waiting..."
            subtitle_str = "Collecting data"
            border_color = "#444"

        # Compute background color from border color
        if border_color != "#444":
            r = int(border_color[1:3], 16)
            g = int(border_color[3:5], 16)
            b = int(border_color[5:7], 16)
            bg_color = f"rgba({r}, {g}, {b}, 0.2)"
        else:
            bg_color = "#333"

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

        # Model Insights
        model_samples_total = _shared_state["model_samples_total"]
        model_samples_no_change = _shared_state["model_samples_no_change"]
        model_samples_change = _shared_state["model_samples_change"]
        model_ready_pct = _shared_state["model_ready_pct"]
        model_accuracy = _shared_state["model_accuracy"]
        model_weights = _shared_state["model_weights"]

        # Training progress bar style
        progress_bar_style = {
            "height": "8px",
            "backgroundColor": "#17a2b8" if model_ready_pct < 100 else "#28a745",
            "borderRadius": "4px",
            "width": f"{min(100, model_ready_pct):.0f}%",
            "transition": "width 0.3s ease",
        }

        # Training stats text
        if model_samples_total > 0:
            training_stats_str = (
                f"{model_samples_total} samples | "
                f"No change: {model_samples_no_change} | "
                f"Change: {model_samples_change}"
            )
        else:
            training_stats_str = "Waiting for data..."

        # Accuracy display
        if model_accuracy is not None:
            accuracy_str = f"{model_accuracy * 100:.1f}%"
            # Color based on accuracy
            if model_accuracy >= 0.6:
                accuracy_color = "#28a745"  # Green
            elif model_accuracy >= 0.5:
                accuracy_color = "#ffc107"  # Yellow
            else:
                accuracy_color = "#dc3545"  # Red
        else:
            accuracy_str = "--"
            accuracy_color = "white"

        accuracy_style = {
            "fontSize": "24px",
            "fontWeight": "bold",
            "color": accuracy_color,
        }

        # Feature weights chart
        if model_weights and any(v != 0 for v in model_weights.values()):
            feature_names = list(model_weights.keys())
            weights = list(model_weights.values())
            colors = ["#28a745" if w >= 0 else "#dc3545" for w in weights]

            weights_chart = {
                "data": [
                    {
                        "type": "bar",
                        "x": weights,
                        "y": feature_names,
                        "orientation": "h",
                        "marker": {"color": colors},
                    }
                ],
                "layout": {
                    "margin": {"l": 70, "r": 10, "t": 5, "b": 5},
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "xaxis": {
                        "showgrid": True,
                        "gridcolor": "rgba(255,255,255,0.1)",
                        "zeroline": True,
                        "zerolinecolor": "rgba(255,255,255,0.3)",
                        "tickfont": {"color": "#666", "size": 9},
                    },
                    "yaxis": {
                        "tickfont": {"color": "#aaa", "size": 9},
                    },
                    "height": 80,
                },
            }
        else:
            weights_chart = {
                "data": [],
                "layout": {
                    "margin": {"l": 10, "r": 10, "t": 5, "b": 5},
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "xaxis": {"visible": False},
                    "yaxis": {"visible": False},
                    "annotations": [
                        {
                            "text": "Training...",
                            "xref": "paper",
                            "yref": "paper",
                            "x": 0.5,
                            "y": 0.5,
                            "showarrow": False,
                            "font": {"color": "#666", "size": 12},
                        }
                    ],
                    "height": 80,
                },
            }

        return (
            bid_str,
            mid_str,
            ask_str,
            spread_str,
            ts_str,
            price_chart,
            prediction_value_str,
            prediction_label_str,
            indicator_style,
            subtitle_str,
            spread_bps_str,
            imbalance_str,
            imbalance_style,
            depth_str,
            volatility_str,
            # Model Insights
            progress_bar_style,
            training_stats_str,
            accuracy_str,
            accuracy_style,
            weights_chart,
        )

    return app
