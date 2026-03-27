#!/usr/bin/env python3
"""
scripts/debug_gemini.py
────────────────────────
Diagnoses GOOGLE_API_KEY issues and auto-detects the right Gemini model.
Run from repo root: python scripts/debug_gemini.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
console = Console()

console.print("\n[bold]Diagnosing GOOGLE_API_KEY...[/bold]\n")

# ── 1. .env file ──────────────────────────────────────────────────────────────
from pathlib import Path
env_path = Path(".env")
console.print(f"1. Looking for .env in: [cyan]{Path('.').resolve()}[/cyan]")
if not env_path.exists():
    console.print("   [red]✗ .env not found — run from the repo root.[/red]\n")
    sys.exit(1)
console.print("   [green]✓ .env found[/green]")

# ── 2. Raw key check ──────────────────────────────────────────────────────────
console.print("\n2. Reading .env...")
raw_key = None
for line in env_path.read_text().splitlines():
    if line.strip().startswith("GOOGLE_API_KEY"):
        val = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not val or "your_" in val:
            console.print("   [red]✗ Key is empty or still a placeholder.[/red]\n")
            sys.exit(1)
        elif " " in val:
            console.print("   [red]✗ Key has a space — copy/paste issue.[/red]\n")
            sys.exit(1)
        elif not val.startswith("AIza"):
            console.print(f"   [yellow]⚠  Doesn't start with 'AIza' (starts: '{val[:6]}'). May be wrong key.[/yellow]")
        else:
            console.print(f"   [green]✓ Key looks valid (length {len(val)})[/green]")
        raw_key = val
        break

if not raw_key:
    console.print("   [red]✗ GOOGLE_API_KEY line not found in .env[/red]\n")
    sys.exit(1)

# ── 3. dotenv load ────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(override=True)
env_key = os.getenv("GOOGLE_API_KEY", "")
console.print("\n3. dotenv load: " + ("[green]✓ loaded[/green]" if env_key else "[red]✗ failed[/red]"))

# ── 4. Auto-detect available model ────────────────────────────────────────────
console.print("\n4. Detecting available Gemini models...")
try:
    import google.generativeai as genai
    genai.configure(api_key=env_key)

    # Priority order — newest / best first
    CANDIDATES = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ]

    available = [m.name.replace("models/", "") for m in genai.list_models()
                 if "generateContent" in m.supported_generation_methods]

    console.print(f"   Models on your account that support generateContent:")
    for m in available:
        tag = " [green]← will use this[/green]" if any(m == c for c in CANDIDATES) else ""
        console.print(f"     • {m}{tag}")

    # Pick best available
    chosen = next((c for c in CANDIDATES if c in available), None)

    if not chosen and available:
        chosen = available[0]
        console.print(f"\n   [yellow]No standard candidate matched — falling back to: {chosen}[/yellow]")

    if not chosen:
        console.print("   [red]✗ No generateContent-capable models found.[/red]\n")
        sys.exit(1)

    console.print(f"\n   [green]✓ Using: {chosen}[/green]")

except Exception as e:
    console.print(f"   [red]✗ Could not list models: {e}[/red]\n")
    sys.exit(1)

# ── 5. Test call with detected model ──────────────────────────────────────────
console.print(f"\n5. Testing API call with {chosen}...")
try:
    m = genai.GenerativeModel(chosen)
    r = m.generate_content("Reply with just the word PONG")
    if "PONG" in r.text.upper():
        console.print(f"   [green]✓ {chosen} responded correctly — key works![/green]")
    else:
        console.print(f"   [green]✓ Responded: {r.text[:60]}[/green]")
except Exception as e:
    console.print(f"   [red]✗ API call failed: {e}[/red]\n")
    sys.exit(1)

# ── 6. Write detected model to .env ───────────────────────────────────────────
console.print(f"\n6. Saving detected model to .env as GEMINI_MODEL={chosen}...")
env_text = env_path.read_text()
if "GEMINI_MODEL=" in env_text:
    import re
    env_text = re.sub(r"GEMINI_MODEL=.*", f"GEMINI_MODEL={chosen}", env_text)
else:
    env_text += f"\nGEMINI_MODEL={chosen}\n"
env_path.write_text(env_text)
console.print(f"   [green]✓ Saved. All Scholar scripts will now use {chosen}.[/green]")

console.print("\n[bold green]✓ Gemini key is working. You are ready to run Scholar.[/bold green]\n")
