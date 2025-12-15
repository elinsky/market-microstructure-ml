"""Tests for CandleAggregator."""

from src.dashboard.app import CandleAggregator


class TestCandleAggregator:
    """Tests for CandleAggregator class."""

    # =========================================================================
    # Test Data Helpers
    # =========================================================================

    def make_aggregator(
        self, ticks_per_candle: int = 5, max_candles: int = 10
    ) -> CandleAggregator:
        """Create a CandleAggregator with configurable settings."""
        return CandleAggregator(
            ticks_per_candle=ticks_per_candle, max_candles=max_candles
        )

    # =========================================================================
    # Tests - Initial State
    # =========================================================================

    def test_initial_state_has_no_candles(self):
        """New aggregator has no candles."""
        # GIVEN a new aggregator
        aggregator = self.make_aggregator()

        # WHEN we get candles (no action)
        candles = aggregator.get_candles()

        # THEN there are no candles
        assert len(candles) == 0

    def test_initial_current_candle_is_none(self):
        """New aggregator has no current candle."""
        # GIVEN a new aggregator
        aggregator = self.make_aggregator()

        # WHEN we check current candle (no action)
        current = aggregator.current_candle

        # THEN it is None
        assert current is None

    def test_initial_tick_count_is_zero(self):
        """New aggregator has zero tick count."""
        # GIVEN a new aggregator
        aggregator = self.make_aggregator()

        # WHEN we check tick count (no action)
        count = aggregator.tick_count

        # THEN count is 0
        assert count == 0

    # =========================================================================
    # Tests - Adding Ticks
    # =========================================================================

    def test_first_tick_starts_new_candle(self):
        """First tick creates a new candle."""
        # GIVEN an empty aggregator
        aggregator = self.make_aggregator()

        # WHEN we add a tick
        aggregator.add_tick(100.0)

        # THEN current candle exists with all prices equal
        candle = aggregator.current_candle
        assert candle is not None
        assert candle.open == 100.0
        assert candle.high == 100.0
        assert candle.low == 100.0
        assert candle.close == 100.0

    def test_second_tick_updates_candle(self):
        """Second tick updates the current candle."""
        # GIVEN an aggregator with one tick
        aggregator = self.make_aggregator()
        aggregator.add_tick(100.0)

        # WHEN we add a second tick
        aggregator.add_tick(105.0)

        # THEN candle is updated
        candle = aggregator.current_candle
        assert candle is not None
        assert candle.open == 100.0  # Unchanged
        assert candle.high == 105.0  # Updated
        assert candle.low == 100.0  # Unchanged
        assert candle.close == 105.0  # Updated

    def test_high_is_tracked_correctly(self):
        """High is the maximum price seen."""
        # GIVEN an aggregator
        aggregator = self.make_aggregator()

        # WHEN we add ticks with a spike in the middle
        aggregator.add_tick(100.0)
        aggregator.add_tick(110.0)
        aggregator.add_tick(105.0)

        # THEN high is the maximum
        candle = aggregator.current_candle
        assert candle is not None
        assert candle.high == 110.0

    def test_low_is_tracked_correctly(self):
        """Low is the minimum price seen."""
        # GIVEN an aggregator
        aggregator = self.make_aggregator()

        # WHEN we add ticks with a dip in the middle
        aggregator.add_tick(100.0)
        aggregator.add_tick(90.0)
        aggregator.add_tick(95.0)

        # THEN low is the minimum
        candle = aggregator.current_candle
        assert candle is not None
        assert candle.low == 90.0

    def test_tick_count_increments(self):
        """Tick count increments with each tick."""
        # GIVEN an aggregator
        aggregator = self.make_aggregator()

        # WHEN we add 3 ticks
        aggregator.add_tick(100.0)
        aggregator.add_tick(101.0)
        aggregator.add_tick(102.0)

        # THEN tick count is 3
        assert aggregator.tick_count == 3

    # =========================================================================
    # Tests - Candle Closing
    # =========================================================================

    def test_candle_closes_after_ticks_per_candle(self):
        """Candle closes and moves to history after configured ticks."""
        # GIVEN an aggregator with ticks_per_candle=3
        aggregator = self.make_aggregator(ticks_per_candle=3)

        # WHEN we add exactly 3 ticks
        aggregator.add_tick(100.0)
        aggregator.add_tick(105.0)
        aggregator.add_tick(102.0)

        # THEN candle is closed (current is None, history has 1)
        assert aggregator.current_candle is None
        assert len(aggregator.history) == 1
        assert aggregator.tick_count == 0

    def test_closed_candle_has_correct_ohlc(self):
        """Closed candle has correct OHLC values."""
        # GIVEN an aggregator with ticks_per_candle=3
        aggregator = self.make_aggregator(ticks_per_candle=3)

        # WHEN we add 3 ticks
        aggregator.add_tick(100.0)
        aggregator.add_tick(110.0)
        aggregator.add_tick(105.0)

        # THEN closed candle has correct values
        candle = aggregator.history[0]
        assert candle.open == 100.0
        assert candle.high == 110.0
        assert candle.low == 100.0
        assert candle.close == 105.0
        assert candle.tick_count == 3

    def test_new_candle_starts_after_close(self):
        """New tick after close starts a new candle."""
        # GIVEN an aggregator that just closed a candle
        aggregator = self.make_aggregator(ticks_per_candle=3)
        aggregator.add_tick(100.0)
        aggregator.add_tick(105.0)
        aggregator.add_tick(102.0)

        # WHEN we add another tick
        aggregator.add_tick(200.0)

        # THEN a new candle is started
        assert aggregator.current_candle is not None
        assert aggregator.current_candle.open == 200.0
        assert aggregator.tick_count == 1

    # =========================================================================
    # Tests - get_candles Method
    # =========================================================================

    def test_get_candles_includes_current(self):
        """get_candles includes the current in-progress candle."""
        # GIVEN an aggregator with history and current candle
        aggregator = self.make_aggregator(ticks_per_candle=3)
        aggregator.add_tick(100.0)
        aggregator.add_tick(105.0)
        aggregator.add_tick(102.0)  # Closes first candle
        aggregator.add_tick(200.0)  # Starts second candle

        # WHEN we get all candles
        candles = aggregator.get_candles()

        # THEN both candles are included
        assert len(candles) == 2
        assert candles[0].close == 102.0  # First (closed)
        assert candles[1].open == 200.0  # Second (current)

    def test_history_excludes_current(self):
        """history property excludes the current candle."""
        # GIVEN an aggregator with history and current candle
        aggregator = self.make_aggregator(ticks_per_candle=3)
        aggregator.add_tick(100.0)
        aggregator.add_tick(105.0)
        aggregator.add_tick(102.0)  # Closes first candle
        aggregator.add_tick(200.0)  # Starts second candle

        # WHEN we get history
        history = aggregator.history

        # THEN only closed candles are included
        assert len(history) == 1
        assert history[0].close == 102.0

    # =========================================================================
    # Tests - Max Candles Limit
    # =========================================================================

    def test_max_candles_limits_history(self):
        """History is capped at max_candles."""
        # GIVEN an aggregator with max_candles=2, ticks_per_candle=2
        aggregator = self.make_aggregator(ticks_per_candle=2, max_candles=2)

        # WHEN we create 4 candles (8 ticks)
        for i in range(8):
            aggregator.add_tick(100.0 + i)

        # THEN history has only 2 candles (most recent)
        assert len(aggregator.history) == 2
        # First kept candle starts with tick 5 (index 4)
        assert aggregator.history[0].open == 104.0
        # Second kept candle starts with tick 7 (index 6)
        assert aggregator.history[1].open == 106.0
