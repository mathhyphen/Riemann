"""Command-line interface for Riemann."""

import signal
from typing import Callable, Generator, Optional

from rich import print as rprint
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt

from .formatters import OutputFormatter, ProgressFormatter


class RiemannCLI:
    """Main CLI interface for Riemann proof assistant."""

    def __init__(self, verbose: bool = False):
        self.console = Console()
        self.formatter = OutputFormatter(self.console, verbose)
        self.progress_formatter = ProgressFormatter(self.console)
        self.verbose = verbose
        self._interrupted = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame) -> None:
        del signum, frame
        self._interrupted = True
        self.console.print("\n[yellow]Interrupted by user[/yellow]")
        self.console.print("[dim]Press Enter to exit or continue...[/dim]")

    def show_welcome(self) -> None:
        self.console.print(self.formatter.format_welcome())

    def show_help(self) -> None:
        self.console.print(self.formatter.format_help())

    def get_input(self, prompt_text: str = ">>> ") -> Optional[str]:
        try:
            user_input = Prompt.ask(prompt_text, console=self.console)
            if self._interrupted:
                return None
            return user_input.strip()
        except (KeyboardInterrupt, EOFError):
            self._interrupted = True
            return None

    def confirm_action(self, message: str, default: bool = False) -> bool:
        return Confirm.ask(message, console=self.console, default=default)

    def display_proof(self, proof: str) -> None:
        self.console.print()
        self.console.print(self.formatter.format_lean_code(proof))
        self.console.print()

    def display_error(self, error: str, error_type: str = "Error") -> None:
        self.console.print()
        self.console.print(self.formatter.format_error(error, error_type))
        self.console.print()

    def display_verification_stage(self, stage: str, detail: Optional[str] = None) -> None:
        self.console.print(
            self.progress_formatter.format_verification_progress(stage, detail)
        )

    def display_iteration(self, iteration: int, status: str, error_count: int = 0) -> None:
        summary = self.formatter.format_iteration_summary(iteration, status, error_count)
        self.console.print(summary)

    def display_statistics(
        self,
        iterations: int,
        elapsed_time: float,
        tokens_used: int = 0,
        success: bool = False,
    ) -> None:
        table = self.formatter.format_statistics(iterations, elapsed_time, tokens_used, success)
        self.console.print(table)

    def display_streaming(self, generator: Generator[str, None, None], prefix: str = "") -> str:
        content_parts: list[str] = []

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
        display_content = content[-5000:] if len(content) > 5000 else content
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
        if style:
            rprint(f"[{style}]{message}[/{style}]")
        else:
            self.console.print(message)

    def print_verbose(self, message: str) -> None:
        if self.verbose:
            self.console.print(f"[dim]{message}[/dim]")

    def clear_screen(self) -> None:
        self.console.clear()

    def separator(self) -> None:
        self.console.print("[dim]" + "-" * 60 + "[/dim]")

    def new_line(self) -> None:
        self.console.print()

    def display_markdown(self, content: str) -> None:
        self.console.print(Markdown(content))
