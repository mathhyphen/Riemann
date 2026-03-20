"""Local theorem retrieval against a checked-out mathlib tree."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MathlibTheoremHit:
    """Single theorem candidate surfaced from the local mathlib checkout."""

    name: str
    signature: str
    source_path: str
    line_number: int
    score: int


class MathlibRetriever:
    """Very small local retriever for theorem/lemma declarations in mathlib."""

    DECL_PATTERN = re.compile(r"^\s*(?:theorem|lemma)\s+([A-Za-z0-9_'.]+)")
    TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_']+")

    def __init__(self, mathlib_root: str | Path | None = None):
        self.mathlib_root = Path(mathlib_root) if mathlib_root else self._default_mathlib_root()
        self._index: list[MathlibTheoremHit] | None = None

    def _default_mathlib_root(self) -> Path | None:
        project_root = os.environ.get("LEAN_PROJECT_ROOT")
        if not project_root:
            return None
        candidate = Path(project_root) / ".lake" / "packages" / "mathlib" / "Mathlib"
        return candidate if candidate.exists() else None

    def _iter_declarations(self) -> Iterable[MathlibTheoremHit]:
        if self.mathlib_root is None or not self.mathlib_root.exists():
            return []

        hits: list[MathlibTheoremHit] = []
        for path in self.mathlib_root.rglob("*.lean"):
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue

            for line_number, line in enumerate(lines, start=1):
                match = self.DECL_PATTERN.match(line)
                if not match:
                    continue
                hits.append(
                    MathlibTheoremHit(
                        name=match.group(1),
                        signature=line.strip(),
                        source_path=str(path),
                        line_number=line_number,
                        score=0,
                    )
                )
        return hits

    @property
    def index(self) -> list[MathlibTheoremHit]:
        if self._index is None:
            self._index = list(self._iter_declarations())
        return self._index

    def search(
        self,
        theorem_name: str,
        theorem_statement: str,
        *,
        last_error: str = "",
        limit: int = 5,
    ) -> list[MathlibTheoremHit]:
        """Return the highest-scoring local theorem candidates."""

        query_tokens = self._build_query_tokens(theorem_name, theorem_statement, last_error)
        if not query_tokens or not self.index:
            return []

        scored_hits: list[MathlibTheoremHit] = []
        for hit in self.index:
            score = self._score_hit(hit, query_tokens, theorem_name)
            if score <= 0:
                continue
            scored_hits.append(
                MathlibTheoremHit(
                    name=hit.name,
                    signature=hit.signature,
                    source_path=hit.source_path,
                    line_number=hit.line_number,
                    score=score,
                )
            )

        scored_hits.sort(key=lambda hit: (-hit.score, hit.name))
        return scored_hits[:limit]

    def _build_query_tokens(
        self,
        theorem_name: str,
        theorem_statement: str,
        last_error: str,
    ) -> set[str]:
        tokens = set()
        for chunk in (theorem_name, theorem_statement, last_error):
            tokens.update(token.lower() for token in self.TOKEN_PATTERN.findall(chunk))

        operator_tokens = {
            "+": "add",
            "*": "mul",
            "0": "zero",
            "1": "one",
        }
        for marker, token in operator_tokens.items():
            if marker in theorem_statement:
                tokens.add(token)

        statement_body = theorem_statement.rsplit(",", 1)[-1]
        normalized_statement = re.sub(r"\s+", "", statement_body)
        if "=" in normalized_statement:
            left, right = normalized_statement.split("=", 1)
            if "+" in left and "+" in right:
                tokens.add("add")
                if left.split("+") == list(reversed(right.split("+"))):
                    tokens.add("comm")
                if normalized_statement.count("+") >= 3:
                    tokens.add("assoc")
            if "*" in left and "*" in right:
                tokens.add("mul")
                if left.split("*") == list(reversed(right.split("*"))):
                    tokens.add("comm")
                if normalized_statement.count("*") >= 3:
                    tokens.add("assoc")

        return {token for token in tokens if len(token) >= 3}

    def _score_hit(
        self,
        hit: MathlibTheoremHit,
        query_tokens: set[str],
        theorem_name: str,
    ) -> int:
        # Build haystack from signature only (the actual theorem statement)
        # NOT from the theorem name, since user_theorem is meaningless
        haystack = hit.signature.lower()
        name_haystack = hit.name.lower()

        structured_hints = (
            ("add", "comm"),
            ("mul", "comm"),
            ("add", "assoc"),
            ("mul", "assoc"),
        )
        for left_hint, right_hint in structured_hints:
            if {left_hint, right_hint}.issubset(query_tokens):
                if left_hint not in haystack and left_hint not in name_haystack:
                    return 0
                if right_hint not in haystack and right_hint not in name_haystack:
                    return 0

        score = 0

        # Count how many query tokens match the signature (higher value)
        signature_matches = 0
        for token in query_tokens:
            if token in haystack:
                score += 3  # Higher weight for signature matches
                signature_matches += 1
            if token in name_haystack:
                score += 1  # Lower weight for name matches

        # Only boost mathematical keywords that actually appeared in the query.
        key_terms = {'nat', 'add', 'zero', 'mul', 'one', 'comm', 'assoc'}
        for term in query_tokens & key_terms:
            if term in haystack:
                score += 2

        compound_hints = (
            "add_comm",
            "mul_comm",
            "add_assoc",
            "mul_assoc",
            "add_zero",
            "zero_add",
            "mul_one",
            "one_mul",
            "sub_self",
        )
        for hint in compound_hints:
            hint_parts = set(hint.split("_"))
            if hint_parts.issubset(query_tokens) and hint in name_haystack:
                score += 8

        return score

    def get_proof_content(self, source_path: str, line_number: int) -> str:
        """Read full proof content starting from line_number.

        Extracts the proof block from a Lean source file by finding the theorem
        definition and reading until the proof terminator (usually ':=') is reached.

        Args:
            source_path: Path to the Lean source file.
            line_number: Line number where the theorem is defined.

        Returns:
            The full proof content as a string, or empty string if not found.
        """
        try:
            path = Path(source_path)
            if not path.exists():
                logger.warning(f"Source file not found: {source_path}")
                return ""

            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line_number < 1 or line_number > len(lines):
                logger.warning(f"Line number {line_number} out of range in {source_path}")
                return ""

            # Find the proof start (after ':=' in the theorem declaration)
            proof_lines: list[str] = []
            proof_started = False
            brace_depth = 0
            paren_depth = 0
            in_proof = False

            for i in range(line_number - 1, len(lines)):
                line = lines[i]
                stripped = line.strip()

                # Skip the theorem declaration line itself
                if i == line_number - 1:
                    # Check if there's a proof after ':=' on the same line
                    if ':=' in line:
                        after_colon = line.split(':=', 1)[1].strip()
                        if after_colon:
                            if after_colon.startswith('by'):
                                # Inline proof: 'theorem X := by proof'
                                proof_started = True
                                # Extract content after 'by'
                                proof_content = after_colon[2:].strip()
                                if proof_content.startswith('{'):
                                    brace_depth = 1
                                    proof_lines.append(proof_content.lstrip('{'))
                                elif proof_content.startswith('('):
                                    paren_depth = 1
                                    proof_lines.append(proof_content.lstrip('('))
                                else:
                                    proof_lines.append(proof_content)
                    continue

                if not in_proof and ':=' in stripped:
                    in_proof = True
                    # Check if proof is inline after ':='
                    if 'by' in stripped:
                        idx = stripped.find('by')
                        rest = stripped[idx + 2:].strip()
                        if rest.startswith('{'):
                            brace_depth = 1
                            proof_lines.append(rest.lstrip('{'))
                        elif rest.startswith('('):
                            paren_depth = 1
                            proof_lines.append(rest.lstrip('('))
                        else:
                            proof_lines.append(rest)
                    continue

                if in_proof:
                    proof_lines.append(line)

                    # Track brace depth for { } blocks
                    brace_depth += line.count('{') - line.count('}')
                    paren_depth += line.count('(') - line.count(')')

                    # End of proof when braces/parentheses are closed
                    if brace_depth == 0 and paren_depth == 0 and proof_lines:
                        # Check if this line just closes the proof
                        if line.strip() in ('}', ')', 'sorry', 'admit'):
                            break
                        # Check if next non-empty line is the end
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if next_line in ('}', ')', 'sorry', 'admit', ':=', 'end'):
                                break

            return '\n'.join(proof_lines).strip()

        except OSError as e:
            logger.error(f"Failed to read proof content: {e}")
            return ""

    def search_online(self, theorem_statement: str) -> Optional[dict]:
        """Fallback online search if local fails.

        Args:
            theorem_statement: The theorem statement to search for.

        Returns:
            Dictionary with theorem info if found, None otherwise.
        """
        # Online search placeholder - would integrate with web search
        # For now, return None to indicate no online result
        logger.info(f"Online search requested for: {theorem_statement[:100]}")
        return None
