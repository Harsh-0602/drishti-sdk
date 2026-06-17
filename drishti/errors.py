"""Custom exceptions for the Drishti SDK."""


class DrishtiError(Exception):
    """Base exception for all Drishti SDK errors."""
    pass


class DrishtiAuthError(DrishtiError):
    """Raised when the API key is invalid or missing."""
    pass


class DrishtiNetworkError(DrishtiError):
    """Raised when the Drishti backend cannot be reached."""
    pass


class DrishtiQueueFullError(DrishtiError):
    """Raised when the local send queue is at capacity (1000 traces)."""
    pass
