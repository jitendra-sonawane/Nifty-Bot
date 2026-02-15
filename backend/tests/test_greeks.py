"""Tests for Black-Scholes Greeks Calculator."""

import pytest
import numpy as np
from scipy.stats import norm
from app.core.greeks import GreeksCalculator


class TestGreeksCalculatorD1D2:
    """Test d1 and d2 helper calculations."""

    def setup_method(self):
        self.calc = GreeksCalculator(risk_free_rate=0.06)

    def test_d1_basic(self):
        """d1 for ATM option with known inputs."""
        S, K, T, sigma = 100, 100, 1.0, 0.20
        d1 = self.calc.d1(S, K, T, sigma)
        # manual: (ln(1) + (0.06 + 0.02)*1) / (0.20*1) = 0.08/0.20 = 0.4
        assert pytest.approx(d1, rel=1e-6) == 0.4

    def test_d2_basic(self):
        """d2 = d1 - sigma*sqrt(T)."""
        S, K, T, sigma = 100, 100, 1.0, 0.20
        d2 = self.calc.d2(S, K, T, sigma)
        assert pytest.approx(d2, rel=1e-6) == 0.4 - 0.20

    def test_d1_zero_time(self):
        """d1 returns 0 when T <= 0."""
        assert self.calc.d1(100, 100, 0, 0.2) == 0
        assert self.calc.d1(100, 100, -1, 0.2) == 0

    def test_d1_zero_sigma(self):
        """d1 returns 0 when sigma <= 0."""
        assert self.calc.d1(100, 100, 1, 0) == 0
        assert self.calc.d1(100, 100, 1, -0.1) == 0


