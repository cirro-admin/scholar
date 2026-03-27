#!/usr/bin/env python3
"""
scripts/check_keys.py
──────────────────────
Verifies all API keys are reachable before a full run.
Uses GEMINI_MODEL from .env (set by debug_gemini.py) — no hardcoded model names.
Run from repo root: python scripts/check_keys.py
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def check_gemini():
    key   = os.getenv("GOOGLE_API_KEY", "")
    model = os.getenv("GEMINI_MODEL", "")
    if not key:
        return False, "GOOGLE_API_KEY not set"
    if not model:
        return None, "Key set but GEMINI_MODEL not detected yet — run scripts/debug_gemini.py first"
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        r = genai.GenerativeModel(model).generate_content("Reply with just the word PONG")
        if "PONG" in r.text.upper():
            return True, f"{model} responded"
        return True, f"{model}: {r.text[:40]}"
    except Exception as e:
        return False, str(e)[:80]


def check_perplexity():
    key = os.getenv("PERPLEXITY_API_KEY", "")
    if not key:
        return None, "Not set (optional — SerpAPI is fallback)"
    try:
        import requests
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "sonar", "messages": [{"role": "user", "content": "1+1=?"}], "max_tokens": 5},
            timeout=15,
        )
        resp.raise_for_status()
        return True, "API reachable"
    except Exception as e:
        return False, str(e)[:80]


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
        return True, f"{len(resp.json().get('items', []))} result(s)"
    except Exception as e:
        return False, str(e)[:80]


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
        r = resp.json()["rate"]
        return True, f"Rate limit: {r['remaining']:,}/{r['limit']:,} remaining"
    except Exception as e:
        return False, str(e)[:80]


def check_serpapi():
    key = os.getenv("SERPAPI_KEY", "")
    if not key:
        return None, "Not set (optional)"
    try:
        import requests
        resp = requests.get(
            "https://serpapi.com/account",
            params={"api_key": key}, timeout=15,
        )
        resp.raise_for_status()
        return True, f"Account OK"
    except Exception as e:
        return False, str(e)[:80]


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
        mode = "authenticated (10 req/sec)" if key else "unauthenticated (1 req/sec)"
        return True, f"API reachable — {mode}"
    except Exception as e:
        return False, str(e)[:80]


# ── Run ───────────────────────────────────────────────────────────────────────

console.print("\n[bold]Checking Scholar API keys...[/bold]\n")

checks = [
    ("Google Gemini",     check_gemini,           True),
    ("Perplexity",        check_perplexity,        True),
    ("YouTube Data API",  check_youtube,           False),
    ("GitHub",            check_github,            False),
    ("SerpAPI",           check_serpapi,           False),
    ("Semantic Scholar",  check_semantic_scholar,  False),
]

table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
table.add_column("Service",  width=22)
table.add_column("Status",   width=6)
table.add_column("Required", width=10)
table.add_column("Detail")

any_required_failed = False
for label, fn, required in checks:
    ok, detail = fn()
    status    = "[green]✓[/green]" if ok is True else "[red]✗[/red]" if ok is False else "[dim]-[/dim]"
    req_label = "[red]required[/red]" if required else "[dim]optional[/dim]"
    if ok is False and required:
        any_required_failed = True
    table.add_row(label, status, req_label, detail)
    time.sleep(0.05)

console.print(table)

if any_required_failed:
    console.print("[red bold]✗ One or more required keys are missing or invalid.[/red bold]")
    console.print("[dim]Run: python scripts/debug_gemini.py  for detailed diagnosis.[/dim]\n")
    sys.exit(1)
else:
    console.print("[green bold]✓ All required keys OK — Scholar is ready.[/green bold]")
    console.print("\n[dim]Next:[/dim] [cyan]python scripts/test_run.py[/cyan]\n")
