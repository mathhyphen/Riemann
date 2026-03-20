# Benchmark Summary

- Mode: fixture
- Total cases: 20
- Matched expectation: 20
- Mismatched expectation: 0
- Actual successes: 10
- Truth breakdown: {'true': 11, 'false': 8, 'classically_true': 1}
- Diagnostic breakdown: {'success': 10, 'expected_negative_case': 8, 'pipeline_caveat': 2}

## Key Findings

1. All cases matched the benchmark expectation.
2. The dominant non-success diagnostic bucket was `expected_negative_case`.
3. The suite covered 7 categories with median latency 0.0004s.

## Failure Diagnostics

| Diagnostic | Count |
| --- | ---: |
| expected_negative_case | 8 |
| pipeline_caveat | 2 |
| success | 10 |

## Cases Requiring Attention

| Case | Category | State | Error |
| --- | --- | --- | --- |
| case_11 | false_statement | max_iterations | False for all naturals except no cases; impossible as stated. |
| case_12 | false_statement | max_iterations | Strict inequality is irreflexive on naturals. |
| case_13 | false_statement | max_iterations | Only true for zero, so the universal claim is false. |
| case_14 | false_statement | max_iterations | Fails whenever b is nonzero. |
| case_15 | false_statement | max_iterations | Fails for positive inputs such as a = 1 and b = 1. |
| case_16 | logic_false | max_iterations | Contradicts the assumption that P implies Q. |
| case_17 | logic_caveat | max_iterations | Useful expected pipeline failure without explicit classical handling. |
| case_18 | logic_caveat | max_iterations | Useful expected pipeline failure even though the theorem is provable by explosion. |
| case_19 | existential_false | max_iterations | No natural number satisfies this equality. |
| case_20 | false_statement | max_iterations | The universal equality is false because distinct naturals need not be equal. |
