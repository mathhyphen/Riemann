"""Command-line interface for Riemann."""

import re
import signal
import sys
from typing import Any, Callable, Generator, Mapping, Optional, Sequence

from rich import print as rprint
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .formatters import OutputFormatter, ProgressFormatter


def _safe_encode(text: str) -> str:
    """Replace non-ASCII characters for Windows console compatibility."""
    if sys.platform == "win32":
        # Replace common Unicode characters with ASCII equivalents
        replacements = {
            '\u0151': 'o',  # Hungarian o
            '\u00e9': 'e',  # e acute
            '\u00f3': 'o',  # o acute
            '\u00fc': 'u',  # u umlaut
            '\u00e1': 'a',  # a acute
            '\u00ed': 'i',  # i acute
            '\u00f6': 'o',  # o umlaut
            '\u00e4': 'a',  # a umlaut
            '\u2200': 'forall',  # forall symbol
            '\u2203': 'exists',  # exists symbol
            '\u2227': 'and',  # logical and
            '\u2228': 'or',   # logical or
            '\u00ac': 'not',  # not symbol
            '\u2192': '->',   # arrow
            '\u2194': '<->',  # double arrow
            '\u2260': '!=',   # not equal
            '\u2264': '<=',   # less or equal
            '\u2265': '>=',   # greater or equal
            '\u00d7': '*',    # multiplication
            '\u00f7': '/',    # division
            '\u2022': '*',    # bullet point
            '\u2023': '*',    # triangle bullet
            '\u2043': '-',    # hyphen bullet
            '\u2212': '-',    # minus sign
            '\u2013': '-',    # en dash
            '\u2014': '-',    # em dash
            '\u2018': "'",   # left single quote
            '\u2019': "'",   # right single quote
            '\u201c': '"',   # left double quote
            '\u201d': '"',   # right double quote
            '\u00b0': 'deg',  # degree symbol
            '\u03b1': 'alpha',  # Greek
            '\u03b2': 'beta',
            '\u03b3': 'gamma',
            '\u03b4': 'delta',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        # Remove any remaining non-ASCII characters
        text = re.sub(r'[^\x00-\x7f]', '', text)
    return text


class RiemannCLI:
    """Main CLI interface for Riemann proof assistant."""

    def __init__(self, verbose: bool = False, safe_mode: bool = True):
        # Use safe_mode=True by default on Windows to handle encoding issues
        if safe_mode and sys.platform == "win32":
            self.console = Console(emoji=False, markup=False)
        else:
            self.console = Console()
        self.formatter = OutputFormatter(self.console, verbose)
        self.progress_formatter = ProgressFormatter(self.console)
        self.verbose = verbose
        self._interrupted = False
        self._safe_mode = safe_mode
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
        safe_content = _safe_encode(content) if self._safe_mode else content
        if self._safe_mode and sys.platform == "win32":
            self.console.print(safe_content)
            return
        self.console.print(Markdown(safe_content))

    def display_proof_explanation(
        self,
        theorem: str,
        explanation: str,
        source: str = "generated",
    ) -> None:
        """Display user-friendly proof explanation.

        Args:
            theorem: The theorem name or statement.
            explanation: The explanation text to display.
            source: Source of the proof ('mathlib' or 'generated').
        """
        self.console.print()
        source_label = "[green]From Mathlib[/green]" if source == "mathlib" else "[cyan]Generated Explanation[/cyan]"
        safe_theorem = _safe_encode(theorem) if self._safe_mode else theorem
        header = Panel(
            f"[bold]{safe_theorem}[/bold]\n{source_label}",
            border_style="green",
            title="[bold]Proof Explanation[/bold]",
        )
        self.console.print(header)
        self.console.print()
        safe_explanation = _safe_encode(explanation) if self._safe_mode else explanation
        self.console.print(Markdown(safe_explanation))
        self.console.print()

    def display_mathlib_hit(self, hit: dict) -> None:
        """Display a Mathlib theorem hit.

        Args:
            hit: Dictionary with theorem info (name, signature, source_path, etc.).
        """
        self.console.print()
        info = Panel(
            f"[bold cyan]{hit.get('name', 'Unknown')}[/bold cyan]\n"
            f"[dim]{hit.get('signature', '')}[/dim]\n"
            f"[dim]Source: {hit.get('source_path', 'N/A')}[/dim]",
            border_style="cyan",
            title="[bold]Mathlib Hit[/bold]",
        )
        self.console.print(info)

    def display_workspace_status(self, session: Any) -> None:
        """Display a compact research workspace summary."""

        project_root = self._get_value(session, "project_root", "N/A")
        active_file = self._get_value(session, "active_file", "N/A")
        module_name = self._get_value(session, "module_name", "N/A")
        active_target = self._get_value(session, "active_target", None)
        recent_runs = self._get_value(session, "recent_runs", []) or []
        open_plans = self._get_value(session, "open_plans", []) or []
        last_diagnostic = self._get_value(session, "last_diagnostic", None)

        target_name = self._get_value(active_target, "name", None)
        if target_name is None:
            target_name = self._get_value(active_target, "theorem_name", "None")
        target_status = self._get_value(active_target, "status", "idle")

        lines = [
            f"Project: {self._format_workbench_value(project_root)}",
            f"File: {self._format_workbench_value(active_file)}",
            f"Module: {self._format_workbench_value(module_name)}",
            f"Target: {self._format_workbench_value(target_name)} ({self._format_workbench_value(target_status)})",
            f"Plans: {len(open_plans)}",
            f"Recent Runs: {len(recent_runs)}",
        ]

        if last_diagnostic:
            last_error = self._get_value(last_diagnostic, "raw_message", None)
            if not last_error:
                last_error = self._get_value(last_diagnostic, "message", None)
            if last_error:
                lines.append(f"Last Error: {self._format_workbench_value(last_error, limit=100)}")

        self.console.print()
        self.console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Workspace[/bold]",
                border_style="cyan",
            )
        )
        self.console.print()

    def display_active_target(self, target: Any) -> None:
        """Display the currently focused theorem or lemma."""

        if target is None:
            self.console.print()
            self.console.print(
                Panel(
                    "No active target selected.",
                    title="[bold]Active Target[/bold]",
                    border_style="cyan",
                )
            )
            self.console.print()
            return

        name = self._get_value(target, "name", self._get_value(target, "theorem_name", "N/A"))
        statement = self._get_value(
            target, "statement", self._get_value(target, "theorem_statement", "N/A")
        )
        file_path = self._get_value(target, "file_path", "N/A")
        start_line = self._get_value(target, "start_line", None)
        status = self._get_value(target, "status", "unknown")
        notes = self._get_value(target, "notes", "")

        lines = [
            f"Name: {self._format_workbench_value(name)}",
            f"Statement: {self._format_workbench_value(statement, limit=160)}",
            f"Location: {self._format_workbench_value(file_path)}"
            + (f":{start_line}" if start_line is not None else ""),
            f"Status: {self._format_workbench_value(status)}",
        ]

        if notes:
            lines.append(f"Notes: {self._format_workbench_value(notes, limit=120)}")

        self.console.print()
        self.console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Active Target[/bold]",
                border_style="green",
            )
        )
        self.console.print()

    def display_attempt_history(self, attempts: Sequence[Any]) -> None:
        """Display a compact attempt history table."""

        self.console.print()
        table = Table(title="Attempt History", show_header=True, header_style="cyan")
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Status", style="white")
        table.add_column("Source", style="white")
        table.add_column("Lean Code", style="white")
        table.add_column("Error", style="white")

        if not attempts:
            table.add_row("-", "-", "-", "No attempts yet", "-")
            self.console.print(table)
            self.console.print()
            return

        for index, attempt in enumerate(attempts, start=1):
            status = "success" if self._get_value(attempt, "was_successful", False) else self._get_value(
                attempt, "status", "failed"
            )
            source = self._get_value(attempt, "proof_idea", "")
            lean_code = self._get_value(attempt, "lean_code", "")
            error = self._get_value(attempt, "error_message", "")
            table.add_row(
                str(index),
                self._format_workbench_value(status, limit=16),
                self._format_workbench_value(source, limit=22),
                self._format_workbench_value(lean_code, limit=48),
                self._format_workbench_value(error, limit=48),
            )

        self.console.print(table)
        self.console.print()

    def display_latest_lean_diagnostic(self, diagnostic: Any) -> None:
        """Display the latest structured Lean diagnostic."""

        if not diagnostic:
            self.console.print()
            self.console.print(
                Panel(
                    "No Lean diagnostic available.",
                    title="[bold]Lean Diagnostic[/bold]",
                    border_style="yellow",
                )
            )
            self.console.print()
            return

        file_path = self._get_value(diagnostic, "failing_file", "")
        raw_message = self._get_value(diagnostic, "raw_message", "")
        message = self._get_value(diagnostic, "message", "")
        errors = self._get_value(diagnostic, "errors", []) or []
        warnings = self._get_value(diagnostic, "warnings", []) or []
        execution_time = self._get_value(diagnostic, "execution_time", None)
        code = self._get_value(diagnostic, "last_submitted_code", "")

        lines = []
        if file_path:
            lines.append(f"File: {self._format_workbench_value(file_path)}")
        if execution_time is not None:
            lines.append(f"Time: {execution_time:.2f}s")
        if message:
            lines.append(f"Message: {self._format_workbench_value(message, limit=120)}")
        if raw_message and raw_message != message:
            lines.append(f"Raw: {self._format_workbench_value(raw_message, limit=120)}")
        if errors:
            lines.append(f"Errors: {self._format_workbench_value('; '.join(map(str, errors)), limit=140)}")
        if warnings:
            lines.append(f"Warnings: {self._format_workbench_value('; '.join(map(str, warnings)), limit=140)}")
        if code:
            lines.append(f"Code: {self._format_workbench_value(code, limit=140)}")

        self.console.print()
        self.console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Lean Diagnostic[/bold]",
                border_style="red" if errors else "yellow",
            )
        )
        self.console.print()

    def _get_value(self, obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, Mapping):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _format_workbench_value(self, value: Any, *, limit: int = 80) -> str:
        text = "" if value is None else str(value)
        if self._safe_mode:
            text = _safe_encode(text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > limit:
            return text[: max(0, limit - 3)] + "..."
        return text
