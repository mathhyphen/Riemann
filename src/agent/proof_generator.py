"""Proof generator using LLM for mathematical proof generation."""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generator, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for LLM API calls."""

    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 4096
    api_endpoint: Optional[str] = None


class ProofGenerator:
    """Generate mathematical proofs using LLM.

    This class handles:
    - Constructing prompts for proof generation
    - Calling LLM API with streaming support
    - Managing proof idea history
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

{focus_instruction}

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

    def __init__(
        self,
        llm_client: Any,
        config: Optional[LLMConfig] = None,
    ):
        """Initialize the proof generator.

        Args:
            llm_client: Client for calling LLM API
            config: LLM configuration
        """
        self.llm_client = llm_client
        self.config = config or LLMConfig()
        self._proof_history: list[str] = []

    def generate_proof(
        self,
        theorem_name: str,
        theorem_statement: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Generate a proof for the given theorem.

        Args:
            theorem_name: Name of the theorem
            theorem_statement: Statement of the theorem
            context: Optional context including previous attempts and errors

        Returns:
            Dictionary with 'strategy', 'lean_code', and 'explanation'
        """
        context = context or {}
        prompt = self._build_prompt(
            theorem_name, theorem_statement, context
        )

        logger.info(f"Generating proof for theorem: {theorem_name}")

        try:
            response = self._call_llm(prompt)
            result = self._parse_response(response)

            self._proof_history.append(result.get("lean_code", ""))
            logger.info(
                f"Proof generated successfully, "
                f"history length: {len(self._proof_history)}"
            )

            return result
        except Exception as e:
            logger.error(f"Proof generation failed: {e}")
            raise

    def generate_proof_stream(
        self,
        theorem_name: str,
        theorem_statement: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """Generate proof with streaming output.

        Args:
            theorem_name: Name of the theorem
            theorem_statement: Statement of the theorem
            context: Optional context including previous attempts and errors

        Yields:
            Chunks of the generated proof
        """
        context = context or {}
        prompt = self._build_prompt(theorem_name, theorem_statement, context)

        logger.info(f"Generating proof (streaming) for: {theorem_name}")

        try:
            for chunk in self.llm_client.stream_generate(
                prompt=prompt,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            ):
                yield chunk
        except Exception as e:
            logger.error(f"Streaming proof generation failed: {e}")
            raise

    def _build_prompt(
        self,
        theorem_name: str,
        theorem_statement: str,
        context: Dict[str, Any],
    ) -> str:
        """Build the prompt for LLM.

        Args:
            theorem_name: Name of the theorem
            theorem_statement: Statement to prove
            context: Context including previous attempts

        Returns:
            Formatted prompt string
        """
        previous_attempts = ""
        if context.get("previous_attempts"):
            formatted_attempts = []
            for i, attempt in enumerate(context["previous_attempts"][-3:], 1):
                formatted_attempts.append(
                    f"### Attempt {i}\n"
                    f"Strategy: {attempt.get('strategy', 'N/A')}\n"
                    f"Lean Code:\n{attempt.get('lean_code', 'N/A')}\n"
                    f"Error: {attempt.get('error', 'None')}\n"
                )
            previous_attempts = "\n---\n".join(formatted_attempts)

        last_error = context.get("last_error", "None")
        error_category = context.get("error_category", "N/A")

        focus_instruction = ""
        if error_category == "proof_idea_error":
            focus_instruction = (
                "IMPORTANT: The previous proof strategy was fundamentally wrong. "
                "Consider a completely different approach."
            )
        elif last_error != "None":
            focus_instruction = (
                "Try to fix the specific error mentioned above. "
                "The tactic or approach may need adjustment."
            )

        return self.PROOF_TEMPLATE.format(
            theorem_name=theorem_name,
            theorem_statement=theorem_statement,
            previous_attempts=previous_attempts or "No previous attempts",
            last_error=last_error,
            error_category=error_category,
            focus_instruction=focus_instruction,
        )

    def _call_llm(self, prompt: str) -> str:
        """Call LLM API to generate proof.

        Args:
            prompt: Formatted prompt

        Returns:
            LLM response text
        """
        return self.llm_client.generate(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    def _parse_response(self, response: str) -> Dict[str, str]:
        """Parse LLM response into structured format.

        Args:
            response: Raw LLM response

        Returns:
            Parsed dictionary with strategy, lean_code, explanation
        """
        result = {
            "strategy": "",
            "lean_code": "",
            "explanation": "",
        }

        sections = response.split("###")
        for section in sections:
            section = section.strip()
            if section.startswith("Proof Strategy"):
                result["strategy"] = section.replace("Proof Strategy", "").strip()
            elif section.startswith("Lean Code"):
                code = section.replace("Lean Code", "").strip()
                if code.startswith("```lean"):
                    code = code.replace("```lean", "").strip()
                if code.endswith("```"):
                    code = code[:-3].strip()
                result["lean_code"] = code
            elif section.startswith("Explanation"):
                result["explanation"] = section.replace("Explanation", "").strip()

        if not result["lean_code"]:
            logger.warning("No Lean code found in LLM response, using full response")
            result["lean_code"] = response

        return result

    def get_proof_history(self) -> list[str]:
        """Get history of generated proofs.

        Returns:
            List of previously generated proof codes
        """
        return self._proof_history.copy()
