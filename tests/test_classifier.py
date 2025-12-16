"""Tests for OnlineClassifier and Prediction dataclass."""

from src.features.extractor import FeatureSnapshot
from src.model.classifier import OnlineClassifier, Prediction


class TestOnlineClassifier:
    """Tests for OnlineClassifier class."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

    def make_features(
        self,
        spread_bps: float = 10.0,
        imbalance: float = 0.0,
        depth: float = 5.0,
        volatility: float = 1.0,
    ) -> FeatureSnapshot:
        """Create a FeatureSnapshot with configurable values."""
        return FeatureSnapshot(
            spread_bps=spread_bps,
            imbalance=imbalance,
            depth=depth,
            volatility=volatility,
        )

    def make_classifier(self) -> OnlineClassifier:
        """Create a new OnlineClassifier."""
        return OnlineClassifier()

    def make_trained_classifier(self, samples_per_class: int = 50) -> OnlineClassifier:
        """Create a classifier trained with samples of each class."""
        classifier = self.make_classifier()
        for i in range(samples_per_class):
            classifier.partial_fit(self.make_features(spread_bps=i), 0)
            classifier.partial_fit(self.make_features(spread_bps=i + 100), 1)
        return classifier

    # =========================================================================
    # Tests - Initial State
    # =========================================================================

    def test_initial_sample_count_is_zero(self):
        """New classifier has zero samples."""
        # GIVEN a new classifier
        classifier = self.make_classifier()

        # WHEN we check sample count (no action)
        count = classifier.sample_count

        # THEN count is 0
        assert count == 0

    def test_initial_state_not_ready(self):
        """New classifier is not ready for predictions."""
        # GIVEN a new classifier
        classifier = self.make_classifier()

        # WHEN we check readiness (no action)
        ready = classifier.is_ready

        # THEN it's not ready
        assert ready is False

    # =========================================================================
    # Tests - Predictions Before Training
    # =========================================================================

    def test_predict_proba_returns_half_before_training(self):
        """Returns 0.5 (maximum uncertainty) before any training."""
        # GIVEN a new classifier and features
        classifier = self.make_classifier()
        features = self.make_features()

        # WHEN we predict probability
        proba = classifier.predict_proba(features)

        # THEN probability is 0.5
        assert proba == 0.5

    def test_predict_returns_one_before_training(self):
        """Returns 1 before training (proba=0.5 rounds to 1)."""
        # GIVEN a new classifier and features
        classifier = self.make_classifier()
        features = self.make_features()

        # WHEN we predict class
        pred = classifier.predict(features)

        # THEN prediction is 1 (proba >= 0.5)
        assert pred == 1

    # =========================================================================
    # Tests - Training (partial_fit)
    # =========================================================================

    def test_partial_fit_increments_sample_count(self):
        """partial_fit increases sample count by one."""
        # GIVEN a new classifier
        classifier = self.make_classifier()
        features = self.make_features()

        # WHEN we fit one sample
        classifier.partial_fit(features, 0)

        # THEN sample count is 1
        assert classifier.sample_count == 1

    def test_partial_fit_tracks_class_counts(self):
        """partial_fit tracks samples by class."""
        # GIVEN a classifier with samples of both classes
        classifier = self.make_classifier()
        features = self.make_features()
        classifier.partial_fit(features, 0)
        classifier.partial_fit(features, 1)
        classifier.partial_fit(features, 0)

        # WHEN we get stats (no action)
        stats = classifier.get_stats()

        # THEN class counts are correct
        assert stats.samples_no_change == 2
        assert stats.samples_change == 1

    def test_is_ready_after_min_samples_per_class(self):
        """Model is ready after MIN_SAMPLES_PER_CLASS of each class."""
        # GIVEN a classifier trained with enough samples
        classifier = self.make_classifier()
        for i in range(OnlineClassifier.MIN_SAMPLES_PER_CLASS):
            classifier.partial_fit(self.make_features(spread_bps=i), 0)
            classifier.partial_fit(self.make_features(spread_bps=i + 100), 1)

        # WHEN we check readiness (no action)
        ready = classifier.is_ready

        # THEN it's ready
        assert ready is True

    # =========================================================================
    # Tests - Predictions After Training
    # =========================================================================

    def test_predict_returns_valid_class_after_training(self):
        """predict returns 0 or 1 after training."""
        # GIVEN a trained classifier
        classifier = self.make_trained_classifier()

        # WHEN we predict
        pred = classifier.predict(self.make_features())

        # THEN prediction is 0 or 1
        assert pred in [0, 1]

    def test_predict_proba_in_valid_range_after_training(self):
        """predict_proba returns value in [0, 1] after training."""
        # GIVEN a trained classifier
        classifier = self.make_trained_classifier()

        # WHEN we predict probability
        proba = classifier.predict_proba(self.make_features())

        # THEN probability is in valid range
        assert 0.0 <= proba <= 1.0

    # =========================================================================
    # Tests - Accuracy Tracking
    # =========================================================================

    def test_record_prediction_tracks_accuracy(self):
        """record_prediction tracks prediction accuracy."""
        # GIVEN a classifier with recorded predictions
        classifier = self.make_classifier()
        classifier.record_prediction(1, 1)  # correct
        classifier.record_prediction(0, 0)  # correct
        classifier.record_prediction(1, 0)  # wrong
        # Add more to reach minimum for accuracy calculation
        for _ in range(10):
            classifier.record_prediction(1, 1)

        # WHEN we get stats (no action)
        stats = classifier.get_stats()

        # THEN accuracy is tracked and above 0.5
        assert stats.accuracy_recent is not None
        assert stats.accuracy_recent > 0.5

    # =========================================================================
    # Tests - Statistics
    # =========================================================================

    def test_get_stats_includes_feature_weights(self):
        """get_stats includes feature weights after training."""
        # GIVEN a trained classifier
        classifier = self.make_trained_classifier()

        # WHEN we get stats (no action)
        stats = classifier.get_stats()

        # THEN weights include all features
        assert "spread_bps" in stats.weights
        assert "imbalance" in stats.weights
        assert "depth" in stats.weights
        assert "volatility" in stats.weights

    def test_get_stats_shows_ready_percentage(self):
        """get_stats shows progress toward ready state."""
        # GIVEN a classifier with 50% of required samples
        classifier = self.make_classifier()
        for i in range(50):
            classifier.partial_fit(self.make_features(spread_bps=i), 0)
            classifier.partial_fit(self.make_features(spread_bps=i + 100), 1)

        # WHEN we get stats (no action)
        stats = classifier.get_stats()

        # THEN ready_pct is 50%
        assert stats.ready_pct == 50.0


class TestPrediction:
    """Tests for Prediction dataclass."""

    def test_prediction_has_required_fields(self):
        """Prediction dataclass has all required fields."""
        # GIVEN prediction data
        # WHEN we create a Prediction
        pred = Prediction(
            timestamp_ms=1704067200000,
            prediction=1,
            probability=0.75,
            label=1,
            labeled_at_ms=1704067200500,
        )

        # THEN all fields are accessible
        assert pred.timestamp_ms == 1704067200000
        assert pred.prediction == 1
        assert pred.probability == 0.75
        assert pred.label == 1
        assert pred.labeled_at_ms == 1704067200500

    def test_prediction_is_dataclass(self):
        """Prediction is a proper dataclass."""
        # GIVEN a Prediction
        pred = Prediction(
            timestamp_ms=1704067200000,
            prediction=0,
            probability=0.3,
            label=0,
            labeled_at_ms=1704067200500,
        )

        # WHEN we check it's a dataclass (no action)

        # THEN it's an instance of the dataclass
        from dataclasses import is_dataclass

        assert is_dataclass(pred)
