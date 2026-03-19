"""Output formatters for Riemann CLI.

This module provides formatting utilities for:
- Lean code highlighting
- Error message display
- Statistics presentation
"""

import re
import time
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


class OutputFormatter:
    """Formatter for various output types."""

    def __init__(self, console: Optional[Console] = None, verbose: bool = False):
        """Initialize formatter.

        Args:
            console: Rich console instance. Creates default if None.
            verbose: Enable verbose output.
        """
        self.console = console or Console()
        self.verbose = verbose

    def format_lean_code(self, code: str, theme: str = "monokai") -> Panel:
        """Format Lean code with syntax highlighting.

        Args:
            code: Lean code to format.
            theme: Syntax highlighting theme.

        Returns:
            Panel containing highlighted code.
        """
        syntax = Syntax(code, "lean4", theme=theme, line_numbers=True)
        return Panel(syntax, title="Lean Code", border_style="blue")

    def format_error(self, error_msg: str, error_type: str = "Error") -> Panel:
        """Format error message with highlighting.

        Args:
            error_msg: Error message content.
            error_type: Type of error (Error, Warning, Info).

        Returns:
            Styled panel with error message.
        """
        style_map = {
            "Error": "red",
            "Warning": "yellow",
            "Info": "blue",
        }
        style = style_map.get(error_type, "white")

        # Highlight key error patterns
        highlighted = self._highlight_error_patterns(error_msg)

        return Panel(
            highlighted,
            title=f"[bold {style}]{error_type}[/bold {style}]",
            border_style=style,
        )

    def _highlight_error_patterns(self, text: str) -> Text:
        """Highlight common error patterns in text.

        Args:
            text: Text to process.

        Returns:
            Text with highlighted patterns.
        """
        result = Text(text)

        # Highlight file:line patterns
        file_line_pattern = re.compile(r"(\S+\.lean:\d+)")
        for match in file_line_pattern.finditer(text):
            result.stylize("bold cyan", match.start(), match.end())

        # Highlight specific error keywords
        keywords = ["error", "failed", "unexpected", "unknown", "cannot"]
        for keyword in keywords:
            pattern = re.compile(rf"\b{keyword}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                result.stylize("bold red", match.start(), match.end())

        return result

    def format_proof_step(self, step: int, content: str) -> Panel:
        """Format a proof step.

        Args:
            step: Step number.
            content: Step content.

        Returns:
            Formatted panel for proof step.
        """
        return Panel(
            content,
            title=f"[bold]Step {step}[/bold]",
            border_style="green",
        )

    def format_statistics(
        self,
        iterations: int,
        elapsed_time: float,
        tokens_used: int = 0,
        success: bool = False,
    ) -> Table:
        """Format execution statistics.

        Args:
            iterations: Number of iterations.
            elapsed_time: Elapsed time in seconds.
            tokens_used: Number of tokens used.
            success: Whether verification succeeded.

        Returns:
            Table with statistics.
        """
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
        """Format iteration summary.

        Args:
            iteration: Iteration number.
            status: Status message.
            error_count: Number of errors.

        Returns:
            Formatted text.
        """
        status_icons = {
            "success": "[green]✓[/green]",
            "failed": "[red]✗[/red]",
            "retry": "[yellow]⟳[/yellow]",
            "running": "[blue]●[/blue]",
        }
        icon = status_icons.get(status, "○")

        result = Text()
        result.append(f"{icon} ", style="bold")
        result.append(f"Iteration {iteration}: ", style="bold white")
        result.append(status)

        if error_count > 0:
            result.append(f" ({error_count} errors)", style="red")

        return result

    def format_welcome(self) -> Panel:
        """Format welcome message.

        Returns:
            Welcome panel.
        """
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
        """Format help message.

        Returns:
            Help panel.
        """
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
        """Initialize progress formatter.

        Args:
            console: Rich console instance.
        """
        self.console = console or Console()

    def format_verification_progress(self, stage: str, detail: Optional[str] = None) -> Text:
        """Format verification progress message.

        Args:
            stage: Current stage (generating, verifying, etc.)
            detail: Optional detail message.

        Returns:
            Formatted progress text.
        """
        stages = {
            "initializing": ("[blue]●[/blue]", "Initializing"),
            "generating": ("[cyan]◐[/cyan]", "Generating proof"),
            "verifying": ("[yellow]◑[/yellow]", "Verifying with Lean"),
            "fixing": ("[magenta]◑[/magenta]", "Fixing errors"),
            "complete": ("[green]✓[/green]", "Complete"),
            "failed": ("[red]✗[/red]", "Failed"),
        }

        icon, label = stages.get(stage, ("○", stage))
        result = Text()
        result.append(f"{icon} ", style="bold")
        result.append(f"{label}", style="bold white")

        if detail:
            result.append(f": {detail}", style="dim")

        return result


def format_timestamp(ts: Optional[float] = None) -> str:
    """Format timestamp for display.

    Args:
        ts: Unix timestamp. Uses current time if None.

    Returns:
        Formatted timestamp string.
    """
    if ts is None:
        ts = time.time()
    return time.strftime("%H:%M:%S", time.localtime(ts))
