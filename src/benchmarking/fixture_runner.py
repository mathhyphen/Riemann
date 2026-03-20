"""Benchmark runners for Riemann."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from src.agent.proof_generator import ProofGenerator
from src.agent.proof_to_lean import ProofToLeanConverter
from src.agent.state import AgentConfig, ProofState
from src.agent.verification_loop import VerificationLoop


@dataclass(frozen=True)
class BenchmarkExpectation:
    """Validation rules for a converted Lean proof."""

    success: bool
    required_substrings: list[str] = field(default_factory=list)
    forbidden_substrings: list[str] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True)
class BenchmarkCase:
    """Single benchmark case description."""

    case_id: str
    category: str
    difficulty: str
    theorem_name: str
    theorem_statement: str
    theorem_truth: str
    llm_response: str
    expectation: BenchmarkExpectation
    notes: str = ""


@dataclass(frozen=True)
class BenchmarkResult:
    """Result of running a single benchmark case."""

    case_id: str
    category: str
    difficulty: str
    theorem_name: str
    theorem_statement: str
    theorem_truth: str
    expected_success: bool
    actual_success: bool
    passed_expectation: bool
    state: str
    iterations: int
    error: str
    lean_code: str
    duration_seconds: float
    notes: str = ""


@dataclass(frozen=True)
class FixtureBenchmarkSummary:
    """Summary of a benchmark run."""

    mode: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    expected_successes: int
    actual_successes: int
    truth_breakdown: dict[str, int]
    median_duration_seconds: float
    category_breakdown: dict[str, dict[str, int]]
    results: list[BenchmarkResult]


class BenchmarkEnvironmentError(RuntimeError):
    """Raised when live benchmark prerequisites are not available."""


class _SingleResponseLLM:
    """Small LLM double that always returns a single fixture response."""

    def __init__(self, response: str):
        self._response = response

    def generate(self, **_: Any) -> Any:
        return type("FixtureResponse", (), {"content": self._response})()

    def stream_generate(self, **_: Any):
        yield self._response


class _ExpectationVerifier:
    """Verifier that validates converted code against fixture expectations."""

    def __init__(self, expectation: BenchmarkExpectation):
        self.expectation = expectation
        self.last_code = ""
        self.expectation_checks_passed = False

    def verify_proof(self, code: str, timeout: float | None = None) -> dict[str, Any]:
        del timeout
        self.last_code = code
        self.expectation_checks_passed = False

        for fragment in self.expectation.required_substrings:
            if fragment not in code:
                return {
                    "success": False,
                    "error": f"Missing expected fragment: {fragment}",
                }

        for fragment in self.expectation.forbidden_substrings:
            if fragment in code:
                return {
                    "success": False,
                    "error": f"Forbidden fragment present: {fragment}",
                }

        self.expectation_checks_passed = True

        if self.expectation.success:
            return {"success": True}

        return {
            "success": False,
            "error": self.expectation.error or "Fixture expected failure",
        }


class _CapturingVerifier:
    """Proxy verifier that records the last Lean code sent for verification."""

    def __init__(self, verifier_api: Any):
        self.verifier_api = verifier_api
        self.last_code = ""

    def verify_proof(self, code: str, timeout: float | None = None) -> dict[str, Any]:
        self.last_code = code
        if hasattr(self.verifier_api, "verify_proof"):
            return self.verifier_api.verify_proof(code=code, timeout=timeout)
        return self.verifier_api.verify(code=code, timeout=timeout)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.verifier_api, name)


def _parse_case(raw_case: dict[str, Any]) -> BenchmarkCase:
    if "expectation" not in raw_case:
        return _expand_simple_case(raw_case)

    expectation = BenchmarkExpectation(**raw_case["expectation"])
    return BenchmarkCase(
        case_id=raw_case["case_id"],
        category=raw_case["category"],
        difficulty=raw_case["difficulty"],
        theorem_name=raw_case["theorem_name"],
        theorem_statement=raw_case["theorem_statement"],
        theorem_truth=raw_case.get("theorem_truth", "unknown"),
        llm_response=raw_case["llm_response"],
        expectation=expectation,
        notes=raw_case.get("notes", ""),
    )


def _make_llm_response(code: str, *, fenced: bool = True) -> str:
    lean_block = f"```lean\n{code}\n```" if fenced else code
    return (
        "### Proof Strategy\n"
        "Fixture response.\n"
        "### Lean Code\n"
        f"{lean_block}\n"
        "### Explanation\n"
        "Generated from the fixture library."
    )


def _simple_case_catalog() -> dict[str, dict[str, Any]]:
    return {
        "case_01": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro n\nsimpa using Nat.add_zero n"),
            "required_substrings": ["simpa using Nat.add_zero n"],
        },
        "case_02": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro n\nsimpa using Nat.zero_add n"),
            "required_substrings": ["simpa using Nat.zero_add n"],
        },
        "case_03": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro n\nsimpa using Nat.mul_one n"),
            "required_substrings": ["simpa using Nat.mul_one n"],
        },
        "case_04": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro n\nsimpa using Nat.one_mul n"),
            "required_substrings": ["simpa using Nat.one_mul n"],
        },
        "case_05": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro n\nsimpa using Nat.sub_self n"),
            "required_substrings": ["simpa using Nat.sub_self n"],
        },
        "case_06": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro a b c\nsimpa [Nat.add_assoc]"),
            "required_substrings": ["simpa [Nat.add_assoc]"],
        },
        "case_07": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro P h\nexact h"),
            "required_substrings": ["intro P h", "exact h"],
        },
        "case_08": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro P Q hP hQ\nexact And.intro hP hQ", fenced=False),
            "required_substrings": ["intro P Q hP hQ", "And.intro hP hQ"],
        },
        "case_09": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro P Q h\nexact And.intro h.right h.left"),
            "required_substrings": ["And.intro h.right h.left"],
        },
        "case_10": {
            "difficulty": "easy",
            "llm_response": _make_llm_response("intro P Q hP hQ\nexact Or.inl hP", fenced=False),
            "required_substrings": ["intro P Q hP hQ", "Or.inl hP"],
        },
        "case_11": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("intro n\nomega"),
            "required_substrings": ["omega"],
        },
        "case_12": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("intro n\nomega"),
            "required_substrings": ["omega"],
        },
        "case_13": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("intro n\nrfl"),
            "required_substrings": ["rfl"],
        },
        "case_14": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("intro a b\nomega"),
            "required_substrings": ["omega"],
        },
        "case_15": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("intro a b\nomega"),
            "required_substrings": ["omega"],
        },
        "case_16": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("intro P Q hPQ hP hQ\nexact hQ (hPQ hP)"),
            "required_substrings": ["intro P Q hPQ hP hQ"],
        },
        "case_17": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("intro P\nexact Classical.em P"),
            "required_substrings": ["Classical.em P"],
            "notes": "Semantically provable with classical reasoning, but benchmark expects failure.",
        },
        "case_18": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("intro P Q hP hnP\nexact False.elim (hnP hP)"),
            "required_substrings": ["False.elim (hnP hP)"],
            "notes": "Semantically provable by explosion, but benchmark expects failure.",
        },
        "case_19": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("refine Exists.intro 0 ?_\nomega"),
            "required_substrings": ["refine Exists.intro 0 ?_", "omega"],
        },
        "case_20": {
            "difficulty": "medium",
            "llm_response": _make_llm_response("intro a b\nrfl"),
            "required_substrings": ["intro a b", "rfl"],
        },
    }


def _expand_simple_case(raw_case: dict[str, Any]) -> BenchmarkCase:
    catalog = _simple_case_catalog()
    fixture = catalog[raw_case["id"]]
    expected_outcome = raw_case.get("expected_pipeline_outcome", raw_case.get("expected_outcome"))
    expected_success = expected_outcome == "success"
    theorem_name = raw_case["id"]
    theorem_statement = raw_case["statement"]
    theorem_line = f"theorem {theorem_name} : {theorem_statement} := by"

    expectation = BenchmarkExpectation(
        success=expected_success,
        required_substrings=[theorem_line, *fixture["required_substrings"]],
        forbidden_substrings=[] if not expected_success else ["sorry"],
        error=raw_case["rationale"],
    )

    return BenchmarkCase(
        case_id=raw_case["id"],
        category=raw_case["category"],
        difficulty=fixture["difficulty"],
        theorem_name=theorem_name,
        theorem_statement=theorem_statement,
        theorem_truth=raw_case.get("theorem_truth", "unknown"),
        llm_response=fixture["llm_response"],
        expectation=expectation,
        notes=fixture.get("notes", raw_case.get("rationale", "")),
    )


def load_cases(path: str | Path) -> list[BenchmarkCase]:
    """Load benchmark cases from a JSON file."""

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [_parse_case(case) for case in payload["cases"]]


def filter_cases(
    cases: Iterable[BenchmarkCase],
    *,
    case_ids: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    limit: int | None = None,
) -> list[BenchmarkCase]:
    """Filter cases by ids, categories, and optional limit."""

    selected = list(cases)
    id_set = {case_id for case_id in (case_ids or []) if case_id}
    category_set = {category for category in (categories or []) if category}

    if id_set:
        selected = [case for case in selected if case.case_id in id_set]
    if category_set:
        selected = [case for case in selected if case.category in category_set]
    if limit is not None:
        selected = selected[:limit]

    return selected


def inspect_live_environment(
    *,
    env: dict[str, str] | None = None,
    lean_api_url: str | None = None,
    llm_provider: str | None = None,
) -> dict[str, Any]:
    """Inspect whether live benchmark prerequisites are available."""

    env = env or dict(os.environ)
    chosen_provider = llm_provider or env.get("LLM_PROVIDER")
    if not chosen_provider:
        if env.get("ANTHROPIC_API_KEY"):
            chosen_provider = "anthropic"
        elif env.get("OPENAI_API_KEY"):
            chosen_provider = "openai"
        else:
            chosen_provider = "anthropic"

    lean_url = lean_api_url or env.get("LEAN_API_URL") or "http://localhost:5000"
    issues: list[str] = []

    if chosen_provider == "anthropic" and not env.get("ANTHROPIC_API_KEY"):
        issues.append("ANTHROPIC_API_KEY is not set for live mode.")
    if chosen_provider == "openai" and not env.get("OPENAI_API_KEY"):
        issues.append("OPENAI_API_KEY is not set for live mode.")

    return {
        "llm_provider": chosen_provider,
        "lean_api_url": lean_url,
        "issues": issues,
        "ready_for_client_init": not issues,
    }


def create_live_runtime(
    *,
    max_iterations: int = 5,
    timeout_seconds: float = 60.0,
    llm_provider: str | None = None,
    lean_api_url: str | None = None,
) -> tuple[Any, Any, AgentConfig]:
    """Create live benchmark dependencies from the current environment."""

    from src.lean_api import LeanAPIClient, LeanConfig
    from src.llm_module import LLMConfig, LLMFactory
    from src.main import detect_llm_provider

    status = inspect_live_environment(lean_api_url=lean_api_url, llm_provider=llm_provider)
    if status["issues"]:
        raise BenchmarkEnvironmentError(" ".join(status["issues"]))

    provider = llm_provider or detect_llm_provider()
    llm_config = LLMConfig()
    llm_client = LLMFactory(provider, config=llm_config)

    lean_config = LeanConfig(base_url=lean_api_url or status["lean_api_url"])
    lean_client = LeanAPIClient(lean_config)
    if not lean_client.health_check():
        raise BenchmarkEnvironmentError(
            f"Lean server is unavailable at {lean_config.base_url}. "
            "Set LEAN_API_URL to a healthy server before running live benchmarks."
        )

    agent_config = AgentConfig(
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
        stream_output=False,
        verbose=False,
    )
    return llm_client, lean_client, agent_config


def _run_case_with_runtime(
    case: BenchmarkCase,
    *,
    mode: str,
    llm_client: Any,
    verifier_api: Any,
    config: AgentConfig,
) -> BenchmarkResult:
    started_at = time.perf_counter()
    generator = ProofGenerator(llm_client)
    converter = ProofToLeanConverter()
    verifier = _CapturingVerifier(verifier_api)
    loop = VerificationLoop(
        proof_generator=generator,
        lean_converter=converter,
        verifier_api=verifier,
        config=config,
    )

    context = loop.verify(case.theorem_name, case.theorem_statement)
    duration_seconds = time.perf_counter() - started_at
    actual_success = context.state == ProofState.SUCCESS
    error = context.recent_errors[-1]["message"] if context.recent_errors else ""
    expectation_checks_passed = getattr(verifier_api, "expectation_checks_passed", True)

    return BenchmarkResult(
        case_id=case.case_id,
        category=case.category,
        difficulty=case.difficulty,
        theorem_name=case.theorem_name,
        theorem_statement=case.theorem_statement,
        theorem_truth=case.theorem_truth,
        expected_success=case.expectation.success,
        actual_success=actual_success,
        passed_expectation=actual_success == case.expectation.success and expectation_checks_passed,
        state=context.state.value,
        iterations=context.current_iteration,
        error=error,
        lean_code=verifier.last_code,
        duration_seconds=duration_seconds,
        notes=case.notes if mode == "fixture" else "",
    )


def _run_fixture_case(case: BenchmarkCase) -> BenchmarkResult:
    verifier = _ExpectationVerifier(case.expectation)
    return _run_case_with_runtime(
        case,
        mode="fixture",
        llm_client=_SingleResponseLLM(case.llm_response),
        verifier_api=verifier,
        config=AgentConfig(max_iterations=1, stream_output=False, verbose=False),
    )


def _build_category_breakdown(results: list[BenchmarkResult]) -> dict[str, dict[str, int]]:
    breakdown: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = breakdown.setdefault(
            result.category,
            {"total": 0, "matched_expectation": 0, "actual_success": 0},
        )
        bucket["total"] += 1
        bucket["matched_expectation"] += int(result.passed_expectation)
        bucket["actual_success"] += int(result.actual_success)
    return breakdown


def _build_truth_breakdown(results: list[BenchmarkResult]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for result in results:
        breakdown[result.theorem_truth] = breakdown.get(result.theorem_truth, 0) + 1
    return breakdown


def _build_summary(mode: str, results: list[BenchmarkResult]) -> FixtureBenchmarkSummary:
    passed_cases = sum(result.passed_expectation for result in results)
    actual_successes = sum(result.actual_success for result in results)
    expected_successes = sum(result.expected_success for result in results)

    return FixtureBenchmarkSummary(
        mode=mode,
        total_cases=len(results),
        passed_cases=passed_cases,
        failed_cases=len(results) - passed_cases,
        expected_successes=expected_successes,
        actual_successes=actual_successes,
        truth_breakdown=_build_truth_breakdown(results),
        median_duration_seconds=median(result.duration_seconds for result in results) if results else 0.0,
        category_breakdown=_build_category_breakdown(results),
        results=results,
    )


def run_fixture_benchmark(cases: list[BenchmarkCase]) -> FixtureBenchmarkSummary:
    """Run the fixture benchmark suite."""

    return _build_summary("fixture", [_run_fixture_case(case) for case in cases])


def run_live_benchmark(
    cases: list[BenchmarkCase],
    *,
    llm_client: Any,
    verifier_api: Any,
    config: AgentConfig,
) -> FixtureBenchmarkSummary:
    """Run a live benchmark suite against real clients."""

    results = [
        _run_case_with_runtime(
            case,
            mode="live",
            llm_client=llm_client,
            verifier_api=verifier_api,
            config=config,
        )
        for case in cases
    ]
    return _build_summary("live", results)


def run_benchmark(
    cases: list[BenchmarkCase],
    *,
    mode: str = "fixture",
    llm_client: Any | None = None,
    verifier_api: Any | None = None,
    config: AgentConfig | None = None,
) -> FixtureBenchmarkSummary:
    """Run benchmark cases in fixture or live mode."""

    if mode == "fixture":
        return run_fixture_benchmark(cases)

    if mode != "live":
        raise ValueError(f"Unsupported benchmark mode: {mode}")

    if llm_client is None or verifier_api is None or config is None:
        raise ValueError("live mode requires llm_client, verifier_api, and config")

    return run_live_benchmark(
        cases,
        llm_client=llm_client,
        verifier_api=verifier_api,
        config=config,
    )


def summary_to_dict(summary: FixtureBenchmarkSummary) -> dict[str, Any]:
    """Convert a summary to a JSON-serializable dict."""

    return {
        "mode": summary.mode,
        "total_cases": summary.total_cases,
        "passed_cases": summary.passed_cases,
        "failed_cases": summary.failed_cases,
        "expected_successes": summary.expected_successes,
        "actual_successes": summary.actual_successes,
        "truth_breakdown": summary.truth_breakdown,
        "median_duration_seconds": summary.median_duration_seconds,
        "category_breakdown": summary.category_breakdown,
        "results": [asdict(result) for result in summary.results],
    }


def render_markdown_report(summary: FixtureBenchmarkSummary) -> str:
    """Render a compact Markdown report."""

    lines = [
        "# Fixture Benchmark Report" if summary.mode == "fixture" else "# Live Benchmark Report",
        "",
        f"- Mode: {summary.mode}",
        f"- Total cases: {summary.total_cases}",
        f"- Matched expectation: {summary.passed_cases}",
        f"- Mismatched expectation: {summary.failed_cases}",
        f"- Expected successes: {summary.expected_successes}",
        f"- Actual successes: {summary.actual_successes}",
        f"- Truth breakdown: {summary.truth_breakdown}",
        f"- Median latency: {summary.median_duration_seconds:.4f}s",
        "",
        "## By Category",
        "",
        "| Category | Total | Matched | Actual Success |",
        "| --- | ---: | ---: | ---: |",
    ]

    for category, counts in sorted(summary.category_breakdown.items()):
        lines.append(
            f"| {category} | {counts['total']} | {counts['matched_expectation']} | {counts['actual_success']} |"
        )

    lines.extend(
        [
            "",
            "## Case Results",
            "",
            "| Case | Category | Difficulty | Theorem Truth | Expected Pipeline | Actual | Match | Notes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for result in summary.results:
        lines.append(
            "| {case} | {category} | {difficulty} | {truth} | {expected} | {actual} | {match} | {notes} |".format(
                case=result.case_id,
                category=result.category,
                difficulty=result.difficulty,
                truth=result.theorem_truth,
                expected="pass" if result.expected_success else "fail",
                actual="pass" if result.actual_success else "fail",
                match="yes" if result.passed_expectation else "no",
                notes=result.notes or "-",
            )
        )

    return "\n".join(lines) + "\n"
