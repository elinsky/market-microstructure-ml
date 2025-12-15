"""Tests for StabilityScorer."""

from src.features.extractor import FeatureSnapshot
from src.features.stability import StabilityScorer


class TestStabilityScorer:
    """Tests for StabilityScorer class."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

    def make_features(
        self,
        spread_bps: float = 5.0,
        imbalance: float = 0.0,
        depth: float = 10.0,
        volatility: float = 2.0,
    ) -> FeatureSnapshot:
        """Create a FeatureSnapshot with configurable values."""
        return FeatureSnapshot(
            spread_bps=spread_bps,
            imbalance=imbalance,
            depth=depth,
            volatility=volatility,
        )

    def make_scorer(self) -> StabilityScorer:
        """Create a scorer with default settings."""
        return StabilityScorer()

    # =========================================================================
    # Tests - Stable Market Conditions
    # =========================================================================

    def test_stable_market_returns_high_score(self):
        """Tight spread, balanced book, low volatility = high score."""
        # GIVEN a scorer and features representing a stable market
        scorer = self.make_scorer()
        features = self.make_features(
            spread_bps=0.5,  # Very tight (below 1.0 threshold)
            imbalance=0.0,  # Perfectly balanced
            volatility=0.2,  # Very low (below 0.5 threshold)
        )

        # WHEN we score
        result = scorer.score(features)

        # THEN score is high and category is STABLE
        assert result.score >= 70.0
        assert result.category == "STABLE"
        assert result.color == "green"

    # =========================================================================
    # Tests - Unstable Market Conditions
    # =========================================================================

    def test_unstable_market_returns_low_score(self):
        """Wide spread, imbalanced book, high volatility = low score."""
        # GIVEN a scorer and features representing an unstable market
        scorer = self.make_scorer()
        features = self.make_features(
            spread_bps=15.0,  # Wide (above 10.0 threshold)
            imbalance=0.9,  # Heavily imbalanced
            volatility=10.0,  # High (above 5.0 threshold)
        )

        # WHEN we score
        result = scorer.score(features)

        # THEN score is low and category is UNSTABLE
        assert result.score < 40.0
        assert result.category == "UNSTABLE"
        assert result.color == "red"

    # =========================================================================
    # Tests - Moderate Market Conditions
    # =========================================================================

    def test_moderate_market_returns_middle_score(self):
        """Mixed conditions = moderate score."""
        # GIVEN a scorer and features with mixed conditions
        scorer = self.make_scorer()
        features = self.make_features(
            spread_bps=5.0,  # Middle of range
            imbalance=0.3,  # Slight imbalance
            volatility=2.5,  # Middle of range
        )

        # WHEN we score
        result = scorer.score(features)

        # THEN score is in moderate range
        assert 40.0 <= result.score < 70.0
        assert result.category == "MODERATE"
        assert result.color == "yellow"

    # =========================================================================
    # Tests - Individual Component Scoring
    # =========================================================================

    def test_spread_below_threshold_gives_max_score(self):
        """Spread below low threshold contributes 100 to weighted score."""
        # GIVEN a scorer and features with very tight spread only
        scorer = self.make_scorer()
        features = self.make_features(
            spread_bps=0.5,  # Below 1.0 threshold = 100 score
            imbalance=0.0,  # 100 score
            volatility=0.2,  # Below 0.5 threshold = 100 score
        )

        # WHEN we score
        result = scorer.score(features)

        # THEN all components at 100 = total 100
        assert result.score == 100.0

    def test_spread_above_threshold_gives_zero_contribution(self):
        """Spread above high threshold contributes 0 to weighted score."""
        # GIVEN features with very wide spread but perfect other metrics
        scorer = self.make_scorer()
        features = self.make_features(
            spread_bps=15.0,  # Above 10.0 = 0 score (40% weight)
            imbalance=0.0,  # 100 score (30% weight)
            volatility=0.2,  # 100 score (30% weight)
        )

        # WHEN we score
        result = scorer.score(features)

        # THEN score = 0*0.4 + 100*0.3 + 100*0.3 = 60
        assert result.score == 60.0

    def test_imbalance_affects_score_symmetrically(self):
        """Positive and negative imbalance have same effect on score."""
        # GIVEN a scorer
        scorer = self.make_scorer()

        # WHEN we score positive vs negative imbalance
        positive = scorer.score(self.make_features(imbalance=0.5))
        negative = scorer.score(self.make_features(imbalance=-0.5))

        # THEN scores are equal (absolute value used)
        assert positive.score == negative.score
