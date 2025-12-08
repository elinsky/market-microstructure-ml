"""Tests for OnlineClassifier."""

import pytest

from src.features.extractor import FeatureSnapshot
from src.model.classifier import OnlineClassifier


class TestOnlineClassifier:
    """Tests for OnlineClassifier class."""

    def _make_features(
        self,
        spread_bps: float = 10.0,
        imbalance: float = 0.0,
        depth: float = 5.0,
        volatility: float = 1.0,
    ) -> FeatureSnapshot:
        """Helper to create a FeatureSnapshot."""
        return FeatureSnapshot(
            spread_bps=spread_bps,
            imbalance=imbalance,
            depth=depth,
            volatility=volatility,
        )

    def test_initial_state(self):
        """Classifier starts not ready with zero samples."""
        classifier = OnlineClassifier()

        assert classifier.sample_count == 0
        assert classifier.is_ready is False

    def test_predict_proba_before_fit(self):
        """Returns 0.5 before model is fitted."""
        classifier = OnlineClassifier()
        features = self._make_features()

        proba = classifier.predict_proba(features)

        assert proba == 0.5

    def test_predict_before_fit(self):
        """Returns 1 before model is fitted (proba=0.5 rounds to 1)."""
        classifier = OnlineClassifier()
        features = self._make_features()

        pred = classifier.predict(features)

        # predict returns 1 when proba >= 0.5
        assert pred == 1

    def test_partial_fit_increments_count(self):
        """partial_fit increases sample count."""
        classifier = OnlineClassifier()
        features = self._make_features()

        classifier.partial_fit(features, 0)

        assert classifier.sample_count == 1

    def test_partial_fit_tracks_classes(self):
        """partial_fit tracks samples by class."""
        classifier = OnlineClassifier()
        features = self._make_features()

        classifier.partial_fit(features, 0)
        classifier.partial_fit(features, 1)
        classifier.partial_fit(features, 0)

        stats = classifier.get_stats()
        assert stats.samples_no_change == 2
        assert stats.samples_change == 1

    def test_is_ready_after_min_samples(self):
        """Model is ready after MIN_SAMPLES_PER_CLASS of each class."""
        classifier = OnlineClassifier()

        # Add samples of each class
        for i in range(OnlineClassifier.MIN_SAMPLES_PER_CLASS):
            classifier.partial_fit(self._make_features(spread_bps=i), 0)
            classifier.partial_fit(self._make_features(spread_bps=i + 100), 1)

        assert classifier.is_ready is True

    def test_predict_after_fit(self):
        """predict returns 0 or 1 after fitting."""
        classifier = OnlineClassifier()

        # Train with some samples
        for i in range(50):
            classifier.partial_fit(self._make_features(spread_bps=i), 0)
            classifier.partial_fit(self._make_features(spread_bps=i + 100), 1)

        pred = classifier.predict(self._make_features())

        assert pred in [0, 1]

    def test_predict_proba_range(self):
        """predict_proba returns value in [0, 1] after fitting."""
        classifier = OnlineClassifier()

        # Train with some samples
        for i in range(50):
            classifier.partial_fit(self._make_features(spread_bps=i), 0)
            classifier.partial_fit(self._make_features(spread_bps=i + 100), 1)

        proba = classifier.predict_proba(self._make_features())

        assert 0.0 <= proba <= 1.0

    def test_record_prediction_accuracy(self):
        """record_prediction tracks accuracy correctly."""
        classifier = OnlineClassifier()

        # Record some predictions
        classifier.record_prediction(1, 1)  # correct
        classifier.record_prediction(0, 0)  # correct
        classifier.record_prediction(1, 0)  # wrong

        # Need at least 10 for accuracy to show
        for _ in range(10):
            classifier.record_prediction(1, 1)

        stats = classifier.get_stats()
        assert stats.accuracy_recent is not None
        assert stats.accuracy_recent > 0.5

    def test_get_stats_weights(self):
        """get_stats includes feature weights after fitting."""
        classifier = OnlineClassifier()

        # Train with some samples
        for i in range(50):
            classifier.partial_fit(self._make_features(spread_bps=i), 0)
            classifier.partial_fit(self._make_features(spread_bps=i + 100), 1)

        stats = classifier.get_stats()

        assert "spread_bps" in stats.weights
        assert "imbalance" in stats.weights
        assert "depth" in stats.weights
        assert "volatility" in stats.weights

    def test_get_stats_ready_pct(self):
        """get_stats shows progress toward ready state."""
        classifier = OnlineClassifier()

        # Add 50 of each class (half of MIN_SAMPLES_PER_CLASS=100)
        for i in range(50):
            classifier.partial_fit(self._make_features(spread_bps=i), 0)
            classifier.partial_fit(self._make_features(spread_bps=i + 100), 1)

        stats = classifier.get_stats()

        assert stats.ready_pct == 50.0
