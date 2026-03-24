from __future__ import annotations

import subprocess

from src.lean_module.local_client import LocalLeanClient


def test_local_client_verify_file_uses_project_root_and_reports_checked_file(
    monkeypatch,
    tmp_path,
) -> None:
    project_root = tmp_path / "lean_project"
    project_root.mkdir()
    (project_root / "lakefile.toml").write_text("[package]\nname = \"demo\"\n", encoding="utf-8")
    target_file = project_root / "Demo.lean"
    target_file.write_text("theorem demo : True := by\n  trivial\n", encoding="utf-8")

    monkeypatch.setattr(LocalLeanClient, "_find_lean", lambda self: "lean")
    monkeypatch.setattr(LocalLeanClient, "_find_lake", lambda self: "lake")

    calls: list[tuple[list[str], str | None, float | None]] = []

    def fake_run(cmd, **kwargs):
        calls.append((list(cmd), kwargs.get("cwd"), kwargs.get("timeout")))
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = LocalLeanClient(project_root=str(project_root))
    result = client.verify_file("Demo.lean", timeout=12.5)

    assert result.success is True
    assert result.checked_file == str(target_file.resolve())
    assert calls == [
        (
            ["lake", "env", "lean", str(target_file.resolve())],
            str(project_root.resolve()),
            12.5,
        )
    ]


def test_local_client_verify_file_fails_before_invoking_lean_when_missing(
    monkeypatch,
    tmp_path,
) -> None:
    project_root = tmp_path / "lean_project"
    project_root.mkdir()

    monkeypatch.setattr(LocalLeanClient, "_find_lean", lambda self: "lean")
    monkeypatch.setattr(LocalLeanClient, "_find_lake", lambda self: "lake")

    def fake_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called for a missing file")

    monkeypatch.setattr(subprocess, "run", fake_run)

    client = LocalLeanClient(project_root=str(project_root))
    result = client.verify_file("Missing.lean", timeout=4.0)

    assert result.success is False
    assert "Lean file not found" in result.message
    assert result.checked_file == str((project_root / "Missing.lean").resolve())
