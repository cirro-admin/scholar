"""
utils/llm.py
─────────────
Centralised LLM helper using the new google-genai SDK.
All modules import from here — no direct SDK calls scattered around the codebase.
"""

from __future__ import annotations
import os, json, re
from google import genai
from google.genai import types


def _client() -> genai.Client:
    return genai.Client(api_key=os.environ.get("GOOGLE_API_KEY", ""))


def _model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def generate(prompt: str, system: str = "", temperature: float = 1.0) -> str:
    """Simple text generation. Returns the response text."""
    client = _client()
    cfg    = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system or None,
    )
    response = client.models.generate_content(
        model=_model(),
        contents=prompt,
        config=cfg,
    )
    return response.text.strip()


def generate_json(prompt: str, system: str = "", retries: int = 2) -> dict | list:
    """
    Generate and parse JSON. Strips markdown fences if present.
    Retries up to `retries` times on parse failure.
    Raises ValueError if all attempts fail.
    """
    for attempt in range(retries + 1):
        raw = generate(prompt, system=system)
        # Strip markdown fences
        clean = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        clean = re.sub(r"\s*```$", "", clean.strip(), flags=re.MULTILINE)
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            if attempt < retries:
                # Ask model to fix its own output
                prompt = f"Your previous response was not valid JSON. Return ONLY valid JSON, no prose, no fences.\n\nOriginal prompt:\n{prompt}"
            else:
                raise ValueError(f"Could not parse JSON after {retries+1} attempts. Raw: {raw[:200]}")


def list_available_models() -> list[str]:
    """Return model names that support generateContent."""
    client = _client()
    return [
        m.name.replace("models/", "")
        for m in client.models.list()
        if hasattr(m, "supported_actions") and "generateContent" in (m.supported_actions or [])
        or hasattr(m, "supported_generation_methods") and "generateContent" in (m.supported_generation_methods or [])
    ]
