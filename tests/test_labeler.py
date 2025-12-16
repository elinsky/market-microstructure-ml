"""Tests for Labeler."""

from src.features.extractor import FeatureSnapshot
from src.features.labeler import Labeler


class TestLabeler:
    """Tests for Labeler class."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

    def make_features(self, timestamp: str | None = None) -> FeatureSnapshot:
        """Create a default FeatureSnapshot for testing."""
        return FeatureSnapshot(
            spread_bps=10.0,
            imbalance=0.0,
            depth=5.0,
            volatility=1.0,
            timestamp=timestamp,
        )

    def make_labeler(
        self,
        delta_ms: int = 500,
        threshold_pct: float = 0.01,
        max_buffer_size: int = 100,
    ) -> Labeler:
        """Create a Labeler with configurable parameters."""
        return Labeler(
            delta_ms=delta_ms,
            threshold_pct=threshold_pct,
            max_buffer_size=max_buffer_size,
        )

    # =========================================================================
    # Tests
    # =========================================================================

    def test_buffer_starts_empty(self):
        """Buffer starts with zero samples."""
        # GIVEN a new labeler
        labeler = self.make_labeler()

        # WHEN we check the buffer size (no action)
        size = labeler.buffer_size

        # THEN buffer is empty
        assert size == 0

    def test_add_sample_increases_buffer_size(self):
        """Adding a sample increases buffer size by one."""
        # GIVEN a labeler and a feature snapshot
        labeler = self.make_labeler()
        features = self.make_features()

        # WHEN we add a sample
        labeler.add_sample(1000, 100.0, features)

        # THEN buffer size is 1
        assert labeler.buffer_size == 1

    def test_no_label_before_delta_elapsed(self):
        """No label emitted before delta time passes."""
        # GIVEN a labeler with delta=500ms and a sample at t=1000
        labeler = self.make_labeler(delta_ms=500)
        features = self.make_features()
        labeler.add_sample(1000, 100.0, features)

        # WHEN we add another sample at t=1400 (only 400ms later)
        result = labeler.add_sample(1400, 100.0, features)

        # THEN no label is emitted
        assert result is None
        assert labeler.buffer_size == 2

    def test_label_emitted_after_delta_elapsed(self):
        """Label emitted after delta time passes."""
        # GIVEN a labeler with delta=500ms and a sample at t=1000
        labeler = self.make_labeler(delta_ms=500)
        features = self.make_features()
        labeler.add_sample(1000, 100.0, features)

        # WHEN we add a sample at t=1500 (exactly 500ms later)
        result = labeler.add_sample(1500, 100.0, features)

        # THEN a labeled sample is emitted
        assert result is not None
        assert labeler.buffer_size == 1  # Second sample still buffered

    def test_label_zero_when_price_unchanged(self):
        """Label is 0 when price doesn't change beyond threshold."""
        # GIVEN a labeler with 0.01% threshold
        labeler = self.make_labeler(delta_ms=500, threshold_pct=0.01)
        features = self.make_features()
        labeler.add_sample(1000, 100.0, features)

        # WHEN price stays the same
        result = labeler.add_sample(1500, 100.0, features)

        # THEN label is 0 (no significant change)
        assert result is not None
        assert result.label == 0
        assert result.mid_price_t == 100.0
        assert result.mid_price_t_delta == 100.0

    def test_label_one_when_price_increases_above_threshold(self):
        """Label is 1 when price increases above threshold."""
        # GIVEN a labeler with 0.01% threshold
        labeler = self.make_labeler(delta_ms=500, threshold_pct=0.01)
        features = self.make_features()
        labeler.add_sample(1000, 100.0, features)

        # WHEN price increases by 0.02% (above threshold)
        result = labeler.add_sample(1500, 100.02, features)

        # THEN label is 1 (significant change)
        assert result is not None
        assert result.label == 1

    def test_label_one_when_price_decreases_above_threshold(self):
        """Label is 1 when price decreases above threshold."""
        # GIVEN a labeler with 0.01% threshold
        labeler = self.make_labeler(delta_ms=500, threshold_pct=0.01)
        features = self.make_features()
        labeler.add_sample(1000, 100.0, features)

        # WHEN price decreases by 0.02% (above threshold)
        result = labeler.add_sample(1500, 99.98, features)

        # THEN label is 1 (significant change)
        assert result is not None
        assert result.label == 1

    def test_prediction_stored_with_sample(self):
        """Prediction at time t is stored in labeled sample."""
        # GIVEN a labeler with a sample that includes a prediction
        labeler = self.make_labeler(delta_ms=500)
        features = self.make_features()
        labeler.add_sample(1000, 100.0, features, prediction=1)

        # WHEN the label is emitted
        result = labeler.add_sample(1500, 100.0, features)

        # THEN the prediction is included in the result
        assert result is not None
        assert result.prediction_at_t == 1

    def test_probability_stored_with_sample(self):
        """Probability at time t is stored in labeled sample."""
        # GIVEN a labeler with a sample that includes a probability
        labeler = self.make_labeler(delta_ms=500)
        features = self.make_features()
        labeler.add_sample(1000, 100.0, features, prediction=1, probability=0.75)

        # WHEN the label is emitted
        result = labeler.add_sample(1500, 100.0, features)

        # THEN the probability is included in the result
        assert result is not None
        assert result.probability_at_t == 0.75

    def test_probability_defaults_to_none(self):
        """Probability defaults to None when not provided."""
        # GIVEN a labeler with a sample without probability
        labeler = self.make_labeler(delta_ms=500)
        features = self.make_features()
        labeler.add_sample(1000, 100.0, features, prediction=1)

        # WHEN the label is emitted
        result = labeler.add_sample(1500, 100.0, features)

        # THEN the probability is None
        assert result is not None
        assert result.probability_at_t is None

    def test_flush_clears_buffer(self):
        """Flush clears all buffered samples."""
        # GIVEN a labeler with samples in the buffer
        labeler = self.make_labeler(delta_ms=500)
        features = self.make_features()
        labeler.add_sample(1000, 100.0, features)
        labeler.add_sample(1100, 100.0, features)
        assert labeler.buffer_size == 2

        # WHEN we flush
        labeler.flush()

        # THEN buffer is empty
        assert labeler.buffer_size == 0

    def test_buffer_respects_max_size(self):
        """Buffer respects configured max size limit."""
        # GIVEN a labeler with max_buffer_size=3
        labeler = self.make_labeler(delta_ms=500, max_buffer_size=3)
        features = self.make_features()

        # WHEN we add 5 samples
        for i in range(5):
            labeler.add_sample(1000 + i * 100, 100.0, features)

        # THEN buffer is capped at 3
        assert labeler.buffer_size == 3

    def test_properties_return_configured_values(self):
        """Properties return the configured values."""
        # GIVEN a labeler with specific config
        labeler = self.make_labeler(delta_ms=500, threshold_pct=0.01)

        # WHEN we access properties (no action)
        delta = labeler.delta_ms
        threshold = labeler.threshold_pct

        # THEN they match the config
        assert delta == 500
        assert threshold == 0.01
