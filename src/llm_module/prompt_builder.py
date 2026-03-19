"""Prompt builder for proof generation."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProofContext:
    """Context for proof generation."""

    theorem_name: str
    theorem_statement: str
    previous_attempts: Optional[List[Dict[str, Any]]] = None
    last_error: Optional[str] = None
    error_category: Optional[str] = None


class ProofPromptBuilder:
    """Builder for constructing prompts for proof generation.

    This class handles the construction of prompts sent to the LLM
    for generating mathematical proofs in Lean 4.
    """

    SYSTEM_PROMPT = """You are an expert mathematician and Lean 4 prover.
Your task is to generate rigorous mathematical proofs that can be verified by Lean 4.

Guidelines:
1. Understand the theorem statement completely before proving
2. Break down the proof into clear logical steps
3. Use appropriate Lean 4 tactics (rw, simp, exact, apply, intro, etc.)
4. Ensure each step follows logically from previous steps
5. Consider edge cases and ensure completeness

When providing a proof:
- First explain your proof strategy in natural language
- Then provide the Lean 4 code
- Use comments to explain key steps
"""

    PROOF_TEMPLATE = """## Theorem
```
{ theorem_name} : { theorem_statement }
```

## Previous Attempts (for reference)
{ previous_attempts}

## Current Context
- Error from last attempt: { last_error}
- Error category: { error_category}

## Task
Generate a proof for the theorem above.

{ focus_instruction}

Provide your response in the following format:
### Proof Strategy
[Explain your proof approach]

### Lean Code
```lean
-- Your proof here
```

### Explanation
[Detailed explanation of each step]
"""

    RETRY_TEMPLATE = """## Theorem
```
{ theorem_name} : { theorem_statement }
```

## Previous Proof Attempt
```lean
{ previous_proof}
```

## Error Message
```
{ error_message}
```

## Error Category
{ error_category}

## Task
Fix the proof above to resolve the error. The error is a { error_category}.

Provide your response in the following format:
### Fixed Proof Strategy
[Explain how you fixed the issue]

### Lean Code
```lean
-- Your fixed proof here
```

### Explanation
[Explanation of the fix]
"""

    def __init__(self):
        """Initialize the prompt builder."""
        pass

    def build_proof_prompt(
        self,
        theorem_name: str,
        theorem_statement: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """Build a prompt for initial proof generation.

        Args:
            theorem_name: Name of the theorem
            theorem_statement: Statement to prove
            context: Optional context including previous attempts and errors

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = context or {}

        previous_attempts = self._format_previous_attempts(
            context.get("previous_attempts", [])
        )
        last_error = context.get("last_error", "None")
        error_category = context.get("error_category", "N/A")

        focus_instruction = self._build_focus_instruction(
            last_error, error_category
        )

        user_prompt = self.PROOF_TEMPLATE.format(
            theorem_name=theorem_name,
            theorem_statement=theorem_statement,
            previous_attempts=previous_attempts or "No previous attempts",
            last_error=last_error,
            error_category=error_category,
            focus_instruction=focus_instruction,
        )

        return self.SYSTEM_PROMPT, user_prompt

    def build_retry_prompt(
        self,
        theorem_name: str,
        theorem_statement: str,
        previous_proof: str,
        error_message: str,
        error_category: str,
    ) -> tuple[str, str]:
        """Build a prompt for retrying after a failed proof attempt.

        Args:
            theorem_name: Name of the theorem
            theorem_statement: Statement to prove
            previous_proof: The previous proof attempt
            error_message: Error message from verification
            error_category: Category of the error

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        user_prompt = self.RETRY_TEMPLATE.format(
            theorem_name=theorem_name,
            theorem_statement=theorem_statement,
            previous_proof=previous_proof,
            error_message=error_message,
            error_category=error_category,
        )

        return self.SYSTEM_PROMPT, user_prompt

    def _format_previous_attempts(
        self, attempts: List[Dict[str, Any]]
    ) -> str:
        """Format previous attempts for inclusion in prompt.

        Args:
            attempts: List of previous attempt dictionaries

        Returns:
            Formatted string of previous attempts
        """
        if not attempts:
            return "No previous attempts"

        formatted = []
        for i, attempt in enumerate(attempts[-3:], 1):
            formatted.append(
                f"### Attempt {i}\n"
                f"Strategy: {attempt.get('strategy', 'N/A')}\n"
                f"Lean Code:\n{attempt.get('lean_code', 'N/A')}\n"
                f"Error: {attempt.get('error', 'None')}\n"
            )
        return "\n---\n".join(formatted)

    def _build_focus_instruction(
        self, last_error: str, error_category: str
    ) -> str:
        """Build focus instruction based on error context.

        Args:
            last_error: Error message from last attempt
            error_category: Category of the error

        Returns:
            Focus instruction string
        """
        if error_category == "proof_idea_error":
            return (
                "IMPORTANT: The previous proof strategy was fundamentally wrong. "
                "Consider a completely different approach."
            )
        elif last_error and last_error != "None":
            return (
                "Try to fix the specific error mentioned above. "
                "The tactic or approach may need adjustment."
            )
        return ""

    def build_lean_imports_prompt(
        self,
        theorem_name: str,
        theorem_statement: str,
    ) -> tuple[str, str]:
        """Build a prompt to suggest necessary Lean imports.

        Args:
            theorem_name: Name of the theorem
            theorem_statement: Statement to prove

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = """You are a Lean 4 expert. Based on the theorem statement,
suggest which Lean libraries need to be imported."""

        user_prompt = f"""For the following theorem, suggest which Lean imports are needed:

Theorem: {theorem_name} : {theorem_statement}

List the required imports in the following format:
### Imports
```lean
import Mathlib.{library_name}
-- or
import Std.{library_name}
```
"""

        return system_prompt, user_prompt
