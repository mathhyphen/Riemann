# 20-Problem Benchmark Report

## Run Metadata

- Run mode: `fixture`
- Date: `2026-03-20 01:05:18 +08:00`
- Branch: `codex/fixture-benchmark-20`
- Base commit before benchmark changes: `7331e8d`
- Runner: `scripts/run_fixture_benchmark.py`
- Raw results:
  - `reports/20_problem_fixture_results.json`
  - `reports/20_problem_fixture_results.md`
- Notes: run executed in fixture mode because no LLM key, no Lean HTTP verifier, and no local `lean` executable were available.

## Executive Summary

- Problems run: `20`
- Matched expectation: `20`
- Mismatched expectation: `0`
- Expected successes: `10`
- Actual successes: `10`
- Theorem truth breakdown: `11 true`, `8 false`, `1 classically_true`
- Median latency: `0.0002s`

## Per-Category Summary

| Category | Total | Matched | Actual Success | Notes |
| --- | ---: | ---: | ---: | --- |
| `nat_identity` | 5 | 5 | 5 | Simple algebraic identities behaved as expected. |
| `nat_rewrite` | 1 | 1 | 1 | Associativity now sits in its own rewrite bucket instead of being mislabeled as an identity law. |
| `logic_basic` | 4 | 4 | 4 | Basic intro/exact/constructor patterns converted cleanly. |
| `false_statement` | 6 | 6 | 0 | Fixture verifier correctly rejected obviously false universal claims. |
| `logic_false` | 1 | 1 | 0 | The genuinely false implication case stays negative as expected. |
| `logic_caveat` | 2 | 2 | 0 | These are deliberate pipeline negatives, not theorem-truth negatives. |
| `existential_false` | 1 | 1 | 0 | Impossible existential stayed negative as expected. |

## Key Findings

1. The current pipeline is stable on a balanced 20-case offline benchmark once the theorem wrapper and raw-tactic conversion path are fixed.
2. The repo still does not support real end-to-end theorem evaluation in this environment because there is no LLM API key, no Lean HTTP verifier, and no local `lean` executable.
3. `case_17` and `case_18` are now explicitly modeled as theorem-truth caveats, so the benchmark no longer conflates "pipeline should currently fail" with "the theorem is false."

## Follow-Up

- Add a live benchmark mode that consumes real `LEAN_API_URL` and provider credentials when available.
- Keep `expected_pipeline_outcome` and `theorem_truth` separate going forward so semantically provable negatives remain explicit.
- Consider adding case filtering and JSONL output for easier multi-agent parallel runs.