class TestCalculateGreeks:
    """Test the main calculate_greeks method."""

    def setup_method(self):
        self.calc = GreeksCalculator(risk_free_rate=0.06)

    def test_ce_delta_atm(self):
        """ATM call delta should be close to 0.5."""
        greeks = self.calc.calculate_greeks(100, 100, 1.0, 0.20, 'CE')
        assert 0.45 < greeks['delta'] < 0.75

    def test_pe_delta_atm(self):
        """ATM put delta should be close to -0.5."""
        greeks = self.calc.calculate_greeks(100, 100, 1.0, 0.20, 'PE')
        assert -0.75 < greeks['delta'] < -0.25

    def test_ce_delta_range(self):
        """Call delta must be between 0 and 1."""
        for S in [80, 100, 120]:
            greeks = self.calc.calculate_greeks(S, 100, 0.5, 0.25, 'CE')
            assert 0 <= greeks['delta'] <= 1

    def test_pe_delta_range(self):
        """Put delta must be between -1 and 0."""
        for S in [80, 100, 120]:
            greeks = self.calc.calculate_greeks(S, 100, 0.5, 0.25, 'PE')
            assert -1 <= greeks['delta'] <= 0

    def test_gamma_positive(self):
        """Gamma should always be positive for both CE and PE."""
        for opt_type in ['CE', 'PE']:
            greeks = self.calc.calculate_greeks(100, 100, 0.5, 0.25, opt_type)
            assert greeks['gamma'] >= 0

    def test_gamma_same_for_call_and_put(self):
        """Gamma is the same for call and put at same strike."""
        ce = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'CE')
        pe = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'PE')
        assert pytest.approx(ce['gamma'], abs=1e-6) == pe['gamma']

    def test_theta_negative_for_long(self):
        """Theta should typically be negative (time decay) for CE."""
        greeks = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'CE')
        assert greeks['theta'] < 0

    def test_vega_positive(self):
        """Vega should be positive."""
        greeks = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'CE')
        assert greeks['vega'] > 0

    def test_vega_same_for_call_and_put(self):
        """Vega is the same for call and put."""
        ce = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'CE')
        pe = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'PE')
        assert pytest.approx(ce['vega'], abs=1e-4) == pe['vega']

    def test_rho_ce_positive(self):
        """Call rho should be positive."""
        greeks = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'CE')
        assert greeks['rho'] > 0

    def test_rho_pe_negative(self):
        """Put rho should be negative."""
        greeks = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'PE')
        assert greeks['rho'] < 0

    def test_zero_time_returns_zeros(self):
        """When T=0, all greeks should be zero."""
        greeks = self.calc.calculate_greeks(100, 100, 0, 0.25, 'CE')
        assert greeks == {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0, 'quality_score': 0}

    def test_zero_sigma_returns_zeros(self):
        """When sigma=0, all greeks should be zero."""
        greeks = self.calc.calculate_greeks(100, 100, 0.5, 0, 'CE')
        assert greeks == {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0, 'quality_score': 0}

    def test_deep_itm_call_delta_near_1(self):
        """Deep ITM call should have delta near 1."""
        greeks = self.calc.calculate_greeks(150, 100, 0.5, 0.25, 'CE')
        assert greeks['delta'] > 0.9

    def test_deep_otm_call_delta_near_0(self):
        """Deep OTM call should have delta near 0."""
        greeks = self.calc.calculate_greeks(50, 100, 0.5, 0.25, 'CE')
        assert greeks['delta'] < 0.1

    def test_custom_risk_free_rate(self):
        """Overriding risk_free_rate parameter should be used - higher rate -> higher call price."""
        p1 = self.calc.black_scholes_price(100, 100, 1.0, 0.20, 'CE', risk_free_rate=0.01)
        p2 = self.calc.black_scholes_price(100, 100, 1.0, 0.20, 'CE', risk_free_rate=0.10)
        # Higher risk-free rate -> higher call price
        assert p2 > p1

    def test_quality_score_in_range(self):
        """Quality score should be between 0 and 100."""
        greeks = self.calc.calculate_greeks(100, 100, 0.05, 0.25, 'CE')
        assert 0 <= greeks['quality_score'] <= 100

    def test_put_call_parity_delta(self):
        """Put-call parity: CE delta - PE delta ≈ 1."""
        ce = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'CE')
        pe = self.calc.calculate_greeks(100, 100, 0.5, 0.25, 'PE')
        assert pytest.approx(ce['delta'] - pe['delta'], abs=0.01) == 1.0


class TestBlackScholesPrice:
    """Test option pricing."""

    def setup_method(self):
        self.calc = GreeksCalculator(risk_free_rate=0.06)

    def test_call_price_positive(self):
        price = self.calc.black_scholes_price(100, 100, 1.0, 0.20, 'CE')
        assert price > 0

    def test_put_price_positive(self):
        price = self.calc.black_scholes_price(100, 100, 1.0, 0.20, 'PE')
        assert price > 0

    def test_put_call_parity(self):
        """C - P = S - K*exp(-rT)."""
        S, K, T, sigma, r = 100, 100, 1.0, 0.20, 0.06
        call = self.calc.black_scholes_price(S, K, T, sigma, 'CE')
        put = self.calc.black_scholes_price(S, K, T, sigma, 'PE')
        expected = S - K * np.exp(-r * T)
        assert pytest.approx(call - put, abs=0.01) == expected

    def test_zero_time_call_intrinsic(self):
        """At expiry, call price = max(0, S-K)."""
        assert self.calc.black_scholes_price(110, 100, 0, 0.25, 'CE') == 10
        assert self.calc.black_scholes_price(90, 100, 0, 0.25, 'CE') == 0

    def test_zero_time_put_intrinsic(self):
        """At expiry, put price = max(0, K-S)."""
        assert self.calc.black_scholes_price(90, 100, 0, 0.25, 'PE') == 10
        assert self.calc.black_scholes_price(110, 100, 0, 0.25, 'PE') == 0

    def test_call_increases_with_spot(self):
        """Call price increases as spot increases."""
        p1 = self.calc.black_scholes_price(90, 100, 0.5, 0.25, 'CE')
        p2 = self.calc.black_scholes_price(100, 100, 0.5, 0.25, 'CE')
        p3 = self.calc.black_scholes_price(110, 100, 0.5, 0.25, 'CE')
        assert p1 < p2 < p3

    def test_put_increases_with_lower_spot(self):
        """Put price increases as spot decreases."""
        p1 = self.calc.black_scholes_price(110, 100, 0.5, 0.25, 'PE')
        p2 = self.calc.black_scholes_price(100, 100, 0.5, 0.25, 'PE')
        p3 = self.calc.black_scholes_price(90, 100, 0.5, 0.25, 'PE')
        assert p1 < p2 < p3


