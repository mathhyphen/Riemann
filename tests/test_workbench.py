from __future__ import annotations

from tests.conftest import load_module_from_source


def test_workbench_discovers_targets_with_full_body_extent(tmp_path) -> None:
    workbench = load_module_from_source(
        "riemann_test_workbench",
        "src/agent/workbench.py",
    )

    lean_file = tmp_path / "Research.lean"
    lean_file.write_text(
        """import Mathlib

theorem add_zero_right (n : Nat) : n + 0 = n := by
  simpa using Nat.add_zero n

def helper : Nat := 0

lemma and_comm (P Q : Prop) : P /\\ Q -> Q /\\ P := by
  intro h
  exact And.intro h.right h.left
""",
        encoding="utf-8",
    )

    wb = workbench.ResearchWorkbench(tmp_path)
    targets = wb.open_file("Research.lean")

    assert [target.name for target in targets] == ["add_zero_right", "and_comm"]
    assert targets[0].statement == "(n : Nat) : n + 0 = n"
    assert "simpa using Nat.add_zero n" in targets[0].raw_text
    assert targets[0].end_line == 4

    focused = wb.focus_target("and_comm")
    assert focused.name == "and_comm"
    assert wb.session.active_target == focused


def test_workbench_builds_run_summary_from_mixed_inputs(tmp_path) -> None:
    workbench = load_module_from_source(
        "riemann_test_workbench_summary",
        "src/agent/workbench.py",
    )

    lean_file = tmp_path / "Research.lean"
    lean_file.write_text(
        """theorem sample (n : Nat) : n + 0 = n := by
  simpa using Nat.add_zero n
""",
        encoding="utf-8",
    )

    wb = workbench.ResearchWorkbench(tmp_path)
    wb.open_file("Research.lean")
    wb.focus_target("sample")

    context = type(
        "Context",
        (),
        {
            "current_iteration": 2,
            "mathlib_proof": "theorem sample (n : Nat) : n + 0 = n := by\n  simpa using Nat.add_zero n",
            "explanation": "A short explanation",
        },
    )()
    result = {
        "success": True,
        "iterations": 2,
        "source": "mathlib",
        "state": "success",
        "lean_code": "theorem sample (n : Nat) : n + 0 = n := by\n  simpa using Nat.add_zero n",
        "error": "",
        "explanation": "A short explanation",
    }

    summary = wb.build_run_summary(
        session=wb.session,
        context=context,
        result=result,
        timestamp="2026-03-21T10:00:00+08:00",
    )

    assert summary.timestamp == "2026-03-21T10:00:00+08:00"
    assert summary.success is True
    assert summary.source == "mathlib"
    assert summary.iterations == 2
    assert summary.project_root == str(tmp_path.resolve())
    assert summary.active_file == str(lean_file.resolve())
    assert summary.target_name == "sample"
    assert summary.target_statement == "(n : Nat) : n + 0 = n"
    assert "Nat.add_zero" in summary.lean_code
    assert summary.explanation == "A short explanation"

    stored = wb.record_run_summary(summary)
    assert stored == summary
    assert wb.session.recent_runs[0]["target_name"] == "sample"


def test_workbench_applies_proof_and_verifies_file(tmp_path) -> None:
    workbench = load_module_from_source(
        "riemann_test_workbench_apply_success",
        "src/agent/workbench.py",
    )

    lean_file = tmp_path / "Research.lean"
    lean_file.write_text(
        """import Mathlib

theorem sample (n : Nat) : n + 0 = n := by
  sorry

lemma keep_me : True := by
  trivial
""",
        encoding="utf-8",
    )

    class FakeVerifier:
        def __init__(self) -> None:
            self.calls = []

        def verify_file(self, file_path: str, timeout=None):
            self.calls.append((file_path, timeout))
            return type("Verification", (), {"success": True, "message": "ok"})()

    wb = workbench.ResearchWorkbench(tmp_path)
    wb.open_file("Research.lean")
    wb.focus_target("sample")
    verifier = FakeVerifier()

    result = wb.apply_proof(
        """import Mathlib

theorem sample (n : Nat) : n + 0 = n := by
  simpa using Nat.add_zero n
""",
        theorem_name="sample",
        verifier=verifier,
        timeout=12.5,
    )

    updated = lean_file.read_text(encoding="utf-8")
    assert result.success is True
    assert result.restored is False
    assert "import Mathlib\n\nimport Mathlib" not in updated
    assert "simpa using Nat.add_zero n" in updated
    assert "sorry" not in updated
    assert "lemma keep_me : True := by" in updated
    assert verifier.calls == [(str(lean_file.resolve()), 12.5)]
    assert wb.session.active_target is not None
    assert wb.session.active_target.name == "sample"


def test_workbench_reverts_failed_apply(tmp_path) -> None:
    workbench = load_module_from_source(
        "riemann_test_workbench_apply_failure",
        "src/agent/workbench.py",
    )

    lean_file = tmp_path / "Research.lean"
    original = """theorem sample (n : Nat) : n + 0 = n := by
  sorry
"""
    lean_file.write_text(original, encoding="utf-8")

    class RejectingVerifier:
        def verify_file(self, file_path: str, timeout=None):
            del file_path, timeout
            return type(
                "Verification",
                (),
                {"success": False, "message": "error: unknown tactic"},
            )()

    wb = workbench.ResearchWorkbench(tmp_path)
    wb.open_file("Research.lean")
    wb.focus_target("sample")

    result = wb.apply_proof(
        """theorem sample (n : Nat) : n + 0 = n := by
  exact Nat.add_zero n
""",
        theorem_name="sample",
        verifier=RejectingVerifier(),
    )

    assert result.success is False
    assert result.restored is True
    assert "error: unknown tactic" in result.message
    assert lean_file.read_text(encoding="utf-8") == original


def test_workbench_verifies_active_file_with_file_backend(tmp_path) -> None:
    workbench = load_module_from_source(
        "riemann_test_workbench_verify_file",
        "src/agent/workbench.py",
    )

    lean_file = tmp_path / "Research.lean"
    lean_file.write_text(
        """theorem sample : True := by
  trivial
""",
        encoding="utf-8",
    )

    class StubVerifier:
        def __init__(self) -> None:
            self.calls = []

        def verify_file(self, file_path: str, timeout=None):
            self.calls.append((file_path, timeout))
            return type(
                "Verification",
                (),
                {"success": True, "message": "ok", "checked_file": file_path},
            )()

    verifier = StubVerifier()
    wb = workbench.ResearchWorkbench(tmp_path)
    wb.open_file("Research.lean")

    result = wb.verify_active_file(verifier, timeout=12.5)

    assert result["success"] is True
    assert result["checked_file"] == str(lean_file.resolve())
    assert verifier.calls == [(str(lean_file.resolve()), 12.5)]
