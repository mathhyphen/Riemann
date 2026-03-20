# Fixture Benchmark Report

- Total cases: 20
- Matched expectation: 20
- Mismatched expectation: 0
- Expected successes: 10
- Actual successes: 10
- Truth breakdown: {'true': 11, 'false': 8, 'classically_true': 1}
- Median latency: 0.0001s

## By Category

| Category | Total | Matched | Actual Success |
| --- | ---: | ---: | ---: |
| existential_false | 1 | 1 | 0 |
| false_statement | 6 | 6 | 0 |
| logic_basic | 4 | 4 | 4 |
| logic_caveat | 2 | 2 | 0 |
| logic_false | 1 | 1 | 0 |
| nat_identity | 5 | 5 | 5 |
| nat_rewrite | 1 | 1 | 1 |

## Case Results

| Case | Category | Difficulty | Theorem Truth | Expected Pipeline | Actual | Match | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| case_01 | nat_identity | easy | true | pass | pass | yes | Canonical right-identity of addition on naturals. |
| case_02 | nat_identity | easy | true | pass | pass | yes | Canonical left-identity of addition on naturals. |
| case_03 | nat_identity | easy | true | pass | pass | yes | Simple multiplicative identity. |
| case_04 | nat_identity | easy | true | pass | pass | yes | Simple multiplicative identity on the left. |
| case_05 | nat_identity | easy | true | pass | pass | yes | Standard subtraction simplification on naturals. |
| case_06 | nat_rewrite | easy | true | pass | pass | yes | Associativity is a basic algebraic rewrite. |
| case_07 | logic_basic | easy | true | pass | pass | yes | Direct implication introduction and reuse. |
| case_08 | logic_basic | easy | true | pass | pass | yes | Straightforward conjunction construction. |
| case_09 | logic_basic | easy | true | pass | pass | yes | Commutativity of conjunction by unpacking assumptions. |
| case_10 | logic_basic | easy | true | pass | pass | yes | Immediate disjunction introduction. |
| case_11 | false_statement | medium | false | fail | fail | yes | False for all naturals except no cases; impossible as stated. |
| case_12 | false_statement | medium | false | fail | fail | yes | Strict inequality is irreflexive on naturals. |
| case_13 | false_statement | medium | false | fail | fail | yes | Only true for zero, so the universal claim is false. |
| case_14 | false_statement | medium | false | fail | fail | yes | Fails whenever b is nonzero. |
| case_15 | false_statement | medium | false | fail | fail | yes | Fails for positive inputs such as a = 1 and b = 1. |
| case_16 | logic_false | medium | false | fail | fail | yes | Contradicts the assumption that P implies Q. |
| case_17 | logic_caveat | medium | classically_true | fail | fail | yes | Semantically provable with classical reasoning, but benchmark expects failure. |
| case_18 | logic_caveat | medium | true | fail | fail | yes | Semantically provable by explosion, but benchmark expects failure. |
| case_19 | existential_false | medium | false | fail | fail | yes | No natural number satisfies this equality. |
| case_20 | false_statement | medium | false | fail | fail | yes | The universal equality is false because distinct naturals need not be equal. |
