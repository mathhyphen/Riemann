"""Agent state management for Riemann proof verification."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ProofState(Enum):
    """Enumeration of proof verification states."""

    IDLE = "idle"
    GENERATING = "generating"
    CONVERTING = "converting"
    VERIFYING = "verifying"
    ANALYZING_ERROR = "analyzing_error"
    FIXING_CODE = "fixing_code"
    RESETTING_PROOF = "resetting_proof"
    SUCCESS = "success"
    FAILED = "failed"
    MAX_ITERATIONS = "max_iterations"


class ErrorCategory(Enum):
    """Classification of verification errors."""

    SYNTAX_ERROR = "syntax_error"  # Invalid Lean syntax
    TYPE_ERROR = "type_error"  # Type mismatch
    TACTIC_FAILED = "tactic_failed"  # Tactic cannot prove goal
    UNDEFINED_NAME = "undefined_name"  # Reference to undefined identifier
    IMPORT_ERROR = "import_error"  # Missing import
    PROOF_IDEA_ERROR = "proof_idea_error"  # Fundamental proof strategy wrong
    TIMEOUT = "timeout"  # Verification took too long
    UNKNOWN = "unknown"  # Unclassified error


@dataclass(frozen=True)
class AgentConfig:
    """Immutable configuration for the verification agent."""

    max_iterations: int = 10
    max_proof_attempts: int = 3
    code_fix_attempts: int = 3
    timeout_seconds: float = 60.0
    stream_output: bool = True
    verbose: bool = True


@dataclass
class ProofAttempt:
    """Record of a single proof attempt."""

    attempt_number: int
    proof_idea: str
    lean_code: str
    error_message: Optional[str] = None
    error_category: Optional[ErrorCategory] = None
    was_successful: bool = False


@dataclass
class AgentContext:
    """Execution context for the verification agent."""

    theorem_name: str
    theorem_statement: str
    config: AgentConfig
    proof_attempts: List[ProofAttempt] = field(default_factory=list)
    current_iteration: int = 0
    state: ProofState = ProofState.IDLE
    error_history: List[Dict] = field(default_factory=list)

    @property
    def current_proof_attempt(self) -> Optional[ProofAttempt]:
        """Get the most recent proof attempt."""
        if self.proof_attempts:
            return self.proof_attempts[-1]
        return None

    @property
    def total_attempts(self) -> int:
        """Total number of proof attempts made."""
        return len(self.proof_attempts)

    @property
    def can_continue(self) -> bool:
        """Check if more iterations are allowed."""
        return (
            self.current_iteration < self.config.max_iterations
            and self.state not in [ProofState.SUCCESS, ProofState.FAILED]
        )

    @property
    def recent_errors(self) -> List[Dict]:
        """Get the last N error messages for context."""
        return self.error_history[-5:] if self.error_history else []

    def add_proof_attempt(self, attempt: ProofAttempt) -> None:
        """Add a new proof attempt to history."""
        self.proof_attempts.append(attempt)
        self.current_iteration += 1
        logger.info(
            f"Added proof attempt #{attempt.attempt_number}, "
            f"total iterations: {self.current_iteration}"
        )

    def add_error(self, error_info: Dict) -> None:
        """Record an error for analysis."""
        self.error_history.append(error_info)
        logger.debug(f"Recorded error: {error_info.get('message', 'unknown')[:100]}")

    def update_state(self, new_state: ProofState) -> None:
        """Update the current agent state."""
        old_state = self.state
        self.state = new_state
        logger.info(f"State transition: {old_state.value} -> {new_state.value}")
