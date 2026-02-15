"""Tests for Greeks Quality Validator."""

import pytest
from app.core.greeks_validator import GreeksValidator, validate_greeks_quality


class TestValidateDelta:
    """Test delta validation."""

    def setup_method(self):
        self.v = GreeksValidator()

    def test_valid_ce_delta(self):
        self.v._validate_delta(0.5, 'CE', 100, 100)
        assert len(self.v.validation_errors) == 0

    def test_ce_delta_out_of_range(self):
        self.v._validate_delta(1.5, 'CE', 100, 100)
        assert len(self.v.validation_errors) == 1

    def test_ce_delta_negative_error(self):
        self.v._validate_delta(-0.1, 'CE', 100, 100)
        assert len(self.v.validation_errors) == 1

    def test_valid_pe_delta(self):
        self.v._validate_delta(-0.5, 'PE', 100, 100)
        assert len(self.v.validation_errors) == 0

    def test_pe_delta_out_of_range(self):
        self.v._validate_delta(0.5, 'PE', 100, 100)
        assert len(self.v.validation_errors) == 1

    def test_itm_ce_low_delta_warning(self):
        """ITM CE (S>K) with low delta should warn."""
        self.v._validate_delta(0.3, 'CE', 110, 100)
        assert len(self.v.warnings) == 1

    def test_itm_pe_high_delta_warning(self):
        """ITM PE (S<K) with high delta should warn."""
        self.v._validate_delta(-0.3, 'PE', 90, 100)
        assert len(self.v.warnings) == 1


class TestValidateGamma:

    def setup_method(self):
        self.v = GreeksValidator()

    def test_positive_gamma(self):
        self.v._validate_gamma(0.005)
        assert len(self.v.validation_errors) == 0

    def test_negative_gamma_error(self):
        self.v._validate_gamma(-0.001)
        assert len(self.v.validation_errors) == 1

    def test_very_high_gamma_warning(self):
        self.v._validate_gamma(0.02)
        assert len(self.v.warnings) == 1


class TestValidateTheta:

    def setup_method(self):
        self.v = GreeksValidator()

    def test_negative_theta_ok(self):
        self.v._validate_theta(-5.0, 'CE')
        assert len(self.v.validation_errors) == 0
        assert len(self.v.warnings) == 0

    def test_positive_ce_theta_warning(self):
        self.v._validate_theta(1.0, 'CE')
        assert len(self.v.warnings) == 1

    def test_very_high_theta_warning(self):
        self.v._validate_theta(-60.0, 'CE')
        assert len(self.v.warnings) == 1


class TestValidateVega:

    def setup_method(self):
        self.v = GreeksValidator()

    def test_positive_vega_ok(self):
        self.v._validate_vega(5.0)
        assert len(self.v.validation_errors) == 0

    def test_negative_vega_error(self):
        self.v._validate_vega(-1.0)
        assert len(self.v.validation_errors) == 1

    def test_very_high_vega_warning(self):
        self.v._validate_vega(150.0)
        assert len(self.v.warnings) == 1


class TestValidateRho:

    def setup_method(self):
        self.v = GreeksValidator()

    def test_positive_ce_rho_ok(self):
        self.v._validate_rho(2.0, 'CE')
        assert len(self.v.warnings) == 0

    def test_negative_ce_rho_warning(self):
        self.v._validate_rho(-1.0, 'CE')
        assert len(self.v.warnings) == 1

    def test_positive_pe_rho_warning(self):
        self.v._validate_rho(1.0, 'PE')
        assert len(self.v.warnings) == 1


class TestValidateIV:

    def setup_method(self):
        self.v = GreeksValidator()

    def test_reasonable_iv(self):
        self.v._validate_iv(0.25, 10, 100, 100, 0.5)
        assert len(self.v.validation_errors) == 0
        assert len(self.v.warnings) == 0

    def test_zero_iv_error(self):
        self.v._validate_iv(0, 10, 100, 100, 0.5)
        assert len(self.v.validation_errors) == 1

    def test_very_low_iv_warning(self):
        self.v._validate_iv(0.03, 10, 100, 100, 0.5)
        assert len(self.v.warnings) == 1

    def test_very_high_iv_warning(self):
        self.v._validate_iv(1.5, 10, 100, 100, 0.5)
        assert len(self.v.warnings) == 1


class TestValidateRelationships:

    def setup_method(self):
        self.v = GreeksValidator()

    def test_high_gamma_low_theta_warning(self):
        self.v._validate_relationships(0.5, 0.005, -0.5, 5.0, 0.1)
        assert len(self.v.warnings) == 1

    def test_deep_itm_high_gamma_warning(self):
        self.v._validate_relationships(0.95, 0.006, -5.0, 5.0, 0.1)
        assert any("Deep ITM/OTM" in w for w in self.v.warnings)


class TestQualityScore:

    def setup_method(self):
        self.v = GreeksValidator()

    def test_perfect_score(self):
        """No errors or warnings -> 100."""
        assert self.v._calculate_quality_score() == 100

    def test_score_with_errors(self):
        self.v.validation_errors = ["err1"]
        assert self.v._calculate_quality_score() == 70

    def test_score_with_warnings(self):
        self.v.warnings = ["warn1", "warn2"]
        assert self.v._calculate_quality_score() == 80

    def test_score_floor_at_zero(self):
        self.v.validation_errors = ["e1", "e2", "e3", "e4"]
        assert self.v._calculate_quality_score() == 0


class TestQualitySummary:

    def setup_method(self):
        self.v = GreeksValidator()

    def test_excellent(self):
        assert self.v._get_quality_summary(95) == "Excellent"

    def test_good(self):
        assert self.v._get_quality_summary(75) == "Good"

    def test_fair(self):
        assert self.v._get_quality_summary(55) == "Fair"

    def test_poor(self):
        assert self.v._get_quality_summary(30) == "Poor"


class TestFullValidation:
    """Test the full validate_greeks method end-to-end."""

    def test_valid_greeks(self):
        greeks_data = {
            'delta': 0.5, 'gamma': 0.003, 'theta': -5.0,
            'vega': 10.0, 'rho': 2.0, 'iv': 0.25
        }
        result = validate_greeks_quality(greeks_data, 100, 100, 0.1, 'CE', 10)
        assert result['is_valid'] is True
        assert result['quality_score'] > 0
        assert 'summary' in result

    def test_invalid_greeks(self):
        greeks_data = {
            'delta': 1.5, 'gamma': -0.01, 'theta': -5.0,
            'vega': -1.0, 'rho': 2.0, 'iv': 0
        }
        result = validate_greeks_quality(greeks_data, 100, 100, 0.1, 'CE', 10)
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
