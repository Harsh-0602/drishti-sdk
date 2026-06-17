"""Drishti — India's AI Agent Observability SDK"""
from .client import Drishti
from .costs import calculate_cost_inr, get_usd_inr_rate
from .trace import ActiveTrace, ActiveStep, TraceData, StepData
from .errors import DrishtiError, DrishtiAuthError, DrishtiNetworkError

__version__ = "0.1.0"
__all__ = [
    "Drishti",
    "calculate_cost_inr",
    "get_usd_inr_rate",
    "ActiveTrace",
    "ActiveStep",
    "TraceData",
    "StepData",
    "DrishtiError",
    "DrishtiAuthError",
    "DrishtiNetworkError",
]
