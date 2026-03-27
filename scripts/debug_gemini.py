#!/usr/bin/env python3
"""
scripts/debug_gemini.py
────────────────────────
Diagnoses GOOGLE_API_KEY and auto-detects the best available Gemini model.
Writes GEMINI_MODEL to .env on success.
Run from repo root: python scripts/debug_gemini.py
"""

import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from rich.console import Console
console = Console()
console.print("\n[bold]Diagnosing GOOGLE_API_KEY...[/bold]\n")

from pathlib import Path
env_path = Path(".env")

# 1. .env exists?
console.print(f"1. Looking for .env in: [cyan]{Path('.').resolve()}[/cyan]")
if not env_path.exists():
    console.print("   [red]✗ .env not found — run from the repo root.[/red]\n"); sys.exit(1)
console.print("   [green]✓ .env found[/green]")

# 2. Key shape check
console.print("\n2. Reading .env...")
raw_key = None
for line in env_path.read_text().splitlines():
    if line.strip().startswith("GOOGLE_API_KEY"):
        val = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not val or "your_" in val:
            console.print("   [red]✗ Key is empty or still a placeholder.[/red]\n"); sys.exit(1)
        elif " " in val:
            console.print("   [red]✗ Key has a space — copy/paste issue.[/red]\n"); sys.exit(1)
        elif not val.startswith("AIza"):
            console.print(f"   [yellow]⚠  Starts with '{val[:6]}' not 'AIza' — check key source[/yellow]")
        else:
            console.print(f"   [green]✓ Key shape OK (length {len(val)})[/green]")
        raw_key = val
        break

if not raw_key:
    console.print("   [red]✗ GOOGLE_API_KEY not found in .env[/red]\n"); sys.exit(1)

# 3. Auto-detect best available model
console.print("\n3. Detecting available Gemini models...")
PRIORITY = [
    "gemini-2.5-pro", "gemini-2.5-flash",
    "gemini-2.0-pro", "gemini-2.0-flash",
    "gemini-1.5-pro", "gemini-1.5-flash",
]
try:
    from google import genai
    client = genai.Client(api_key=raw_key)
    all_models = client.models.list()
    available  = []
    for m in all_models:
        name = m.name.replace("models/", "")
        methods = getattr(m, "supported_generation_methods", []) or \
                  getattr(m, "supported_actions", []) or []
        if "generateContent" in methods:
            available.append(name)

    console.print("   Models supporting generateContent on your account:")
    for m in available:
        tag = " [green]← candidate[/green]" if any(m == c for c in PRIORITY) else ""
        console.print(f"     • {m}{tag}")

    chosen = next((c for c in PRIORITY if c in available), None)
    if not chosen and available:
        chosen = available[0]
    if not chosen:
        console.print("   [red]✗ No suitable models found.[/red]\n"); sys.exit(1)

    console.print(f"\n   [green]✓ Selected: {chosen}[/green]")
except Exception as e:
    console.print(f"   [red]✗ Could not list models: {e}[/red]\n"); sys.exit(1)

# 4. Live test
console.print(f"\n4. Testing {chosen}...")
try:
    r = client.models.generate_content(model=chosen, contents="Reply with just the word PONG")
    text = r.text.strip() if hasattr(r, "text") else str(r)
    if "PONG" in text.upper():
        console.print(f"   [green]✓ {chosen} responded correctly[/green]")
    else:
        console.print(f"   [green]✓ Responded: {text[:60]}[/green]")
except Exception as e:
    console.print(f"   [red]✗ API call failed: {e}[/red]\n"); sys.exit(1)

# 5. Write to .env
console.print(f"\n5. Saving GEMINI_MODEL={chosen} to .env...")
env_text = env_path.read_text()
if "GEMINI_MODEL=" in env_text:
    env_text = re.sub(r"GEMINI_MODEL=.*", f"GEMINI_MODEL={chosen}", env_text)
else:
    env_text += f"\nGEMINI_MODEL={chosen}\n"
env_path.write_text(env_text)
console.print(f"   [green]✓ Saved[/green]")

console.print(f"\n[bold green]✓ Ready. All Scholar scripts will use {chosen}.[/bold green]\n")
