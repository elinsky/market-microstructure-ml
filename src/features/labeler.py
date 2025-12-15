"""Labeler for generating price change labels with configurable delay."""

import threading
from collections import deque
from dataclasses import dataclass

from src.features.extractor import FeatureSnapshot


@dataclass
class LabeledSample:
    """A feature snapshot paired with its label."""

    features: FeatureSnapshot
    label: int  # 0 = no change, 1 = price changed
    mid_price_t: float  # Price at time t
    mid_price_t_delta: float  # Price at time t + delta
    price_change_pct: float  # Percentage change
    prediction_at_t: int | None = None  # Prediction made at time t (for accuracy)


class Labeler:
    """Generate binary labels for price change prediction.

    Labels are generated after a configurable delay (delta_ms).
    A label is 1 if the price changed by more than threshold_pct,
    otherwise 0.

    The labeler maintains a buffer of (timestamp, mid_price, features)
    tuples. When a new sample arrives, it checks if any buffered samples
    are old enough to compute their labels.
    """

    def __init__(
        self,
        delta_ms: int = 500,
        threshold_pct: float = 0.01,
        max_buffer_size: int = 1000,
    ):
        """Initialize the labeler.

        Args:
            delta_ms: Prediction horizon in milliseconds.
            threshold_pct: Price change threshold as percentage (0.01 = 0.01%).
            max_buffer_size: Maximum samples to buffer (prevents memory growth).
        """
        self._delta_ms = delta_ms
        self._threshold = threshold_pct / 100  # Convert to decimal
        self._max_buffer_size = max_buffer_size

        # Buffer stores (timestamp_ms, mid_price, features, prediction)
        self._buffer: deque[tuple[float, float, FeatureSnapshot, int | None]] = deque(
            maxlen=max_buffer_size
        )
        self._lock = threading.RLock()

    @property
    def delta_ms(self) -> int:
        """Prediction horizon in milliseconds."""
        return self._delta_ms

    @property
    def threshold_pct(self) -> float:
        """Price change threshold as percentage."""
        return self._threshold * 100

    @property
    def buffer_size(self) -> int:
        """Current number of samples in buffer."""
        with self._lock:
            return len(self._buffer)

    def add_sample(
        self,
        timestamp_ms: float,
        mid_price: float,
        features: FeatureSnapshot,
        prediction: int | None = None,
    ) -> LabeledSample | None:
        """Add a new sample and return a labeled sample if one is ready.

        Args:
            timestamp_ms: Current timestamp in milliseconds.
            mid_price: Current mid price.
            features: Current feature snapshot.
            prediction: Optional prediction made at this time (for accuracy tracking).

        Returns:
            LabeledSample if a buffered sample is old enough, else None.
        """
        with self._lock:
            # Add current sample to buffer (with prediction for accuracy tracking)
            self._buffer.append((timestamp_ms, mid_price, features, prediction))

            # Check if oldest sample is ready for labeling
            return self._try_emit_label(timestamp_ms, mid_price)

    def _try_emit_label(
        self,
        current_timestamp_ms: float,
        current_mid_price: float,
    ) -> LabeledSample | None:
        """Check if oldest sample is ready and emit label if so.

        Args:
            current_timestamp_ms: Current timestamp in milliseconds.
            current_mid_price: Current mid price.

        Returns:
            LabeledSample if ready, else None.
        """
        if not self._buffer:
            return None

        # Check oldest sample
        oldest_ts, oldest_price, oldest_features, oldest_prediction = self._buffer[0]
        age_ms = current_timestamp_ms - oldest_ts

        if age_ms >= self._delta_ms:
            # Sample is old enough - compute label and remove from buffer
            self._buffer.popleft()

            # Compute price change
            if oldest_price == 0:
                price_change_pct = 0.0
            else:
                price_change_pct = abs(current_mid_price - oldest_price) / oldest_price

            # Generate label
            label = 1 if price_change_pct > self._threshold else 0

            return LabeledSample(
                features=oldest_features,
                label=label,
                mid_price_t=oldest_price,
                mid_price_t_delta=current_mid_price,
                price_change_pct=price_change_pct * 100,  # Convert to percentage
                prediction_at_t=oldest_prediction,
            )

        return None

    def flush(self) -> None:
        """Clear the buffer (useful for testing or reset)."""
        with self._lock:
            self._buffer.clear()
