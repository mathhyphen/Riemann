"""Lean API client for proof verification.

This module provides a client for interacting with a Lean proof assistant
via HTTP API. It handles code submission, verification results retrieval,
and implements retry logic with exponential backoff.
"""

import logging
import time
from typing import Optional

import requests

from .exceptions import (
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

logger = logging.getLogger(__name__)


class LeanAPIClient:
    """Client for interacting with Lean server API.

    This client handles communication with a Lean proof assistant server,
    including code submission and verification result retrieval.

    Attributes:
        config: Configuration for the client.

    Example:
        >>> config = LeanConfig(base_url="http://localhost:5000")
        >>> client = LeanAPIClient(config)
        >>> result = client.verify(code="theorem add_comm (a b : Nat) : a + b = b + a := by ring")
        >>> print(result.is_success)
    """

    def __init__(self, config: LeanConfig):
        """Initialize the Lean API client.

        Args:
            config: Configuration for the client.
        """
        self.config = config
        self._session = requests.Session()

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint.

        Args:
            endpoint: API endpoint path.

        Returns:
            Full URL string.
        """
        base = self.config.base_url.rstrip("/")
        path = endpoint.lstrip("/")
        return f"{base}/{path}"

    def _parse_errors(self, data: dict) -> list[LeanError]:
        """Parse errors from response data.

        Args:
            data: Response data dictionary.

        Returns:
            List of parsed LeanError objects.
        """
        errors = []
        error_list = data.get("errors", [])

        for err in error_list:
            severity_str = err.get("severity", "error")
            try:
                severity = ErrorSeverity(severity_str)
            except ValueError:
                severity = ErrorSeverity.ERROR

            errors.append(
                LeanError(
                    message=err.get("message", "Unknown error"),
                    error_type=err.get("error_type"),
                    line=err.get("line"),
                    column=err.get("column"),
                    severity=severity,
                )
            )

        return errors

    def _parse_tactic_state(self, data: dict) -> Optional[TacticState]:
        """Parse tactic state from response data.

        Args:
            data: Response data dictionary.

        Returns:
            TacticState object if available, None otherwise.
        """
        state_data = data.get("tactic_state")
        if not state_data:
            return None

        if isinstance(state_data, str):
            return TacticState(main_goal=state_data, goals=[state_data])

        if isinstance(state_data, dict):
            goals = state_data.get("goals", [])
            main_goal = state_data.get("main_goal")
            if goals or main_goal:
                return TacticState(goals=goals, main_goal=main_goal)

        return None

    def _parse_verification_result(self, data: dict) -> VerificationResult:
        """Parse verification result from response data.

        Args:
            data: Response data dictionary.

        Returns:
            VerificationResult object.
        """
        status_str = data.get("status", "error")
        try:
            status = VerificationStatus(status_str)
        except ValueError:
            logger.warning(f"Unknown verification status: {status_str}")
            status = VerificationStatus.ERROR

        message = data.get("message", "")
        errors = self._parse_errors(data)
        execution_time = data.get("execution_time")
        tactic_state = self._parse_tactic_state(data)

        return VerificationResult(
            status=status,
            message=message,
            errors=errors,
            execution_time=execution_time,
            tactic_state=tactic_state,
        )

    def _handle_response(self, response: requests.Response) -> dict:
        """Handle HTTP response and raise appropriate exceptions.

        Args:
            response: Response object from requests.

        Returns:
            Parsed JSON data.

        Raises:
            LeanServerError: For server errors.
            LeanConnectionError: For connection errors.
        """
        try:
            data = response.json()
        except ValueError as e:
            raise LeanServerError(
                f"Invalid JSON response: {e}",
                status_code=response.status_code,
            )

        if response.status_code >= 500:
            message = data.get("error", "Internal server error")
            raise LeanServerError(
                f"Server error: {message}",
                status_code=response.status_code,
                details=data,
            )

        if response.status_code >= 400:
            message = data.get("error", data.get("message", "Client error"))
            error_type = data.get("error_type")
            raise LeanExecutionError(
                f"Execution error: {message}",
                error_type=error_type,
                details=data,
            )

        return data

    def _retry_with_backoff(
        self,
        func,
        *args,
        **kwargs,
    ) -> VerificationResult:
        """Execute function with exponential backoff retry.

        Args:
            func: Function to execute.
            *args: Positional arguments for func.
            **kwargs: Keyword arguments for func.

        Returns:
            Result from func.

        Raises:
            LeanTimeoutError: If timeout occurs after all retries.
            LeanConnectionError: If connection fails after all retries.
            LeanExecutionError: For execution errors.
        """
        last_exception = None
        delay = self.config.retry_delay

        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except LeanTimeoutError as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    logger.warning(
                        f"Timeout on attempt {attempt + 1}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= self.config.retry_backoff
                else:
                    raise e
            except LeanConnectionError as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    logger.warning(
                        f"Connection error on attempt {attempt + 1}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= self.config.retry_backoff
                else:
                    raise e

        # This should not happen, but just in case
        if last_exception:
            raise last_exception
        raise LeanExecutionError("Unexpected error during retry")

    def verify(self, request: LeanRequest) -> VerificationResult:
        """Submit Lean code for verification.

        Args:
            request: Lean code request to verify.

        Returns:
            VerificationResult with verification status and details.

        Raises:
            LeanTimeoutError: If verification times out.
            LeanConnectionError: If connection to server fails.
            LeanExecutionError: If Lean code has errors.
        """
        return self._retry_with_backoff(self._verify, request)

    def verify_proof(
        self,
        code: str,
        timeout: Optional[float] = None,
        filename: Optional[str] = None,
    ) -> dict:
        """Compatibility wrapper used by the app-level verification loop."""
        request = LeanRequest(code=code, timeout=timeout, filename=filename)

        try:
            result = self.verify(request)
        except (LeanConnectionError, LeanExecutionError, LeanServerError, LeanTimeoutError) as e:
            return {"success": False, "error": str(e)}
        except LeanValidationError as e:
            details = e.details or {}
            return {
                "success": False,
                "error": details.get("message", str(e)),
                "details": details,
            }

        return {
            "success": result.is_success,
            "message": result.message,
            "errors": [str(error) for error in result.errors],
            "execution_time": result.execution_time,
        }

    def _verify(self, request: LeanRequest) -> VerificationResult:
        """Internal method to submit verification request.

        Args:
            request: Lean code request to verify.

        Returns:
            VerificationResult with verification status and details.
        """
        url = self._build_url("/verify")
        payload = {"code": request.code}

        if request.filename:
            payload["filename"] = request.filename

        timeout = request.timeout or self.config.timeout

        logger.debug(f"Submitting code for verification: {payload.get('filename', 'inline')}")

        try:
            response = self._session.post(
                url,
                json=payload,
                timeout=timeout,
            )
        except requests.Timeout as e:
            raise LeanTimeoutError(
                f"Request timed out after {timeout}s",
                timeout=timeout,
            ) from e
        except requests.ConnectionError as e:
            raise LeanConnectionError(
                f"Failed to connect to Lean server at {url}",
            ) from e
        except requests.RequestException as e:
            raise LeanConnectionError(
                f"Request failed: {str(e)}",
            ) from e

        data = self._handle_response(response)

        # Check for timeout in response
        if data.get("status") == "timeout":
            raise LeanTimeoutError(
                "Verification timed out",
                timeout=timeout,
                details=data,
            )

        # Check for validation errors
        if data.get("status") == "failed":
            errors = self._parse_errors(data)
            tactic_state = self._parse_tactic_state(data)

            if errors or tactic_state:
                raise LeanValidationError(
                    data.get("message", "Proof verification failed"),
                    tactic_state=tactic_state.main_goal if tactic_state else None,
                    remaining_goals=len(tactic_state.goals) if tactic_state else None,
                    details=data,
                )

        return self._parse_verification_result(data)

    def health_check(self) -> bool:
        """Check if the Lean server is available.

        Returns:
            True if server is healthy, False otherwise.
        """
        try:
            url = self._build_url("/health")
            response = self._session.get(url, timeout=5.0)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def close(self) -> None:
        """Close the client session."""
        self._session.close()

    def __enter__(self) -> "LeanAPIClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
