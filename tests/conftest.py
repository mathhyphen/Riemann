"""Shared test helpers for loading source modules with lightweight stubs."""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, Mapping, MutableMapping

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def temporary_sys_modules(stubs: Mapping[str, types.ModuleType]) -> Iterator[None]:
    """Temporarily inject modules into ``sys.modules``."""
    previous: Dict[str, types.ModuleType | None] = {}
    try:
        for name, module in stubs.items():
            previous[name] = sys.modules.get(name)
            sys.modules[name] = module
        yield
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def make_module(name: str, **attrs) -> types.ModuleType:
    """Create a lightweight module object for test doubles."""
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def load_module_from_source(
    module_name: str,
    relative_path: str,
    *,
    replacements: MutableMapping[str, str] | None = None,
    stubs: Mapping[str, types.ModuleType] | None = None,
) -> types.ModuleType:
    """Load a module from source text with optional in-memory patches."""
    path = ROOT / relative_path
    source = path.read_text(encoding="utf-8")
    for old, new in (replacements or {}).items():
        source = source.replace(old, new)

    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = module_name.rpartition(".")[0]

    modules_to_stub = dict(stubs or {})
    with temporary_sys_modules(modules_to_stub):
        sys.modules[module_name] = module
        try:
            exec(compile(source, str(path), "exec"), module.__dict__)
        finally:
            sys.modules.pop(module_name, None)

    return module


def build_main_stubs() -> Dict[str, types.ModuleType]:
    """Build the minimum module tree required to load ``src/main.py``."""
    src_pkg = make_module("src")
    src_pkg.__path__ = []  # type: ignore[attr-defined]

    agent_pkg = make_module("src.agent")
    agent_pkg.__path__ = []  # type: ignore[attr-defined]

    cli_pkg = make_module("src.cli", RiemannCLI=type("RiemannCLI", (), {}))
    llm_pkg = make_module(
        "src.llm_module",
        LLMFactory=lambda *args, **kwargs: None,
        LLMConfig=type("LLMConfig", (), {}),
    )
    lean_pkg = make_module(
        "src.lean_api",
        LeanAPIClient=type("LeanAPIClient", (), {}),
        LeanConfig=type("LeanConfig", (), {}),
    )
    proof_generator_pkg = make_module(
        "src.agent.proof_generator",
        ProofGenerator=type("ProofGenerator", (), {}),
    )
    proof_to_lean_pkg = make_module(
        "src.agent.proof_to_lean",
        ProofToLeanConverter=type("ProofToLeanConverter", (), {}),
    )
    verification_loop_pkg = make_module(
        "src.agent.verification_loop",
        VerificationLoop=type("VerificationLoop", (), {}),
    )
    state_pkg = make_module(
        "src.agent.state",
        AgentConfig=type("AgentConfig", (), {}),
    )

    return {
        "src": src_pkg,
        "src.agent": agent_pkg,
        "src.cli": cli_pkg,
        "src.llm_module": llm_pkg,
        "src.lean_api": lean_pkg,
        "src.agent.proof_generator": proof_generator_pkg,
        "src.agent.proof_to_lean": proof_to_lean_pkg,
        "src.agent.verification_loop": verification_loop_pkg,
        "src.agent.state": state_pkg,
    }
