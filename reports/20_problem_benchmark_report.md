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
- Median latency: `0.0001s`

## Per-Category Summary

| Category | Total | Matched | Actual Success | Notes |
| --- | ---: | ---: | ---: | --- |
| `nat_identity` | 6 | 6 | 6 | Simple algebraic rewrites and identities behaved as expected. |
| `logic_basic` | 4 | 4 | 4 | Basic intro/exact/constructor patterns converted cleanly. |
| `false_statement` | 6 | 6 | 0 | Fixture verifier correctly rejected obviously false universal claims. |
| `logic_false` | 3 | 3 | 0 | Two cases are benchmark-design caveats rather than theorem impossibilities. |
| `existential_false` | 1 | 1 | 0 | Impossible existential stayed negative as expected. |

## Key Findings

1. The current pipeline is stable on a balanced 20-case offline benchmark once the theorem wrapper and raw-tactic conversion path are fixed.
2. The repo still does not support real end-to-end theorem evaluation in this environment because there is no LLM API key, no Lean HTTP verifier, and no local `lean` executable.
3. `case_17` and `case_18` are useful as "likely current-agent failures", but they are not mathematical impossibilities, so this fixture suite should be treated as a repeatable pipeline benchmark, not as theorem-truth ground truth.

## Follow-Up

- Add a live benchmark mode that consumes real `LEAN_API_URL` and provider credentials when available.
- Consider splitting fixture labels into `expected_pipeline_outcome` and `theorem_truth` so semantically provable negatives are explicit.
- Consider adding case filtering and JSONL output for easier multi-agent parallel runs.
