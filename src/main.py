"""Main entry point for Riemann proof assistant CLI.

This module provides:
- Command-line argument parsing
- Main application loop
- Graceful shutdown handling
"""

import argparse
import logging
import os
import re
import sys
import time
from typing import Any, Optional

from dotenv import load_dotenv
from rich.console import Console

try:
    from .agent.mathlib_retriever import MathlibRetriever
    from .agent.proof_explainer import ProofExplainer
    from .agent.proof_generator import ProofGenerator
    from .agent.proof_to_lean import ProofToLeanConverter
    from .agent.state import AgentConfig, LeanDiagnostic, TheoremPlan
    from .agent.verification_loop import VerificationLoop
    from .agent.workbench import ResearchWorkbench
    from .cli import RiemannCLI
    from .lean_api import LeanAPIClient, LeanConfig
    from .lean_module import LeanFactory
    from .llm_module import LLMFactory, resolve_llm_config
except ImportError:  # pragma: no cover - script execution fallback
    from src.agent.mathlib_retriever import MathlibRetriever
    from src.agent.proof_explainer import ProofExplainer
    from src.agent.proof_generator import ProofGenerator
    from src.agent.proof_to_lean import ProofToLeanConverter
    from src.agent.state import AgentConfig, LeanDiagnostic, TheoremPlan
    from src.agent.verification_loop import VerificationLoop
    from src.agent.workbench import ResearchWorkbench
    from src.cli import RiemannCLI
    from src.lean_api import LeanAPIClient, LeanConfig
    from src.lean_module import LeanFactory
    from src.llm_module import LLMFactory, resolve_llm_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def detect_llm_provider() -> str:
    """Select an LLM provider based on explicit config or available API keys."""
    provider = os.environ.get("LLM_PROVIDER")
    if provider:
        return provider

    if os.environ.get("MINIMAX_API_KEY"):
        return "minimax"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"

    return "anthropic"


def detect_lean_backend() -> str:
    """Select the Lean verification backend."""
    return os.environ.get("LEAN_BACKEND", "http")


def detect_user_language(text: str) -> str:
    """Detect if user is using Chinese or English.

    Args:
        text: User input text.

    Returns:
        'zh' for Chinese, 'en' for English.
    """
    # Chinese character range
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    if chinese_pattern.search(text):
        return "zh"

    # Check for common Chinese words
    chinese_words = ["定理", "证明", "对于", "所有", "存在", "如果", "那么", "因为", "所以"]
    text_lower = text.lower()
    for word in chinese_words:
        if word in text_lower:
            return "zh"

    return "en"


