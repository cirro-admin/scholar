"""
utils/llm.py
─────────────
Centralised LLM helper.

Primary:  Claude (Anthropic API) — claude-sonnet-4-6 for drafting, haiku for fast tasks
Fallback: Gemini (Google) — 2.5-flash → 2.0-flash → 1.5-flash

Both support retry with exponential backoff on 503/429.
"""

from __future__ import annotations
import os, json, re, time
from dotenv import load_dotenv
load_dotenv(override=True)


# ── Model config ──────────────────────────────────────────────────────────────

# Claude models — primary
CLAUDE_MAIN_MODEL  = os.environ.get("CLAUDE_MODEL",       "claude-sonnet-4-6")
CLAUDE_FAST_MODEL  = os.environ.get("CLAUDE_FAST_MODEL",  "claude-haiku-4-5-20251001")

# Gemini models — fallback chain
GEMINI_FALLBACK_CHAIN = [
    os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


# ── Claude (primary) ──────────────────────────────────────────────────────────

def _generate_claude(
    prompt: str,
    system: str = "",
    fast: bool = False,
    max_retries: int = 3,
    retry_delay: float = 8.0,
) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("Run: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

    client = anthropic.Anthropic(api_key=api_key)
    model  = CLAUDE_FAST_MODEL if fast else CLAUDE_MAIN_MODEL
    kwargs = dict(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        kwargs["system"] = system

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            msg = client.messages.create(**kwargs)
            return msg.content[0].text.strip()
        except Exception as e:
            last_error = e
            err_str    = str(e)
            if "529" in err_str or "529" in err_str or "overloaded" in err_str.lower() \
               or "529" in err_str or "rate_limit" in err_str.lower() or "529" in err_str:
                wait = retry_delay * (2 ** (attempt - 1))
                print(f"[llm] Claude {model} busy "
                      f"(attempt {attempt}/{max_retries}) — retrying in {wait:.0f}s...")
                time.sleep(wait)
            else:
                raise   # non-retryable — surface immediately

    raise RuntimeError(f"Claude failed after {max_retries} attempts: {last_error}")


# ── Gemini (fallback) ─────────────────────────────────────────────────────────

def _generate_gemini(
    prompt: str,
    system: str = "",
    temperature: float = 1.0,
    max_retries: int = 3,
    retry_delay: float = 10.0,
) -> str:
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    if not google_key:
        raise RuntimeError("GOOGLE_API_KEY not set — Gemini fallback unavailable")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=google_key)
    cfg    = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system or None,
    )

    seen = set()
    chain = [m for m in GEMINI_FALLBACK_CHAIN if not (m in seen or seen.add(m))]

    last_error = None
    for model in chain:
        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt, config=cfg,
                )
                print(f"[llm] Gemini fallback used: {model}")
                return response.text.strip()
            except Exception as e:
                last_error = e
                err_str    = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str \
                   or "429" in err_str or "RATE_LIMIT" in err_str:
                    wait = retry_delay * (2 ** (attempt - 1))
                    print(f"[llm] Gemini {model} busy "
                          f"(attempt {attempt}/{max_retries}) — retrying in {wait:.0f}s...")
                    time.sleep(wait)
                else:
                    break   # non-retryable for this model — try next

    raise RuntimeError(f"All Gemini fallbacks failed. Last: {last_error}")


# ── Public interface ──────────────────────────────────────────────────────────

def generate(
    prompt: str,
    system: str = "",
    temperature: float = 1.0,
    fast: bool = False,
    max_retries: int = 3,
    retry_delay: float = 8.0,
) -> str:
    """
    Generate text. Tries Claude first, falls back to Gemini chain.
    Set fast=True for quick tasks (uses claude-haiku instead of claude-sonnet).
    """
    # ── Primary: Claude ───────────────────────────────────────────────────────
    try:
        return _generate_claude(prompt, system=system, fast=fast,
                                max_retries=max_retries, retry_delay=retry_delay)
    except RuntimeError as e:
        if "ANTHROPIC_API_KEY not set" in str(e):
            print("[llm] No ANTHROPIC_API_KEY — skipping Claude, using Gemini directly")
        else:
            print(f"[llm] Claude failed: {str(e)[:100]} — trying Gemini fallback...")

    # ── Fallback: Gemini ──────────────────────────────────────────────────────
    return _generate_gemini(prompt, system=system, temperature=temperature,
                            max_retries=max_retries, retry_delay=retry_delay)


def generate_json(
    prompt: str,
    system: str = "",
    fast: bool = False,
    retries: int = 2,
) -> dict | list:
    """
    Generate and parse JSON. Strips markdown fences automatically.
    Retries with a correction prompt on parse failure.
    """
    original_prompt = prompt
    for attempt in range(retries + 1):
        raw   = generate(prompt, system=system, fast=fast)
        clean = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        clean = re.sub(r"\s*```$",           "", clean.strip(), flags=re.MULTILINE)
        clean = re.sub(r"\s*//.*$",          "", clean, flags=re.MULTILINE)
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            if attempt < retries:
                prompt = (
                    f"Your previous response was not valid JSON. "
                    f"Return ONLY a valid JSON object or array — "
                    f"no prose, no markdown fences, no comments.\n\n"
                    f"Original task:\n{original_prompt}"
                )
            else:
                raise ValueError(
                    f"Could not parse JSON after {retries+1} attempts. "
                    f"Raw: {raw[:300]}"
                )


def list_available_models() -> list[str]:
    """Return available Gemini models (for debug_gemini.py)."""
    try:
        from google import genai
        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))
        result = []
        for m in client.models.list():
            methods = (getattr(m, "supported_generation_methods", None) or
                       getattr(m, "supported_actions", None) or [])
            if "generateContent" in methods:
                result.append(m.name.replace("models/", ""))
        return result
    except Exception:
        return []
