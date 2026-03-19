"""Custom exceptions for Lean API integration."""

from typing import Optional


class LeanAPIError(Exception):
    """Base exception for Lean API errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class LeanConnectionError(LeanAPIError):
    """Raised when connection to Lean server fails."""

    pass


class LeanTimeoutError(LeanAPIError):
    """Raised when Lean execution times out."""

    def __init__(
        self,
        message: str,
        timeout: Optional[float] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, details)
        self.timeout = timeout


class LeanExecutionError(LeanAPIError):
    """Raised when Lean code execution fails."""

    def __init__(
        self,
        message: str,
        error_type: Optional[str] = None,
        line: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, details)
        self.error_type = error_type
        self.line = line


class LeanValidationError(LeanAPIError):
    """Raised when Lean proof validation fails."""

    def __init__(
        self,
        message: str,
        tactic_state: Optional[str] = None,
        remaining_goals: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, details)
        self.tactic_state = tactic_state
        self.remaining_goals = remaining_goals


class LeanServerError(LeanAPIError):
    """Raised when Lean server returns an error response."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, details)
        self.status_code = status_code
