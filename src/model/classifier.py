"""Online classifier for price change prediction."""

import threading
from collections import deque
from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler

from src.features.extractor import FeatureSnapshot


@dataclass
class Prediction:
    """A model prediction with its eventual label.

    Created when a prediction is made and labeled after the prediction horizon.
    """

    timestamp_ms: int  # When prediction was made (ms since epoch)
    prediction: int  # Predicted class (0 or 1)
    probability: float  # P(price_change) in [0, 1]
    label: int  # Actual outcome (0 or 1)
    labeled_at_ms: int  # When label was determined (ms since epoch)


@dataclass
class ModelStats:
    """Statistics about the model's training state."""

    samples_total: int
    samples_no_change: int  # Class 0
    samples_change: int  # Class 1
    is_ready: bool
    ready_pct: float  # 0-100, percentage to ready state
    accuracy_recent: float | None  # Accuracy over last N predictions
    weights: dict[str, float]  # Feature name -> coefficient


class OnlineClassifier:
    """Online-trained classifier for price change prediction.

    Uses SGDClassifier with log_loss for incremental learning.
    Tracks training statistics and prediction accuracy.
    """

    # Feature names in order (must match FeatureSnapshot attributes)
    FEATURE_NAMES = ["spread_bps", "imbalance", "depth", "volatility"]

    # Minimum samples of each class before model is ready
    MIN_SAMPLES_PER_CLASS = 100

    def __init__(
        self,
        learning_rate: float = 0.01,
        accuracy_window: int = 100,
    ):
        """Initialize the online classifier.

        Args:
            learning_rate: Learning rate for SGD.
            accuracy_window: Number of predictions to track for accuracy.
        """
        self._model = SGDClassifier(
            loss="log_loss",
            learning_rate="constant",
            eta0=learning_rate,
            warm_start=True,
            random_state=42,
        )
        self._scaler = StandardScaler()
        self._is_fitted = False
        self._scaler_fitted = False

        # Training statistics
        self._samples_total = 0
        self._samples_by_class = {0: 0, 1: 0}

        # Accuracy tracking: stores (prediction, actual) tuples
        self._accuracy_window = accuracy_window
        self._prediction_history: deque[tuple[int, int]] = deque(maxlen=accuracy_window)

        self._lock = threading.RLock()

    @property
    def is_ready(self) -> bool:
        """True if model has seen enough samples to make predictions."""
        with self._lock:
            return (
                self._samples_by_class[0] >= self.MIN_SAMPLES_PER_CLASS
                and self._samples_by_class[1] >= self.MIN_SAMPLES_PER_CLASS
            )

    @property
    def sample_count(self) -> int:
        """Total number of training samples seen."""
        with self._lock:
            return self._samples_total

    def get_stats(self) -> ModelStats:
        """Get current model statistics."""
        with self._lock:
            # Calculate ready percentage
            min_per_class = min(self._samples_by_class[0], self._samples_by_class[1])
            ready_pct = min(100.0, (min_per_class / self.MIN_SAMPLES_PER_CLASS) * 100)

            # Calculate recent accuracy
            accuracy = None
            if len(self._prediction_history) >= 10:
                correct = sum(
                    1 for pred, actual in self._prediction_history if pred == actual
                )
                accuracy = correct / len(self._prediction_history)

            # Get model weights
            weights = {}
            if self._is_fitted and hasattr(self._model, "coef_"):
                for i, name in enumerate(self.FEATURE_NAMES):
                    if i < len(self._model.coef_[0]):
                        weights[name] = float(self._model.coef_[0][i])
                    else:
                        weights[name] = 0.0
            else:
                for name in self.FEATURE_NAMES:
                    weights[name] = 0.0

            return ModelStats(
                samples_total=self._samples_total,
                samples_no_change=self._samples_by_class[0],
                samples_change=self._samples_by_class[1],
                is_ready=self.is_ready,
                ready_pct=ready_pct,
                accuracy_recent=accuracy,
                weights=weights,
            )

    def _features_to_array(self, features: FeatureSnapshot) -> np.ndarray:
        """Convert FeatureSnapshot to numpy array."""
        return np.array(
            [
                features.spread_bps,
                features.imbalance,
                features.depth,
                features.volatility,
            ]
        ).reshape(1, -1)

    def partial_fit(self, features: FeatureSnapshot, label: int) -> None:
        """Update model with a single training sample.

        Args:
            features: Feature snapshot at time t.
            label: Binary label (0 = no change, 1 = change).
        """
        with self._lock:
            X = self._features_to_array(features)

            # Update scaler incrementally
            if not self._scaler_fitted:
                self._scaler.partial_fit(X)
                self._scaler_fitted = True
            else:
                self._scaler.partial_fit(X)

            # Scale features
            X_scaled = self._scaler.transform(X)

            # Update model
            self._model.partial_fit(X_scaled, [label], classes=[0, 1])
            self._is_fitted = True

            # Update statistics
            self._samples_total += 1
            self._samples_by_class[label] += 1

    def predict_proba(self, features: FeatureSnapshot) -> float:
        """Predict probability of price change.

        Args:
            features: Current feature snapshot.

        Returns:
            Probability of price change (0.0 to 1.0).
            Returns 0.5 if model is not ready.
        """
        with self._lock:
            if not self._is_fitted or not self._scaler_fitted:
                return 0.5

            X = self._features_to_array(features)
            X_scaled = self._scaler.transform(X)

            # Get probability of class 1 (price change)
            proba = self._model.predict_proba(X_scaled)[0]

            # proba is [P(class 0), P(class 1)]
            if len(proba) > 1:
                return float(proba[1])
            return 0.5

    def predict(self, features: FeatureSnapshot) -> int:
        """Predict binary class (0 or 1).

        Args:
            features: Current feature snapshot.

        Returns:
            Predicted class (0 = no change, 1 = change).
        """
        proba = self.predict_proba(features)
        return 1 if proba >= 0.5 else 0

    def record_prediction(self, predicted: int, actual: int) -> None:
        """Record a prediction and its actual outcome for accuracy tracking.

        Args:
            predicted: Predicted class (0 or 1).
            actual: Actual class (0 or 1).
        """
        with self._lock:
            self._prediction_history.append((predicted, actual))
