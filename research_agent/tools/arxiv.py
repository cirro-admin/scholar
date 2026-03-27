"""
research_agent/tools/arxiv.py
──────────────────────────────
Academic paper search via arXiv and Semantic Scholar.
Returns normalised Paper objects with title, abstract, authors, year, url.
"""

from __future__ import annotations
import os, time, requests
import arxiv as arxiv_lib
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Paper:
    title:    str
    abstract: str
    authors:  list[str]
    year:     int
    url:      str
    source:   str   # "arxiv" | "semantic_scholar"
    doi:      str = ""
    citation_count: int = 0




def _clean_query(query: str) -> str:
    import re as _re
    query = _re.sub(r'\w+:\S+', '', query)
    query = _re.sub(r'\b(OR|AND|NOT)\b', '', query)
    query = _re.sub(r'[()\"\']', '', query)
    return _re.sub(r'\s+', ' ', query).strip()[:200]


# ── arXiv ─────────────────────────────────────────────────────────────────────

def search_arxiv(query: str, max_results: int = 8) -> list[Paper]:
    """Search arXiv and return Paper objects."""
    client = arxiv_lib.Client()
    search = arxiv_lib.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv_lib.SortCriterion.Relevance,
    )
    papers = []
    for result in client.results(search):
        papers.append(Paper(
            title=result.title,
            abstract=result.summary,
            authors=[a.name for a in result.authors],
            year=result.published.year,
            url=result.entry_id,
            source="arxiv",
            doi=result.doi or "",
        ))
    return papers


# ── Semantic Scholar ──────────────────────────────────────────────────────────

def search_semantic_scholar(
    query: str,
    api_key: Optional[str] = None,
    max_results: int = 8,
) -> list[Paper]:
    """Search Semantic Scholar. Works unauthenticated but is rate-limited."""
    key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    headers = {"x-api-key": key} if key else {}

    params = {
        "query": _clean_query(query),
        "limit": max_results,
        "fields": "title,abstract,authors,year,externalIds,citationCount,url",
    }
    resp = requests.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params=params, headers=headers, timeout=30,
    )
    resp.raise_for_status()

    papers = []
    for item in resp.json().get("data", []):
        papers.append(Paper(
            title=item.get("title", ""),
            abstract=item.get("abstract") or "",
            authors=[a["name"] for a in item.get("authors", [])],
            year=item.get("year") or 0,
            url=item.get("url") or
                f"https://www.semanticscholar.org/paper/{item.get('paperId','')}",
            source="semantic_scholar",
            doi=item.get("externalIds", {}).get("DOI", ""),
            citation_count=item.get("citationCount", 0),
        ))
        time.sleep(0.1)   # respect rate limit on unauthenticated calls
    return papers


# ── Public interface ──────────────────────────────────────────────────────────

def search_papers(
    query: str,
    max_results: int = 8,
    use_semantic_scholar: bool = True,
    api_key: Optional[str] = None,
) -> list[Paper]:
    """
    Search both arXiv and (optionally) Semantic Scholar.
    Deduplicates by title. Returns papers sorted by citation count desc.
    """
    results: list[Paper] = []

    try:
        results += search_arxiv(query, max_results)
    except Exception as e:
        print(f"[arxiv] Search failed: {e}")

    if use_semantic_scholar:
        try:
            results += search_semantic_scholar(query, api_key, max_results)
        except Exception as e:
            print(f"[semantic_scholar] Search failed: {e}")

    # Deduplicate by normalised title
    seen, deduped = set(), []
    for p in results:
        key = p.title.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(p)

    return sorted(deduped, key=lambda p: p.citation_count, reverse=True)
