"""
research_agent/agent.py
────────────────────────
ReAct-loop research orchestrator.

Loop:
  1. Generate search queries from topic + mode context
  2. [HITL] User approves / edits queries
  3. Dispatch queries to all enabled sources in parallel
  4. Synthesize results into a ResearchBundle
  5. Reflect: are there coverage gaps? If yes and rounds remain → loop
  6. Return final ResearchBundle to the writing workflow
"""

from __future__ import annotations
from utils.llm import generate_json
import os, textwrap, concurrent.futures
from dataclasses import dataclass, field
from typing import Optional


from config.modes import OutputModeConfig
from config.sources import SourceConfig
from research_agent.synthesizer import ResearchBundle, synthesize
from research_agent.tools.web_search import SearchResult, search
from research_agent.tools.arxiv import Paper, search_papers
from research_agent.tools.youtube import VideoTranscript, search_and_fetch
from research_agent.tools.github import RepoSummary, search_repos
from research_agent.tools.pdf_reader import TextChunk


@dataclass
class AgentState:
    topic:          str
    mode:           OutputModeConfig
    sources:        SourceConfig
    round:          int = 0
    all_web:        list[SearchResult]    = field(default_factory=list)
    all_papers:     list[Paper]           = field(default_factory=list)
    all_videos:     list[VideoTranscript] = field(default_factory=list)
    all_repos:      list[RepoSummary]     = field(default_factory=list)
    all_pdf_chunks: list[TextChunk]       = field(default_factory=list)
    bundle:         Optional[ResearchBundle] = None


# ── Query generation ──────────────────────────────────────────────────────────


def _simplify_query(query: str) -> str:
    import re as _re
    query = _re.sub(r'\w+:\S+', '', query)
    query = _re.sub(r'\b(OR|AND|NOT)\b', '', query)
    query = _re.sub(r'[()\"\']', '', query)
    return _re.sub(r'\s+', ' ', query).strip()[:150]


def generate_queries(
    topic: str,
    mode: OutputModeConfig,
    previous_gaps: list[str] = (),
    api_key: str = "",
) -> list[str]:
    """Generate targeted search queries for the topic and output mode."""
    gaps_section = ""
    if previous_gaps:
        gaps_section = f"\nKnowledge gaps to address:\n" + "\n".join(f"- {g}" for g in previous_gaps)

    prompt = textwrap.dedent(f"""
        You are a research strategist planning queries for a {mode.display_name}.

        Topic: {topic}
        Depth: {mode.depth_level}
        Preferred sources: {', '.join(mode.preferred_sources)}
        {gaps_section}

        Generate 6-8 specific, diverse search queries that together would give
        comprehensive coverage of this topic for a {mode.display_name}.

        Rules:
        - Mix broad overview queries with specific deep-dive queries
        - Include at least one query targeting recent developments
        - For academic modes, include queries for seminal papers and methodologies
        - Make queries specific enough to return high-signal results

        Return ONLY a JSON array of query strings, no markdown fences.
        Example: ["query 1", "query 2", "query 3"]
    """)

    try:
        return generate_json(prompt)
    except Exception:
        # Fallback: basic queries
        return [
            topic,
            f"{topic} research overview",
            f"{topic} recent developments 2024",
            f"{topic} key challenges",
            f"{topic} case studies examples",
        ]


# ── Source dispatch ───────────────────────────────────────────────────────────

def _fetch_web(query: str, src: SourceConfig) -> list[SearchResult]:
    if not src.is_enabled("web"):
        return []
    return search(query, src.perplexity_api_key, src.serpapi_key, num_results=5)


def _fetch_papers(query: str, src: SourceConfig) -> list[Paper]:
    if not src.is_enabled("arxiv"):
        return []
    return search_papers(query, max_results=6, api_key=src.semantic_scholar_api_key)


def _fetch_videos(query: str, src: SourceConfig) -> list[VideoTranscript]:
    if not src.is_enabled("youtube"):
        return []
    return search_and_fetch(query, api_key=src.youtube_api_key, max_results=3)


