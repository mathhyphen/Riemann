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
