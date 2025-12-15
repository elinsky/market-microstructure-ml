"""Quote stability scoring algorithm."""

from dataclasses import dataclass

from src.features.extractor import FeatureSnapshot


@dataclass
class StabilityScore:
    """Stability assessment of current market state."""

    score: float  # 0-100 (100 = very stable)
    category: str  # STABLE, MODERATE, UNSTABLE
    color: str  # green, yellow, red


class StabilityScorer:
    """Heuristic-based stability scoring from market features.

    Combines spread, imbalance, and volatility into a single score.
    """

    def __init__(
        self,
        spread_weight: float = 0.4,
        imbalance_weight: float = 0.3,
        volatility_weight: float = 0.3,
        # Spread thresholds (in bps)
        spread_low: float = 1.0,  # Below this = 100 score
        spread_high: float = 10.0,  # Above this = 0 score
        # Volatility thresholds (in bps std)
        vol_low: float = 0.5,  # Below this = 100 score
        vol_high: float = 5.0,  # Above this = 0 score
        # Category thresholds
        stable_threshold: float = 70.0,
        unstable_threshold: float = 40.0,
    ):
        """Initialize the stability scorer.

        Args:
            spread_weight: Weight for spread component (0-1).
            imbalance_weight: Weight for imbalance component (0-1).
            volatility_weight: Weight for volatility component (0-1).
            spread_low: Spread (bps) below which score is 100.
            spread_high: Spread (bps) above which score is 0.
            vol_low: Volatility (bps std) below which score is 100.
            vol_high: Volatility (bps std) above which score is 0.
            stable_threshold: Score above which market is STABLE.
            unstable_threshold: Score below which market is UNSTABLE.
        """
        self.spread_weight = spread_weight
        self.imbalance_weight = imbalance_weight
        self.volatility_weight = volatility_weight
        self.spread_low = spread_low
        self.spread_high = spread_high
        self.vol_low = vol_low
        self.vol_high = vol_high
        self.stable_threshold = stable_threshold
        self.unstable_threshold = unstable_threshold

    def score(self, features: FeatureSnapshot) -> StabilityScore:
        """Compute stability score from features.

        Args:
            features: Current feature snapshot.

        Returns:
            StabilityScore with numeric score, category, and color.
        """
        # Compute individual component scores (0-100)
        spread_score = self._score_spread(features.spread_bps)
        imbalance_score = self._score_imbalance(features.imbalance)
        volatility_score = self._score_volatility(features.volatility)

        # Weighted average
        total_score = (
            self.spread_weight * spread_score
            + self.imbalance_weight * imbalance_score
            + self.volatility_weight * volatility_score
        )

        # Determine category and color
        category, color = self._categorize(total_score)

        return StabilityScore(
            score=round(total_score, 1),
            category=category,
            color=color,
        )

    def _score_spread(self, spread_bps: float) -> float:
        """Score spread component (lower spread = higher score)."""
        return self._linear_score(spread_bps, self.spread_low, self.spread_high)

    def _score_imbalance(self, imbalance: float) -> float:
        """Score imbalance component (balanced = higher score).

        imbalance is in [-1, 1], we want 0 = 100, ±1 = 0
        """
        abs_imbalance = abs(imbalance)
        return self._linear_score(abs_imbalance, 0.0, 1.0)

    def _score_volatility(self, volatility: float) -> float:
        """Score volatility component (lower volatility = higher score)."""
        return self._linear_score(volatility, self.vol_low, self.vol_high)

    def _linear_score(self, value: float, low: float, high: float) -> float:
        """Convert value to 0-100 score using linear interpolation.

        Args:
            value: Current value.
            low: Value at which score = 100.
            high: Value at which score = 0.

        Returns:
            Score in [0, 100].
        """
        if value <= low:
            return 100.0
        if value >= high:
            return 0.0
        # Linear interpolation
        return 100.0 * (high - value) / (high - low)

    def _categorize(self, score: float) -> tuple[str, str]:
        """Determine category and color from score.

        Args:
            score: Numeric score (0-100).

        Returns:
            Tuple of (category, color).
        """
        if score >= self.stable_threshold:
            return "STABLE", "green"
        elif score >= self.unstable_threshold:
            return "MODERATE", "yellow"
        else:
            return "UNSTABLE", "red"
