"""Lean API integration module for proof verification.

This module provides functionality to interact with a Lean proof assistant
server for verifying mathematical proofs.

Example:
    >>> from lean_api import LeanAPIClient, LeanConfig, LeanRequest
    >>>
    >>> config = LeanConfig(base_url="http://localhost:5000")
    >>> client = LeanAPIClient(config)
    >>> request = LeanRequest(code="theorem hello : True := trivial")
    >>> result = client.verify(request)
    >>> print(result.is_success)
"""

from .client import LeanAPIClient
from .exceptions import (
    LeanAPIError,
    LeanConnectionError,
    LeanExecutionError,
    LeanServerError,
    LeanTimeoutError,
    LeanValidationError,
)
from .models import (
    ErrorSeverity,
    LeanConfig,
    LeanError,
    LeanRequest,
    TacticState,
    VerificationResult,
    VerificationStatus,
)

__all__ = [
    # Client
    "LeanAPIClient",
    # Exceptions
    "LeanAPIError",
    "LeanConnectionError",
    "LeanExecutionError",
    "LeanServerError",
    "LeanTimeoutError",
    "LeanValidationError",
    # Models
    "ErrorSeverity",
    "LeanConfig",
    "LeanError",
    "LeanRequest",
    "TacticState",
    "VerificationResult",
    "VerificationStatus",
]
