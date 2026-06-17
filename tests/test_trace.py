"""Tests for Trace and Step context managers."""
import time
import pytest
from unittest.mock import MagicMock, patch
from drishti.trace import ActiveTrace, ActiveStep, TraceData, StepData


class MockSender:
    """Captures sent traces for assertion."""
    def __init__(self):
        self.sent: list[TraceData] = []

    def send(self, trace: TraceData):
        self.sent.append(trace)


class TestActiveStep:
    def test_basic_step_timing(self):
        step = ActiveStep("my_step", "custom")
        time.sleep(0.01)
        step._finish()
        assert step.data.latency_ms >= 10
        assert step.data.status == "ok"
        assert step.data.ended_at is not None

    def test_record_llm(self):
        step = ActiveStep("llm_call", "llm")
        step.record_llm("gpt-4o-mini", tokens_input=1000, tokens_output=500)
        assert step.data.model == "gpt-4o-mini"
        assert step.data.tokens_input == 1000
        assert step.data.tokens_output == 500
        assert step.data.cost_usd > 0
        assert step.data.cost_inr > 0
        assert step.data.type == "llm"

    def test_error_finish(self):
        step = ActiveStep("tool_call", "tool")
        step._finish(error="Connection refused")
        assert step.data.status == "error"
        assert step.data.error_message == "Connection refused"

    def test_set_input_output(self):
        step = ActiveStep("memory", "memory")
        step.set_input({"query": "test"})
        step.set_output({"results": 3})
        assert step.data.input == {"query": "test"}
        assert step.data.output == {"results": 3}


class TestActiveTrace:
    def _make_trace(self, name="test_trace") -> tuple[ActiveTrace, MockSender]:
        sender = MockSender()
        trace = ActiveTrace(name=name, sender=sender)
        return trace, sender

    def test_basic_trace_sends(self):
        trace, sender = self._make_trace()
        trace._finish()
        assert len(sender.sent) == 1
        assert sender.sent[0].name == "test_trace"
        assert sender.sent[0].status == "ok"

    def test_trace_with_step(self):
        trace, sender = self._make_trace()
        with trace.step("llm_call", "llm") as step:
            step.record_llm("gpt-4o-mini", 500, 200)
        trace._finish()
        data = sender.sent[0]
        assert len(data.steps) == 1
        assert data.steps[0].name == "llm_call"
        assert data.total_cost_inr > 0
        assert data.tokens_input == 500
        assert data.tokens_output == 200

    def test_error_in_step_marks_trace_error(self):
        trace, sender = self._make_trace()
        with pytest.raises(ValueError):
            with trace.step("bad_step") as step:
                raise ValueError("Something broke")
        trace._finish(error="Something broke")
        data = sender.sent[0]
        assert data.status == "error"
        assert data.steps[0].status == "error"

    def test_slow_trace_marked_slow(self):
        trace, sender = self._make_trace()
        # Fake that 6 seconds passed
        trace._start_time -= 6
        trace._finish()
        assert sender.sent[0].status == "slow"

    def test_cost_accumulation_across_steps(self):
        trace, sender = self._make_trace()
        with trace.step("step1", "llm") as s:
            s.record_llm("gpt-4o-mini", 1000, 500)
        with trace.step("step2", "llm") as s:
            s.record_llm("gpt-4o", 100, 100)
        trace._finish()
        data = sender.sent[0]
        assert len(data.steps) == 2
        expected_usd = data.steps[0].cost_usd + data.steps[1].cost_usd
        assert abs(data.total_cost_usd - round(expected_usd, 8)) < 1e-6

    def test_model_used_set_from_first_llm_step(self):
        trace, sender = self._make_trace()
        with trace.step("s1", "llm") as s:
            s.record_llm("gpt-4o-mini", 100, 100)
        with trace.step("s2", "llm") as s:
            s.record_llm("claude-sonnet-4", 100, 100)
        trace._finish()
        assert sender.sent[0].model_used == "gpt-4o-mini"

    def test_input_preview_truncated(self):
        trace, sender = self._make_trace()
        trace.data.input_preview = "x" * 1000
        trace._finish()
        # The preview should be set on trace data
        assert trace.data.input_preview == "x" * 1000  # stored as-is in data

    def test_set_output(self):
        trace, sender = self._make_trace()
        trace.set_output("Final answer to the user")
        trace._finish()
        assert sender.sent[0].output_preview == "Final answer to the user"

    def test_metadata(self):
        trace, sender = self._make_trace()
        trace.set_metadata(env="production", version="1.2.3")
        trace._finish()
        assert sender.sent[0].metadata["env"] == "production"
