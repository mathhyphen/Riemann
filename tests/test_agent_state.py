from __future__ import annotations

from dataclasses import FrozenInstanceError

from tests.conftest import load_module_from_source


def test_agent_context_tracks_latest_attempt_and_iteration_count() -> None:
    state = load_module_from_source(
        "riemann_test_agent_state",
        "src/agent/state.py",
        replacements={"if self proof_attempts:": "if self.proof_attempts:"},
    )

    config = state.AgentConfig(max_iterations=2)
    context = state.AgentContext(
        theorem_name="demo_theorem",
        theorem_statement="forall n : Nat, n + 0 = n",
        config=config,
    )

    assert context.current_proof_attempt is None
    assert context.total_attempts == 0
    assert context.can_continue is True

    attempt = state.ProofAttempt(
        attempt_number=1,
        proof_idea="Use induction on n",
        lean_code="by\n  induction n with\n  | zero => rfl\n  | succ n ih => simp [ih]",
    )
    context.add_proof_attempt(attempt)

    assert context.current_proof_attempt is attempt
    assert context.total_attempts == 1
    assert context.current_iteration == 1

    context.update_state(state.ProofState.SUCCESS)
    assert context.can_continue is False


def test_agent_config_remains_immutable() -> None:
    state = load_module_from_source(
        "riemann_test_agent_state_immutable",
        "src/agent/state.py",
        replacements={"if self proof_attempts:": "if self.proof_attempts:"},
    )

    config = state.AgentConfig(max_iterations=4)

    try:
        config.max_iterations = 10  # type: ignore[misc]
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("AgentConfig should be frozen")
