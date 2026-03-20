from src.agent.proof_generator import ProofGenerator
from src.agent.proof_explainer import ProofExplainer
from src.agent.mathlib_retriever import MathlibRetriever, MathlibTheoremHit
from src.agent.proof_to_lean import ProofToLeanConverter
from src.agent.state import AgentConfig, AgentContext, ErrorCategory, ProofAttempt
from src.agent.verification_loop import VerificationLoop
from src.lean_api import LeanRequest, VerificationResult, VerificationStatus
from src.llm_module import AnthropicClient
from src.llm_module.client import resolve_llm_config
from src.main import create_parser, detect_llm_provider


class FakeLLMClient:
    def generate(self, **kwargs):
        return type("Response", (), {"content": "### Lean Code\n```lean\nrfl\n```"})()


class FakeExplainingLLMClient:
    def generate(self, **kwargs):
        prompt = kwargs.get("prompt", "")
        if "Please explain the above Lean proof" in prompt:
            return type("Response", (), {"content": "Proof explanation"})()
        return type(
            "Response",
            (),
            {
                "content": (
                    "### Proof Strategy\nUse the standard library theorem.\n"
                    "### Lean Code\n```lean\n"
                    "theorem t (a b : Nat) : a + b = b + a :=\n"
                    "  Nat.add_comm a b\n"
                    "```\n"
                    "### Explanation\nDirect reuse."
                )
            },
        )()


class FakeVerifier:
    def __init__(self, result: VerificationResult):
        self.result = result
        self.last_request = None

    def verify(self, request: LeanRequest) -> VerificationResult:
        self.last_request = request
        return self.result


class FakeLocalVerifier:
    def verify_proof(self, code: str, timeout=None):
        del code, timeout
        return type("LocalResult", (), {"success": True, "message": "ok", "errors": []})()


class CapturingLocalVerifier:
    def __init__(self):
        self.code = ""

    def verify_proof(self, code: str, timeout=None):
        del timeout
        self.code = code
        return type("LocalResult", (), {"success": True, "message": "ok", "errors": []})()


class FakeMathlibRetriever:
    def search(self, theorem_name: str, theorem_statement: str, limit: int = 3):
        del theorem_name, theorem_statement, limit
        return [
            MathlibTheoremHit(
                name="add_comm",
                signature="theorem add_comm : a + b = b + a",
                source_path="Mathlib/Test.lean",
                line_number=1,
                score=42,
            )
        ]

    def get_proof_content(self, source_path: str, line_number: int) -> str:
        del source_path, line_number
        raise AssertionError("alias proof should be used before raw proof extraction")


def test_agent_context_returns_latest_attempt() -> None:
    context = AgentContext(
        theorem_name="t",
        theorem_statement="True",
        config=AgentConfig(),
    )
    assert context.current_proof_attempt is None

    attempt = ProofAttempt(
        attempt_number=1,
        proof_idea="idea",
        lean_code="trivial",
        error_category=ErrorCategory.UNKNOWN,
    )
    context.add_proof_attempt(attempt)

    assert context.current_proof_attempt == attempt


def test_verification_loop_uses_lean_request() -> None:
    generator = ProofGenerator(FakeLLMClient())
    converter = ProofToLeanConverter()
    verifier = FakeVerifier(
        VerificationResult(
            status=VerificationStatus.SUCCESS,
            message="ok",
        )
    )
    loop = VerificationLoop(generator, converter, verifier, AgentConfig(max_iterations=1))

    context = loop.verify("t", "True")

    assert context.state.value == "success"
    assert verifier.last_request is not None
    assert "theorem t" in verifier.last_request.code


def test_verification_loop_accepts_local_verify_proof_result() -> None:
    generator = ProofGenerator(FakeLLMClient())
    converter = ProofToLeanConverter()
    loop = VerificationLoop(generator, converter, FakeLocalVerifier(), AgentConfig(max_iterations=1))

    context = loop.verify("t", "True")

    assert context.state.value == "success"


