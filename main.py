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
    output_dir: str   = typer.Option("./outputs", "--out", "-o", help="Output directory"),
    skip_sections: str = typer.Option("", "--skip", help="Comma-separated section keys to skip e.g. 'references,appendices'"),
    pdf_paths:  str = typer.Option("", "--pdfs", "-p", help="Comma-separated PDF paths to ingest"),
    # Document metadata
    author:     str = typer.Option("", "--author",     help="Author name"),
    university: str = typer.Option("", "--university", help="University name (thesis)"),
    department: str = typer.Option("", "--department", help="Department (thesis)"),
    supervisor: str = typer.Option("", "--supervisor", help="Supervisor name (thesis)"),
    student_id: str = typer.Option("", "--student-id", help="Student ID (thesis)"),
    degree:     str = typer.Option("", "--degree",     help="Degree title e.g. 'MSc Computer Science'"),
    affiliation:str = typer.Option("", "--affiliation",help="Affiliation (article)"),
    keywords:   str = typer.Option("", "--keywords",   help="Comma-separated keywords (article)"),
    journal_style: str = typer.Option("nature", "--journal-style",
                          help="Journal style: nature, ieee, apa, acm (article mode)"),
    submission_date: str = typer.Option("", "--submission-date",
                          help="Submission date e.g. 'May 2025' (thesis)"),
    organisation:str= typer.Option("", "--org",        help="Organisation name (report)"),
    fmt: str = typer.Option("", "--format", "-f", help="Override output format: docx, markdown, pdf, html"),
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

    # Apply output format override
    if fmt:
        valid_formats = {"docx", "markdown", "pdf", "html"}
        if fmt not in valid_formats:
            app.print(f"[red]Unknown format '{fmt}'. Choose: {', '.join(valid_formats)}[/red]")
            raise typer.Exit(1)
        ext_map = {"docx": ".docx", "markdown": ".md", "pdf": ".pdf", "html": ".html"}
        mode_cfg.output_format  = fmt
        mode_cfg.file_extension = ext_map[fmt]
        app.print(f"[dim]Format override: {fmt}[/dim]")

    # Apply section skipping
    if skip_sections:
        skip_set = {s.strip() for s in skip_sections.split(",") if s.strip()}
        mode_cfg.structure_template = [s for s in mode_cfg.structure_template if s not in skip_set]
        app.print(f"[dim]Skipping sections: {skip_set}[/dim]")

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

    # Build document metadata from CLI args
    from writing_workflow.document_templates import DocumentMeta
    meta = DocumentMeta(
        author=author or "Author",
        university=university,
        department=department,
        supervisor=supervisor,
        student_id=student_id,
        degree=degree,
        affiliation=affiliation,
        keywords=[k.strip() for k in keywords.split(",") if k.strip()],
        organisation=organisation,
        journal_style=journal_style,
        submission_date=submission_date,
    )

    # Run writing workflow (HITL outline approval is inside the graph)
    output = run_writing_workflow(
        bundle=bundle,
        mode=mode_cfg,
        api_key=src_cfg.google_api_key,
        output_dir=output_dir,
        meta=meta,
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
    """List all available output modes and journal styles."""
    from rich.table import Table
    from writing_workflow.journal_styles import JOURNAL_STYLES

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

    app.print("[bold]Available journal styles[/bold] (use with --mode article --journal-style NAME)")
    jt = Table(show_header=True)
    jt.add_column("Style",    style="cyan")
    jt.add_column("Name")
    jt.add_column("Citation")
    jt.add_column("Spacing")
    jt.add_column("Abstract")
    for name, js in JOURNAL_STYLES.items():
        default = " [green](default)[/green]" if name == "nature" else ""
        jt.add_row(name + default, js.display_name, js.citation_format,
                   str(js.line_spacing), js.abstract_format)
    app.print(jt)


if __name__ == "__main__":
    cli()
