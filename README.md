# Riemann

Riemann is a CLI proof assistant that uses an LLM to generate Lean proofs and a Lean
verification service to check them.

## What It Does

1. Accept a theorem statement from the user.
2. Ask an LLM to propose a proof.
3. Convert the response into Lean code.
4. Send the Lean code to a verification service.
5. Retry with error context until the proof succeeds or the iteration limit is reached.

## Project Layout

```text
src/
  agent/        Verification loop and proof generation
  cli/          Rich-based terminal interface
  lean_api/     HTTP client and models for Lean verification
  llm_module/   LLM client abstractions and provider implementations
  main.py       Application entry point
```

## Setup

```bash
pip install -e .[dev]
```

Create a `.env` file or export environment variables:

```bash
ANTHROPIC_API_KEY=...
# or
OPENAI_API_KEY=...

LEAN_API_URL=http://localhost:5000
LLM_PROVIDER=anthropic
```

For MiniMax Token Plan, use the native MiniMax environment names:

```bash
MINIMAX_API_KEY=...
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
LLM_PROVIDER=minimax
LLM_MODEL=MiniMax-M2.7-highspeed
LEAN_API_URL=http://localhost:5000
```

If you want to verify locally without running an HTTP verifier service, use:

```bash
LEAN_BACKEND=local
LEAN_PATH=lean
LEAN_PROJECT_ROOT=.lean_verifier
```

If `lean` is already on your `PATH`, you can omit `LEAN_PATH`. `LEAN_PROJECT_ROOT` should point at a Lean project directory that has `Mathlib` available.

## Usage

```bash
python -m src.main --version
python -m src.main "forall n : Nat, n + 0 = n"
python -m src.main
```

## Benchmark

Run the offline 20-problem benchmark with:

```bash
python scripts/run_benchmark.py --mode fixture --workers 4
```

This writes:

- `reports/20_problem_fixture_results.json`
- `reports/20_problem_fixture_results.md`
- `reports/20_problem_fixture_report.md`
- `reports/20_problem_benchmark_report.md`

The fixture benchmark validates the proof-generation pipeline shape and regression behavior without requiring an API key or a live Lean server.

When you have a real verifier and provider credentials available, you can run live mode:

```bash
python scripts/run_benchmark.py --mode live --workers 4 --category logic_basic --jsonl-output reports/live_logic_basic.jsonl
```

Useful flags:

- `--category <name>` to run one or more categories
- `--case-id <id>` to run specific cases
- `--limit <n>` to trim the filtered set
- `--workers <n>` to parallelize case execution
- `--jsonl-output <path>` for one-result-per-line output
- `--report-output <path>` for a richer Markdown summary
- `--benchmark-report-output <path>` for the unified formal benchmark report

## Notes

- A working Lean verification server is required for end-to-end proof checking.
- If `LLM_PROVIDER` is not set, the app auto-detects `anthropic` or `openai` from
  available API keys.
