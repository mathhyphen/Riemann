# Benchmark Fixtures

This directory contains a fixed 20-case benchmark fixture set for Riemann.

The cases are balanced across:
- Arithmetic identities
- Basic propositions and quantifiers
- Conjunction and implication reasoning
- Deliberately false or underpowered statements
- Import-sensitive statements that should fail without extra context

Use `benchmark_cases.json` as the canonical fixture source. Each entry includes:
- `statement`: the theorem to evaluate
- `expected_outcome`: `success` or `failure`
- `rationale`: a short reason for the expected outcome

The intent is to keep these cases stable so future runs can compare behavior over time.

Important caveat:

- In fixture mode, `expected_outcome` means the expected pipeline result for this benchmark, not necessarily the theorem's absolute truth value under a real Lean checker.
- `case_17` and `case_18` are intentionally useful examples of this distinction: they are reasonable "current pipeline may fail" cases, but they are not mathematical impossibilities in Lean.
