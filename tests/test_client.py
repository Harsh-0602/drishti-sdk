"""Tests for the main Drishti client."""
import pytest
from unittest.mock import MagicMock, patch
from drishti import Drishti
from drishti.errors import DrishtiAuthError


class TestDrishtiInit:
    def test_valid_key(self):
        client = Drishti(api_key="dk_test_abc123")
        assert client.api_key == "dk_test_abc123"

    def test_missing_key_raises(self):
        with pytest.raises(DrishtiAuthError, match="API key missing"):
            Drishti(api_key="")

    def test_invalid_key_prefix_raises(self):
        with pytest.raises(DrishtiAuthError, match="Invalid API key format"):
            Drishti(api_key="sk_not_a_drishti_key")

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("DRISHTI_API_KEY", "dk_from_env_123")
        client = Drishti()
        assert client.api_key == "dk_from_env_123"

    def test_custom_endpoint(self):
        client = Drishti(api_key="dk_test", endpoint="http://localhost:8000")
        assert client.endpoint == "http://localhost:8000"


class TestDrishtiTrace:
    def setup_method(self):
        self.client = Drishti(api_key="dk_test_abc")
        # Replace sender with a mock
        self.mock_sender = MagicMock()
        self.client._sender = self.mock_sender

    def test_trace_sends_on_exit(self):
        with self.client.trace("test_run"):
            pass
        self.mock_sender.send.assert_called_once()
        sent = self.mock_sender.send.call_args[0][0]
        assert sent.name == "test_run"

    def test_trace_with_input(self):
        with self.client.trace("test_run", input="hello world"):
            pass
        sent = self.mock_sender.send.call_args[0][0]
        assert sent.input_preview == "hello world"

    def test_trace_with_tags(self):
        with self.client.trace("test_run", tags=["prod", "v2"]):
            pass
        sent = self.mock_sender.send.call_args[0][0]
        assert "prod" in sent.tags

    def test_trace_exception_propagates(self):
        with pytest.raises(RuntimeError, match="agent crashed"):
            with self.client.trace("failing_run"):
                raise RuntimeError("agent crashed")
        # Trace should still be sent
        self.mock_sender.send.assert_called_once()
        sent = self.mock_sender.send.call_args[0][0]
        assert sent.status == "error"

    def test_trace_sends_even_on_exception(self):
        """Agent failure should never prevent trace from being sent."""
        try:
            with self.client.trace("test"):
                raise ValueError("boom")
        except ValueError:
            pass
        self.mock_sender.send.assert_called_once()


class TestDrishtiWatch:
    def setup_method(self):
        self.client = Drishti(api_key="dk_test_abc")
        self.mock_sender = MagicMock()
        self.client._sender = self.mock_sender

    def test_watch_decorator(self):
        @self.client.watch
        def my_func(query: str) -> str:
            return f"Answer: {query}"

        result = my_func("What is 2+2?")
        assert result == "Answer: What is 2+2?"
        self.mock_sender.send.assert_called_once()
        sent = self.mock_sender.send.call_args[0][0]
        assert sent.name == "my_func"

    def test_watch_with_custom_name(self):
        @self.client.watch(name="custom_agent_run")
        def my_func():
            return "ok"

        my_func()
        sent = self.mock_sender.send.call_args[0][0]
        assert sent.name == "custom_agent_run"

    def test_watch_preserves_return_value(self):
        @self.client.watch
        def compute() -> int:
            return 42

        assert compute() == 42