class TestImpliedVolatility:
    """Test IV calculation using Newton-Raphson."""

    def setup_method(self):
        self.calc = GreeksCalculator(risk_free_rate=0.06)

    def test_iv_round_trip(self):
        """Calculate price from known sigma, then recover sigma via IV."""
        sigma = 0.25
        S, K, T = 100, 100, 0.5
        price = self.calc.black_scholes_price(S, K, T, sigma, 'CE')
        recovered = self.calc.implied_volatility(price, S, K, T, 'CE')
        assert pytest.approx(recovered, abs=0.01) == sigma

    def test_iv_round_trip_put(self):
        """IV round-trip for put option."""
        sigma = 0.30
        S, K, T = 100, 100, 0.5
        price = self.calc.black_scholes_price(S, K, T, sigma, 'PE')
        recovered = self.calc.implied_volatility(price, S, K, T, 'PE')
        assert pytest.approx(recovered, abs=0.01) == sigma

    def test_iv_below_intrinsic_returns_low(self):
        """When market price is at or below intrinsic, IV should be minimal."""
        iv = self.calc.implied_volatility(5, 105, 100, 0.5, 'CE')
        assert iv <= 0.05

    def test_iv_positive(self):
        """IV should always be positive."""
        iv = self.calc.implied_volatility(10, 100, 100, 0.5, 'CE')
        assert iv > 0


class TestQualityScore:
    """Test the quality scoring logic."""

    def setup_method(self):
        self.calc = GreeksCalculator(risk_free_rate=0.06)

    def test_atm_high_score(self):
        """ATM option with reasonable time and vol should score well."""
        # T=20/365 (20 days), sigma=0.20, ATM
        greeks = self.calc.calculate_greeks(100, 100, 20 / 365, 0.20, 'CE')
        assert greeks['quality_score'] >= 60

    def test_deep_otm_low_score(self):
        """Deep OTM option should score lower on moneyness."""
        greeks = self.calc.calculate_greeks(100, 150, 20 / 365, 0.20, 'CE')
        assert greeks['quality_score'] < 80

    def test_score_clamped_0_100(self):
        """Score should always be between 0 and 100."""
        for S in [50, 100, 200]:
            for T in [1 / 365, 10 / 365, 60 / 365, 200 / 365]:
                for sigma in [0.01, 0.20, 0.50, 2.0]:
                    greeks = self.calc.calculate_greeks(S, 100, T, sigma, 'CE')
                    assert 0 <= greeks['quality_score'] <= 100


class TestTimeToExpiry:
    """Test time_to_expiry helper."""

    def setup_method(self):
        self.calc = GreeksCalculator()

    def test_future_date_positive(self):
        """A future expiry date should return positive T."""
        T = self.calc.time_to_expiry("2030-12-31")
        assert T > 0

    def test_past_date_returns_minimum(self):
        """A past expiry date should return the minimum (0.0001)."""
        T = self.calc.time_to_expiry("2020-01-01")
        assert T == 0.0001

    def test_invalid_date_returns_zero(self):
        """An invalid date string should return 0."""
        T = self.calc.time_to_expiry("not-a-date")
        assert T == 0
