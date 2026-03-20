# 20-Problem Benchmark Report

## Run Metadata

- Run mode: `fixture`
- Generated at: `2026-03-20 10:29:26 +0800`
- Runner: `scripts/run_benchmark.py`
- Case source: `benchmarks/benchmark_cases.json`
- Worker count: `4`
- Git branch: `codex/fixture-benchmark-20`
- Git commit: `5a4dd0b`
- Selected categories: `all`
- Selected case ids: `all`
- Limit: `none`
- Notes: `fixture mode validates pipeline behavior without live dependencies.`

## Output Artifacts

- JSON results: `reports\20_problem_fixture_results.json`
- Markdown results: `reports\20_problem_fixture_results.md`
- Detailed report: `reports\20_problem_fixture_report.md`

## Executive Summary

- Problems run: `20`
- Matched expectation: `20`
- Mismatched expectation: `0`
- Expected successes: `10`
- Actual successes: `10`
- Cases needing attention: `10`
- Pipeline caveat cases: `2`
- Theorem truth breakdown: `{'true': 11, 'false': 8, 'classically_true': 1}`
- Diagnostic breakdown: `{'success': 10, 'expected_negative_case': 8, 'pipeline_caveat': 2}`
- Median latency: `0.0003s`

## Per-Category Summary

| Category | Total | Matched | Actual Success |
| --- | ---: | ---: | ---: |
| existential_false | 1 | 1 | 0 |
| false_statement | 6 | 6 | 0 |
| logic_basic | 4 | 4 | 4 |
| logic_caveat | 2 | 2 | 0 |
| logic_false | 1 | 1 | 0 |
| nat_identity | 5 | 5 | 5 |
| nat_rewrite | 1 | 1 | 1 |

## Diagnostic Summary

| Diagnostic | Count |
| --- | ---: |
| expected_negative_case | 8 |
| pipeline_caveat | 2 |
| success | 10 |

## Cases Requiring Attention

| Case | Category | Theorem Truth | Diagnostic | State | Error |
| --- | --- | --- | --- | --- | --- |
| case_11 | false_statement | false | expected_negative_case | max_iterations | False for all naturals except no cases; impossible as stated. |
| case_12 | false_statement | false | expected_negative_case | max_iterations | Strict inequality is irreflexive on naturals. |
| case_13 | false_statement | false | expected_negative_case | max_iterations | Only true for zero, so the universal claim is false. |
| case_14 | false_statement | false | expected_negative_case | max_iterations | Fails whenever b is nonzero. |
| case_15 | false_statement | false | expected_negative_case | max_iterations | Fails for positive inputs such as a = 1 and b = 1. |
| case_16 | logic_false | false | expected_negative_case | max_iterations | Contradicts the assumption that P implies Q. |
| case_17 | logic_caveat | classically_true | pipeline_caveat | max_iterations | Useful expected pipeline failure without explicit classical handling. |
| case_18 | logic_caveat | true | pipeline_caveat | max_iterations | Useful expected pipeline failure even though the theorem is provable by explosion. |
| case_19 | existential_false | false | expected_negative_case | max_iterations | No natural number satisfies this equality. |
| case_20 | false_statement | false | expected_negative_case | max_iterations | The universal equality is false because distinct naturals need not be equal. |

## Pipeline Caveats

| Case | Theorem Truth | Notes |
| --- | --- | --- |
| case_17 | classically_true | Semantically provable with classical reasoning, but benchmark expects failure. |
| case_18 | true | Semantically provable by explosion, but benchmark expects failure. |

## Case Results

| Case | Category | Difficulty | Expected Pipeline | Actual | Match |
| --- | --- | --- | --- | --- | --- |
| case_01 | nat_identity | easy | pass | pass | yes |
| case_02 | nat_identity | easy | pass | pass | yes |
| case_03 | nat_identity | easy | pass | pass | yes |
| case_04 | nat_identity | easy | pass | pass | yes |
| case_05 | nat_identity | easy | pass | pass | yes |
| case_06 | nat_rewrite | easy | pass | pass | yes |
| case_07 | logic_basic | easy | pass | pass | yes |
| case_08 | logic_basic | easy | pass | pass | yes |
| case_09 | logic_basic | easy | pass | pass | yes |
| case_10 | logic_basic | easy | pass | pass | yes |
| case_11 | false_statement | medium | fail | fail | yes |
| case_12 | false_statement | medium | fail | fail | yes |
| case_13 | false_statement | medium | fail | fail | yes |
| case_14 | false_statement | medium | fail | fail | yes |
| case_15 | false_statement | medium | fail | fail | yes |
| case_16 | logic_false | medium | fail | fail | yes |
| case_17 | logic_caveat | medium | fail | fail | yes |
| case_18 | logic_caveat | medium | fail | fail | yes |
| case_19 | existential_false | medium | fail | fail | yes |
| case_20 | false_statement | medium | fail | fail | yes |

## Recommendations

1. Keep theorem truth and expected pipeline outcome separate when interpreting caveat cases.
2. Follow up with a live run against a real Lean verifier before claiming end-to-end proof capability.
