from __future__ import annotations

from tests.conftest import build_main_stubs, load_module_from_source


def test_create_parser_handles_statement_and_max_iterations() -> None:
    main_module = load_module_from_source(
        "riemann_test_main_parser",
        "src/main.py",
        stubs=build_main_stubs(),
    )

    args = main_module.create_parser().parse_args(
        ["-m", "7", "forall n : Nat, n + 0 = n"]
    )

    assert args.max_iterations == 7
    assert args.statement == "forall n : Nat, n + 0 = n"
    assert args.verbose is False


def test_main_version_flag_exits_cleanly(monkeypatch, capsys) -> None:
    main_module = load_module_from_source(
        "riemann_test_main_version",
        "src/main.py",
        stubs=build_main_stubs(),
    )

    monkeypatch.setattr(
        "sys.argv",
        ["riemann", "--version"],
    )
    exit_code = main_module.main()

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Version: 0.1.0" in captured.out


def test_detect_lean_backend_defaults_to_http(monkeypatch) -> None:
    main_module = load_module_from_source(
        "riemann_test_lean_backend_default",
        "src/main.py",
        stubs=build_main_stubs(),
    )

    monkeypatch.delenv("LEAN_BACKEND", raising=False)

    assert main_module.detect_lean_backend() == "http"


def test_create_parser_handles_workbench_target_options() -> None:
    main_module = load_module_from_source(
        "riemann_test_main_workbench_parser",
        "src/main.py",
        stubs=build_main_stubs(),
    )

    args = main_module.create_parser().parse_args(
        [
            "--project-root",
            "D:/apps/lean/lean_verifier",
            "--target-file",
            "SpherePacking/Main.lean",
            "--target-name",
            "main_theorem",
            "--plan-only",
            "--apply",
        ]
    )

    assert args.project_root == "D:/apps/lean/lean_verifier"
    assert args.target_file == "SpherePacking/Main.lean"
    assert args.target_name == "main_theorem"
    assert args.plan_only is True
    assert args.apply is True
