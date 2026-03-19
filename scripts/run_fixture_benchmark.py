"""Run the fixture-based 20-problem benchmark for Riemann."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.benchmarking.fixture_runner import (
    load_cases,
    render_markdown_report,
    run_benchmark,
    summary_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Riemann fixture benchmark.")
    parser.add_argument(
        "--cases",
        default="benchmarks/benchmark_cases.json",
        help="Path to the fixture case file.",
    )
    parser.add_argument(
        "--json-output",
        default="reports/20_problem_fixture_results.json",
        help="Path to write JSON results.",
    )
    parser.add_argument(
        "--markdown-output",
        default="reports/20_problem_fixture_results.md",
        help="Path to write Markdown results.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    cases = load_cases(args.cases)
    summary = run_benchmark(cases)

    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(summary_to_dict(summary), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    markdown_path = Path(args.markdown_output)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown_report(summary), encoding="utf-8")

    print(f"Cases: {summary.total_cases}")
    print(f"Matched expectation: {summary.passed_cases}")
    print(f"Mismatched expectation: {summary.failed_cases}")
    print(f"Actual successes: {summary.actual_successes}")
    print(f"Median latency: {summary.median_duration_seconds:.4f}s")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
