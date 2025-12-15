"""Tests for prediction display state logic."""

from src.dashboard.app import (
    AccuracyDisplayState,
    ImbalanceStyle,
    PredictionDisplayState,
    get_accuracy_display_state,
    get_imbalance_style,
    get_prediction_display_state,
)


class TestGetPredictionDisplayState:
    """Tests for get_prediction_display_state function."""

    # =========================================================================
    # Tests - Model Ready State
    # =========================================================================

    def test_model_ready_with_low_probability_shows_green(self):
        """Low probability (<30%) shows green border."""
        # GIVEN model is ready with low prediction probability
        prediction_proba = 0.20  # 20%

        # WHEN we get the display state
        state = get_prediction_display_state(
            prediction_proba=prediction_proba,
            model_ready=True,
            model_samples=100,
            model_ready_pct=100.0,
        )

        # THEN border is green and value shows percentage
        assert state.value == "20%"
        assert state.label == "Price Move"
        assert state.subtitle == "in next 500ms"
        assert state.border_color == "#28a745"  # Green

    def test_model_ready_with_medium_probability_shows_yellow(self):
        """Medium probability (30-59%) shows yellow border."""
        # GIVEN model is ready with medium prediction probability
        prediction_proba = 0.45  # 45%

        # WHEN we get the display state
        state = get_prediction_display_state(
            prediction_proba=prediction_proba,
            model_ready=True,
            model_samples=100,
            model_ready_pct=100.0,
        )

        # THEN border is yellow
        assert state.value == "45%"
        assert state.border_color == "#ffc107"  # Yellow

    def test_model_ready_with_high_probability_shows_red(self):
        """High probability (>=60%) shows red border."""
        # GIVEN model is ready with high prediction probability
        prediction_proba = 0.75  # 75%

        # WHEN we get the display state
        state = get_prediction_display_state(
            prediction_proba=prediction_proba,
            model_ready=True,
            model_samples=100,
            model_ready_pct=100.0,
        )

        # THEN border is red
        assert state.value == "75%"
        assert state.border_color == "#dc3545"  # Red

    def test_model_ready_boundary_at_30_percent(self):
        """Exactly 30% prediction shows yellow (boundary test)."""
        # GIVEN model is ready with exactly 30% probability
        prediction_proba = 0.30

        # WHEN we get the display state
        state = get_prediction_display_state(
            prediction_proba=prediction_proba,
            model_ready=True,
            model_samples=100,
            model_ready_pct=100.0,
        )

        # THEN border is yellow (30% is not < 30%)
        assert state.border_color == "#ffc107"

    def test_model_ready_boundary_at_60_percent(self):
        """Exactly 60% prediction shows red (boundary test)."""
        # GIVEN model is ready with exactly 60% probability
        prediction_proba = 0.60

        # WHEN we get the display state
        state = get_prediction_display_state(
            prediction_proba=prediction_proba,
            model_ready=True,
            model_samples=100,
            model_ready_pct=100.0,
        )

        # THEN border is red (60% is not < 60%)
        assert state.border_color == "#dc3545"

    # =========================================================================
    # Tests - Training State
    # =========================================================================

    def test_training_state_shows_progress(self):
        """Model training shows progress percentage."""
        # GIVEN model is not ready but has samples
        model_samples = 50
        model_ready_pct = 50.0

        # WHEN we get the display state
        state = get_prediction_display_state(
            prediction_proba=None,
            model_ready=False,
            model_samples=model_samples,
            model_ready_pct=model_ready_pct,
        )

        # THEN shows training progress
        assert state.value == "50%"
        assert state.label == "Training..."
        assert state.subtitle == "50 samples"
        assert state.border_color == "#17a2b8"  # Blue

    def test_training_state_with_prediction_but_not_ready(self):
        """Model not ready shows training even if prediction available."""
        # GIVEN model is not ready but has a prediction
        prediction_proba = 0.5

        # WHEN we get the display state
        state = get_prediction_display_state(
            prediction_proba=prediction_proba,
            model_ready=False,
            model_samples=30,
            model_ready_pct=30.0,
        )

        # THEN shows training state (model_ready takes precedence)
        assert state.label == "Training..."
        assert state.border_color == "#17a2b8"

    # =========================================================================
    # Tests - Waiting State
    # =========================================================================

    def test_waiting_state_no_samples(self):
        """No samples shows waiting state."""
        # GIVEN no samples collected yet

        # WHEN we get the display state
        state = get_prediction_display_state(
            prediction_proba=None,
            model_ready=False,
            model_samples=0,
            model_ready_pct=0.0,
        )

        # THEN shows waiting state
        assert state.value == "--"
        assert state.label == "Waiting..."
        assert state.subtitle == "Collecting data"
        assert state.border_color == "#444"

    # =========================================================================
    # Tests - Return Type
    # =========================================================================

    def test_returns_prediction_display_state(self):
        """Function returns PredictionDisplayState dataclass."""
        # GIVEN any inputs

        # WHEN we get the display state
        state = get_prediction_display_state(
            prediction_proba=None,
            model_ready=False,
            model_samples=0,
            model_ready_pct=0.0,
        )

        # THEN returns PredictionDisplayState
        assert isinstance(state, PredictionDisplayState)


