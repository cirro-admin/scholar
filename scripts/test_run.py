#!/usr/bin/env python3
"""
scripts/test_run.py
────────────────────
Minimal end-to-end smoke test — uses only arXiv (no API key needed)
to verify the full pipeline works before a real run.

Run from repo root:  python scripts/test_run.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
console = Console()

def auto_approve(queries):
    """Skip HITL for the smoke test — auto-approve all queries."""
    console.print(f"[dim]  Auto-approving {len(queries)} queries (smoke test)[/dim]")
    return queries

console.print("\n[bold]Scholar smoke test[/bold]")
console.print("[dim]Topic: 'transformer attention mechanisms'  |  Mode: blog  |  Source: arxiv only[/dim]\n")

# Step 1: check Gemini key
api_key = os.getenv("GOOGLE_API_KEY", "")
if not api_key:
    console.print("[red]✗ GOOGLE_API_KEY not set — cannot run smoke test.[/red]")
    sys.exit(1)

# Step 2: pull a few arXiv papers directly (no other API keys needed)
console.print("[1/4] Fetching arXiv papers...")
from research_agent.tools.arxiv import search_papers
papers = search_papers("transformer attention mechanisms", max_results=4, use_semantic_scholar=False)
console.print(f"  → {len(papers)} papers fetched")
for p in papers[:2]:
    console.print(f"     • {p.title[:70]}")

# Step 3: synthesize
console.print("\n[2/4] Synthesizing research notes...")
from research_agent.synthesizer import synthesize
from config.sources import load_source_config
bundle = synthesize(
    topic="transformer attention mechanisms",
    mode_name="blog",
    papers=papers,
    api_key=api_key,
)
console.print(f"  → {len(bundle.source_notes)} notes")
console.print(f"  → {len(bundle.topic_clusters)} clusters: {list(bundle.topic_clusters.keys())[:3]}")
console.print(f"  → {len(bundle.human_voices)} human voices extracted")

# Step 4: generate outline only (skip full draft to save tokens)
console.print("\n[3/4] Generating outline...")
from config.modes import get_mode
from writing_workflow.outline_gen import generate_outline
mode    = get_mode("blog")
outline = generate_outline(bundle, mode, api_key)
console.print(f"  → Title: {outline.title}")
for sec in outline.sections:
    console.print(f"     • {sec.title}")

# Step 5: draft first section only
console.print("\n[4/4] Drafting first section (hook)...")
from writing_workflow.section_drafter import draft_section
from writing_workflow.evaluator import evaluate_section
first = outline.sections[0]
drafted = draft_section(first, bundle, mode, api_key=api_key)
console.print(f"  → {drafted.word_count} words drafted")

result = evaluate_section(drafted, mode, api_key)
console.print(f"  → Overall score : {result.overall_score:.2f}  (threshold: {mode.eval_threshold})")
console.print(f"  → Humanization  : {result.humanization_score:.2f}")
console.print(f"  → AI-signature  : {result.ai_signature_score:.2f}")
if result.flagged_phrases:
    console.print(f"  → Flagged       : {result.flagged_phrases}")
else:
    console.print(f"  → No AI phrases detected")

console.print(f"\n[bold green]Smoke test passed.[/bold green]")
console.print("\nFirst section preview:")
console.print("─" * 60)
console.print(drafted.content[:600])
console.print("─" * 60)
console.print("\n[dim]Run the full pipeline:[/dim]")
console.print("  [cyan]python main.py run --topic 'Your topic' --mode blog --sources web,arxiv[/cyan]\n")
