"""Output formatters for Riemann CLI."""

import re
import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


class OutputFormatter:
    """Formatter for various output types."""

    def __init__(self, console: Optional[Console] = None, verbose: bool = False):
        self.console = console or Console()
        self.verbose = verbose

    def format_lean_code(self, code: str, theme: str = "monokai") -> Panel:
        syntax = Syntax(code, "lean4", theme=theme, line_numbers=True)
        return Panel(syntax, title="Lean Code", border_style="blue")

    def format_error(self, error_msg: str, error_type: str = "Error") -> Panel:
        style_map = {
            "Error": "red",
            "Warning": "yellow",
            "Info": "blue",
        }
        style = style_map.get(error_type, "white")
        highlighted = self._highlight_error_patterns(error_msg)
        return Panel(
            highlighted,
            title=f"[bold {style}]{error_type}[/bold {style}]",
            border_style=style,
        )

    def _highlight_error_patterns(self, text: str) -> Text:
        result = Text(text)

        file_line_pattern = re.compile(r"(\S+\.lean:\d+)")
        for match in file_line_pattern.finditer(text):
            result.stylize("bold cyan", match.start(), match.end())

        for keyword in ["error", "failed", "unexpected", "unknown", "cannot"]:
            pattern = re.compile(rf"\b{keyword}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                result.stylize("bold red", match.start(), match.end())

        return result

    def format_proof_step(self, step: int, content: str) -> Panel:
        return Panel(content, title=f"[bold]Step {step}[/bold]", border_style="green")

    def format_statistics(
        self,
        iterations: int,
        elapsed_time: float,
        tokens_used: int = 0,
        success: bool = False,
    ) -> Table:
        table = Table(title="Execution Statistics", show_header=True)
        table.add_column("Metric", style="cyan", justify="left")
        table.add_column("Value", style="white", justify="right")

        status = "[green]Success[/green]" if success else "[red]Failed[/red]"
        table.add_row("Status", status)
        table.add_row("Iterations", str(iterations))
        table.add_row("Time", f"{elapsed_time:.2f}s")

        if tokens_used > 0:
            table.add_row("Tokens Used", f"{tokens_used:,}")

        return table

    def format_iteration_summary(
        self,
        iteration: int,
        status: str,
        error_count: int = 0,
    ) -> Text:
        status_icons = {
            "success": "OK",
            "failed": "FAIL",
            "retry": "RETRY",
            "running": "RUN",
        }
        icon = status_icons.get(status, "...")

        result = Text()
        result.append(f"{icon} ", style="bold")
        result.append(f"Iteration {iteration}: ", style="bold white")
        result.append(status)

        if error_count > 0:
            result.append(f" ({error_count} errors)", style="red")

        return result

    def format_welcome(self) -> Panel:
        welcome_text = Text()
        welcome_text.append("Riemann - Mathematical Proof Assistant\n\n", style="bold cyan")
        welcome_text.append("Enter your mathematical statement or theorem to begin.\n")
        welcome_text.append("Type ", style="white")
        welcome_text.append(":help", style="cyan")
        welcome_text.append(" for commands, ", style="white")
        welcome_text.append(":quit", style="cyan")
        welcome_text.append(" to exit.", style="white")

        return Panel(
            welcome_text,
            title="[bold]Welcome to Riemann[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )

    def format_help(self) -> Panel:
        help_text = Text()
        help_text.append("Available Commands:\n\n", style="bold cyan")

        commands = [
            (":help", "Show this help message"),
            (":quit, :q", "Exit the program"),
            (":clear, :c", "Clear the screen"),
            (":verbose", "Toggle verbose output"),
            (":model", "Show current model configuration"),
        ]

        for cmd, desc in commands:
            help_text.append(f"  {cmd:<15} - {desc}\n", style="white")

        help_text.append("\nExamples:\n", style="bold cyan")
        help_text.append('  prove "forall n : Nat, n + 0 = n"\n', style="dim")
        help_text.append('  verify "theorem example : 1 + 1 = 2 := rfl"\n', style="dim")

        return Panel(
            help_text,
            title="[bold]Help[/bold]",
            border_style="blue",
            padding=(1, 2),
        )


class ProgressFormatter:
    """Formatter for progress indicators."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def format_verification_progress(self, stage: str, detail: Optional[str] = None) -> Text:
        stages = {
            "initializing": ("INIT", "Initializing"),
            "generating": ("GEN", "Generating proof"),
            "verifying": ("VERIFY", "Verifying with Lean"),
            "fixing": ("FIX", "Fixing errors"),
            "complete": ("DONE", "Complete"),
            "failed": ("FAIL", "Failed"),
        }

        icon, label = stages.get(stage, ("...", stage))
        result = Text()
        result.append(f"{icon} ", style="bold")
        result.append(label, style="bold white")

        if detail:
            result.append(f": {detail}", style="dim")

        return result


def format_timestamp(ts: Optional[float] = None) -> str:
    if ts is None:
        ts = time.time()
    return time.strftime("%H:%M:%S", time.localtime(ts))
