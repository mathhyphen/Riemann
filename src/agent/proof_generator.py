"""Proof generator using LLM for mathematical proof generation."""

import logging
from typing import Any, Dict, Generator, Optional

from ..llm_module.client import LLMConfig

logger = logging.getLogger(__name__)

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

    PLAN_SYSTEM_PROMPT = """You are a mathematical research assistant working inside a Lean project.
Your task is to decompose a theorem into an informal research plan before code generation.

Guidelines:
1. State the main proof idea in plain language.
2. Break the work into small subgoals that could become lemmas.
3. Mention likely reusable Mathlib or local lemmas when appropriate.
4. Keep the plan short, concrete, and implementation-oriented.

Respond in the following format:
### Overview
[one short paragraph]

### Subgoals
- [subgoal]
- [subgoal]

### Candidate Lemmas
- [lemma name or search hint]
- [lemma name or search hint]
"""

    PROOF_TEMPLATE = """## Theorem
```
{theorem_name} : {theorem_statement}
```

## Previous Attempts (for reference)
{previous_attempts}

## Current Context
- Error from last attempt: {last_error}
- Error category: {error_category}
- Current file: {file_path}
- Research notes: {notes}
- Plan status: {plan_status}

## Existing Theorem Plan
{theorem_plan}

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

    PLAN_TEMPLATE = """## Theorem
```
{theorem_name} : {theorem_statement}
```

## Research Context
- Current file: {file_path}
- Prior Lean error: {last_error}
- Existing notes: {notes}
- Existing plan status: {plan_status}

## Task
Produce a concise research workbench plan for this theorem before formal proof search.
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

    def generate_plan(
        self,
        theorem_name: str,
        theorem_statement: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate an informal theorem plan for research workflows."""

        context = context or {}
        prompt = self._build_plan_prompt(theorem_name, theorem_statement, context)

        logger.info(f"Generating plan for theorem: {theorem_name}")

        try:
            response = self.llm_client.generate(
                prompt=prompt,
                system_prompt=self.PLAN_SYSTEM_PROMPT,
                model=self.config.model,
                temperature=0.3,
                max_tokens=self.config.max_tokens,
            )
            content = response.content if hasattr(response, "content") else response
            return self._parse_plan_response(content)
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            return self._fallback_plan(theorem_name, theorem_statement)

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
            file_path=context.get("file_path", "N/A"),
            notes=context.get("notes", "None"),
            plan_status=context.get("plan_status", "new"),
            theorem_plan=context.get("theorem_plan", "No saved plan"),
            focus_instruction=focus_instruction,
        )

    def _build_plan_prompt(
        self,
        theorem_name: str,
        theorem_statement: str,
        context: Dict[str, Any],
    ) -> str:
        """Build a lightweight theorem-planning prompt."""

        return self.PLAN_TEMPLATE.format(
            theorem_name=theorem_name,
            theorem_statement=theorem_statement,
            file_path=context.get("file_path", "N/A"),
            last_error=context.get("last_error", "None"),
            notes=context.get("notes", "None"),
            plan_status=context.get("plan_status", "new"),
        )

    def _call_llm(self, prompt: str) -> str:
        """Call LLM API to generate proof.

        Args:
            prompt: Formatted prompt

        Returns:
            LLM response text
        """
        response = self.llm_client.generate(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.content if hasattr(response, "content") else response

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

    def _parse_plan_response(self, response: str) -> Dict[str, Any]:
        """Parse a plan response into overview, subgoals, and candidate lemmas."""

        overview = ""
        subgoals: list[str] = []
        candidate_lemmas: list[str] = []
        section = ""

        for raw_line in response.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("### Overview"):
                section = "overview"
                continue
            if line.startswith("### Subgoals"):
                section = "subgoals"
                continue
            if line.startswith("### Candidate Lemmas"):
                section = "lemmas"
                continue

            if section == "overview":
                overview = f"{overview} {line}".strip()
            elif section == "subgoals" and line.startswith("-"):
                subgoals.append(line[1:].strip())
            elif section == "lemmas" and line.startswith("-"):
                candidate_lemmas.append(line[1:].strip())

        if not overview:
            overview = response.strip()

        return {
            "overview": overview,
            "subgoals": subgoals,
            "candidate_lemmas": candidate_lemmas,
            "raw_plan": response.strip(),
        }

    def _fallback_plan(self, theorem_name: str, theorem_statement: str) -> Dict[str, Any]:
        """Produce a deterministic fallback plan when the LLM is unavailable."""

        return {
            "overview": f"Analyze `{theorem_name}` by reducing `{theorem_statement}` into smaller reusable lemmas.",
            "subgoals": [
                "Identify the main introduction steps and target shape.",
                "Search for reusable Mathlib or local lemmas before writing tactics.",
                "Validate each candidate proof against Lean and inspect raw diagnostics.",
            ],
            "candidate_lemmas": [],
            "raw_plan": "",
        }

    def get_proof_history(self) -> list[str]:
        """Get history of generated proofs.

        Returns:
            List of previously generated proof codes
        """
        return self._proof_history.copy()
