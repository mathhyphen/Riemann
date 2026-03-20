"""Convert natural language proofs to Lean 4 code."""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LeanTemplate:
    """Template for Lean proof structure."""

    theorem_template: str = """{imports}

theorem {theorem_name} : {theorem_statement} := by
{proof_code}
"""
    imports_template: str = """import Mathlib"""

    tactic_prefix: str = "  "

    valid_tactics: tuple = (
        "intro",
        "intros",
        "rw",
        "simp",
        "exact",
        "apply",
        "refine",
        "have",
        "let",
        "calc",
        "cases",
        "induction",
        "split",
        "left",
        "right",
        "rfl",
        "exfalso",
        "trivial",
        "assumption",
        "contradiction",
        "decide",
        "omega",
        "linarith",
        "aesop",
    )


class ProofToLeanConverter:
    """Convert natural language proofs to Lean 4 code.

    This class handles:
    - Parsing proof strategies
    - Extracting Lean code from mixed content
    - Formatting code with proper indentation
    - Template-based code generation
    """

    CODE_BLOCK_PATTERN = re.compile(
        r"```(?:lean)?\s*(.*?)```", re.DOTALL | re.IGNORECASE
    )

    def __init__(self, template: Optional[LeanTemplate] = None):
        """Initialize the converter.

        Args:
            template: Custom Lean template (optional)
        """
        self.template = template or LeanTemplate()

    def convert(
        self,
        proof_content: str,
        theorem_name: str,
        theorem_statement: str,
    ) -> str:
        """Convert proof content to Lean 4 code.

        Args:
            proof_content: Natural language proof or mixed content
            theorem_name: Name of the theorem
            theorem_statement: Statement to prove

        Returns:
            Complete Lean 4 proof file content
        """
        normalized_content = proof_content.strip()
        lean_code = self.extract_lean_code(normalized_content)

        if not lean_code and self._looks_like_lean_code(normalized_content):
            # The proof generator often returns raw tactic text without fences.
            lean_code = normalized_content

        if not lean_code:
            lean_code = self._extract_proof_steps(normalized_content)
            if lean_code == "sorry":
                logger.warning("No Lean code found in content, attempting extraction")

        if not lean_code:
            logger.warning("Could not extract proof, using theorem only")
            lean_code = "sorry"

        formatted_code = self.format_proof(lean_code)

        full_proof = self._build_full_proof(
            theorem_name, theorem_statement, formatted_code
        )

        logger.info(f"Converted proof for: {theorem_name}")
        return full_proof

    def _looks_like_lean_code(self, content: str) -> bool:
        """Heuristic check for raw Lean tactic text."""
        if not content:
            return False

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return False

        if any(re.match(r"^\d+\.\s+", line) for line in lines):
            return False

        lean_prefixes = set(self.template.valid_tactics) | {
            "theorem",
            "lemma",
            "example",
            "have",
            "show",
            "from",
            "fun",
            "|",
            "--",
            "refine",
            "simpa",
        }

        matches = 0
        for line in lines:
            cleaned = re.sub(r"^\d+\.\s*", "", line)
            if any(cleaned.startswith(prefix) for prefix in lean_prefixes):
                matches += 1

        return matches > 0

    def extract_lean_code(self, content: str) -> Optional[str]:
        """Extract Lean code from markdown-style content.

        Args:
            content: Mixed content with Lean code blocks

        Returns:
            Extracted Lean code or None
        """
        match = self.CODE_BLOCK_PATTERN.search(content)
        if match:
            code = match.group(1).strip()
            logger.debug(f"Extracted code block ({len(code)} chars)")
            return code

        lines = content.split("\n")
        lean_lines = []
        in_lean_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_lean_block = not in_lean_block
                continue
            if in_lean_block:
                lean_lines.append(line)

        if lean_lines:
            code = "\n".join(lean_lines).strip()
            logger.debug(f"Extracted inline code ({len(code)} chars)")
            return code

        return None

    def _extract_proof_steps(self, content: str) -> str:
        """Extract proof steps from unstructured content.

        Args:
            content: Proof content

        Returns:
            Extracted proof steps as Lean tactics
        """
        lines = content.split("\n")
        tactics = []

        tactic_keywords = self.template.valid_tactics

        for line in lines:
            line = line.strip()
            if not line:
                continue

            for tactic in tactic_keywords:
                if line.startswith(tactic) or f" {tactic}" in line:
                    cleaned = self._clean_tactic(line)
                    if cleaned:
                        tactics.append(cleaned)
                    break

        if tactics:
            return "\n".join(tactics)

        return "sorry"

    def _clean_tactic(self, tactic_line: str) -> str:
        """Clean and normalize a tactic line.

        Args:
            tactic_line: Raw tactic line

        Returns:
            Cleaned tactic
        """
        tactic_line = tactic_line.strip()

        tactic_line = re.sub(r"^\d+\.\s*", "", tactic_line)

        tactic_line = re.sub(r"\*+$", "", tactic_line)

        if "--" in tactic_line:
            tactic_line = tactic_line.split("--")[0].strip()

        return tactic_line

    def format_proof(self, proof_code: str) -> str:
        """Format proof code with proper indentation.

        Args:
            proof_code: Raw proof code

        Returns:
            Formatted proof code
        """
        lines = proof_code.split("\n")
        formatted_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line in ["begin", "by", "{"]:
                formatted_lines.append(line)
            elif line in ["end", "}"]:
                if formatted_lines and formatted_lines[-1]:
                    pass
                formatted_lines.append(line)
            else:
                formatted_lines.append(f"  {line}")

        return "\n".join(formatted_lines)

    def _build_full_proof(
        self,
        theorem_name: str,
        theorem_statement: str,
        proof_code: str,
    ) -> str:
        """Build complete Lean proof file.

        Args:
            theorem_name: Theorem name
            theorem_statement: Theorem statement
            proof_code: Formatted proof code

        Returns:
            Complete Lean file content
        """
        imports = self.template.imports_template

        return self.template.theorem_template.format(
            imports=imports,
            theorem_name=theorem_name,
            theorem_statement=theorem_statement,
            proof_code=proof_code,
        )

    def validate_tactics(self, proof_code: str) -> List[str]:
        """Validate that tactics are well-formed.

        Args:
            proof_code: Lean proof code

        Returns:
            List of validation warnings
        """
        warnings: List[str] = []
        lines = proof_code.split("\n")

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line in ["begin", "by", "end", "}"]:
                continue

            tactic_found = False
            for tactic in self.template.valid_tactics:
                if line.startswith(tactic):
                    tactic_found = True
                    break

            if not tactic_found and not line.startswith("--"):
                warnings.append(f"Line {i}: Unknown tactic '{line[:30]}'")

        return warnings

    def suggest_fixes(self, error_message: str) -> List[str]:
        """Suggest potential fixes based on error message.

        Args:
            error_message: Lean error message

        Returns:
            List of suggested fixes
        """
        suggestions: List[str] = []

        error_lower = error_message.lower()

        if "unknown identifier" in error_lower:
            match = re.search(r"unknown identifier '(\w+)'", error_message)
            if match:
                ident = match.group(1)
                suggestions.append(f"Import the module containing '{ident}'")
                suggestions.append(f"Check if '{ident}' is correctly spelled")

        if "type mismatch" in error_lower:
            suggestions.append("Check argument types in the expression")
            suggestions.append("Verify the goal state matches expected type")

        if "tactic failed" in error_lower:
            suggestions.append("The tactic cannot prove the current goal")
            suggestions.append("Try a different approach or break into smaller steps")

        if "unknown function" in error_lower:
            match = re.search(r"unknown function '(\w+)'", error_message)
            if match:
                suggestions.append(f"Check if '{match.group(1)}' is imported")

        return suggestions