class RiemannApp:
    """Main application for Riemann proof assistant."""

    def __init__(self, args: argparse.Namespace):
        """Initialize application.

        Args:
            args: Parsed command-line arguments.
        """
        self.args = args
        self.console = Console()
        self.cli = RiemannCLI(verbose=args.verbose)
        self.running = True
        self.max_iterations = args.max_iterations
        self.project_root = self._resolve_project_root()
        self.workbench = ResearchWorkbench(self.project_root)
        self.latest_context = None
        self.latest_result: Optional[dict] = None
        self.latest_runtime: Optional[dict[str, Any]] = None

    def run(self) -> int:
        """Run the main application loop.

        Returns:
            Exit code.
        """
        try:
            self.cli.show_welcome()

            if self.args.target_file and not self.args.target_name:
                self.cli.display_error("--target-file requires --target-name")
                return 1
            if self.args.target_name and not self.args.target_file:
                self.cli.display_error("--target-name requires --target-file")
                return 1
            if self.args.apply and not (self.args.target_file and self.args.target_name):
                self.cli.display_error("--apply requires --target-file and --target-name")
                return 1

            if self.args.target_file and self.args.target_name:
                return self._handle_target_file(
                    self.args.target_file,
                    self.args.target_name,
                    plan_only=self.args.plan_only,
                    apply_after_success=self.args.apply,
                )

            if self.args.statement:
                return self._handle_statement(self.args.statement)

            return self._main_loop()

        except KeyboardInterrupt:
            self._handle_shutdown()
            return 0
        except Exception as e:
            logger.exception("Unexpected error")
            self.cli.display_error(f"Unexpected error: {str(e)}", "Fatal Error")
            return 1

    def _handle_statement(
        self,
        statement: str,
        theorem_name: str = "user_theorem",
        file_path: Optional[str] = None,
    ) -> int:
        """Handle a single statement from command line.

        Args:
            statement: Statement to prove/verify.

        Returns:
            Exit code.
        """
        self.cli.separator()
        self.cli.print(f"Statement: {statement}", "bold cyan")

        start_time = time.time()

        try:
            result = self._process_statement(
                statement,
                theorem_name=theorem_name,
                file_path=file_path,
            )
            elapsed = time.time() - start_time

            if result.get("success"):
                self.cli.display_statistics(
                    iterations=result.get("iterations", 1),
                    elapsed_time=elapsed,
                    tokens_used=result.get("tokens", 0),
                    success=True,
                )
                if result.get("plan"):
                    self.cli.display_markdown(result["plan"])
                self.cli.print("\n[green]Proof verified successfully![/green]")
                return 0
            else:
                self.cli.display_statistics(
                    iterations=result.get("iterations", 1),
                    elapsed_time=elapsed,
                    tokens_used=result.get("tokens", 0),
                    success=False,
                )
                if result.get("plan"):
                    self.cli.display_markdown(result["plan"])
                if result.get("diagnostic"):
                    self.cli.display_latest_lean_diagnostic(result["diagnostic"])
                self.cli.display_error(result.get("error", "Verification failed"))
                return 1

        except Exception as e:
            logger.exception("Error processing statement")
            self.cli.display_error(f"Error: {str(e)}")
            return 1

    def _process_statement(
        self,
        statement: str,
        theorem_name: str = "user_theorem",
        file_path: Optional[str] = None,
        plan_only: bool = False,
    ) -> dict:
        """Process a proof statement.

        This method:
        1. Generate proof using LLM
        2. Verify with Lean API
        3. Iterate on errors

        Args:
            statement: Statement to prove.

        Returns:
            Result dictionary with success status and details.
        """
        self.cli.display_verification_stage("initializing", "Setting up clients...")

        user_language = detect_user_language(statement)

        try:
            runtime = self._build_runtime(require_verifier=not plan_only)
            self.latest_runtime = runtime
            proof_generator = runtime["proof_generator"]
            verification_loop = runtime["verification_loop"]

            target_name = theorem_name or "user_theorem"
            target_file = file_path or self.workbench.session.active_file
            plan_dict = proof_generator.generate_plan(
                theorem_name=target_name,
                theorem_statement=statement,
                context={
                    "file_path": target_file or "N/A",
                    "last_error": (
                        self.workbench.session.last_diagnostic.primary_error
                        if self.workbench.session.last_diagnostic
                        else "None"
                    ),
                    "notes": self.workbench.session.notes.get(target_name, ""),
                    "plan_status": "new",
                },
            )
            theorem_plan = TheoremPlan(
                overview=plan_dict.get("overview", ""),
                subgoals=plan_dict.get("subgoals", []),
                candidate_lemmas=plan_dict.get("candidate_lemmas", []),
                notes=self.workbench.session.notes.get(target_name, ""),
                raw_plan=plan_dict.get("raw_plan", ""),
                status="planned",
            )
            self.workbench.session.set_plan(target_name, theorem_plan)

            if plan_only:
                return {
                    "success": True,
                    "iterations": 0,
                    "tokens": 0,
                    "plan": theorem_plan.raw_plan or theorem_plan.overview,
                    "source": "plan",
                }

            self.cli.display_verification_stage("generating", "Generating proof...")

            context = verification_loop.verify(
                theorem_name=target_name,
                theorem_statement=statement,
                theorem_plan=theorem_plan,
                file_path=target_file,
            )
            self.latest_context = context

            explanation = ""
            if context.state.value == "success":
                explanation = verification_loop.generate_explanation(
                    context, language=user_language
                )

            last_attempt = context.proof_attempts[-1] if context.proof_attempts else None
            proof_source = "mathlib" if context.mathlib_proof else "generated"
            proof = context.mathlib_proof or (last_attempt.lean_code if last_attempt else "")

            result = {
                "success": context.state.value == "success",
                "iterations": context.current_iteration,
                "tokens": 0,
                "proof": proof,
                "lean_code": context.latest_lean_code or proof,
                "explanation": explanation,
                "source": proof_source,
                "plan": theorem_plan.raw_plan or theorem_plan.overview,
                "diagnostic": context.last_diagnostic,
                "error": (
                    ""
                    if context.state.value == "success"
                    else (
                        context.last_diagnostic.primary_error
                        if context.last_diagnostic
                        else f"Failed after {context.current_iteration} iterations"
                    )
                ),
                "state": context.state.value,
            }
            self.latest_result = result

            if explanation:
                self.cli.display_proof_explanation(
                    theorem=f"{target_name} : {statement}",
                    explanation=explanation,
                    source=proof_source,
                )

            self._record_workbench_run(target_name, statement, result, context)
            return result

        except Exception as e:
            logger.exception("Error in proof processing")
            return {
                "success": False,
                "iterations": 0,
                "tokens": 0,
                "error": str(e),
            }

    def _build_runtime(self, require_verifier: bool = True) -> dict:
        """Create the current proving runtime for the active workspace."""

        provider = detect_llm_provider()
        llm_config = resolve_llm_config(provider)
        llm_client = LLMFactory(provider, config=llm_config)

        lean_client = None
        if require_verifier:
            lean_client = self._build_verifier()

        proof_generator = ProofGenerator(llm_client, llm_config)
        verification_loop = None
        if require_verifier:
            verification_loop = VerificationLoop(
                proof_generator=proof_generator,
                lean_converter=ProofToLeanConverter(),
                verifier_api=lean_client,
                config=AgentConfig(max_iterations=self.max_iterations),
                mathlib_retriever=MathlibRetriever(),
                proof_explainer=ProofExplainer(llm_client, llm_config),
            )
        return {
            "provider": provider,
            "lean_backend": detect_lean_backend(),
            "lean_client": lean_client,
            "proof_generator": proof_generator,
            "verification_loop": verification_loop,
        }

    def _build_verifier(self):
        """Create a Lean verifier without initializing the LLM stack."""

        lean_backend = detect_lean_backend()
        project_root = self.workbench.session.project_root or self.project_root
        if lean_backend == "local":
            lean_client = LeanFactory(
                "local",
                lean_path=os.environ.get("LEAN_PATH"),
                lake_path=os.environ.get("LAKE_PATH"),
                lean_library_path=os.environ.get("LEAN_LIBRARY_PATH") or None,
                project_root=project_root,
                timeout=60.0,
            )
            if not lean_client.check_health():
                raise RuntimeError(
                    "Local Lean executable is unavailable. "
                    "Set LEAN_PATH to a working Lean 4 binary or install Lean via elan."
                )
            return lean_client

        lean_config = LeanConfig(
            base_url=os.environ.get("LEAN_API_URL", "http://localhost:5000")
        )
        lean_client = LeanAPIClient(lean_config)
        if not lean_client.health_check():
            raise RuntimeError(
                f"Lean server is unavailable at {lean_config.base_url}. "
                "Set LEAN_API_URL to a healthy server before running proofs."
            )
        return lean_client

    def _record_workbench_run(
        self,
        theorem_name: str,
        statement: str,
        result: dict,
        context: Optional[object],
    ) -> None:
        """Persist the latest run in the research workbench session."""

        summary = self.workbench.build_run_summary(
            session=self.workbench.session,
            context=context,
            result={
                **result,
                "target_name": theorem_name,
                "statement": statement,
            },
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S %z"),
        )
        self.workbench.record_run_summary(summary)
        if context is not None and getattr(context, "last_diagnostic", None):
            self.workbench.session.last_diagnostic = context.last_diagnostic

    def _handle_target_file(
        self,
        target_file: str,
        target_name: str,
        *,
        plan_only: bool = False,
        apply_after_success: bool = False,
    ) -> int:
        """Run the workbench against a theorem found in a Lean file."""

        self.workbench.open_file(target_file)
        target = self.workbench.focus_target(target_name)
        self.cli.display_workspace_status(self.workbench.session)
        self.cli.display_active_target(target)
        if plan_only:
            result = self._process_statement(
                target.statement,
                theorem_name=target.name,
                file_path=target.file_path,
                plan_only=True,
            )
            if result.get("plan"):
                self.cli.display_markdown(result["plan"])
            return 0 if result.get("success") else 1

        exit_code = self._handle_statement(
            target.statement,
            theorem_name=target.name,
            file_path=target.file_path,
        )
        if exit_code == 0 and apply_after_success:
            return self._apply_and_verify_active_target()
        return exit_code

    def _apply_and_verify_active_target(self) -> int:
        """Apply the latest verified proof to the active target and verify the file."""

        target = self.workbench.session.active_target
        if target is None:
            self.cli.display_error("No active target selected. Use :file and :focus first.")
            return 1

        lean_code = (self.latest_result or {}).get("lean_code", "")
        if not (self.latest_result or {}).get("success") or not lean_code:
            self.cli.display_error("No successful proof is available to apply.")
            return 1

        try:
            runtime = self.latest_runtime or self._build_runtime(require_verifier=True)
            verifier = runtime.get("lean_client")
            update = self.workbench.apply_proof(
                lean_code,
                theorem_name=target.name,
                verifier=verifier,
                timeout=self._build_runtime_timeout(),
            )
            if getattr(update, "target", None) is not None:
                self.cli.display_active_target(update.target)
            else:
                self.cli.display_active_target(self.workbench.session.active_target)
            if update.diagnostic is not None:
                diagnostic = self._diagnostic_from_verification(
                    update.diagnostic,
                    file_path=update.file_path,
                    last_code=update.applied_declaration,
                )
                self.workbench.session.last_diagnostic = diagnostic
                self.cli.display_latest_lean_diagnostic(diagnostic)
            if update.success:
                self.cli.print(
                    update.message or "Applied proof and verified the file successfully.",
                    "green",
                )
                return 0
            self.cli.display_error(
                update.message or "Applied proof, but file verification failed."
            )
            return 1
        except NotImplementedError as e:
            self.cli.display_error(f"{e} Set LEAN_BACKEND=local for :apply/--apply.")
            return 1
        except Exception as e:
            logger.exception("Failed to apply proof to target")
            self.cli.display_error(str(e))
            return 1

    def _verify_active_file(self) -> dict:
        """Verify the currently active Lean file."""

        if not self.workbench.session.active_file:
            raise ValueError("No active Lean file selected")

        runtime = self.latest_runtime or self._build_runtime(require_verifier=True)
        verifier = runtime.get("lean_client") or self._build_verifier()
        response = self.workbench.verify_active_file(
            verifier,
            timeout=self._build_runtime_timeout(),
        )
        diagnostic = self._diagnostic_from_verification(
            response,
            file_path=self.workbench.session.active_file,
        )
        self.workbench.session.last_diagnostic = diagnostic
        return {
            "success": self._lookup_verification_value(response, "success", False),
            "message": self._lookup_verification_value(response, "message", ""),
            "errors": self._lookup_verification_value(response, "errors", []),
            "warnings": self._lookup_verification_value(response, "warnings", []),
            "execution_time": self._lookup_verification_value(response, "execution_time", None),
            "diagnostic": diagnostic,
            "error": diagnostic.primary_error,
        }

    def _build_runtime_timeout(self) -> float:
        return AgentConfig().timeout_seconds

    def _diagnostic_from_verification(
        self,
        verification: Any,
        *,
        file_path: Optional[str] = None,
        last_code: str = "",
    ) -> LeanDiagnostic:
        message = self._lookup_verification_value(verification, "message", "") or ""
        failing_file = self._lookup_verification_value(
            verification,
            "checked_file",
            None,
        ) or file_path
        if isinstance(message, str):
            match = re.search(r"([A-Za-z]:\\[^:]+\.lean|\S+\.lean)", message)
            if match:
                failing_file = match.group(1)

        diagnostic_code = last_code
        checked_file = failing_file or file_path
        if not diagnostic_code and checked_file and os.path.exists(checked_file):
            try:
                with open(checked_file, "r", encoding="utf-8") as handle:
                    diagnostic_code = handle.read()
            except OSError:
                diagnostic_code = ""

        return LeanDiagnostic(
            raw_message=str(message),
            errors=[
                str(error)
                for error in self._lookup_verification_value(verification, "errors", [])
            ],
            warnings=[
                str(warning)
                for warning in self._lookup_verification_value(verification, "warnings", [])
            ],
            last_submitted_code=diagnostic_code,
            failing_file=failing_file,
            execution_time=self._lookup_verification_value(
                verification,
                "execution_time",
                None,
            ),
        )

    def _lookup_verification_value(self, verification: Any, key: str, default: Any) -> Any:
        if isinstance(verification, dict):
            return verification.get(key, default)
        return getattr(verification, key, default)

    def _resolve_project_root(self) -> str:
        """Resolve the active Lean project root for the workbench."""

        return (
            getattr(self.args, "project_root", None)
            or os.environ.get("LEAN_PROJECT_ROOT")
            or os.getcwd()
        )

    def _main_loop(self) -> int:
        """Run the interactive main loop.

        Returns:
            Exit code.
        """
        while self.running:
            user_input = self.cli.get_input()

            if user_input is None or self._should_quit(user_input):
                break

            if not user_input:
                continue

            if self._is_command(user_input):
                self._handle_command(user_input)
            else:
                self._handle_statement(user_input)

            if self.running:
                self.cli.separator()

        self._handle_shutdown()
        return 0

    def _is_command(self, user_input: str) -> bool:
        """Check if input is a command.

        Args:
            user_input: User input string.

        Returns:
            True if input is a command.
        """
        return user_input.startswith(":")

    def _handle_command(self, command: str) -> None:
        """Handle a command.

        Args:
            command: Command string.
        """
        raw = command.strip()
        head, _, tail = raw.partition(" ")
        cmd = head.lower()
        arg = tail.strip()

        if cmd in (":help", ":h", "help"):
            self.cli.show_help()

        elif cmd in (":quit", ":q", "exit"):
            self.running = False

        elif cmd in (":clear", ":c"):
            self.cli.clear_screen()

        elif cmd == ":verbose":
            self.cli.verbose = not self.cli.verbose
            status = "enabled" if self.cli.verbose else "disabled"
            self.cli.print(f"Verbose mode {status}", "cyan")

        elif cmd == ":model":
            self._show_model_info()

        elif cmd == ":open":
            if not arg:
                self.cli.display_error("Usage: :open <lean-project-root>")
                return
            self.project_root = arg
            self.workbench.open_project(arg)
            self.cli.display_workspace_status(self.workbench.session)

        elif cmd == ":file":
            if not arg:
                self.cli.display_error("Usage: :file <relative-or-absolute-lean-file>")
                return
            try:
                targets = self.workbench.open_file(arg)
                self.cli.display_workspace_status(self.workbench.session)
                if self.workbench.session.active_target:
                    self.cli.display_active_target(self.workbench.session.active_target)
                if targets:
                    self.cli.print(
                        "Discovered targets: " + ", ".join(target.name for target in targets[:10]),
                        "cyan",
                    )
            except Exception as e:
                self.cli.display_error(str(e))

        elif cmd == ":focus":
            if not arg:
                self.cli.display_error("Usage: :focus <theorem-name>")
                return
            try:
                target = self.workbench.focus_target(arg)
                self.cli.display_active_target(target)
            except Exception as e:
                self.cli.display_error(str(e))

        elif cmd == ":targets":
            targets = self.workbench.session.targets
            if not targets:
                self.cli.display_error("No theorem targets discovered. Use :file first.", "Info")
                return
            self.cli.print(
                "Targets: " + ", ".join(target.name for target in targets),
                "cyan",
            )

        elif cmd == ":status":
            self.cli.display_workspace_status(self.workbench.session)
            self.cli.display_active_target(self.workbench.session.active_target)
            if self.workbench.session.last_diagnostic:
                self.cli.display_latest_lean_diagnostic(self.workbench.session.last_diagnostic)

        elif cmd == ":history":
            attempts = [
                {
                    "was_successful": run.get("success", False),
                    "proof_idea": run.get("source", ""),
                    "lean_code": run.get("lean_code", ""),
                    "error_message": run.get("error", ""),
                    "status": run.get("status", "unknown"),
                }
                for run in self.workbench.session.recent_runs
            ]
            self.cli.display_attempt_history(attempts)

        elif cmd == ":goals":
            self.cli.display_active_target(self.workbench.session.active_target)
            if self.latest_context and getattr(self.latest_context, "latest_lean_code", ""):
                self.cli.display_proof(self.latest_context.latest_lean_code)
            if self.workbench.session.last_diagnostic:
                self.cli.display_latest_lean_diagnostic(self.workbench.session.last_diagnostic)

        elif cmd == ":plan":
            if not self.workbench.session.active_target:
                self.cli.display_error("No active target selected. Use :file and :focus first.")
                return
            target = self.workbench.session.active_target
            result = self._process_statement(
                target.statement,
                theorem_name=target.name,
                file_path=target.file_path,
                plan_only=True,
            )
            if result.get("plan"):
                self.cli.display_markdown(result["plan"])

        elif cmd == ":prove":
            if not self.workbench.session.active_target:
                self.cli.display_error("No active target selected. Use :file and :focus first.")
                return
            target = self.workbench.session.active_target
            self._handle_target_file(target.file_path or "", target.name, plan_only=False)

        elif cmd == ":apply":
            self._apply_and_verify_active_target()

        elif cmd == ":verify-file":
            try:
                result = self._verify_active_file()
                self.cli.display_latest_lean_diagnostic(result.get("diagnostic"))
                if result.get("success"):
                    self.cli.print("Lean file verified successfully.", "green")
                else:
                    self.cli.display_error(result.get("error", "File verification failed"))
            except Exception as e:
                self.cli.display_error(str(e))

        else:
            self.cli.print(f"Unknown command: {command}", "yellow")
            self.cli.print("Type :help for available commands")

    def _should_quit(self, user_input: str) -> bool:
        """Check if input should quit the application.

        Args:
            user_input: User input.

        Returns:
            True if should quit.
        """
        return user_input.lower().strip() in (":quit", ":q", "exit", "quit")

    def _show_model_info(self) -> None:
        """Show current model configuration."""
        self.cli.print("Model Configuration:", "bold cyan")
        self.cli.print("  Provider: Not configured")
        self.cli.print("  Model: Not configured")
        self.cli.print("  Temperature: 0.7")

    def _handle_shutdown(self) -> None:
        """Handle graceful shutdown."""
        self.cli.new_line()
        self.cli.print("[cyan]Goodbye![/cyan]")


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="riemann",
        description="Riemann - Mathematical Proof Assistant",
        epilog="Enter a statement to prove or use interactive mode.",
    )

    parser.add_argument(
        "statement",
        nargs="?",
        help="Statement or theorem to prove",
    )

    parser.add_argument(
        "--project-root",
        help="Lean project root for workbench mode",
    )

    parser.add_argument(
        "--target-file",
        help="Lean file to inspect in workbench mode",
    )

    parser.add_argument(
        "--target-name",
        help="Theorem or lemma name to focus inside --target-file",
    )

    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Generate a theorem plan without running Lean verification",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply a successful proof back into --target-file and verify the file",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "-m", "--max-iterations",
        type=int,
        default=5,
        help="Maximum number of verification iterations (default: 5)",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information",
    )

    return parser


def main() -> int:
    """Main entry point.

    Returns:
        Exit code.
    """
    load_dotenv()

    parser = create_parser()
    args = parser.parse_args()

    if args.version:
        print("Riemann - Mathematical Proof Assistant")
        print("Version: 0.1.0")
        return 0

    app = RiemannApp(args)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