def _fetch_repos(query: str, src: SourceConfig) -> list[RepoSummary]:
    if not src.is_enabled("github"):
        return []
    return search_repos(query, token=src.github_token, max_results=3)


def dispatch_queries(queries: list[str], src: SourceConfig) -> dict:
    """Run all queries across all sources in parallel. Returns collected results."""
    collected: dict = {
        "web": [], "papers": [], "videos": [], "repos": []
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {}
        for q in queries:
            sq = _simplify_query(q)
            futures[ex.submit(_fetch_web,    sq, src)] = ("web",    q)
            futures[ex.submit(_fetch_papers, sq, src)] = ("papers", q)
            futures[ex.submit(_fetch_videos, sq, src)] = ("videos", q)
            futures[ex.submit(_fetch_repos,  sq, src)] = ("repos",  q)

        for future in concurrent.futures.as_completed(futures):
            kind, q = futures[future]
            try:
                results = future.result()
                collected[kind].extend(results)
                print(f"[agent] {kind:8s} | {len(results):2d} results | '{q[:50]}'")
            except Exception as e:
                print(f"[agent] {kind:8s} | FAILED | '{q[:50]}' | {e}")

    return collected


# ── Coverage reflection ───────────────────────────────────────────────────────

def _should_continue(bundle: ResearchBundle, mode: OutputModeConfig, round_num: int) -> bool:
    """Decide whether another research round is warranted."""
    if round_num >= mode.max_research_rounds:
        return False
    if len(bundle.gaps) == 0:
        return False
    total_notes = len(bundle.source_notes)
    if total_notes >= 20:
        return False
    return True


# ── Main public interface ──────────────────────────────────────────────────────

def run_research(
    topic: str,
    mode: OutputModeConfig,
    sources: SourceConfig,
    pdf_chunks: list[TextChunk] = (),
    hitl_approve_queries=None,     # callable(queries) -> approved_queries
) -> ResearchBundle:
    """
    Full ReAct research loop.

    hitl_approve_queries: if provided, called with the query list before each
    dispatch round. Should return the (potentially edited) query list.
    If None, queries are auto-approved (useful for fully autonomous mode).
    """
    state = AgentState(topic=topic, mode=mode, sources=sources)
    state.all_pdf_chunks = list(pdf_chunks)

    api_key = sources.google_api_key or os.getenv("GOOGLE_API_KEY", "")
    previous_gaps: list[str] = []

    while True:
        state.round += 1
        print(f"\n[agent] ── Round {state.round} / {mode.max_research_rounds} ──")

        # Generate queries
        queries = generate_queries(topic, mode, previous_gaps, api_key)
        print(f"[agent] Generated {len(queries)} queries")

        # HITL: let user approve / edit queries
        if hitl_approve_queries:
            queries = hitl_approve_queries(queries)
            if not queries:
                print("[agent] All queries rejected — stopping research.")
                break

        # Dispatch
        results = dispatch_queries(queries, sources)
        state.all_web    += results["web"]
        state.all_papers += results["papers"]
        state.all_videos += results["videos"]
        state.all_repos  += results["repos"]

        # Synthesize
        print("[agent] Synthesizing results...")
        state.bundle = synthesize(
            topic=topic,
            mode_name=mode.name,
            web_results=state.all_web,
            papers=state.all_papers,
            videos=state.all_videos,
            repos=state.all_repos,
            pdf_chunks=state.all_pdf_chunks,
            api_key=api_key,
        )

        previous_gaps = state.bundle.gaps
        total = len(state.bundle.source_notes)
        print(f"[agent] Round {state.round} complete — {total} notes, "
              f"{len(state.bundle.gaps)} gaps identified")

        if not _should_continue(state.bundle, mode, state.round):
            break

        print(f"[agent] Gaps found — running follow-up queries: {state.bundle.suggested_queries}")

    return state.bundle