class TestGetImbalanceStyle:
    """Tests for get_imbalance_style function."""

    def test_positive_imbalance_shows_green(self):
        """Positive imbalance (>0.1) shows green for buying pressure."""
        # GIVEN a positive imbalance indicating buying pressure
        imbalance = 0.25

        # WHEN we get the style
        style = get_imbalance_style(imbalance)

        # THEN color is green
        assert style.color == "#28a745"

    def test_negative_imbalance_shows_red(self):
        """Negative imbalance (<-0.1) shows red for selling pressure."""
        # GIVEN a negative imbalance indicating selling pressure
        imbalance = -0.25

        # WHEN we get the style
        style = get_imbalance_style(imbalance)

        # THEN color is red
        assert style.color == "#dc3545"

    def test_neutral_imbalance_shows_white(self):
        """Neutral imbalance (between -0.1 and 0.1) shows white."""
        # GIVEN a neutral imbalance
        imbalance = 0.05

        # WHEN we get the style
        style = get_imbalance_style(imbalance)

        # THEN color is white
        assert style.color == "white"

    def test_none_imbalance_shows_white(self):
        """None imbalance shows white."""
        # GIVEN no imbalance data

        # WHEN we get the style
        style = get_imbalance_style(None)

        # THEN color is white
        assert style.color == "white"

    def test_boundary_at_positive_threshold(self):
        """Exactly 0.1 imbalance shows white (boundary test)."""
        # GIVEN imbalance at exactly the threshold
        imbalance = 0.1

        # WHEN we get the style
        style = get_imbalance_style(imbalance)

        # THEN color is white (0.1 is not > 0.1)
        assert style.color == "white"

    def test_boundary_at_negative_threshold(self):
        """Exactly -0.1 imbalance shows white (boundary test)."""
        # GIVEN imbalance at exactly the negative threshold
        imbalance = -0.1

        # WHEN we get the style
        style = get_imbalance_style(imbalance)

        # THEN color is white (-0.1 is not < -0.1)
        assert style.color == "white"

    def test_returns_imbalance_style(self):
        """Function returns ImbalanceStyle dataclass."""
        # GIVEN any input

        # WHEN we get the style
        style = get_imbalance_style(0.0)

        # THEN returns ImbalanceStyle
        assert isinstance(style, ImbalanceStyle)


class TestGetAccuracyDisplayState:
    """Tests for get_accuracy_display_state function."""

    def test_high_accuracy_shows_green(self):
        """High accuracy (>=60%) shows green."""
        # GIVEN high accuracy
        accuracy = 0.75

        # WHEN we get the display state
        state = get_accuracy_display_state(accuracy)

        # THEN color is green and value is formatted
        assert state.value == "75.0%"
        assert state.color == "#28a745"

    def test_medium_accuracy_shows_yellow(self):
        """Medium accuracy (50-59%) shows yellow."""
        # GIVEN medium accuracy
        accuracy = 0.55

        # WHEN we get the display state
        state = get_accuracy_display_state(accuracy)

        # THEN color is yellow
        assert state.value == "55.0%"
        assert state.color == "#ffc107"

    def test_low_accuracy_shows_red(self):
        """Low accuracy (<50%) shows red."""
        # GIVEN low accuracy
        accuracy = 0.40

        # WHEN we get the display state
        state = get_accuracy_display_state(accuracy)

        # THEN color is red
        assert state.value == "40.0%"
        assert state.color == "#dc3545"

    def test_none_accuracy_shows_placeholder(self):
        """None accuracy shows '--' in white."""
        # GIVEN no accuracy data

        # WHEN we get the display state
        state = get_accuracy_display_state(None)

        # THEN shows placeholder
        assert state.value == "--"
        assert state.color == "white"

    def test_boundary_at_60_percent(self):
        """Exactly 60% accuracy shows green (boundary test)."""
        # GIVEN accuracy at exactly 60%
        accuracy = 0.60

        # WHEN we get the display state
        state = get_accuracy_display_state(accuracy)

        # THEN color is green (60% is >= 60%)
        assert state.color == "#28a745"

    def test_boundary_at_50_percent(self):
        """Exactly 50% accuracy shows yellow (boundary test)."""
        # GIVEN accuracy at exactly 50%
        accuracy = 0.50

        # WHEN we get the display state
        state = get_accuracy_display_state(accuracy)

        # THEN color is yellow (50% is >= 50%)
        assert state.color == "#ffc107"

    def test_returns_accuracy_display_state(self):
        """Function returns AccuracyDisplayState dataclass."""
        # GIVEN any input

        # WHEN we get the display state
        state = get_accuracy_display_state(0.5)

        # THEN returns AccuracyDisplayState
        assert isinstance(state, AccuracyDisplayState)
