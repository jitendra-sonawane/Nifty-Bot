"""Tests for Put-Call Ratio Calculator."""

import pytest
from app.core.pcr_calculator import PCRCalculator


class TestCalculatePCR:
    """Test basic PCR calculation."""

    def setup_method(self):
        self.calc = PCRCalculator()

    def test_basic_pcr(self):
        assert self.calc.calculate_pcr(1500, 1000) == 1.5

    def test_pcr_equal_oi(self):
        assert self.calc.calculate_pcr(1000, 1000) == 1.0

    def test_pcr_bullish(self):
        """More calls than puts -> PCR < 1."""
        pcr = self.calc.calculate_pcr(500, 1000)
        assert pcr == 0.5

    def test_pcr_zero_call_oi(self):
        """Zero call OI should return None."""
        assert self.calc.calculate_pcr(1000, 0) is None

    def test_pcr_negative_call_oi(self):
        """Negative call OI should return None."""
        assert self.calc.calculate_pcr(1000, -100) is None

    def test_pcr_rounded(self):
        """PCR should be rounded to 4 decimals."""
        pcr = self.calc.calculate_pcr(1000, 3000)
        assert pcr == round(1000 / 3000, 4)


class TestCalculatePCRFromOptions:
    """Test PCR from options list."""

    def setup_method(self):
        self.calc = PCRCalculator()

    def test_from_options_basic(self):
        options = [
            {'option_type': 'PE', 'oi': 500},
            {'option_type': 'PE', 'oi': 500},
            {'option_type': 'CE', 'oi': 1000},
        ]
        assert self.calc.calculate_pcr_from_options(options) == 1.0

    def test_from_options_empty(self):
        assert self.calc.calculate_pcr_from_options([]) is None

    def test_from_options_no_calls(self):
        """Only puts, no calls -> None (division by zero)."""
        options = [{'option_type': 'PE', 'oi': 500}]
        assert self.calc.calculate_pcr_from_options(options) is None

    def test_from_options_no_puts(self):
        """Only calls, no puts -> PCR = 0."""
        options = [{'option_type': 'CE', 'oi': 500}]
        assert self.calc.calculate_pcr_from_options(options) == 0.0


class TestGetSentiment:
    """Test sentiment classification from PCR."""

    def setup_method(self):
        self.calc = PCRCalculator()

    def test_extreme_bearish(self):
        assert self.calc.get_sentiment(2.0) == "EXTREME_BEARISH"
        assert self.calc.get_sentiment(1.5) == "EXTREME_BEARISH"

    def test_bearish(self):
        assert self.calc.get_sentiment(1.2) == "BEARISH"
        assert self.calc.get_sentiment(1.0) == "BEARISH"

    def test_bullish(self):
        assert self.calc.get_sentiment(0.7) == "BULLISH"

    def test_extreme_bullish(self):
        assert self.calc.get_sentiment(0.3) == "EXTREME_BULLISH"
        assert self.calc.get_sentiment(0.5) == "EXTREME_BULLISH"

    def test_none_pcr(self):
        assert self.calc.get_sentiment(None) == "UNKNOWN"

    def test_neutral_not_reachable(self):
        """With BEARISH_THRESHOLD == BULLISH_THRESHOLD == 1.0, neutral requires pcr > 1.0 AND pcr < 1.0 (impossible).
        Actually per code: pcr > 1.0 is BEARISH or EXTREME_BEARISH, pcr < 1.0 is BULLISH.
        pcr == 1.0 falls into BEARISH. So NEUTRAL is never returned with equal thresholds."""
        # PCR must be strictly > BULLISH_THRESHOLD (1.0) to not be BULLISH,
        # but >= BEARISH_THRESHOLD (1.0) makes it BEARISH. So 1.0 is BEARISH.
        assert self.calc.get_sentiment(1.0) == "BEARISH"


class TestSignalChecks:
    """Test bullish/bearish/extreme signal checks."""

    def setup_method(self):
        self.calc = PCRCalculator()

    def test_is_bullish(self):
        assert self.calc.is_bullish_signal(0.7) is True
        assert self.calc.is_bullish_signal(1.0) is False
        assert self.calc.is_bullish_signal(1.5) is False

    def test_is_bearish(self):
        assert self.calc.is_bearish_signal(1.5) is True
        assert self.calc.is_bearish_signal(1.0) is False
        assert self.calc.is_bearish_signal(0.5) is False

    def test_is_extreme(self):
        assert self.calc.is_extreme_signal(2.0) is True
        assert self.calc.is_extreme_signal(0.3) is True
        assert self.calc.is_extreme_signal(1.0) is False

    def test_none_returns_false(self):
        assert self.calc.is_bullish_signal(None) is False
        assert self.calc.is_bearish_signal(None) is False
        assert self.calc.is_extreme_signal(None) is False


