"""Agent and workbench state management for Riemann proof verification."""

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
class LeanDiagnostic:
    """Structured Lean verification feedback for research workflows."""

    raw_message: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    last_submitted_code: str = ""
    failing_file: Optional[str] = None
    execution_time: Optional[float] = None

    @property
    def primary_error(self) -> str:
        """Return the most informative top-level error message."""
        if self.errors:
            return self.errors[0]
        return self.raw_message


@dataclass
class TheoremPlan:
    """Informal proof plan and decomposition for a theorem."""

    overview: str = ""
    subgoals: List[str] = field(default_factory=list)
    candidate_lemmas: List[str] = field(default_factory=list)
    notes: str = ""
    raw_plan: str = ""
    status: str = "draft"


@dataclass
class ResearchTarget:
    """A theorem-like target inside a Lean project file."""

    name: str
    statement: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    module_name: Optional[str] = None
    kind: str = "theorem"
    status: str = "unexplored"


@dataclass
class WorkbenchRun:
    """Summary of one workbench proving run."""

    target_name: str
    statement: str
    success: bool
    source: str = ""
    iterations: int = 0
    error: str = ""
    proof_path: Optional[str] = None
    timestamp: Optional[float] = None


@dataclass
class ResearchSession:
    """Long-lived project-oriented session state."""

    project_root: str
    active_file: Optional[str] = None
    active_target: Optional[ResearchTarget] = None
    open_plans: Dict[str, TheoremPlan] = field(default_factory=dict)
    recent_runs: List[WorkbenchRun] = field(default_factory=list)
    last_diagnostic: Optional[LeanDiagnostic] = None
    notes: Dict[str, str] = field(default_factory=dict)

    def remember_run(self, run: WorkbenchRun) -> None:
        """Keep a short run history for the interactive workbench."""
        self.recent_runs.append(run)
        self.recent_runs = self.recent_runs[-10:]

    def set_plan(self, target_name: str, plan: TheoremPlan) -> None:
        """Attach or update a theorem plan inside the session."""
        self.open_plans[target_name] = plan

    def get_plan(self, target_name: str) -> Optional[TheoremPlan]:
        """Retrieve the saved plan for a target if present."""
        return self.open_plans.get(target_name)


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
    mathlib_proof: Optional[str] = None
    mathlib_source: Optional[str] = None
    explanation: Optional[str] = None
    theorem_plan: Optional[TheoremPlan] = None
    file_path: Optional[str] = None
    latest_lean_code: str = ""
    last_diagnostic: Optional[LeanDiagnostic] = None
    mathlib_hits: List[Dict] = field(default_factory=list)

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
