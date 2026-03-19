from __future__ import annotations

from tests.conftest import load_module_from_source


def test_build_lean_imports_prompt_renders_expected_template() -> None:
    prompt_builder = load_module_from_source(
        "riemann_test_prompt_builder",
        "src/llm_module/prompt_builder.py",
        replacements={
            "import Mathlib.{library_name}": "import Mathlib.{{library_name}}",
            "import Std.{library_name}": "import Std.{{library_name}}",
        },
    )

    builder = prompt_builder.ProofPromptBuilder()
    system_prompt, user_prompt = builder.build_lean_imports_prompt(
        theorem_name="add_zero",
        theorem_statement="forall n : Nat, n + 0 = n",
    )

    assert "Lean 4 expert" in system_prompt
    assert "add_zero" in user_prompt
    assert "forall n : Nat, n + 0 = n" in user_prompt
    assert "### Imports" in user_prompt
    assert "import Mathlib.{library_name}" in user_prompt
    assert "import Std.{library_name}" in user_prompt