def test_detect_llm_provider_prefers_available_keys(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    assert detect_llm_provider() == "openai"


def test_detect_llm_provider_prefers_minimax_key(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert detect_llm_provider() == "minimax"


def test_resolve_llm_config_reads_minimax_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "MiniMax-M2.7-highspeed")
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic")
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.2")
    monkeypatch.setenv("LLM_MAX_TOKENS", "2048")

    config = resolve_llm_config("minimax")

    assert config.model == "MiniMax-M2.7-highspeed"
    assert config.api_endpoint == "https://api.minimaxi.com/anthropic"
    assert config.api_key == "test-key"
    assert config.temperature == 0.2
    assert config.max_tokens == 2048


def test_anthropic_client_extracts_text_from_mixed_blocks() -> None:
    client = object.__new__(AnthropicClient)
    response = type(
        "Response",
        (),
        {
            "content": [
                type("ThinkingBlock", (), {"thinking": "internal"})(),
                type("TextBlock", (), {"text": "final answer"})(),
            ]
        },
    )()

    assert client._extract_text_content(response) == "final answer"


def test_arg_parser_supports_version_flag() -> None:
    parser = create_parser()
    args = parser.parse_args(["--version"])

    assert args.version is True


def test_lean_request_rejects_empty_code() -> None:
    try:
        LeanRequest(code="   ")
    except ValueError as exc:
        assert "Code cannot be empty" in str(exc)
    else:
        raise AssertionError("Expected LeanRequest to reject empty code")


def test_converter_strips_outer_theorem_wrapper() -> None:
    converter = ProofToLeanConverter()

    converted = converter.convert(
        "```lean\ntheorem sample (n : Nat) : n + 0 = n := by\n  simpa using Nat.add_zero n\n```",
        "sample",
        "forall n : Nat, n + 0 = n",
    )

    assert converted.count("theorem sample") == 1
    assert "simpa using Nat.add_zero n" in converted


def test_converter_preserves_term_style_theorem_declarations() -> None:
    converter = ProofToLeanConverter()

    converted = converter.convert(
        "```lean\nimport Mathlib\n\ntheorem comm_test (a b : Nat) : a + b = b + a :=\n  Nat.add_comm a b\n```",
        "comm_test",
        "forall a b : Nat, a + b = b + a",
    )

    assert converted.count("import Mathlib") == 1
    assert converted.count("theorem comm_test") == 1
    assert "Nat.add_comm a b" in converted
    assert "forall a b : Nat" not in converted


def test_verification_loop_records_successful_attempt_for_explanation() -> None:
    loop = VerificationLoop(
        ProofGenerator(FakeExplainingLLMClient()),
        ProofToLeanConverter(),
        FakeLocalVerifier(),
        AgentConfig(max_iterations=1),
        proof_explainer=ProofExplainer(FakeExplainingLLMClient()),
    )

    context = loop.verify("t", "forall a b : Nat, a + b = b + a")
    explanation = loop.generate_explanation(context, language="en")

    assert context.state.value == "success"
    assert context.current_iteration == 1
    assert context.proof_attempts[-1].was_successful is True
    assert explanation == "Proof explanation"


def test_mathlib_retriever_prefers_add_comm_for_addition_commutativity() -> None:
    retriever = MathlibRetriever(mathlib_root=".")
    retriever._index = [
        MathlibTheoremHit(
            name="mul_comm",
            signature="theorem mul_comm : a * b = b * a",
            source_path="mul.lean",
            line_number=1,
            score=0,
        ),
        MathlibTheoremHit(
            name="add_comm",
            signature="theorem add_comm : a + b = b + a",
            source_path="add.lean",
            line_number=1,
            score=0,
        ),
    ]

    hits = retriever.search(
        theorem_name="user_theorem",
        theorem_statement="forall a b : Nat, a + b = b + a",
        limit=2,
    )

    assert [hit.name for hit in hits] == ["add_comm"]


def test_verification_loop_reuses_mathlib_theorem_with_adapter_proof() -> None:
    verifier = CapturingLocalVerifier()
    loop = VerificationLoop(
        ProofGenerator(FakeLLMClient()),
        ProofToLeanConverter(),
        verifier,
        AgentConfig(max_iterations=1),
        mathlib_retriever=FakeMathlibRetriever(),
    )

    context = loop.verify("user_theorem", "forall a b : Nat, a + b = b + a")

    assert context.state.value == "success"
    assert "simpa using add_comm a b" in verifier.code
