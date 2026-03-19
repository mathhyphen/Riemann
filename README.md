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

## Usage

```bash
python -m src.main --version
python -m src.main "forall n : Nat, n + 0 = n"
python -m src.main
```

## Notes

- A working Lean verification server is required for end-to-end proof checking.
- If `LLM_PROVIDER` is not set, the app auto-detects `anthropic` or `openai` from
  available API keys.
