"""Data models for Lean API integration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class VerificationStatus(Enum):
    """Status of Lean proof verification."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"
    RUNNING = "running"
    CANCELLED = "cancelled"


class ErrorSeverity(Enum):
    """Severity level of Lean errors."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class LeanError:
    """Represents a Lean error message.

    Attributes:
        message: The error message text.
        error_type: Type of error (e.g., 'type mismatch', 'unknown constant').
        line: Line number where error occurred (1-indexed).
        column: Column number where error occurred (1-indexed).
        severity: Severity level of the error.
    """

    message: str
    error_type: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    severity: ErrorSeverity = ErrorSeverity.ERROR

    def __str__(self) -> str:
        location = ""
        if self.line is not None:
            location = f"line {self.line}"
            if self.column is not None:
                location += f", column {self.column}"
            location += ": "
        return f"{location}{self.message}"


@dataclass(frozen=True)
class TacticState:
    """Represents the current state of tactics in Lean.

    Attributes:
        goals: List of remaining goals as strings.
        main_goal: The current main goal being worked on.
    """

    goals: List[str] = field(default_factory=list)
    main_goal: Optional[str] = None


@dataclass(frozen=True)
class VerificationResult:
    """Result of Lean proof verification.

    Attributes:
        status: Verification status enum.
        message: Human-readable message about the result.
        errors: List of errors encountered during verification.
        execution_time: Time taken to verify in seconds.
        tactic_state: Final tactic state if available.
    """

    status: VerificationStatus
    message: str
    errors: List[LeanError] = field(default_factory=list)
    execution_time: Optional[float] = None
    tactic_state: Optional[TacticState] = None

    @property
    def is_success(self) -> bool:
        """Check if verification was successful."""
        return self.status == VerificationStatus.SUCCESS

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    def __str__(self) -> str:
        parts = [f"Status: {self.status.value}", self.message]
        if self.execution_time is not None:
            parts.append(f"Time: {self.execution_time:.3f}s")
        if self.errors:
            parts.append(f"Errors: {len(self.errors)}")
        return " | ".join(parts)


@dataclass(frozen=True)
class LeanConfig:
    """Configuration for Lean API client.

    Attributes:
        base_url: Base URL of the Lean server.
        timeout: Default timeout for requests in seconds.
        max_retries: Maximum number of retry attempts.
        retry_delay: Initial delay between retries in seconds.
        retry_backoff: Backoff multiplier for exponential retry.
    """

    base_url: str
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0


@dataclass
class LeanRequest:
    """Request to submit to Lean API.

    Attributes:
        code: Lean code to verify.
        filename: Optional filename for the code.
        timeout: Optional timeout override in seconds.
    """

    code: str
    filename: Optional[str] = None
    timeout: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("Code cannot be empty")
