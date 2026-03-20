from __future__ import annotations

import json
from pathlib import Path

from src.agent.state import AgentConfig
from src.benchmarking.fixture_runner import (
    filter_cases,
    inspect_live_environment,
    load_cases,
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
