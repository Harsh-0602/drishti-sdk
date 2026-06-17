"""
Main Drishti client.

Usage:
    from drishti import Drishti

    # Instantiate once at module level
    drishti = Drishti(api_key="dk_live_...")

    # Pattern 1: Context manager (recommended)
    with drishti.trace("handle_user_query", input=user_query) as trace:
        with trace.step("memory_lookup", "memory") as step:
            context = memory.search(user_query)
            step.set_output({"chunks": len(context)})

        with trace.step("llm_call", "llm") as step:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": user_query}],
            )
            step.record_llm(
                "gpt-4o-mini",
                tokens_input=response.usage.prompt_tokens,
                tokens_output=response.usage.completion_tokens,
            )
        trace.set_output(response.choices[0].message.content)

    # Pattern 2: Decorator
    @drishti.watch
    def run_agent(query: str) -> str:
        return agent.run(query)
"""
import functools
import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional, Any

from .errors import DrishtiAuthError
from .sender import AsyncSender
from .trace import ActiveTrace

logger = logging.getLogger("drishti")


class Drishti:
    """
    Main Drishti observability client.
    
    Instantiate once per application. Thread-safe. Never blocks your
    agent's main thread — all sends happen in a background daemon thread.
    
    Args:
        api_key: Your Drishti project API key (starts with "dk_").
                 Falls back to DRISHTI_API_KEY environment variable.
        endpoint: Drishti backend URL. Defaults to https://drishti-backend-3fks.onrender.com.
                  Falls back to DRISHTI_ENDPOINT env var.
        debug:    Print SDK logs to stderr. Useful during development.
    
    Raises:
        DrishtiAuthError: If api_key is missing or malformed.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        debug: bool = False,
    ):
        # Resolve API key
        resolved_key = api_key or os.environ.get("DRISHTI_API_KEY", "")
        if not resolved_key:
            raise DrishtiAuthError(
                "Drishti API key missing. Pass api_key='dk_...' or set "
                "DRISHTI_API_KEY environment variable."
            )
        if not resolved_key.startswith("dk_"):
            raise DrishtiAuthError(
                f"Invalid API key format: '{resolved_key[:8]}...'. "
                "Drishti keys start with 'dk_'. "
                "Get your key from https://drishti.dev/dashboard/settings"
            )

        # Resolve endpoint
        resolved_endpoint = (
            endpoint
            or os.environ.get("DRISHTI_ENDPOINT", "https://drishti-backend-3fks.onrender.com")
        )

        self.api_key = resolved_key
        self.endpoint = resolved_endpoint
        self.debug = debug

        if debug:
            logging.basicConfig(level=logging.DEBUG)
            logger.debug("Drishti client initialised → %s", resolved_endpoint)

        self._sender = AsyncSender(
            api_key=resolved_key,
            endpoint=resolved_endpoint,
            debug=debug,
        )

    # ------------------------------------------------------------------
    # Context manager: drishti.trace(...)
    # ------------------------------------------------------------------

    @contextmanager
    def trace(
        self,
        name: str,
        input: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Generator[ActiveTrace, None, None]:
        """
        Context manager to trace an entire agent run.
        
        Args:
            name:       Descriptive name for this run (e.g. "handle_query")
            input:      The user's input / prompt (first 500 chars stored)
            tags:       List of string tags for filtering in dashboard
            metadata:   Arbitrary key-value pairs (stored as JSON)
            session_id: Group multiple traces into a session
            user_id:    Your app's user identifier for per-user analytics
        
        Yields:
            ActiveTrace: Use this to add steps, set output, etc.
        
        Example:
            with drishti.trace("my_agent", input=user_query) as trace:
                result = agent.run(user_query)
                trace.set_output(result)
        """
        active = ActiveTrace(name=name, sender=self._sender)

        if input is not None:
            active.data.input_preview = str(input)[:500]
        if tags:
            active.data.tags = tags
        if metadata:
            active.data.metadata.update(metadata)
        if session_id:
            active.data.metadata["session_id"] = session_id
        if user_id:
            active.data.metadata["user_identifier"] = user_id

        error: Optional[str] = None
        output: Optional[Any] = None
        try:
            yield active
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            active._finish(output=output, error=error)

    # ------------------------------------------------------------------
    # Decorator: @drishti.watch
    # ------------------------------------------------------------------

    def watch(self, func=None, *, name: Optional[str] = None):
        """
        Decorator to auto-trace a function.
        
        Usage:
            @drishti.watch
            def run_agent(query: str) -> str:
                return agent.run(query)
        
            # Or with a custom trace name:
            @drishti.watch(name="my_custom_name")
            def run_agent(query: str) -> str:
                ...
        """
        def decorator(f):
            trace_name = name or f.__name__

            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                # Extract first string arg as input preview if available
                input_preview = None
                if args and isinstance(args[0], str):
                    input_preview = args[0]

                with self.trace(trace_name, input=input_preview) as trace:
                    result = f(*args, **kwargs)
                    if result is not None:
                        trace.set_output(result)
                    return result

            return wrapper

        # Handle both @drishti.watch and @drishti.watch(name="...")
        if func is not None:
            return decorator(func)
        return decorator

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self, wait: bool = True) -> None:
        """
        Gracefully shut down the background sender.
        
        Call this if you want to ensure all traces are sent before
        your process exits. Not required in most cases — the daemon
        thread will naturally flush on process exit.
        
        Args:
            wait: If True, blocks until queue is fully drained.
        """
        self._sender.shutdown(wait=wait)
