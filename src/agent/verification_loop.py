"""Verification loop controller for iterative proof refinement."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Generator, Optional

from .state import (
    AgentConfig,
    AgentContext,
    ErrorCategory,
    ProofAttempt,
    ProofState,
)
from .proof_generator import ProofGenerator
from .proof_to_lean import ProofToLeanConverter
from .mathlib_retriever import MathlibRetriever
from .proof_explainer import ProofExplainer
from ..lean_api import LeanRequest, LeanValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerificationResult:
    """Result of a verification attempt."""

    success: bool
    lean_code: str
    proof_idea: str = ""
    error_message: Optional[str] = None
    error_category: Optional[ErrorCategory] = None
    message: str = ""


class VerificationLoop:
    """Core verification loop for proof refinement.

    This class implements the iterative verification process:
    1. Generate proof using LLM
    2. Convert to Lean code
    3. Submit to API for verification
    4. Analyze errors and decide fix strategy
    5. Repeat until success or max iterations

    Error handling strategy:
    - Code-level errors (syntax, type, tactic): Attempt code fixes
    - Proof idea errors (fundamental strategy wrong): Reset proof approach
    """

    ERROR_CATEGORY_PATTERNS: Dict[ErrorCategory, list] = {
        ErrorCategory.SYNTAX_ERROR: [
            r"syntax error",
            r"invalid token",
            r"unexpected token",
            r"expected '.*'",
        ],
        ErrorCategory.TYPE_ERROR: [
            r"type mismatch",
            r"type error",
            r"cannot infer type",
            r"instance.*failed",
        ],
        ErrorCategory.TACTIC_FAILED: [
            r"tactic failed",
            r"failed to synthesize",
            r"cannot solve goal",
        ],
        ErrorCategory.UNDEFINED_NAME: [
            r"unknown identifier",
            r"unknown function",
            r"未定义的名称",
        ],
        ErrorCategory.IMPORT_ERROR: [
            r"import failed",
            r"cannot find file",
            r"module.*not found",
        ],
        ErrorCategory.TIMEOUT: [
            r"timeout",
            r"too long",
            r"exceeded time",
        ],
    }
    FORALL_BINDER_PATTERN = re.compile(
        r"^\s*forall\s+([A-Za-z0-9_'\s]+)\s*:\s*([^,]+),\s*(.*)$"
    )

    def __init__(
        self,
        proof_generator: ProofGenerator,
        lean_converter: ProofToLeanConverter,
        verifier_api: Any,
        config: Optional[AgentConfig] = None,
        mathlib_retriever: Optional[MathlibRetriever] = None,
        proof_explainer: Optional[ProofExplainer] = None,
    ):
        """Initialize verification loop.

        Args:
            proof_generator: Proof generator instance
            lean_converter: Proof to Lean converter
            verifier_api: API client for Lean verification
            config: Agent configuration
            mathlib_retriever: Optional retriever for Mathlib theorems
            proof_explainer: Optional explainer for proof explanations
        """
        self.proof_generator = proof_generator
        self.lean_converter = lean_converter
        self.verifier_api = verifier_api
        self.config = config or AgentConfig()
        self.mathlib_retriever = mathlib_retriever
        self.proof_explainer = proof_explainer

    def verify(
        self,
        theorem_name: str,
        theorem_statement: str,
    ) -> AgentContext:
        """Run the complete verification loop.

        Args:
            theorem_name: Name of the theorem
            theorem_statement: Statement to prove

        Returns:
            AgentContext with final state and proof attempts
        """
        context = AgentContext(
            theorem_name=theorem_name,
            theorem_statement=theorem_statement,
            config=self.config,
        )

        logger.info(f"Starting verification for: {theorem_name}")

        # First, check Mathlib for existing proof
        mathlib_hit = self._check_mathlib(theorem_name, theorem_statement)
        if mathlib_hit:
            context.mathlib_proof = mathlib_hit.get("proof", "")
            context.mathlib_source = mathlib_hit.get("source_path", "")

            # Verify the Mathlib proof directly
            if context.mathlib_proof:
                verification_response = self._submit_verification(
                    context.mathlib_proof, context
                )
                if verification_response.get("success"):
                    logger.info(f"Mathlib proof verified successfully: {theorem_name}")
                    context.update_state(ProofState.SUCCESS)
                    return context

        # Proceed with normal LLM generation flow if Mathlib not found or verification failed
        while context.can_continue:
            try:
                result = self._single_iteration(context)

                if result.success:
                    self._record_successful_attempt(context, result)
                    context.update_state(ProofState.SUCCESS)
                    logger.info(f"Proof verified successfully: {theorem_name}")
                    break

                self._handle_verification_failure(context, result)

            except Exception as e:
                logger.error(f"Iteration error: {e}")
                context.add_error({"type": "exception", "message": str(e)})
                context.update_state(ProofState.FAILED)
                break

        if context.state not in [ProofState.SUCCESS]:
            if context.current_iteration >= self.config.max_iterations:
                context.update_state(ProofState.MAX_ITERATIONS)
                logger.warning(
                    f"Max iterations reached for: {theorem_name}"
                )
            else:
                context.update_state(ProofState.FAILED)

        return context

    def verify_stream(
        self,
        theorem_name: str,
        theorem_statement: str,
    ) -> Generator[Dict[str, Any], None, None]:
        """Run verification with streaming updates.

        Args:
            theorem_name: Name of the theorem
            theorem_statement: Statement to prove

        Yields:
            Progress updates
        """
        context = AgentContext(
            theorem_name=theorem_name,
            theorem_statement=theorem_statement,
            config=self.config,
        )

        yield {"state": "started", "theorem": theorem_name}

        while context.can_continue:
            try:
                result = self._single_iteration(context)
                yield {"state": "verified", "result": result}

                if result.success:
                    self._record_successful_attempt(context, result)
                    yield {"state": "completed", "success": True}
                    break

                self._handle_verification_failure(context, result)
                yield {"state": "retry", "iteration": context.current_iteration}

            except Exception as e:
                logger.error(f"Stream iteration error: {e}")
                yield {"state": "error", "message": str(e)}
                break

    def _single_iteration(self, context: AgentContext) -> VerificationResult:
        """Execute a single verification iteration.

        Args:
            context: Current agent context

        Returns:
            Verification result
        """
        context.update_state(ProofState.GENERATING)

        proof_result = self.proof_generator.generate_proof(
            theorem_name=context.theorem_name,
            theorem_statement=context.theorem_statement,
            context=self._build_proof_context(context),
        )

        context.update_state(ProofState.CONVERTING)

        lean_code = self.lean_converter.convert(
            proof_content=proof_result.get("lean_code", ""),
            theorem_name=context.theorem_name,
            theorem_statement=context.theorem_statement,
        )

        context.update_state(ProofState.VERIFYING)

        verification_response = self._submit_verification(lean_code, context)

        if verification_response.get("success"):
            return VerificationResult(
                success=True,
                lean_code=lean_code,
                proof_idea=proof_result.get("strategy", ""),
                message="Proof verified successfully",
            )

        error_msg = verification_response.get("error", "Unknown error")
        error_category = self._categorize_error(error_msg)

        return VerificationResult(
            success=False,
            lean_code=lean_code,
            proof_idea=proof_result.get("strategy", ""),
            error_message=error_msg,
            error_category=error_category,
        )

    def _build_proof_context(self, context: AgentContext) -> Dict[str, Any]:
        """Build context for proof generation.

        Args:
            context: Current agent context

        Returns:
            Context dictionary for proof generator
        """
        previous_attempts = []
        last_error = "None"
        error_category = "N/A"

        if context.proof_attempts:
            recent_attempts = context.proof_attempts[-3:]
            last_attempt = recent_attempts[-1]
            previous_attempts = [
                {
                    "strategy": attempt.proof_idea or "N/A",
                    "lean_code": attempt.lean_code,
                    "error": attempt.error_message or "None",
                }
                for attempt in recent_attempts
            ]
            last_error = last_attempt.error_message or "None"
            if last_attempt.error_category:
                error_category = last_attempt.error_category.value

        return {
            "previous_attempts": previous_attempts,
            "last_error": last_error,
            "error_category": error_category,
        }

    def _submit_verification(
        self, lean_code: str, context: AgentContext
    ) -> Dict[str, Any]:
        """Submit Lean code for verification.

        Args:
            lean_code: Lean proof code
            context: Agent context

        Returns:
            Verification response
        """
        try:
            if hasattr(self.verifier_api, "verify_proof"):
                response = self.verifier_api.verify_proof(
                    code=lean_code,
                    timeout=self.config.timeout_seconds,
                )
                if isinstance(response, dict):
                    return response
                if hasattr(response, "success"):
                    return {
                        "success": response.success,
                        "message": getattr(response, "message", ""),
                        "error": getattr(response, "message", ""),
                        "errors": getattr(response, "errors", []),
                    }
                return response

            response = self.verifier_api.verify(
                LeanRequest(code=lean_code, timeout=self.config.timeout_seconds)
            )
            if getattr(response, "is_success", False):
                return {"success": True}

            error_message = response.message
            if response.errors:
                error_message = "; ".join(str(error) for error in response.errors)

            return {"success": False, "error": error_message}
        except LeanValidationError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Verification API error: {e}")
            return {"success": False, "error": str(e)}

    def _categorize_error(self, error_message: str) -> ErrorCategory:
        """Categorize verification error.

        Args:
            error_message: Error message from verification

        Returns:
            Error category
        """
        error_lower = error_message.lower()

        for category, patterns in self.ERROR_CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_lower):
                    return category

        if "failed" in error_lower or "error" in error_lower:
            return ErrorCategory.TACTIC_FAILED

        return ErrorCategory.UNKNOWN

    def _handle_verification_failure(
        self, context: AgentContext, result: VerificationResult
    ) -> None:
        """Handle verification failure and decide fix strategy.

        Args:
            context: Agent context
            result: Failed verification result
        """
        context.add_error(
            {
                "message": result.error_message,
                "category": result.error_category.value
                if result.error_category
                else "unknown",
            }
        )

        attempt = ProofAttempt(
            attempt_number=context.current_iteration + 1,
            proof_idea="",
            lean_code=result.lean_code,
            error_message=result.error_message,
            error_category=result.error_category,
            was_successful=False,
        )
        context.add_proof_attempt(attempt)

        if self._should_reset_proof(result.error_category):
            context.update_state(ProofState.RESETTING_PROOF)
            logger.info(
                "Proof idea error detected, will reset strategy"
            )
        else:
            context.update_state(ProofState.FIXING_CODE)
            logger.info(
                "Code-level error, will attempt fix"
            )

    def _record_successful_attempt(
        self, context: AgentContext, result: VerificationResult
    ) -> None:
        """Persist successful Lean code so later explanation can reuse it."""

        attempt = ProofAttempt(
            attempt_number=context.current_iteration + 1,
            proof_idea=result.proof_idea,
            lean_code=result.lean_code,
            was_successful=True,
        )
        context.add_proof_attempt(attempt)

    def _should_reset_proof(self, error_category: Optional[ErrorCategory]) -> bool:
        """Determine if proof strategy should be reset.

        Args:
            error_category: Category of error

        Returns:
            True if proof should be reset
        """
        if error_category is None:
            return False

        proof_idea_errors = {
            ErrorCategory.TACTIC_FAILED,
            ErrorCategory.UNDEFINED_NAME,
        }

        return error_category in proof_idea_errors

    def _check_mathlib(
        self,
        theorem_name: str,
        theorem_statement: str,
    ) -> Optional[dict]:
        """Check if theorem exists in Mathlib.

        Args:
            theorem_name: Name of the theorem.
            theorem_statement: Statement of the theorem.

        Returns:
            Dictionary with theorem info and proof if found, None otherwise.
        """
        if not self.mathlib_retriever:
            return None

        try:
            hits = self.mathlib_retriever.search(
                theorem_name=theorem_name,
                theorem_statement=theorem_statement,
                limit=3,
            )

            if not hits:
                return None

            for hit in hits:
                proof_content = self._build_mathlib_alias_proof(
                    theorem_name=theorem_name,
                    theorem_statement=theorem_statement,
                    library_theorem=hit.name,
                )
                if not proof_content:
                    proof_content = self.mathlib_retriever.get_proof_content(
                        source_path=hit.source_path,
                        line_number=hit.line_number,
                    )

                if proof_content:
                    return {
                        "name": hit.name,
                        "signature": hit.signature,
                        "source_path": hit.source_path,
                        "line_number": hit.line_number,
                        "score": hit.score,
                        "proof": proof_content,
                    }

            return None

        except Exception as e:
            logger.warning(f"Mathlib lookup failed: {e}")
            return None

    def _build_mathlib_alias_proof(
        self,
        theorem_name: str,
        theorem_statement: str,
        library_theorem: str,
    ) -> str:
        """Build a small adapter theorem that reuses a library theorem directly."""

        binders = self._extract_forall_binders(theorem_statement)
        theorem_lines = [
            "import Mathlib",
            "",
            f"theorem {theorem_name} : {theorem_statement} := by",
        ]

        if binders:
            theorem_lines.append(f"  intro {' '.join(binders)}")
            theorem_lines.append(
                f"  simpa using {library_theorem} {' '.join(binders)}"
            )
        else:
            theorem_lines.append(f"  simpa using {library_theorem}")

        return "\n".join(theorem_lines)

    def _extract_forall_binders(self, theorem_statement: str) -> list[str]:
        """Extract binder names from a leading chain of forall quantifiers."""

        binders: list[str] = []
        remaining = theorem_statement.strip()

        while True:
            match = self.FORALL_BINDER_PATTERN.match(remaining)
            if not match:
                break

            binders.extend(name for name in match.group(1).split() if name)
            remaining = match.group(3).strip()

        return binders

    def generate_explanation(
        self,
        context: AgentContext,
        language: str = "en",
    ) -> str:
        """Generate user-friendly explanation of the proof.

        Args:
            context: Agent context with proof information.
            language: Language code ('zh' for Chinese, 'en' for English).

        Returns:
            User-friendly explanation string.
        """
        if not self.proof_explainer:
            return ""

        # Use Mathlib proof if available, otherwise use the last successful attempt
        lean_proof = ""
        if context.mathlib_proof:
            lean_proof = context.mathlib_proof
        elif context.proof_attempts:
            for attempt in reversed(context.proof_attempts):
                if attempt.was_successful:
                    lean_proof = attempt.lean_code
                    break
            if not lean_proof:
                lean_proof = context.proof_attempts[-1].lean_code

        if not lean_proof:
            return ""

        try:
            explanation = self.proof_explainer.explain(
                theorem_name=context.theorem_name,
                theorem_statement=context.theorem_statement,
                lean_proof=lean_proof,
                language=language,
            )
            context.explanation = explanation
            return explanation
        except Exception as e:
            logger.error(f"Explanation generation failed: {e}")
            return ""