class TestPCRHistory:
    """Test PCR recording and history."""

    def setup_method(self):
        self.calc = PCRCalculator()

    def test_record_pcr(self):
        self.calc.record_pcr(1.2, 1200, 1000)
        assert len(self.calc.pcr_history) == 1
        assert self.calc.pcr_history[0]['pcr'] == 1.2

    def test_record_none_pcr_skipped(self):
        self.calc.record_pcr(None, 0, 0)
        assert len(self.calc.pcr_history) == 0

    def test_max_history_trimmed(self):
        for i in range(150):
            self.calc.record_pcr(1.0 + i * 0.001, 1000, 1000)
        assert len(self.calc.pcr_history) == 100

    def test_get_pcr_history_limit(self):
        for i in range(20):
            self.calc.record_pcr(1.0, 1000, 1000)
        assert len(self.calc.get_pcr_history(5)) == 5

    def test_clear_history(self):
        self.calc.record_pcr(1.0, 1000, 1000)
        self.calc.clear_history()
        assert len(self.calc.pcr_history) == 0


class TestPCRTrend:
    """Test PCR trend calculation."""

    def setup_method(self):
        self.calc = PCRCalculator()

    def test_increasing_trend(self):
        for pcr in [0.8, 0.9, 1.0, 1.1, 1.2]:
            self.calc.record_pcr(pcr, 1000, 1000)
        assert self.calc.get_pcr_trend(5) == "INCREASING"

    def test_decreasing_trend(self):
        for pcr in [1.2, 1.1, 1.0, 0.9, 0.8]:
            self.calc.record_pcr(pcr, 1000, 1000)
        assert self.calc.get_pcr_trend(5) == "DECREASING"

    def test_stable_trend(self):
        for _ in range(5):
            self.calc.record_pcr(1.0, 1000, 1000)
        assert self.calc.get_pcr_trend(5) == "STABLE"

    def test_insufficient_data(self):
        self.calc.record_pcr(1.0, 1000, 1000)
        assert self.calc.get_pcr_trend(5) is None


class TestPCRAnalysis:
    """Test comprehensive PCR analysis."""

    def setup_method(self):
        self.calc = PCRCalculator()

    def test_analysis_with_none_pcr(self):
        result = self.calc.get_pcr_analysis(None, 0, 0)
        assert result['sentiment'] == 'UNKNOWN'
        assert result['is_bullish'] is False
        assert result['is_bearish'] is False

    def test_analysis_bearish(self):
        result = self.calc.get_pcr_analysis(1.3, 1300, 1000)
        assert result['sentiment'] == 'BEARISH'
        assert result['is_bearish'] is True
        assert result['is_bullish'] is False
        assert result['pcr'] == 1.3

    def test_analysis_bullish(self):
        result = self.calc.get_pcr_analysis(0.7, 700, 1000)
        assert result['sentiment'] == 'BULLISH'
        assert result['is_bullish'] is True

    def test_analysis_has_all_keys(self):
        result = self.calc.get_pcr_analysis(1.0, 1000, 1000)
        expected_keys = {'pcr', 'put_oi', 'call_oi', 'sentiment', 'emoji',
                         'is_bullish', 'is_bearish', 'is_extreme', 'trend',
                         'interpretation', 'timestamp'}
        assert expected_keys == set(result.keys())


class TestSentimentEmoji:
    """Test emoji helper."""

    def setup_method(self):
        self.calc = PCRCalculator()

    def test_known_sentiments(self):
        assert self.calc.get_sentiment_emoji("BULLISH") == "\U0001f7e2"
        assert self.calc.get_sentiment_emoji("BEARISH") == "\U0001f534"
        assert self.calc.get_sentiment_emoji("UNKNOWN") == "\u2753"

    def test_unknown_sentiment(self):
        assert self.calc.get_sentiment_emoji("INVALID") == "\u2753"
