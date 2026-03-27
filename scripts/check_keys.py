#!/usr/bin/env python3
"""
scripts/check_keys.py
──────────────────────
Verifies all API keys are reachable before a full run.
Run from repo root: python scripts/check_keys.py
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

results = []

# ── 1. Google Gemini ──────────────────────────────────────────────────────────
def check_gemini():
    key = os.getenv("GOOGLE_API_KEY", "")
    if not key:
        return False, "Not set"
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        m = genai.GenerativeModel("gemini-1.5-flash")
        r = m.generate_content("Reply with just the word PONG")
        if "PONG" in r.text.upper():
            return True, "Gemini 1.5 Flash responded"
        return True, f"Responded: {r.text[:40]}"
    except Exception as e:
        return False, str(e)[:80]

# ── 2. Perplexity ─────────────────────────────────────────────────────────────
def check_perplexity():
    key = os.getenv("PERPLEXITY_API_KEY", "")
    if not key:
        return None, "Not set (optional fallback: SerpAPI)"
    try:
        import requests
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "sonar", "messages": [{"role": "user", "content": "What is 1+1?"}], "max_tokens": 10},
            timeout=15,
        )
        resp.raise_for_status()
        return True, "Search API reachable"
    except Exception as e:
        return False, str(e)[:80]

# ── 3. YouTube ────────────────────────────────────────────────────────────────
def check_youtube():
    key = os.getenv("YOUTUBE_API_KEY", "")
    if not key:
        return None, "Not set (YouTube source will be skipped)"
    try:
        import requests
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": "test", "maxResults": 1, "key": key},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return True, f"Found {len(items)} result(s)"
    except Exception as e:
        return False, str(e)[:80]

# ── 4. GitHub ─────────────────────────────────────────────────────────────────
def check_github():
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        return None, "Not set (unauthenticated: 60 req/hr)"
    try:
        import requests
        resp = requests.get(
            "https://api.github.com/rate_limit",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        remaining = resp.json()["rate"]["remaining"]
        limit     = resp.json()["rate"]["limit"]
        return True, f"Rate limit: {remaining:,}/{limit:,} remaining"
    except Exception as e:
        return False, str(e)[:80]

# ── 5. SerpAPI ────────────────────────────────────────────────────────────────
def check_serpapi():
    key = os.getenv("SERPAPI_KEY", "")
    if not key:
        return None, "Not set (optional)"
    try:
        import requests
        resp = requests.get(
            "https://serpapi.com/account",
            params={"api_key": key},
            timeout=15,
        )
        resp.raise_for_status()
        searches = resp.json().get("searches_per_month", "?")
        return True, f"Account OK, {searches} searches/month"
    except Exception as e:
        return False, str(e)[:80]

# ── 6. Semantic Scholar ───────────────────────────────────────────────────────
def check_semantic_scholar():
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    try:
        import requests
        headers = {"x-api-key": key} if key else {}
        resp = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": "test", "limit": 1, "fields": "title"},
            headers=headers, timeout=15,
        )
        resp.raise_for_status()
        label = "authenticated" if key else "unauthenticated (1 req/sec limit)"
        return True, f"API reachable — {label}"
    except Exception as e:
        return False, str(e)[:80]


# ── Run all checks ────────────────────────────────────────────────────────────
console.print("\n[bold]Checking Scholar API keys...[/bold]\n")

checks = [
    ("GOOGLE_API_KEY",           "Google Gemini",     check_gemini,           True),
    ("PERPLEXITY_API_KEY",       "Perplexity",        check_perplexity,       True),
    ("YOUTUBE_API_KEY",          "YouTube Data API",  check_youtube,          False),
    ("GITHUB_TOKEN",             "GitHub",            check_github,           False),
    ("SERPAPI_KEY",              "SerpAPI",           check_serpapi,          False),
    ("SEMANTIC_SCHOLAR_API_KEY", "Semantic Scholar",  check_semantic_scholar, False),
]

table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
table.add_column("Service",     width=22)
table.add_column("Status",      width=6)
table.add_column("Required",    width=10)
table.add_column("Detail")

any_required_failed = False
for env_var, label, fn, required in checks:
    ok, detail = fn()
    if ok is True:
        status = "[green]✓[/green]"
    elif ok is False:
        status = "[red]✗[/red]"
        if required:
            any_required_failed = True
    else:
        status = "[dim]-[/dim]"
    req_label = "[red]required[/red]" if required else "[dim]optional[/dim]"
    table.add_row(label, status, req_label, detail)
    time.sleep(0.1)

console.print(table)

if any_required_failed:
    console.print("\n[red bold]✗ One or more required keys are missing or invalid.[/red bold]")
    console.print("[dim]Edit your .env file and re-run this script.[/dim]\n")
    sys.exit(1)
else:
    console.print("\n[green bold]✓ All required keys OK — Scholar is ready to run.[/green bold]\n")
    console.print("Try a quick test:")
    console.print("  [cyan]python main.py run --topic 'Impact of AI on academic writing' --mode blog --sources web,arxiv[/cyan]\n")
