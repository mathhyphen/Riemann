from src.agent.proof_generator import ProofGenerator
from src.agent.proof_to_lean import ProofToLeanConverter
from src.agent.state import AgentConfig, AgentContext, ErrorCategory, ProofAttempt
from src.agent.verification_loop import VerificationLoop
from src.lean_api import LeanRequest, VerificationResult, VerificationStatus
from src.main import create_parser, detect_llm_provider


class FakeLLMClient:
    def generate(self, **kwargs):
        return type("Response", (), {"content": "### Lean Code\n```lean\nrfl\n```"})()


class FakeVerifier:
    def __init__(self, result: VerificationResult):
        self.result = result
        self.last_request = None

    def verify(self, request: LeanRequest) -> VerificationResult:
        self.last_request = request
        return self.result


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


def test_detect_llm_provider_prefers_available_keys(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    assert detect_llm_provider() == "openai"


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
