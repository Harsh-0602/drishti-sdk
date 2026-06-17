"""
INR cost calculation for all major LLM models.

Costs are per 1,000 tokens in USD, converted to INR using
a live exchange rate (cached every 6 hours, fallback to 84.5).
"""
import httpx
from datetime import datetime, timedelta
from typing import Optional

# ------------------------------------------------------------------
# Model costs — USD per 1,000 tokens (input / output)
# ------------------------------------------------------------------
MODEL_COSTS: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o":              {"input": 0.0025,   "output": 0.0100},
    "gpt-4o-mini":         {"input": 0.000150, "output": 0.000600},
    "gpt-4-turbo":         {"input": 0.0100,   "output": 0.0300},
    "gpt-4":               {"input": 0.0300,   "output": 0.0600},
    "gpt-3.5-turbo":       {"input": 0.000500, "output": 0.001500},
    "o1":                  {"input": 0.0150,   "output": 0.0600},
    "o1-mini":             {"input": 0.001100, "output": 0.004400},
    "o3-mini":             {"input": 0.001100, "output": 0.004400},
    "o3":                  {"input": 0.0100,   "output": 0.0400},
    # Anthropic
    "claude-opus-4":       {"input": 0.0150,   "output": 0.0750},
    "claude-sonnet-4":     {"input": 0.003000, "output": 0.015000},
    "claude-haiku-4":      {"input": 0.000800, "output": 0.004000},
    "claude-opus-4-6":     {"input": 0.0150,   "output": 0.0750},
    "claude-sonnet-4-6":   {"input": 0.003000, "output": 0.015000},
    "claude-haiku-4-5":    {"input": 0.000800, "output": 0.004000},
    "claude-3-5-sonnet":   {"input": 0.003000, "output": 0.015000},
    "claude-3-haiku":      {"input": 0.000250, "output": 0.001250},
    # Google
    "gemini-2.0-flash":    {"input": 0.000075, "output": 0.000300},
    "gemini-2.5-pro":      {"input": 0.001250, "output": 0.010000},
    "gemini-1.5-flash":    {"input": 0.000075, "output": 0.000300},
    "gemini-1.5-pro":      {"input": 0.001250, "output": 0.005000},
    # DeepSeek
    "deepseek-v3":         {"input": 0.000140, "output": 0.000280},
    "deepseek-r1":         {"input": 0.000550, "output": 0.002190},
    "deepseek-chat":       {"input": 0.000140, "output": 0.000280},
    # Meta / Llama
    "llama-3.3-70b":       {"input": 0.000230, "output": 0.000400},
    "llama-3.1-8b":        {"input": 0.000060, "output": 0.000060},
    "llama-3.1-70b":       {"input": 0.000230, "output": 0.000400},
    # Mistral
    "mistral-large":       {"input": 0.002000, "output": 0.006000},
    "mistral-small":       {"input": 0.000200, "output": 0.000600},
    "mixtral-8x7b":        {"input": 0.000600, "output": 0.000600},
}

# ------------------------------------------------------------------
# Exchange rate cache
# ------------------------------------------------------------------
_cached_rate: Optional[float] = None
_rate_cached_at: Optional[datetime] = None
FALLBACK_RATE: float = 84.5
CACHE_TTL_HOURS: int = 6


def get_usd_inr_rate() -> float:
    """
    Get live USD/INR exchange rate.
    
    Cached for 6 hours to avoid hammering the exchange rate API.
    Falls back to 84.5 if the API is unreachable.
    """
    global _cached_rate, _rate_cached_at

    if _cached_rate is not None and _rate_cached_at is not None:
        age = datetime.now() - _rate_cached_at
        if age < timedelta(hours=CACHE_TTL_HOURS):
            return _cached_rate

    try:
        resp = httpx.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=3.0,
        )
        resp.raise_for_status()
        rate = float(resp.json()["rates"]["INR"])
        _cached_rate = rate
        _rate_cached_at = datetime.now()
        return rate
    except Exception:
        # Graceful fallback — never crash developer's agent
        return _cached_rate if _cached_rate is not None else FALLBACK_RATE


def _find_model_costs(model: str) -> dict[str, float]:
    """Fuzzy-match model name to cost entry."""
    model_lower = model.lower().strip()

    # Exact match first
    if model_lower in MODEL_COSTS:
        return MODEL_COSTS[model_lower]

    # Partial match — check if any known key appears in the model string
    for key, costs in MODEL_COSTS.items():
        if key in model_lower:
            return costs

    # Reverse partial — check if model string appears in any key
    for key, costs in MODEL_COSTS.items():
        if model_lower in key:
            return costs

    # Default estimate for unknown models
    return {"input": 0.005, "output": 0.015}


def calculate_cost_inr(
    model: str,
    tokens_input: int = 0,
    tokens_output: int = 0,
) -> tuple[float, float]:
    """
    Calculate LLM call cost.
    
    Args:
        model: Model name (e.g. "gpt-4o", "claude-sonnet-4")
        tokens_input: Number of input/prompt tokens
        tokens_output: Number of output/completion tokens
    
    Returns:
        Tuple of (cost_usd, cost_inr) — both rounded appropriately
    
    Example:
        usd, inr = calculate_cost_inr("gpt-4o-mini", 1000, 500)
        print(f"₹{inr}")  # ₹0.0891
    """
    costs = _find_model_costs(model)
    cost_usd = (
        (tokens_input / 1000.0) * costs["input"]
        + (tokens_output / 1000.0) * costs["output"]
    )
    cost_inr = cost_usd * get_usd_inr_rate()
    return round(cost_usd, 8), round(cost_inr, 6)


def format_inr(amount: float) -> str:
    """Format an INR amount with ₹ symbol and 2 decimal places."""
    if amount < 0.01:
        return f"₹{amount:.4f}"
    return f"₹{amount:.2f}"
