from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from src.agent.state import AgentConfig
from src.benchmarking.fixture_runner import (
    filter_cases,
    inspect_live_environment,
    load_cases,
    render_detailed_report,
    render_formal_report,
    render_markdown_report,
    run_benchmark,
)


def test_fixture_runner_handles_mixed_expectations(tmp_path: Path) -> None:
    fixture_path = tmp_path / "cases.json"
    fixture_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "pass_case",
                        "category": "logic",
                        "difficulty": "easy",
                        "theorem_name": "pass_case",
                        "theorem_statement": "True",
                        "llm_response": "### Proof Strategy\nok\n### Lean Code\n```lean\ntrivial\n```\n### Explanation\nok",
                        "expectation": {
                            "success": True,
                            "required_substrings": ["theorem pass_case : True := by", "trivial"],
                            "forbidden_substrings": ["sorry"],
                        },
                    },
                    {
                        "case_id": "expected_failure",
                        "category": "converter",
                        "difficulty": "easy",
                        "theorem_name": "expected_failure",
                        "theorem_statement": "True",
                        "llm_response": "### Proof Strategy\nok\n### Lean Code\n```lean\ntrivial\n```\n### Explanation\nok",
                        "expectation": {
                            "success": False,
                            "required_substrings": ["theorem expected_failure : True := by", "trivial"],
                            "forbidden_substrings": [],
                            "error": "Fixture expected failure",
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    cases = load_cases(fixture_path)
    summary = run_benchmark(cases)

    assert summary.total_cases == 2
    assert summary.passed_cases == 2
    assert summary.actual_successes == 1
    assert summary.category_breakdown["logic"]["actual_success"] == 1
    assert summary.category_breakdown["converter"]["matched_expectation"] == 1
    assert summary.mode == "fixture"


def test_render_markdown_report_contains_counts() -> None:
    cases = load_cases("tests/fixtures/minimal_benchmark_cases.json")
    summary = run_benchmark(cases)

    markdown = render_markdown_report(summary)

    assert "# Fixture Benchmark Report" in markdown
    assert "- Mode: fixture" in markdown
    assert "| logic | 1 | 1 | 1 |" in markdown
    assert "| converter | 1 | 1 | 0 |" in markdown


def test_render_detailed_report_contains_diagnostics() -> None:
    cases = load_cases("tests/fixtures/minimal_benchmark_cases.json")
    summary = run_benchmark(cases, mode="fixture", workers=2)

    report = render_detailed_report(summary)

    assert "# Benchmark Summary" in report
    assert "## Failure Diagnostics" in report
    assert "expected_negative_case" in report or "success" in report


def test_render_formal_report_contains_metadata_and_caveats() -> None:
    cases = load_cases("benchmarks/benchmark_cases.json")
    summary = run_benchmark(cases, mode="fixture", workers=2)

    report = render_formal_report(
        summary,
        run_metadata={
            "generated_at": "2026-03-20 12:00:00 +0800",
            "runner": "scripts/run_benchmark.py",
            "cases_path": "benchmarks/benchmark_cases.json",
            "workers": 2,
            "categories": [],
            "case_ids": [],
            "limit": None,
            "git_branch": "codex/test-report",
            "git_commit": "abc1234",
        },
        output_paths={"JSON results": "reports/test.json"},
    )

    assert "# 20-Problem Benchmark Report" in report
    assert "## Run Metadata" in report
    assert "- Run mode: `fixture`" in report
    assert "## Diagnostic Summary" in report
    assert "## Pipeline Caveats" in report
    assert "| case_17 | classically_true |" in report
    assert "## Cases Requiring Attention" in report


def test_render_formal_report_respects_filtered_scope() -> None:
    cases = filter_cases(load_cases("tests/fixtures/minimal_benchmark_cases.json"), categories=["logic"], limit=1)
    summary = run_benchmark(cases, mode="fixture")

    report = render_formal_report(
        summary,
        run_metadata={
            "generated_at": "2026-03-20 12:00:00 +0800",
            "runner": "scripts/run_benchmark.py",
            "cases_path": "tests/fixtures/minimal_benchmark_cases.json",
            "workers": 1,
            "categories": ["logic"],
            "case_ids": [],
            "limit": 1,
            "git_branch": "codex/test-report",
            "git_commit": "abc1234",
        },
    )

    assert "- Problems run: `1`" in report
    assert "- Selected categories: `logic`" in report
    assert "| logic_true | logic | easy | pass | pass | yes |" in report
    assert "converter_expected_failure" not in report


def test_official_benchmark_fixture_loads_all_20_cases() -> None:
    cases = load_cases("benchmarks/benchmark_cases.json")

    assert len(cases) == 20
    assert sum(case.expectation.success for case in cases) == 10
    assert sum(case.theorem_truth == "false" for case in cases) == 8
    assert any(case.case_id == "case_17" for case in cases)


def test_filter_cases_supports_categories_and_limit() -> None:
    cases = load_cases("benchmarks/benchmark_cases.json")

    selected = filter_cases(cases, categories=["logic_basic"], limit=2)

    assert len(selected) == 2
    assert all(case.category == "logic_basic" for case in selected)


def test_inspect_live_environment_reports_missing_credentials() -> None:
    status = inspect_live_environment(env={}, llm_provider="openai", lean_api_url="http://lean.local")

    assert status["llm_provider"] == "openai"
    assert status["lean_api_url"] == "http://lean.local"
    assert status["ready_for_client_init"] is False
    assert "OPENAI_API_KEY is not set for live mode." in status["issues"]


def test_inspect_live_environment_reports_missing_minimax_credentials() -> None:
    status = inspect_live_environment(env={}, llm_provider="minimax", lean_api_url="http://lean.local")

    assert status["llm_provider"] == "minimax"
    assert status["lean_api_url"] == "http://lean.local"
    assert status["ready_for_client_init"] is False
    assert "MINIMAX_API_KEY is not set for live mode." in status["issues"]


def test_inspect_live_environment_reports_local_backend() -> None:
    status = inspect_live_environment(
        env={"LEAN_BACKEND": "local", "LEAN_PATH": "C:/lean/bin/lean", "MINIMAX_API_KEY": "test"},
        llm_provider="minimax",
    )

    assert status["lean_backend"] == "local"
    assert status["lean_path"] == "C:/lean/bin/lean"
    assert status["ready_for_client_init"] is True


class _FakeLiveLLM:
    def generate(self, **kwargs):
        del kwargs
        return type("Response", (), {"content": "### Lean Code\n```lean\ntrivial\n```"})()

    def stream_generate(self, **kwargs):
        del kwargs
        yield "### Lean Code\n```lean\ntrivial\n```"


class _FakeLiveVerifier:
    def __init__(self):
        self.calls = []

    def verify_proof(self, code: str, timeout: float | None = None):
        self.calls.append((code, timeout))
        return {"success": True}


def test_run_benchmark_supports_live_mode_with_injected_clients() -> None:
    cases = filter_cases(load_cases("benchmarks/benchmark_cases.json"), case_ids=["case_01"])
    summary = run_benchmark(
        cases,
        mode="live",
        llm_client=_FakeLiveLLM(),
        verifier_api=_FakeLiveVerifier(),
        config=AgentConfig(max_iterations=1, stream_output=False, verbose=False),
    )

    assert summary.mode == "live"
    assert summary.total_cases == 1
    assert summary.actual_successes == 1
    assert summary.results[0].case_id == "case_01"


def test_render_formal_report_supports_live_mode() -> None:
    cases = filter_cases(load_cases("benchmarks/benchmark_cases.json"), case_ids=["case_01"])
    summary = run_benchmark(
        cases,
        mode="live",
        llm_client=_FakeLiveLLM(),
        verifier_api=_FakeLiveVerifier(),
        config=AgentConfig(max_iterations=1, stream_output=False, verbose=False),
    )

    report = render_formal_report(
        summary,
        run_metadata={
            "generated_at": "2026-03-20 12:00:00 +0800",
            "runner": "scripts/run_benchmark.py",
            "cases_path": "benchmarks/benchmark_cases.json",
            "workers": 1,
            "categories": [],
            "case_ids": ["case_01"],
            "limit": None,
            "git_branch": "codex/test-report",
            "git_commit": "abc1234",
            "llm_provider": "anthropic",
            "lean_api_url": "http://lean.local",
        },
    )

    assert "- Run mode: `live`" in report
    assert "- LLM provider: `anthropic`" in report
    assert "- Lean API URL: `http://lean.local`" in report
    assert "| case_01 |" in report


def test_run_benchmark_supports_parallel_fixture_mode() -> None:
    cases = filter_cases(load_cases("benchmarks/benchmark_cases.json"), categories=["logic_basic"])
    summary = run_benchmark(cases, mode="fixture", workers=3)

    assert summary.mode == "fixture"
    assert summary.total_cases == 4
    assert summary.passed_cases == 4


def test_cli_writes_unified_benchmark_report(tmp_path: Path, monkeypatch) -> None:
    script_path = Path("scripts/run_benchmark.py").resolve()
    spec = importlib.util.spec_from_file_location("run_benchmark_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    json_output = tmp_path / "results.json"
    markdown_output = tmp_path / "results.md"
    report_output = tmp_path / "report.md"
    benchmark_report_output = tmp_path / "benchmark_report.md"

    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    monkeypatch.setattr(module, "_git_value", lambda *args: "test-value")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_benchmark.py",
            "--cases",
            "tests/fixtures/minimal_benchmark_cases.json",
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
            "--report-output",
            str(report_output),
            "--benchmark-report-output",
            str(benchmark_report_output),
        ],
    )

    assert module.main() == 0
    assert benchmark_report_output.exists()
    content = benchmark_report_output.read_text(encoding="utf-8")
    assert "# 20-Problem Benchmark Report" in content
    assert "- Run mode: `fixture`" in content
