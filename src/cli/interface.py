"""Command-line interface for Riemann.

This module provides the main CLI interface using rich for:
- Colored output
- Progress tracking
- Interactive input handling
- Streaming display
"""

import signal
import sys
from typing import Callable, Generator, Optional

from rich import print as rprint
from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt

from .formatters import OutputFormatter, ProgressFormatter


class RiemannCLI:
    """Main CLI interface for Riemann proof assistant."""

    def __init__(self, verbose: bool = False):
        """Initialize CLI.

        Args:
            verbose: Enable verbose output.
        """
        self.console = Console()
        self.formatter = OutputFormatter(self.console, verbose)
        self.progress_formatter = ProgressFormatter(self.console)
        self.verbose = verbose
        self._interrupted = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful interruption."""
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame) -> None:
        """Handle interrupt signals gracefully."""
        self._interrupted = True
        self.console.print("\n[yellow]Interrupted by user[/yellow]")
        self.console.print("[dim]Press Enter to exit or continue...[/dim]")

    def show_welcome(self) -> None:
        """Display welcome message."""
        self.console.print(self.formatter.format_welcome())

    def show_help(self) -> None:
        """Display help message."""
        self.console.print(self.formatter.format_help())

    def get_input(self, prompt_text: str = ">>> ") -> Optional[str]:
        """Get input from user.

        Args:
            prompt_text: Input prompt text.

        Returns:
            User input or None if interrupted.
        """
        try:
            user_input = Prompt.ask(prompt_text, console=self.console)
            if self._interrupted:
                return None
            return user_input.strip()
        except KeyboardInterrupt:
            self._interrupted = True
            return None
        except EOFError:
            return None

    def confirm_action(self, message: str, default: bool = False) -> bool:
        """Ask user for confirmation.

        Args:
            message: Confirmation message.
            default: Default value if user just presses Enter.

        Returns:
            User's confirmation choice.
        """
        return Confirm.ask(
            message,
            console=self.console,
            default=default,
        )

    def display_proof(self, proof: str) -> None:
        """Display generated proof.

        Args:
            proof: Proof content to display.
        """
        self.console.print()
        self.console.print(self.formatter.format_lean_code(proof))
        self.console.print()

    def display_error(self, error: str, error_type: str = "Error") -> None:
        """Display error message.

        Args:
            error: Error message.
            error_type: Type of error.
        """
        self.console.print()
        self.console.print(self.formatter.format_error(error, error_type))
        self.console.print()

    def display_verification_stage(
        self,
        stage: str,
        detail: Optional[str] = None,
    ) -> None:
        """Display current verification stage.

        Args:
            stage: Stage name.
            detail: Optional stage detail.
        """
        msg = self.progress_formatter.format_verification_progress(stage, detail)
        self.console.print(msg)

    def display_iteration(self, iteration: int, status: str, error_count: int = 0) -> None:
        """Display iteration status.

        Args:
            iteration: Iteration number.
            status: Status string.
            error_count: Number of errors.
        """
        summary = self.formatter.format_iteration_summary(iteration, status, error_count)
        self.console.print(summary)

    def display_statistics(
        self,
        iterations: int,
        elapsed_time: float,
        tokens_used: int = 0,
        success: bool = False,
    ) -> None:
        """Display execution statistics.

        Args:
            iterations: Number of iterations.
            elapsed_time: Elapsed time.
            tokens_used: Tokens used.
            success: Whether verification succeeded.
        """
        table = self.formatter.format_statistics(iterations, elapsed_time, tokens_used, success)
        self.console.print(table)

    def display_streaming(
        self,
        generator: Generator[str, None, None],
        prefix: str = "",
    ) -> str:
        """Display streaming content from a generator.

        Args:
            generator: Generator yielding content chunks.
            prefix: Prefix to display before content.

        Returns:
            Combined content string.
        """
        content_parts = []

        if prefix:
            self.console.print(prefix)

        with Live(console=self.console, refresh_per_second=10) as live:
            current = ""
            for chunk in generator:
                if self._interrupted:
                    break
                current += chunk
                content_parts.append(chunk)
                live.update(self._create_stream_display(current))

        return "".join(content_parts)

    def _create_stream_display(self, content: str) -> Panel:
        """Create display panel for streaming content.

        Args:
            content: Current content.

        Returns:
            Panel with content.
        """
        from rich.panel import Panel

        display_content = content
        if len(display_content) > 5000:
            display_content = display_content[-5000:]

        return Panel(
            display_content,
            title="[bold]Streaming Output[/bold]",
            border_style="cyan",
        )

    def run_with_progress(
        self,
        task: Callable[[], tuple[str, bool]],
        progress_stages: list[str],
    ) -> tuple[str, bool]:
        """Run task with progress display.

        Args:
            task: Task to run. Returns (result, success).
            progress_stages: List of progress stages.

        Returns:
            Task result and success status.
        """
        result = ""
        success = False

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            task_id = progress.add_task("Processing...", total=None)

            for stage in progress_stages:
                if self._interrupted:
                    break
                progress.update(task_id, description=stage)
                result, success = task()
                if success or self._interrupted:
                    break

        return result, success

    def print(self, message: str, style: Optional[str] = None) -> None:
        """Print message with optional style.

        Args:
            message: Message to print.
            style: Optional rich style string.
        """
        if style:
            rprint(f"[{style}]{message}[/{style}]")
        else:
            self.console.print(message)

    def print_verbose(self, message: str) -> None:
        """Print message only in verbose mode.

        Args:
            message: Message to print.
        """
        if self.verbose:
            self.console.print(f"[dim]{message}[/dim]")

    def clear_screen(self) -> None:
        """Clear the console screen."""
        self.console.clear()

    def separator(self) -> None:
        """Print a visual separator."""
        self.console.print("[dim]" + "─" * 60 + "[/dim]")

    def new_line(self) -> None:
        """Print a new line."""
        self.console.print()

    def display_markdown(self, content: str) -> None:
        """Display markdown content.

        Args:
            content: Markdown content.
        """
        md = Markdown(content)
        self.console.print(md)


class Panel:
    """Simple panel wrapper for type compatibility."""

    def __init__(self, content, title: str = "", border_style: str = "white"):
        """Initialize panel.

        Args:
            content: Panel content.
            title: Panel title.
            border_style: Border style.
        """
        self.content = content
        self.title = title
        self.border_style = border_style
