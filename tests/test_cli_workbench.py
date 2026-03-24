from __future__ import annotations

from io import StringIO
from types import SimpleNamespace

from rich.console import Console

from src.cli.formatters import OutputFormatter, ProgressFormatter
from src.cli.interface import RiemannCLI


def make_cli() -> tuple[RiemannCLI, StringIO]:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=120, color_system=None)
    cli = RiemannCLI(verbose=False, safe_mode=False)
    cli.console = console
    cli.formatter = OutputFormatter(console, verbose=False)
    cli.progress_formatter = ProgressFormatter(console)
    cli._safe_mode = False
    return cli, buffer


def test_display_workspace_status_shows_workspace_summary() -> None:
    cli, buffer = make_cli()
    session = SimpleNamespace(
        project_root="D:/apps/lean/lean_verifier",
        active_file="SpherePacking/Main.lean",
        module_name="SpherePacking.Main",
        active_target=SimpleNamespace(name="main_theorem", status="planning"),
        open_plans=[object(), object()],
        recent_runs=[object()],
        last_diagnostic=SimpleNamespace(raw_message="error: unknown identifier"),
    )

    cli.display_workspace_status(session)

    output = buffer.getvalue()
    assert "Workspace" in output
    assert "Project: D:/apps/lean/lean_verifier" in output
    assert "File: SpherePacking/Main.lean" in output
    assert "Target: main_theorem (planning)" in output
    assert "Plans: 2" in output
    assert "Recent Runs: 1" in output
    assert "Last Error: error: unknown identifier" in output


def test_display_active_target_shows_statement_and_notes() -> None:
    cli, buffer = make_cli()
    target = {
        "name": "aux_lemma",
        "statement": "forall n : Nat, n + 0 = n",
        "file_path": "SpherePacking/Notes.lean",
        "start_line": 42,
        "status": "draft",
        "notes": "Try a rewrite with add_zero.",
    }

    cli.display_active_target(target)

    output = buffer.getvalue()
    assert "Active Target" in output
    assert "Name: aux_lemma" in output
    assert "Statement: forall n : Nat, n + 0 = n" in output
    assert "Location: SpherePacking/Notes.lean:42" in output
    assert "Status: draft" in output
    assert "Notes: Try a rewrite with add_zero." in output


def test_display_attempt_history_handles_success_and_failure() -> None:
    cli, buffer = make_cli()
    attempts = [
        SimpleNamespace(
            was_successful=False,
            proof_idea="rewrite with add_comm",
            lean_code="theorem t := by",
            error_message="unexpected token",
        ),
        SimpleNamespace(
            was_successful=True,
            proof_idea="mathlib reuse",
            lean_code="theorem t := by simpa using add_comm a b",
            error_message=None,
        ),
    ]

    cli.display_attempt_history(attempts)

    output = buffer.getvalue()
    assert "Attempt History" in output
    assert "1" in output
    assert "failed" in output
    assert "rewrite with add_comm" in output
    assert "unexpected token" in output
    assert "2" in output
    assert "success" in output
    assert "mathlib reuse" in output


def test_display_latest_lean_diagnostic_shows_error_details() -> None:
    cli, buffer = make_cli()
    diagnostic = SimpleNamespace(
        failing_file="SpherePacking/Main.lean",
        raw_message="SpherePacking/Main.lean:12:5: error: unknown tactic",
        message="unknown tactic",
        errors=["SpherePacking/Main.lean:12:5: error: unknown tactic"],
        warnings=["unused variable"],
        execution_time=1.25,
        last_submitted_code="theorem t := by sorry",
    )

    cli.display_latest_lean_diagnostic(diagnostic)

    output = buffer.getvalue()
    assert "Lean Diagnostic" in output
    assert "File: SpherePacking/Main.lean" in output
    assert "Time: 1.25s" in output
    assert "Message: unknown tactic" in output
    assert "Errors: SpherePacking/Main.lean:12:5: error: unknown tactic" in output
    assert "Warnings: unused variable" in output
    assert "Code: theorem t := by sorry" in output
