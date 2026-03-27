"""
main.py
───────
Scholar CLI — fully wired pipeline.

Usage:
    python main.py run --topic "Impact of LLMs on scientific publishing" --mode thesis
    python main.py run --topic "Rust vs Go for systems programming" --mode tech_doc
    python main.py modes
"""

import os
import typer
from rich.console import Console
from rich.panel import Panel

from config.modes import list_modes, get_mode
from config.sources import load_source_config
from hitl.checkpoints import checkpoint_1_queries

app = Console()
cli = typer.Typer(help="Scholar — adaptive research & writing agent", add_completion=False)


@cli.command()
def run(
    topic:      str = typer.Option(..., "--topic", "-t", help="Research topic"),
    mode:       str = typer.Option(..., "--mode",  "-m", help="Output mode"),
    sources:    str = typer.Option("all", "--sources", "-s", help="Comma-separated sources or 'all'"),
    output_dir: str = typer.Option("./outputs", "--out", "-o", help="Output directory"),
    pdf_paths:  str = typer.Option("", "--pdfs", "-p", help="Comma-separated PDF paths to ingest"),
):
    """Run the full Scholar pipeline: research → HITL → write → HITL → output."""
    from research_agent.agent import run_research
    from writing_workflow.orchestrator import run_writing_workflow

    mode_cfg = get_mode(mode)
    enabled  = None if sources == "all" else sources.split(",")
    src_cfg  = load_source_config(enabled_sources=enabled)

    for w in src_cfg.validate():
        app.print(f"[yellow]⚠  {w}[/yellow]")

    app.print(Panel(
        f"[bold green]Scholar[/bold green] — {mode_cfg.display_name}\n\n"
        f"Topic   : {topic}\n"
        f"Sources : {', '.join(src_cfg.enabled_sources)}\n"
        f"Depth   : {mode_cfg.depth_level}  |  "
        f"Sections: {len(mode_cfg.structure_template)}  |  "
        f"Eval ≥  : {mode_cfg.eval_threshold}",
        border_style="green",
    ))

    # Ingest PDFs if provided
    pdf_chunks = []
    if pdf_paths:
        from research_agent.tools.pdf_reader import read_pdfs
        paths = [p.strip() for p in pdf_paths.split(",") if p.strip()]
        app.print(f"[dim]Ingesting {len(paths)} PDF(s)...[/dim]")
        pdf_chunks = read_pdfs(paths)
        app.print(f"[dim]  → {len(pdf_chunks)} chunks extracted[/dim]")

    # Run research agent with HITL query approval
    bundle = run_research(
        topic=topic,
        mode=mode_cfg,
        sources=src_cfg,
        pdf_chunks=pdf_chunks,
        hitl_approve_queries=checkpoint_1_queries,
    )

    app.print(f"\n[dim]Research complete — {len(bundle.source_notes)} notes, "
              f"{len(bundle.topic_clusters)} clusters[/dim]")

    # Run writing workflow (HITL outline approval is inside the graph)
    output = run_writing_workflow(
        bundle=bundle,
        mode=mode_cfg,
        api_key=src_cfg.google_api_key,
        output_dir=output_dir,
    )

    app.print(Panel(
        f"[bold green]Done![/bold green]\n\n"
        f"File       : {output.file_path}\n"
        f"Format     : {output.format}\n"
        f"Word count : {output.word_count:,}\n"
        f"Sections   : {output.section_count}",
        border_style="green",
    ))


@cli.command()
def modes():
    """List all available output modes."""
    from rich.table import Table
    table = Table(title="Available output modes", show_header=True)
    table.add_column("Mode",         style="cyan")
    table.add_column("Display name")
    table.add_column("Format")
    table.add_column("Sections", justify="right")
    table.add_column("Depth")
    table.add_column("Eval ≥", justify="right")
    for name in list_modes():
        m = get_mode(name)
        table.add_row(
            name, m.display_name, m.output_format,
            str(len(m.structure_template)), m.depth_level,
            str(m.eval_threshold),
        )
    app.print(table)


if __name__ == "__main__":
    cli()
