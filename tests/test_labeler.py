"""Tests for Labeler."""

from src.features.extractor import FeatureSnapshot
from src.features.labeler import Labeler


class TestLabeler:
    """Tests for Labeler class."""

    def _make_features(self, timestamp: str | None = None) -> FeatureSnapshot:
        """Helper to create a FeatureSnapshot."""
        return FeatureSnapshot(
            spread_bps=10.0,
            imbalance=0.0,
            depth=5.0,
            volatility=1.0,
            timestamp=timestamp,
        )

    def test_initial_buffer_empty(self):
        """Buffer starts empty."""
        labeler = Labeler(delta_ms=500)

        assert labeler.buffer_size == 0

    def test_add_sample_buffers(self):
        """Adding sample increases buffer size."""
        labeler = Labeler(delta_ms=500)
        features = self._make_features()

        labeler.add_sample(1000, 100.0, features)

        assert labeler.buffer_size == 1

    def test_no_label_before_delta(self):
        """No label emitted before delta time passes."""
        labeler = Labeler(delta_ms=500)
        features = self._make_features()

        # Add at t=1000
        labeler.add_sample(1000, 100.0, features)

        # Add at t=1400 (only 400ms later)
        result = labeler.add_sample(1400, 100.0, features)

        assert result is None
        assert labeler.buffer_size == 2

    def test_label_after_delta(self):
        """Label emitted after delta time passes."""
        labeler = Labeler(delta_ms=500)
        features = self._make_features()

        # Add at t=1000
        labeler.add_sample(1000, 100.0, features)

        # Add at t=1500 (exactly 500ms later)
        result = labeler.add_sample(1500, 100.0, features)

        assert result is not None
        assert labeler.buffer_size == 1  # Second sample still in buffer

    def test_label_no_change(self):
        """Label is 0 when price doesn't change."""
        labeler = Labeler(delta_ms=500, threshold_pct=0.01)
        features = self._make_features()

        labeler.add_sample(1000, 100.0, features)
        result = labeler.add_sample(1500, 100.0, features)

        assert result is not None
        assert result.label == 0
        assert result.mid_price_t == 100.0
        assert result.mid_price_t_delta == 100.0

    def test_label_price_increase(self):
        """Label is 1 when price increases above threshold."""
        labeler = Labeler(delta_ms=500, threshold_pct=0.01)
        features = self._make_features()

        labeler.add_sample(1000, 100.0, features)
        # Price change of 0.02% (above 0.01% threshold)
        result = labeler.add_sample(1500, 100.02, features)

        assert result is not None
        assert result.label == 1

    def test_label_price_decrease(self):
        """Label is 1 when price decreases above threshold."""
        labeler = Labeler(delta_ms=500, threshold_pct=0.01)
        features = self._make_features()

        labeler.add_sample(1000, 100.0, features)
        # Price change of -0.02% (above 0.01% threshold)
        result = labeler.add_sample(1500, 99.98, features)

        assert result is not None
        assert result.label == 1

    def test_prediction_tracking(self):
        """Prediction at time t is stored in labeled sample."""
        labeler = Labeler(delta_ms=500)
        features = self._make_features()

        labeler.add_sample(1000, 100.0, features, prediction=1)
        result = labeler.add_sample(1500, 100.0, features)

        assert result is not None
        assert result.prediction_at_t == 1

    def test_flush_clears_buffer(self):
        """Flush clears all buffered samples."""
        labeler = Labeler(delta_ms=500)
        features = self._make_features()

        labeler.add_sample(1000, 100.0, features)
        labeler.add_sample(1100, 100.0, features)
        assert labeler.buffer_size == 2

        labeler.flush()

        assert labeler.buffer_size == 0

    def test_max_buffer_size(self):
        """Buffer respects max size limit."""
        labeler = Labeler(delta_ms=500, max_buffer_size=3)
        features = self._make_features()

        for i in range(5):
            labeler.add_sample(1000 + i * 100, 100.0, features)

        # Buffer should be capped at 3
        assert labeler.buffer_size == 3

    def test_properties(self):
        """Properties return configured values."""
        labeler = Labeler(delta_ms=500, threshold_pct=0.01)

        assert labeler.delta_ms == 500
        assert labeler.threshold_pct == 0.01
