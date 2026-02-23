"""Tests for ScalpHealthModule."""

import pytest
import time
import datetime
from unittest.mock import patch
from app.intelligence.scalp_health import ScalpHealthModule


@pytest.fixture
def module():
    return ScalpHealthModule()


@pytest.fixture
def base_greeks():
    """Realistic ATM Nifty Greeks for testing."""
    return {
        "atm_strike": 24800,
        "expiry_date": (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
        "ce": {
            "delta": 0.52,
            "gamma": 0.0008,
            "theta": -5.2,
            "vega": 4.5,
            "iv": 0.14,
            "price": 180.0,
        },
        "pe": {
            "delta": -0.48,
            "gamma": 0.0008,
            "theta": -4.8,
            "vega": 4.3,
            "iv": 0.15,
            "price": 165.0,
        },
    }


@pytest.fixture
def base_data(base_greeks):
    """Base data dict mimicking intelligence engine update()."""
    return {
        "current_price": 24810.0,
        "greeks": base_greeks,
        "atr_pct": 0.8,
        "df_close_std": 0.12,  # 5-day realized vol (annualized decimal)
    }


class TestDTE:
    def test_dte_calculation_future_expiry(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["dte_days"] >= 0
        assert ctx["dte_hours"] >= 0
        assert ctx["dte_minutes"] >= 0
        assert ctx["expiry_date"] == base_data["greeks"]["expiry_date"]

    def test_dte_zero_on_expiry_day(self, module, base_data):
        base_data["greeks"]["expiry_date"] = datetime.date.today().strftime("%Y-%m-%d")
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["dte_days"] == 0


class TestGreeksMetrics:
    def test_gex_calculation(self, module, base_data):
        """GEX = gamma * spot^2 * 0.01 * lot_size."""
        module.update(base_data)
        ctx = module.get_context()
        spot = 24810.0
        gamma = 0.0008  # CE gamma (use higher of CE/PE)
        expected_gex = gamma * (spot ** 2) * 0.01 * 25  # lot_size=25
        assert abs(ctx["gex_rupees"] - expected_gex) < 1.0

    def test_atm_proximity(self, module, base_data):
        """ATM proximity = 100 - (abs(spot - atm) / strike_step * 100), clamped [0,100]."""
        module.update(base_data)
        ctx = module.get_context()
        # spot=24810, atm=24800, step=50 -> 100 - (10/50*100) = 100-20 = 80
        assert ctx["atm_proximity"] == 80

    def test_atm_proximity_exact_atm(self, module, base_data):
        base_data["current_price"] = 24800.0
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["atm_proximity"] == 100

    def test_gamma_theta_ratio(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["gamma_theta_ratio"] > 0

    def test_delta_flip_zone(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["delta_flip_price"] == base_data["greeks"]["atm_strike"]

    def test_delta_per_rupee(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert abs(ctx["delta_per_rupee_ce"] - 0.52 / 180.0) < 0.001
        assert abs(ctx["delta_per_rupee_pe"] - 0.48 / 165.0) < 0.001

    def test_iv_hv_spread(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        expected = ((0.14 + 0.15) / 2 * 100) - (0.12 * 100)
        assert abs(ctx["iv_hv_spread"] - expected) < 0.1

    def test_vega_risk_label(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["vega_risk_label"] == "MEDIUM"

    def test_theta_per_minute(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["theta_per_minute"] < 0

    def test_gamma_peak_false_when_dte_gt_1(self, module, base_data):
        base_data["greeks"]["expiry_date"] = (
            datetime.date.today() + datetime.timedelta(days=3)
        ).strftime("%Y-%m-%d")
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["gamma_peak"] is False

    def test_gamma_peak_true_when_near_atm_0dte(self, module, base_data):
        base_data["greeks"]["expiry_date"] = datetime.date.today().strftime("%Y-%m-%d")
        base_data["current_price"] = 24810.0
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["gamma_peak"] is True


class TestOIMetrics:
    def test_empty_oi_returns_defaults(self, module, base_data):
        """No OI data -> safe defaults."""
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["oi_buildup_signal"] == "NEUTRAL"
        assert ctx["oi_change_ce"] == 0
        assert ctx["oi_change_pe"] == 0

    def test_oi_snapshots_accumulate(self, module, base_data):
        """OI snapshots build up over multiple updates."""
        oi_data = {"key1": 1000.0, "key2": 2000.0}
        metadata = {"key1": {"strike": 24800, "option_type": "CE"}, "key2": {"strike": 24800, "option_type": "PE"}}
        base_data["pcr_oi_data"] = oi_data
        base_data["pcr_option_metadata"] = metadata

        # First update
        module.update(base_data)
        # Force time advancement for second snapshot
        module._last_oi_time = 0
        base_data["pcr_oi_data"] = {"key1": 1100.0, "key2": 2100.0}
        module.update(base_data)

        ctx = module.get_context()
        assert ctx["oi_change_ce"] == 100  # 1100 - 1000
        assert ctx["oi_change_pe"] == 100  # 2100 - 2000

    def test_max_pain_calculation(self, module):
        per_strike = {
            24700: {"ce_oi": 5000, "pe_oi": 1000},
            24800: {"ce_oi": 3000, "pe_oi": 3000},
            24900: {"ce_oi": 1000, "pe_oi": 5000},
        }
        result = module._compute_max_pain(per_strike)
        assert result is not None
        assert result in [24700, 24800, 24900]

    def test_oi_concentration(self, module):
        per_strike = {
            24700: {"ce_oi": 100, "pe_oi": 100},
            24800: {"ce_oi": 5000, "pe_oi": 5000},  # dominant
            24900: {"ce_oi": 100, "pe_oi": 100},
        }
        total = sum(v["ce_oi"] + v["pe_oi"] for v in per_strike.values())
        result = module._compute_oi_concentration(per_strike, total)
        assert result > 50  # Most OI concentrated at 24800


class TestCompositeScore:
    def test_score_in_range(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert 0 <= ctx["score"] <= 100

    def test_score_band_mapping(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["score_band"] in ("PRIME", "GOOD", "CAUTION", "AVOID")

    def test_sub_scores_present(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert "greeks" in ctx["sub_scores"]
        assert "oi" in ctx["sub_scores"]
        assert "time_decay" in ctx["sub_scores"]
        assert "liquidity" in ctx["sub_scores"]
        assert "market_context" in ctx["sub_scores"]


class TestMarketContext:
    def test_time_zone_detection(self, module):
        zone, mins = module._compute_time_zone()
        assert zone in ("PEAK", "LOW", "MODERATE", "CLOSED")
        assert isinstance(mins, int)

    def test_regime_recommendation(self, module, base_data):
        base_data["market_regime"] = "TRENDING"
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["regime_scalp_recommendation"] == "Directional scalps"


class TestLiquidity:
    def test_empty_bid_ask_returns_defaults(self, module, base_data):
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["spread_ce_label"] == "POOR"
        assert ctx["lot_liquidity_score"] == 0

    def test_excellent_spread(self, module, base_data):
        base_data["bid_ask_cache"] = {
            "ce_spread_pct": 0.1,
            "pe_spread_pct": 0.2,
            "ce_bid_qty": 500,
            "ce_ask_qty": 500,
            "pe_bid_qty": 400,
            "pe_ask_qty": 400,
        }
        module.update(base_data)
        ctx = module.get_context()
        assert ctx["spread_ce_label"] == "EXCELLENT"


class TestEdgeCases:
    def test_no_data_returns_safe_defaults(self, module):
        """Module with no data should return safe defaults without errors."""
        ctx = module.get_context()
        assert ctx["score"] == 0 or ctx["score"] >= 0
        assert ctx["gex_rupees"] == 0.0
        assert ctx["oi_buildup_signal"] == "NEUTRAL"

    def test_partial_greeks_data(self, module):
        """Only CE greeks, no PE -> should not crash."""
        module.update({
            "current_price": 24800,
            "greeks": {
                "atm_strike": 24800,
                "expiry_date": "2026-02-24",
                "ce": {"delta": 0.5, "gamma": 0.001, "theta": -5, "vega": 4, "iv": 0.14, "price": 150},
            }
        })
        ctx = module.get_context()
        assert ctx["gex_rupees"] == 0.0  # needs both CE and PE

    def test_module_name(self, module):
        assert module.name == "scalp_health"

    def test_reset_clears_state(self, module, base_data):
        module.update(base_data)
        module.reset()
        assert len(module._oi_snapshots) == 0
        assert module._day_open == 0.0
