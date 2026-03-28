"""
research_agent/tools/web_search.py
───────────────────────────────────
Web search tool — Perplexity primary, SerpAPI fallback.
Returns a normalised list of SearchResult objects.
"""

from __future__ import annotations
from utils.rate_limiter import wait_for
import os, requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    title:   str
    url:     str
    snippet: str
    source:  str   # "perplexity" | "serpapi"


# ── Perplexity ────────────────────────────────────────────────────────────────

def _perplexity_search(query: str, api_key: str, num_results: int = 5) -> list[SearchResult]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Return a factual, source-rich answer."},
            {"role": "user",   "content": query},
        ],
        "return_citations": True,
        "max_tokens": 1024,
    }
    resp = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers, json=payload, timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    content  = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])

    results = []
    for i, url in enumerate(citations[:num_results]):
        results.append(SearchResult(
            title=f"Source {i+1}",
            url=url,
            snippet=content[:400] if i == 0 else "",
            source="perplexity",
        ))
    # Always include the full answer as a synthetic result
    results.insert(0, SearchResult(
        title=f"Perplexity answer: {query[:60]}",
        url="perplexity://answer",
        snippet=content,
        source="perplexity",
    ))
    return results


# ── SerpAPI fallback ──────────────────────────────────────────────────────────

def _serpapi_search(query: str, api_key: str, num_results: int = 5) -> list[SearchResult]:
    params = {
        "q": query,
        "api_key": api_key,
        "num": num_results,
        "engine": "google",
    }
    resp = requests.get("https://serpapi.com/search", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("organic_results", [])[:num_results]:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("link", ""),
            snippet=item.get("snippet", ""),
            source="serpapi",
        ))
    return results


# ── Public interface ──────────────────────────────────────────────────────────

def search(
    query: str,
    perplexity_key: Optional[str] = None,
    serpapi_key: Optional[str]    = None,
    num_results: int = 5,
) -> list[SearchResult]:
    """
    Search the web. Tries Perplexity first; falls back to SerpAPI.
    Raises RuntimeError if neither key is available.
    """
    pk = perplexity_key or os.getenv("PERPLEXITY_API_KEY", "")
    sk = serpapi_key    or os.getenv("SERPAPI_KEY", "")

    if pk:
        try:
            return _perplexity_search(query, pk, num_results)
        except Exception as e:
            print(f"[web_search] Perplexity failed ({e}), trying SerpAPI...")

    if sk:
        return _serpapi_search(query, sk, num_results)

    raise RuntimeError(
        "No web search key available. Set PERPLEXITY_API_KEY or SERPAPI_KEY in .env"
    )
