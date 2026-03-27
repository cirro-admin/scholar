"""
hitl/checkpoints.py
─────────────────────
Human-in-the-loop approval gates.

Checkpoint 1 — query approval  (before research crawl)
Checkpoint 2 — outline approval (inside the LangGraph orchestrator)

Both print clearly formatted summaries and collect user edits via stdin.
In a web/API deployment, replace the input() calls with async event hooks.
"""

from __future__ import annotations
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


# ── Checkpoint 1: Query approval ──────────────────────────────────────────────

def checkpoint_1_queries(queries: list[str]) -> list[str]:
    """
    Display proposed research queries and let the user approve, edit, or remove them.
    Returns the final approved list of queries.

    Commands:
      Enter          → approve all as-is
      d <number>     → delete query by number  (e.g. "d 3")
      a <query>      → add a new query         (e.g. "a transformer attention mechanisms")
      e <num> <text> → edit query by number    (e.g. "e 2 new query text here")
      done           → confirm and continue
    """
    console.print(Panel(
        "[bold]Checkpoint 1 — Research Query Approval[/bold]\n"
        "Review the planned queries before any API calls are made.\n"
        "Commands: [cyan]Enter[/cyan] approve all  "
        "[cyan]d N[/cyan] delete  [cyan]a text[/cyan] add  "
        "[cyan]e N text[/cyan] edit  [cyan]done[/cyan] confirm",
        border_style="yellow",
    ))

    working = list(queries)

    while True:
        _print_query_table(working)
        cmd = input("\n> ").strip()

        if cmd == "" or cmd.lower() == "done":
            if not working:
                console.print("[red]No queries remaining — add at least one.[/red]")
                continue
            break

        parts = cmd.split(None, 2)

        if parts[0].lower() == "d" and len(parts) >= 2:
            try:
                idx = int(parts[1]) - 1
                removed = working.pop(idx)
                console.print(f"[dim]Removed: {removed}[/dim]")
            except (ValueError, IndexError):
                console.print("[red]Usage: d <number>[/red]")

        elif parts[0].lower() == "a" and len(parts) >= 2:
            new_q = cmd[2:].strip()
            working.append(new_q)
            console.print(f"[green]Added: {new_q}[/green]")

        elif parts[0].lower() == "e" and len(parts) >= 3:
            try:
                idx      = int(parts[1]) - 1
                new_text = parts[2]
                working[idx] = new_text
                console.print(f"[green]Updated query {idx+1}[/green]")
            except (ValueError, IndexError):
                console.print("[red]Usage: e <number> <new text>[/red]")

        else:
            console.print("[dim]Unknown command. Press Enter to approve, or use d/a/e/done.[/dim]")

    console.print(f"\n[green]Approved {len(working)} queries — starting research.[/green]\n")
    return working


def _print_query_table(queries: list[str]) -> None:
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    table.add_column("#",     width=4)
    table.add_column("Query", min_width=50)
    for i, q in enumerate(queries, 1):
        table.add_row(str(i), q)
    console.print(table)


# ── Checkpoint 2: Outline approval ────────────────────────────────────────────
# Note: this is also implemented inside orchestrator.py's node_hitl_outline.
# This standalone version is provided for use outside the LangGraph graph.

def checkpoint_2_outline(sections: list[dict]) -> list[dict]:
    """
    Display the proposed document outline and let the user approve or remove sections.

    sections: list of dicts with keys: key, title, brief
    Returns: approved (potentially trimmed) list of sections
    """
    console.print(Panel(
        "[bold]Checkpoint 2 — Outline Approval[/bold]\n"
        "Review the document structure before the full draft begins.\n"
        "Commands: [cyan]Enter[/cyan] approve all  "
        "[cyan]d N[/cyan] remove section  [cyan]done[/cyan] confirm",
        border_style="yellow",
    ))

    working = list(sections)

    while True:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
        table.add_column("#",       width=4)
        table.add_column("Section", width=28)
        table.add_column("Brief",   min_width=40)
        for i, sec in enumerate(working, 1):
            table.add_row(str(i), sec["title"], sec["brief"][:80] + "...")
        console.print(table)

        cmd = input("\n> ").strip()

        if cmd == "" or cmd.lower() == "done":
            break

        parts = cmd.split(None, 1)
        if parts[0].lower() == "d" and len(parts) >= 2:
            try:
                idx     = int(parts[1]) - 1
                removed = working.pop(idx)
                console.print(f"[dim]Removed: {removed['title']}[/dim]")
            except (ValueError, IndexError):
                console.print("[red]Usage: d <number>[/red]")
        else:
            console.print("[dim]Unknown command.[/dim]")

    console.print(f"\n[green]Outline approved — {len(working)} sections — starting draft.[/green]\n")
    return working
