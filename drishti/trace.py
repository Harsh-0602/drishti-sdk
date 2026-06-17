"""
Trace and Step context managers.

Usage:
    with drishti.trace("handle_query") as trace:
        with trace.step("llm_call", "llm", model="gpt-4o-mini") as step:
            response = llm.complete(prompt)
            step.record_llm("gpt-4o-mini", tokens_in=500, tokens_out=200)
"""
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any, Generator, TYPE_CHECKING

from .costs import calculate_cost_inr

if TYPE_CHECKING:
    from .sender import AsyncSender


# ------------------------------------------------------------------
# Data classes (serialisable — sent to backend)
# ------------------------------------------------------------------

@dataclass
class StepData:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: str = "custom"
    status: str = "ok"
    cost_inr: float = 0.0
    cost_usd: float = 0.0
    latency_ms: int = 0
    model: Optional[str] = None
    tokens_input: int = 0
    tokens_output: int = 0
    input: Optional[Any] = None
    output: Optional[Any] = None
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    started_at: Optional[str] = None   # ISO format string
    ended_at: Optional[str] = None


@dataclass
class TraceData:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    status: str = "ok"
    total_cost_inr: float = 0.0
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    model_used: Optional[str] = None
    tokens_input: int = 0
    tokens_output: int = 0
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    error_message: Optional[str] = None
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    steps: list = field(default_factory=list)   # list[StepData]
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------
# ActiveStep — context manager for a single step
# ------------------------------------------------------------------

class ActiveStep:
    """
    Context manager for a single step within a trace.
    
    with trace.step("memory_lookup", "memory") as step:
        results = memory.search(query)
        step.set_output({"results": len(results)})
    """

    def __init__(self, name: str, step_type: str, model: Optional[str] = None):
        self.data = StepData(
            name=name,
            type=step_type,
            model=model,
            started_at=_now_iso(),
        )
        self._start_time = time.perf_counter()

    def record_llm(
        self,
        model: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
        """
        Record LLM usage details and calculate cost.
        Call this after your LLM call completes.
        
        Args:
            model: Model name, e.g. "gpt-4o-mini"
            tokens_input: Prompt token count
            tokens_output: Completion token count
        """
        self.data.model = model
        self.data.tokens_input = tokens_input
        self.data.tokens_output = tokens_output
        self.data.type = "llm"
        cost_usd, cost_inr = calculate_cost_inr(model, tokens_input, tokens_output)
        self.data.cost_usd = cost_usd
        self.data.cost_inr = cost_inr

    def set_input(self, data: Any) -> None:
        """Set the step's input data (will be stored as JSON)."""
        self.data.input = data

    def set_output(self, data: Any) -> None:
        """Set the step's output data (will be stored as JSON)."""
        self.data.output = data

    def set_metadata(self, **kwargs: Any) -> None:
        """Add arbitrary metadata key-value pairs."""
        self.data.metadata.update(kwargs)

    def _finish(self, error: Optional[str] = None) -> None:
        """Finalise timing. Called automatically by ActiveTrace."""
        elapsed = time.perf_counter() - self._start_time
        self.data.ended_at = _now_iso()
        self.data.latency_ms = int(elapsed * 1000)
        if error:
            self.data.status = "error"
            self.data.error_message = error


# ------------------------------------------------------------------
# ActiveTrace — context manager for a full agent run
# ------------------------------------------------------------------

class ActiveTrace:
    """
    Context manager for tracing an entire agent run.
    
    with drishti.trace("handle_user_query") as trace:
        with trace.step("llm_call", "llm") as step:
            resp = llm.complete(prompt)
            step.record_llm("gpt-4o-mini", 500, 200)
    """

    def __init__(self, name: str, sender: "AsyncSender"):
        self._sender = sender
        self._start_time = time.perf_counter()
        self.data = TraceData(
            name=name,
            started_at=_now_iso(),
        )

    @contextmanager
    def step(
        self,
        name: str,
        step_type: str = "custom",
        model: Optional[str] = None,
    ) -> Generator[ActiveStep, None, None]:
        """
        Context manager for a single step within this trace.
        
        Args:
            name: Descriptive name, e.g. "memory_lookup", "llm_call"
            step_type: One of: llm | tool | memory | retrieval | custom
            model: Optional model name for LLM steps
        """
        active_step = ActiveStep(name=name, step_type=step_type, model=model)
        try:
            yield active_step
        except Exception as exc:
            active_step._finish(error=str(exc))
            self.data.status = "error"
            if not self.data.error_message:
                self.data.error_message = str(exc)
            raise
        else:
            active_step._finish()
        finally:
            self.data.steps.append(active_step.data)
            # Accumulate costs and tokens
            self.data.total_cost_inr = round(
                self.data.total_cost_inr + active_step.data.cost_inr, 6
            )
            self.data.total_cost_usd = round(
                self.data.total_cost_usd + active_step.data.cost_usd, 8
            )
            self.data.tokens_input += active_step.data.tokens_input
            self.data.tokens_output += active_step.data.tokens_output
            # Track primary model used
            if active_step.data.model and not self.data.model_used:
                self.data.model_used = active_step.data.model

    def set_output(self, output: Any) -> None:
        """Set the trace output preview (first 500 chars)."""
        self.data.output_preview = str(output)[:500]

    def set_metadata(self, **kwargs: Any) -> None:
        """Add arbitrary metadata to the trace."""
        self.data.metadata.update(kwargs)

    def _finish(self, output: Optional[Any] = None, error: Optional[str] = None) -> None:
        """
        Finalise the trace and enqueue it for sending.
        Called automatically at end of `with drishti.trace(...)` block.
        """
        elapsed = time.perf_counter() - self._start_time
        self.data.ended_at = _now_iso()
        self.data.total_latency_ms = int(elapsed * 1000)

        if output is not None:
            self.data.output_preview = str(output)[:500]

        if error:
            self.data.status = "error"
            if not self.data.error_message:
                self.data.error_message = error

        # Mark slow traces (>5 seconds)
        if self.data.status == "ok" and self.data.total_latency_ms > 5000:
            self.data.status = "slow"

        # Fire and forget — never blocks
        self._sender.send(self.data)
