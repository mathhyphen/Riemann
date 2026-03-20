"""Compatibility wrapper for the fixture benchmark entrypoint."""

from __future__ import annotations

def main() -> int:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from run_benchmark import main as run_benchmark_main

    sys.argv = [sys.argv[0], "--mode", "fixture", *sys.argv[1:]]
    return run_benchmark_main()


if __name__ == "__main__":
    raise SystemExit(main())
