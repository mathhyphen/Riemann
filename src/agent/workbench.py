"""Minimal research workbench helpers for Lean project workflows."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

NAMED_DECLARATION_PATTERN = re.compile(
    r"^\s*(theorem|lemma)\s+([A-Za-z0-9_'.]+)\b(.*)$"
)
EXAMPLE_DECLARATION_PATTERN = re.compile(r"^\s*example\b(.*)$")
TOP_LEVEL_BOUNDARY_PATTERN = re.compile(
    r"^(theorem|lemma|example|def|abbrev|structure|class|inductive|instance|axiom|constant|namespace|section|end)\b"
)
TACTIC_PREFIXES = (
    "intro",
    "intros",
    "rw",
    "simp",
    "simpa",
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
    "refl",
    "aesop",
    "omega",
    "linarith",
    "show",
    "from",
)


@dataclass(frozen=True)
class LeanTarget:
    """A theorem, lemma, or example discovered in a Lean file."""

    kind: str
    name: str
    statement: str
    file_path: str
    start_line: int
    end_line: int
    raw_text: str
    status: str = "discovered"


@dataclass
class WorkbenchSession:
    """State for an active Lean research workspace."""

    project_root: Optional[str] = None
    active_file: Optional[str] = None
    module_name: Optional[str] = None
    active_target: Optional[LeanTarget] = None
    targets: list[LeanTarget] = field(default_factory=list)
    open_plans: dict[str, Any] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    recent_runs: list[dict[str, Any]] = field(default_factory=list)
    last_diagnostic: Any = None

    def set_plan(self, target_name: str, plan: Any) -> None:
        self.open_plans[target_name] = plan

    def get_plan(self, target_name: str) -> Any:
        return self.open_plans.get(target_name)


@dataclass(frozen=True)
class RunSummary:
    """Concise summary of a proof run."""

    timestamp: str
    success: bool
    status: str
    source: str
    iterations: int
    project_root: Optional[str]
    active_file: Optional[str]
    target_name: Optional[str]
    target_statement: Optional[str]
    lean_code: str
    error: str
    explanation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ApplyResult:
    """Result of writing a proof back into a Lean file."""

    success: bool
    message: str
    restored: bool = False
    target: Optional[LeanTarget] = None
    verification: dict[str, Any] = field(default_factory=dict)
    diagnostic: Any = None
    file_path: Optional[str] = None
    applied_declaration: str = ""


class ResearchWorkbench:
    """Lightweight coordinator for research-oriented Lean workflows."""

    def __init__(self, project_root: str | Path | None = None):
        self.session = WorkbenchSession()
        if project_root is not None:
            self.open_project(project_root)

    def open_project(self, project_root: str | Path) -> WorkbenchSession:
        """Attach the workbench to a Lean project root."""

        root = Path(project_root).expanduser().resolve()
        self.session.project_root = str(root)
        return self.session

    def open_file(self, file_path: str | Path) -> list[LeanTarget]:
        """Select a Lean file and refresh the discovered targets."""

        path = self._resolve_file_path(file_path)
        self.session.active_file = str(path)
        self.session.module_name = path.with_suffix("").name
        self.session.targets = self.discover_targets(path)
        self.session.active_target = self.session.targets[0] if self.session.targets else None
        return self.session.targets

    def discover_targets(self, file_path: str | Path | None = None) -> list[LeanTarget]:
        """Discover theorem-like declarations from a Lean source file."""

        path = self._resolve_file_path(file_path or self.session.active_file)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

        discovered: list[LeanTarget] = []
        active: dict[str, Any] | None = None

        for line_number, line in enumerate(lines, start=1):
            if active is not None and self._is_top_level_boundary(line):
                discovered.append(
                    self._finalize_target(
                        path,
                        active,
                        int(active.get("last_content_line", active["start_line"])),
                    )
                )
                active = None

            match = self._match_declaration_start(line, line_number)
            if active is None:
                if match is None:
                    continue
                active = match
                continue

            active["lines"].append(line.rstrip())
            if line.strip():
                active["last_content_line"] = line_number

        if active is not None:
            discovered.append(
                self._finalize_target(
                    path,
                    active,
                    int(active.get("last_content_line", len(lines))),
                )
            )

        return discovered

    def focus_target(
        self,
        theorem_name: str,
        file_path: str | Path | None = None,
    ) -> LeanTarget:
        """Focus a discovered target by name."""

        if file_path is not None:
            targets = self.discover_targets(file_path)
            self.session.active_file = str(self._resolve_file_path(file_path))
            self.session.targets = targets
        elif not self.session.targets and self.session.active_file:
            self.session.targets = self.discover_targets(self.session.active_file)

        for target in self.session.targets:
            if target.name == theorem_name:
                self.session.active_target = target
                return target

        raise KeyError(f"Target not found: {theorem_name}")

    def build_run_summary(
        self,
        *,
        session: WorkbenchSession | Mapping[str, Any] | None = None,
        context: Any = None,
        result: Any = None,
        timestamp: str = "",
    ) -> RunSummary:
        """Create a compact summary from session/context/result-like inputs."""

        session_data = self._coerce_data(session or self.session)
        context_data = self._coerce_data(context)
        result_data = self._coerce_data(result)
        target_data = self._coerce_data(session_data.get("active_target"))

        success = bool(result_data.get("success", False))
        source = result_data.get("source") or (
            "mathlib" if context_data.get("mathlib_proof") else "generated"
        )
        iterations = int(
            result_data.get("iterations")
            or context_data.get("current_iteration")
            or 0
        )
        status = (
            result_data.get("state")
            or context_data.get("state")
            or ("success" if success else "failed")
        )
        lean_code = result_data.get("lean_code") or context_data.get("lean_code") or ""
        error = result_data.get("error") or context_data.get("error") or ""
        explanation = result_data.get("explanation") or context_data.get("explanation") or ""

        return RunSummary(
            timestamp=timestamp,
            success=success,
            status=str(status),
            source=str(source),
            iterations=iterations,
            project_root=session_data.get("project_root"),
            active_file=session_data.get("active_file"),
            target_name=target_data.get("name"),
            target_statement=target_data.get("statement"),
            lean_code=lean_code,
            error=error,
            explanation=explanation,
        )

    def record_run_summary(self, summary: RunSummary) -> RunSummary:
        """Store a run summary in the active session."""

        self.session.recent_runs.append(summary.as_dict())
        return summary

    def apply_proof(
        self,
        lean_code: str,
        *,
        target_name: Optional[str] = None,
        theorem_name: Optional[str] = None,
        verifier: Any = None,
        timeout: Optional[float] = None,
    ) -> LeanTarget | ApplyResult:
        """Write a verified proof back into the active Lean file."""

        if not self.session.active_file:
            raise ValueError("No active Lean file selected")

        resolved_target_name = target_name or theorem_name
        if resolved_target_name:
            target = self.focus_target(resolved_target_name)
        else:
            target = self.session.active_target

        if target is None:
            raise ValueError("No active target selected")

        path = self._resolve_file_path(target.file_path or self.session.active_file)
        original_text = path.read_text(encoding="utf-8", errors="replace")
        line_ending = "\r\n" if "\r\n" in original_text else "\n"
        lines = original_text.splitlines()

        replacement = self._build_target_replacement(target, lean_code)
        updated_lines = (
            lines[: target.start_line - 1]
            + replacement.splitlines()
            + lines[target.end_line :]
        )

        updated_text = line_ending.join(updated_lines)
        if original_text.endswith(("\n", "\r\n")):
            updated_text += line_ending
        path.write_text(updated_text, encoding="utf-8")

        self.open_file(path)
        refreshed = self.focus_target(target.name)
        self.session.active_target = refreshed
        if verifier is None:
            return refreshed

        try:
            verification = self.verify_active_file(verifier, timeout=timeout)
        except Exception as exc:
            path.write_text(original_text, encoding="utf-8")
            self.open_file(path)
            self.focus_target(target.name)
            payload = {"success": False, "error": str(exc), "message": str(exc)}
            return ApplyResult(
                success=False,
                message=f"Verification raised an exception after apply; restored original content: {exc}",
                restored=True,
                target=self.session.active_target,
                verification=payload,
                diagnostic=payload,
                file_path=str(path),
                applied_declaration=replacement,
            )

        if verification.get("success"):
            return ApplyResult(
                success=True,
                message="Applied proof and verified the file successfully.",
                restored=False,
                target=refreshed,
                verification=verification,
                diagnostic=verification,
                file_path=str(path),
                applied_declaration=replacement,
            )

        path.write_text(original_text, encoding="utf-8")
        self.open_file(path)
        self.focus_target(target.name)
        failure_message = verification.get("message") or verification.get("error") or "verification failed"
        return ApplyResult(
            success=False,
            message=f"File verification failed after apply; restored the previous file contents. {failure_message}",
            restored=True,
            target=self.session.active_target,
            verification=verification,
            diagnostic=verification,
            file_path=str(path),
            applied_declaration=replacement,
        )

    def verify_active_file(
        self,
        verifier: Any,
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Verify the active Lean file with the configured verifier."""

        if not self.session.active_file:
            raise ValueError("No active Lean file selected")

        active_file = self.session.active_file
        if hasattr(verifier, "verify_file"):
            response = verifier.verify_file(active_file, timeout=timeout)
        elif hasattr(verifier, "verify_proof"):
            response = verifier.verify_proof(
                code=Path(active_file).read_text(encoding="utf-8"),
                timeout=timeout,
                filename=active_file,
            )
        else:
            raise TypeError("Verifier does not support file verification")

        if isinstance(response, Mapping):
            payload = dict(response)
        else:
            payload = {
                "success": bool(getattr(response, "success", False)),
                "message": getattr(response, "message", ""),
                "errors": list(getattr(response, "errors", []) or []),
                "warnings": list(getattr(response, "warnings", []) or []),
                "execution_time": getattr(response, "execution_time", None),
                "checked_file": getattr(response, "checked_file", active_file),
            }

        payload.setdefault("checked_file", active_file)
        return payload

    def _resolve_file_path(self, file_path: str | Path | None) -> Path:
        if file_path is None:
            raise ValueError("A Lean file path is required")

        path = Path(file_path).expanduser()
        if not path.is_absolute() and self.session.project_root:
            path = Path(self.session.project_root) / path

        if not path.exists():
            raise FileNotFoundError(f"Lean file not found: {path}")

        return path.resolve()

    def _finalize_target(
        self,
        file_path: Path,
        active: dict[str, Any],
        end_line: int,
    ) -> LeanTarget:
        raw_text = "\n".join(active["lines"]).strip()
        statement = self._extract_statement(raw_text)
        return LeanTarget(
            kind=active["kind"],
            name=active["name"],
            statement=statement,
            file_path=str(file_path),
            start_line=active["start_line"],
            end_line=end_line,
            raw_text=raw_text,
        )

    def _extract_statement(self, raw_text: str) -> str:
        header = raw_text.split(":=", 1)[0].strip()
        header_lines = [line.strip() for line in header.splitlines() if line.strip()]
        if not header_lines:
            return ""

        first_line = header_lines[0]
        match = NAMED_DECLARATION_PATTERN.match(first_line)
        if not match:
            return " ".join(header_lines).strip()

        pieces = [match.group(3).strip()]
        pieces.extend(header_lines[1:])
        return " ".join(piece for piece in pieces if piece).strip()

    def _match_declaration_start(
        self,
        line: str,
        line_number: int,
    ) -> dict[str, Any] | None:
        named_match = NAMED_DECLARATION_PATTERN.match(line)
        if named_match:
            return {
                "kind": named_match.group(1),
                "name": named_match.group(2),
                "start_line": line_number,
                "lines": [line.rstrip()],
                "last_content_line": line_number if line.strip() else None,
            }

        example_match = EXAMPLE_DECLARATION_PATTERN.match(line)
        if example_match:
            return {
                "kind": "example",
                "name": f"example_{line_number}",
                "start_line": line_number,
                "lines": [line.rstrip()],
                "last_content_line": line_number if line.strip() else None,
            }

        return None

    def _coerce_data(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        if dataclass_isinstance(value):
            return asdict(value)
        if hasattr(value, "__dict__"):
            return {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        return {}

    def _is_top_level_boundary(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if line.startswith((" ", "\t")):
            return False
        return TOP_LEVEL_BOUNDARY_PATTERN.match(stripped) is not None

    def _build_target_replacement(self, target: LeanTarget, lean_code: str) -> str:
        header = target.raw_text.split(":=", 1)[0].rstrip()
        body = self._extract_body_text(lean_code)
        return f"{header} := {body}".rstrip()

    def _extract_body_text(self, lean_code: str) -> str:
        stripped = self._strip_leading_imports(lean_code)
        if not stripped:
            raise ValueError("No Lean proof content available to apply")

        first_non_empty = next(
            (line.strip() for line in stripped.splitlines() if line.strip()),
            "",
        )
        if first_non_empty.startswith(("theorem ", "lemma ", "example ")):
            if ":=" not in stripped:
                raise ValueError("Theorem declaration is missing ':=' and cannot be applied")
            return stripped.split(":=", 1)[1].strip()

        if stripped.startswith("by"):
            return stripped

        proof_lines = [line.rstrip() for line in stripped.splitlines() if line.strip()]
        if not proof_lines:
            raise ValueError("No proof body available to apply")

        if self._looks_like_tactic_script(proof_lines):
            return "by\n" + "\n".join(f"  {line.lstrip()}" for line in proof_lines)

        return stripped

    def _strip_leading_imports(self, lean_code: str) -> str:
        lines = lean_code.splitlines()
        while lines and (
            not lines[0].strip() or lines[0].strip().startswith("import ")
        ):
            lines.pop(0)
        return "\n".join(lines).strip()

    def _looks_like_tactic_script(self, proof_lines: list[str]) -> bool:
        first = proof_lines[0].lstrip()
        return any(
            first == prefix or first.startswith(prefix + " ")
            for prefix in TACTIC_PREFIXES
        )


def dataclass_isinstance(value: Any) -> bool:
    return hasattr(value, "__dataclass_fields__")


__all__ = [
    "ApplyResult",
    "LeanTarget",
    "RunSummary",
    "ResearchWorkbench",
    "WorkbenchSession",
]