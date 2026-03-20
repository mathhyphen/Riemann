"""Run the Riemann benchmark suite in fixture or live mode."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from src.benchmarking.fixture_runner import (
    BenchmarkEnvironmentError,
    create_live_runtime,
    filter_cases,
    load_cases,
    render_detailed_report,
    render_markdown_report,
    run_benchmark,
    summary_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Riemann benchmark suite.")
    parser.add_argument(
        "--mode",
        choices=("fixture", "live"),
        default="fixture",
        help="Benchmark mode to run.",
    )
    parser.add_argument(
        "--cases",
        default="benchmarks/benchmark_cases.json",
        help="Path to the benchmark case file.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Restrict the run to one or more categories.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Restrict the run to one or more case ids.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of cases after filtering.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker threads to use.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum proof iterations for live mode.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="Verification timeout for live mode.",
    )
    parser.add_argument(
        "--llm-provider",
        help="Override the LLM provider for live mode.",
    )
    parser.add_argument(
        "--lean-api-url",
        help="Override the Lean API base URL for live mode.",
    )
    parser.add_argument(
        "--json-output",
        help="Path to write JSON results. Defaults depend on mode.",
    )
    parser.add_argument(
        "--jsonl-output",
        help="Optional path to write one JSON object per result line.",
    )
    parser.add_argument(
        "--markdown-output",
        help="Path to write Markdown results. Defaults depend on mode.",
    )
    parser.add_argument(
        "--report-output",
        help="Path to write a detailed Markdown report.",
    )
    return parser


def _default_output_path(kind: str, mode: str) -> str:
    suffix = "fixture" if mode == "fixture" else "live"
    if kind == "json":
        return f"reports/20_problem_{suffix}_results.json"
    if kind == "jsonl":
        return f"reports/20_problem_{suffix}_results.jsonl"
    if kind == "markdown":
        return f"reports/20_problem_{suffix}_results.md"
    if kind == "report":
        return f"reports/20_problem_{suffix}_report.md"
    raise ValueError(f"Unknown output kind: {kind}")


def _write_json(path: str, payload: dict) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def _write_jsonl(path: str, results: list[dict]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    return output_path


def _write_markdown(path: str, markdown: str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()

    cases = filter_cases(
        load_cases(args.cases),
        case_ids=args.case_id,
        categories=args.category,
        limit=args.limit,
    )

    if not cases:
        raise SystemExit("No benchmark cases matched the requested filters.")

    if args.mode == "fixture":
        summary = run_benchmark(cases, mode="fixture", workers=args.workers)
    else:
        try:
            def runtime_factory():
                return create_live_runtime(
                    max_iterations=args.max_iterations,
                    timeout_seconds=args.timeout_seconds,
                    llm_provider=args.llm_provider,
                    lean_api_url=args.lean_api_url,
                )

            llm_client, verifier_api, config = runtime_factory()
        except BenchmarkEnvironmentError as exc:
            raise SystemExit(str(exc)) from exc

        summary = run_benchmark(
            cases,
            mode="live",
            llm_client=llm_client,
            verifier_api=verifier_api,
            config=config,
            runtime_factory=runtime_factory,
            workers=args.workers,
        )

    payload = summary_to_dict(summary)
    json_path = _write_json(args.json_output or _default_output_path("json", args.mode), payload)
    markdown_path = _write_markdown(
        args.markdown_output or _default_output_path("markdown", args.mode),
        render_markdown_report(summary),
    )
    report_path = _write_markdown(
        args.report_output or _default_output_path("report", args.mode),
        render_detailed_report(summary),
    )

    jsonl_path = None
    if args.jsonl_output:
        jsonl_path = _write_jsonl(args.jsonl_output, payload["results"])

    print(f"Mode: {summary.mode}")
    print(f"Cases: {summary.total_cases}")
    print(f"Matched expectation: {summary.passed_cases}")
    print(f"Mismatched expectation: {summary.failed_cases}")
    print(f"Actual successes: {summary.actual_successes}")
    print(f"Median latency: {summary.median_duration_seconds:.4f}s")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    print(f"Report: {report_path}")
    if jsonl_path is not None:
        print(f"JSONL: {jsonl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
