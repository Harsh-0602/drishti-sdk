"""
Non-blocking async sender to the Drishti API.

Sends traces in a background daemon thread so the developer's
agent code is never blocked. Retries up to 3 times before dropping.
Local buffer: max 1,000 traces queued.
"""
import importlib.metadata
import json
import logging
import queue
import threading
from dataclasses import asdict
from datetime import datetime, date
from typing import Any

try:
    _SDK_VERSION = importlib.metadata.version("drishti-ai-sdk")
except importlib.metadata.PackageNotFoundError:
    _SDK_VERSION = "dev"

import httpx

from .trace import TraceData

logger = logging.getLogger("drishti.sender")

MAX_QUEUE_SIZE = 1000
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # seconds between retries


def _json_default(obj: Any) -> Any:
    """Custom JSON serialiser for datetime objects and dataclasses."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Cannot serialize type {type(obj).__name__}")


class AsyncSender:
    """
    Background sender that never blocks the main thread.
    
    Uses a daemon thread with a bounded queue. If the queue is full
    (1000 items), oldest items are dropped with a warning in debug mode.
    """

    def __init__(self, api_key: str, endpoint: str, debug: bool = False):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.debug = debug
        self._queue: queue.Queue[TraceData] = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self._shutdown = threading.Event()
        self._thread = threading.Thread(
            target=self._worker,
            name="drishti-sender",
            daemon=True,  # won't block process exit
        )
        self._thread.start()
        if self.debug:
            logger.debug(f"Drishti sender started → {self.endpoint}")

    def send(self, trace: TraceData) -> None:
        """
        Enqueue a trace for background sending.
        This is always non-blocking — returns immediately.
        """
        try:
            self._queue.put_nowait(trace)
        except queue.Full:
            if self.debug:
                logger.warning(
                    "Drishti queue full (1000 items). "
                    "Dropping trace '%s'. Consider increasing send frequency.",
                    trace.name,
                )

    def _worker(self) -> None:
        """Background thread: pull from queue, send with retries."""
        while not self._shutdown.is_set():
            try:
                trace = self._queue.get(timeout=0.5)
                self._send_with_retry(trace)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as exc:
                if self.debug:
                    logger.error("Drishti worker error: %s", exc)

    def _send_with_retry(self, trace: TraceData) -> None:
        """Attempt to POST the trace, retrying up to MAX_RETRIES times."""
        payload = self._serialize(trace)

        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        f"{self.endpoint}/v1/traces",
                        content=payload,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "X-Drishti-SDK": f"python/{_SDK_VERSION}",
                        },
                    )
                    if resp.status_code == 201:
                        if self.debug:
                            logger.debug(
                                "Drishti: trace '%s' sent ✓", trace.name
                            )
                        return
                    elif resp.status_code == 401:
                        # Auth error — no point retrying
                        if self.debug:
                            logger.error(
                                "Drishti: invalid API key — check your dk_ key"
                            )
                        return
                    else:
                        if self.debug:
                            logger.warning(
                                "Drishti: unexpected status %d for trace '%s'",
                                resp.status_code,
                                trace.name,
                            )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if self.debug:
                    logger.warning(
                        "Drishti: send attempt %d/%d failed — %s",
                        attempt + 1,
                        MAX_RETRIES,
                        exc,
                    )

            # Wait before retry (skip delay on last attempt)
            if attempt < MAX_RETRIES - 1:
                import time
                time.sleep(RETRY_DELAYS[attempt])

        if self.debug:
            logger.error(
                "Drishti: gave up sending trace '%s' after %d attempts",
                trace.name,
                MAX_RETRIES,
            )

    def _serialize(self, trace: TraceData) -> bytes:
        """Convert TraceData to JSON bytes."""
        raw = asdict(trace)
        return json.dumps(raw, default=_json_default).encode("utf-8")

    def shutdown(self, wait: bool = True) -> None:
        """
        Gracefully shut down the sender.
        Optionally wait for the queue to drain.
        """
        if wait:
            self._queue.join()
        self._shutdown.set()
        self._thread.join(timeout=5)
