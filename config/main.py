"""
main.py
───────
Scholar CLI — run the full research + writing pipeline from the terminal.

Usage:
    python main.py --topic "Impact of LLMs on scientific publishing" --mode thesis
    python main.py --topic "Rust vs Go for systems programming" --mode tech_doc
    python main.py --topic "The future of remote work" --mode report
"""

import typer
from rich.console import Console
from rich.table import Table
from config.modes import list_modes, get_mode
from config.sources import load_source_config

app = Console()
cli = typer.Typer(help="Scholar — adaptive research & writing agent")


@cli.command()
def run(
    topic: str = typer.Option(..., "--topic", "-t", help="Research topic"),
    mode: str  = typer.Option(..., "--mode",  "-m", help="Output mode (thesis/article/blog/tech_doc/report)"),
    sources: str = typer.Option("all", "--sources", "-s", help="Comma-separated sources to enable, or 'all'"),
    output_dir: str = typer.Option("./outputs", "--out", "-o", help="Directory for output files"),
):
    """Run the full Scholar pipeline: research → HITL → write → HITL → output."""

    # Validate mode
    mode_cfg = get_mode(mode)  # raises ValueError with helpful message if invalid

    # Load source config
    enabled = None if sources == "all" else sources.split(",")
    src_cfg = load_source_config(enabled_sources=enabled)

    # Show warnings for missing keys
    warnings = src_cfg.validate()
    for w in warnings:
        app.print(f"[yellow]⚠  {w}[/yellow]")

    app.print(f"\n[bold green]Scholar[/bold green] — {mode_cfg.display_name}")
    app.print(f"Topic    : {topic}")
    app.print(f"Sources  : {', '.join(src_cfg.enabled_sources)}")
    app.print(f"Depth    : {mode_cfg.depth_level}  |  "
              f"Eval threshold : {mode_cfg.eval_threshold}  |  "
              f"Max rounds : {mode_cfg.max_research_rounds}\n")

    # TODO: wire up research agent and writing workflow
    app.print("[dim]Pipeline not yet connected — populate research_agent/ and writing_workflow/ next.[/dim]")


@cli.command()
def modes():
    """List all available output modes."""
    table = Table(title="Available output modes")
    table.add_column("Mode", style="cyan")
    table.add_column("Display name")
    table.add_column("Format")
    table.add_column("Depth")
    table.add_column("Citation")
    for name in list_modes():
        m = get_mode(name)
        table.add_row(name, m.display_name, m.output_format, m.depth_level, m.citation_style)
    app.print(table)


if __name__ == "__main__":
    cli()
