"""Tests for the INR cost calculation module."""
import pytest
from drishti.costs import (
    calculate_cost_inr,
    get_usd_inr_rate,
    format_inr,
    MODEL_COSTS,
    FALLBACK_RATE,
)


class TestGetUsdInrRate:
    def test_returns_positive_float(self):
        rate = get_usd_inr_rate()
        assert isinstance(rate, float)
        assert rate > 50  # sanity check — rate won't fall below 50

    def test_cached_result(self):
        rate1 = get_usd_inr_rate()
        rate2 = get_usd_inr_rate()
        assert rate1 == rate2  # second call uses cache


class TestCalculateCostInr:
    def test_gpt4o_mini_basic(self):
        usd, inr = calculate_cost_inr("gpt-4o-mini", tokens_input=1000, tokens_output=500)
        assert usd > 0
        assert inr > 0
        # Expected: (1000/1000 * 0.00015) + (500/1000 * 0.0006) = 0.00015 + 0.0003 = 0.00045 USD
        assert abs(usd - 0.00045) < 1e-7

    def test_gpt4o(self):
        usd, inr = calculate_cost_inr("gpt-4o", tokens_input=1000, tokens_output=1000)
        # (1000/1000 * 0.0025) + (1000/1000 * 0.010) = 0.0025 + 0.010 = 0.0125
        assert abs(usd - 0.0125) < 1e-7

    def test_claude_sonnet(self):
        usd, inr = calculate_cost_inr("claude-sonnet-4", tokens_input=500, tokens_output=500)
        # (0.5 * 0.003) + (0.5 * 0.015) = 0.0015 + 0.0075 = 0.009
        assert abs(usd - 0.009) < 1e-7

    def test_gemini_flash(self):
        usd, inr = calculate_cost_inr("gemini-2.0-flash", tokens_input=10000, tokens_output=5000)
        # (10 * 0.000075) + (5 * 0.0003) = 0.00075 + 0.0015 = 0.00225
        assert abs(usd - 0.00225) < 1e-7

    def test_zero_tokens(self):
        usd, inr = calculate_cost_inr("gpt-4o", tokens_input=0, tokens_output=0)
        assert usd == 0.0
        assert inr == 0.0

    def test_unknown_model_fallback(self):
        usd, inr = calculate_cost_inr("some-unknown-model-xyz", tokens_input=1000, tokens_output=500)
        # Should return a non-zero estimate, not crash
        assert usd > 0
        assert inr > 0

    def test_inr_is_usd_times_rate(self):
        usd, inr = calculate_cost_inr("gpt-4o-mini", tokens_input=1000, tokens_output=500)
        rate = get_usd_inr_rate()
        assert abs(inr - round(usd * rate, 6)) < 1e-5

    def test_case_insensitive_model(self):
        usd1, _ = calculate_cost_inr("GPT-4O-MINI", 1000, 500)
        usd2, _ = calculate_cost_inr("gpt-4o-mini", 1000, 500)
        assert usd1 == usd2

    def test_partial_model_match(self):
        # "gpt-4o-mini-2024-07-18" should match "gpt-4o-mini"
        usd, inr = calculate_cost_inr("gpt-4o-mini-2024-07-18", 1000, 500)
        assert usd > 0

    def test_all_models_return_costs(self):
        for model in MODEL_COSTS:
            usd, inr = calculate_cost_inr(model, tokens_input=1000, tokens_output=1000)
            assert usd > 0, f"Model {model} returned zero USD cost"
            assert inr > 0, f"Model {model} returned zero INR cost"


class TestFormatInr:
    def test_small_amount(self):
        result = format_inr(0.001234)
        assert "₹" in result
        assert "0.0012" in result

    def test_normal_amount(self):
        result = format_inr(42.5)
        assert result == "₹42.50"

    def test_zero(self):
        result = format_inr(0.0)
        assert "₹" in result
