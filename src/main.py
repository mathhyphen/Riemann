"""Main entry point for Riemann proof assistant CLI.

This module provides:
- Command-line argument parsing
- Main application loop
- Graceful shutdown handling
"""

import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv
from rich.console import Console

try:
    from .agent.proof_generator import ProofGenerator
    from .agent.proof_to_lean import ProofToLeanConverter
    from .agent.state import AgentConfig
    from .agent.verification_loop import VerificationLoop
    from .cli import RiemannCLI
    from .lean_api import LeanAPIClient, LeanConfig
    from .lean_module import LeanFactory
    from .llm_module import LLMFactory, resolve_llm_config
except ImportError:  # pragma: no cover - script execution fallback
    from src.agent.proof_generator import ProofGenerator
    from src.agent.proof_to_lean import ProofToLeanConverter
    from src.agent.state import AgentConfig
    from src.agent.verification_loop import VerificationLoop
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

    def run(self) -> int:
        """Run the main application loop.

        Returns:
            Exit code.
        """
        try:
            self.cli.show_welcome()

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

    def _handle_statement(self, statement: str) -> int:
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
            result = self._process_statement(statement)
            elapsed = time.time() - start_time

            if result.get("success"):
                self.cli.display_statistics(
                    iterations=result.get("iterations", 1),
                    elapsed_time=elapsed,
                    tokens_used=result.get("tokens", 0),
                    success=True,
                )
                self.cli.print("\n[green]Proof verified successfully![/green]")
                return 0
            else:
                self.cli.display_statistics(
                    iterations=result.get("iterations", 1),
                    elapsed_time=elapsed,
                    tokens_used=result.get("tokens", 0),
                    success=False,
                )
                self.cli.display_error(result.get("error", "Verification failed"))
                return 1

        except Exception as e:
            logger.exception("Error processing statement")
            self.cli.display_error(f"Error: {str(e)}")
            return 1

    def _process_statement(self, statement: str) -> dict:
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

        try:
            # Initialize LLM client
            provider = detect_llm_provider()
            llm_config = resolve_llm_config(provider)
            llm_client = LLMFactory(
                provider,
                config=llm_config
            )

            # Initialize Lean verifier
            lean_backend = detect_lean_backend()
            if lean_backend == "local":
                lean_client = LeanFactory(
                    "local",
                    lean_path=os.environ.get("LEAN_PATH"),
                    lake_path=os.environ.get("LAKE_PATH"),
                    lean_library_path=os.environ.get("LEAN_LIBRARY_PATH") or None,
                    project_root=os.environ.get("LEAN_PROJECT_ROOT"),
                    timeout=60.0,
                )
                if not lean_client.check_health():
                    raise RuntimeError(
                        "Local Lean executable is unavailable. "
                        "Set LEAN_PATH to a working Lean 4 binary or install Lean via elan."
                    )
            else:
                lean_config = LeanConfig(
                    base_url=os.environ.get("LEAN_API_URL", "http://localhost:5000")
                )
                lean_client = LeanAPIClient(lean_config)
                if not lean_client.health_check():
                    raise RuntimeError(
                        f"Lean server is unavailable at {lean_config.base_url}. "
                        "Set LEAN_API_URL to a healthy server before running proofs."
                    )

            # Initialize agent components
            proof_generator = ProofGenerator(llm_client, llm_config)
            proof_converter = ProofToLeanConverter()

            # Create verification loop
            agent_config = AgentConfig(
                max_iterations=self.max_iterations
            )
            verification_loop = VerificationLoop(
                proof_generator=proof_generator,
                lean_converter=proof_converter,
                verifier_api=lean_client,
                config=agent_config
            )

            self.cli.display_verification_stage("generating", "Generating proof...")

            # Run verification
            context = verification_loop.verify(
                theorem_name="user_theorem",
                theorem_statement=statement
            )

            if context.state.value == "success":
                last_attempt = context.proof_attempts[-1] if context.proof_attempts else None
                return {
                    "success": True,
                    "iterations": context.current_iteration,
                    "tokens": 0,
                    "proof": last_attempt.lean_code if last_attempt else "",
                }
            else:
                return {
                    "success": False,
                    "iterations": context.current_iteration,
                    "tokens": 0,
                    "error": f"Failed after {context.current_iteration} iterations",
                }

        except Exception as e:
            logger.exception("Error in proof processing")
            return {
                "success": False,
                "iterations": 0,
                "tokens": 0,
                "error": str(e),
            }

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
        cmd = command.lower().strip()

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
