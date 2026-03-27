"""
research_agent/synthesizer.py
──────────────────────────────
Converts raw multi-source results into structured research notes.
Output is a ResearchBundle — a clean, topic-clustered knowledge package
that the writing workflow consumes.

Humanization note: the synthesizer also extracts:
  - Direct human voices (quotes, anecdotes, first-person accounts)
  - Concrete real-world examples and case studies
  - Contradictions and tensions in the literature
  - Analogies and metaphors used by original authors
These are flagged in the notes so the writer can weave them in naturally,
making the final output feel authored by a person, not assembled by a machine.
"""

from __future__ import annotations
import os, textwrap
from dataclasses import dataclass, field
from typing import Any
import google.generativeai as genai

from research_agent.tools.web_search import SearchResult
from research_agent.tools.arxiv import Paper
from research_agent.tools.youtube import VideoTranscript
from research_agent.tools.github import RepoSummary
from research_agent.tools.pdf_reader import TextChunk


@dataclass
class SourceNote:
    """A processed note from a single source."""
    source_type: str        # "web" | "arxiv" | "youtube" | "github" | "pdf"
    title:       str
    url:         str
    key_points:  list[str]
    human_voices: list[str]  # quotes, anecdotes, real examples to preserve
    year:        int = 0
    citation:    str = ""    # formatted citation string


@dataclass
class ResearchBundle:
    """The complete structured knowledge package handed to the writing workflow."""
    topic:          str
    mode_name:      str
    source_notes:   list[SourceNote]
    topic_clusters: dict[str, list[str]]   # cluster_name → list of key points
    human_voices:   list[str]              # all human voice snippets, deduplicated
    contradictions: list[str]              # tensions / disagreements found
    analogies:      list[str]              # useful metaphors and comparisons
    gaps:           list[str]              # identified knowledge gaps
    suggested_queries: list[str]           # follow-up queries for next round


# ── Helpers ───────────────────────────────────────────────────────────────────

def _llm(prompt: str, api_key: str, model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")) -> str:
    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model)
    return m.generate_content(prompt).text.strip()


def _extract_note_from_web(result: SearchResult, api_key: str) -> SourceNote:
    prompt = textwrap.dedent(f"""
        Analyse this web search result and extract structured notes.

        Title: {result.title}
        URL: {result.url}
        Content: {result.snippet[:3000]}

        Return JSON with these exact keys:
        {{
          "key_points": ["..."],          // 3-6 factual points
          "human_voices": ["..."],         // direct quotes, specific examples, case studies, anecdotes — preserve original wording
          "citation": "..."               // APA-style citation if possible
        }}
        Return ONLY valid JSON, no markdown fences.
    """)
    import json
    try:
        raw  = _llm(prompt, api_key)
        data = json.loads(raw)
    except Exception:
        data = {"key_points": [result.snippet[:200]], "human_voices": [], "citation": result.url}

    return SourceNote(
        source_type="web",
        title=result.title,
        url=result.url,
        key_points=data.get("key_points", []),
        human_voices=data.get("human_voices", []),
        citation=data.get("citation", result.url),
    )


def _extract_note_from_paper(paper: Paper) -> SourceNote:
    key_points = [s.strip() for s in paper.abstract.split(". ") if len(s) > 40][:6]
    authors_str = ", ".join(paper.authors[:3]) + (" et al." if len(paper.authors) > 3 else "")
    citation = f"{authors_str} ({paper.year}). {paper.title}. {paper.url}"
    return SourceNote(
        source_type="arxiv",
        title=paper.title,
        url=paper.url,
        key_points=key_points,
        human_voices=[],      # academic abstracts rarely have informal voices
        year=paper.year,
        citation=citation,
    )


def _extract_note_from_video(video: VideoTranscript, api_key: str) -> SourceNote:
    prompt = textwrap.dedent(f"""
        Analyse this YouTube video transcript and extract research value.

        Title: {video.title}
        Channel: {video.channel}
        Transcript (excerpt): {video.transcript[:3000]}

        Return JSON:
        {{
          "key_points": ["..."],       // 3-5 substantive factual points
          "human_voices": ["..."]      // memorable quotes, specific stories, real examples — keep speaker's own words
        }}
        Return ONLY valid JSON, no markdown fences.
    """)
    import json
    try:
        raw  = _llm(prompt, api_key)
        data = json.loads(raw)
    except Exception:
        data = {"key_points": [], "human_voices": []}

    return SourceNote(
        source_type="youtube",
        title=video.title,
        url=video.url,
        key_points=data.get("key_points", []),
        human_voices=data.get("human_voices", []),
        citation=f"{video.channel}. ({video.title}). YouTube. {video.url}",
    )


def _extract_note_from_repo(repo: RepoSummary) -> SourceNote:
    key_points = []
    if repo.description:
        key_points.append(repo.description)
    if repo.topics:
        key_points.append(f"Topics: {', '.join(repo.topics)}")
    if repo.readme:
        first_para = repo.readme.split("\n\n")[0].strip()
        if first_para:
            key_points.append(first_para[:300])
    key_points.append(f"GitHub stars: {repo.stars:,}")

    return SourceNote(
        source_type="github",
        title=f"{repo.owner}/{repo.repo}",
        url=repo.url,
        key_points=key_points,
        human_voices=[],
        citation=f"{repo.owner}. ({repo.repo}). GitHub. {repo.url}",
    )


def _extract_note_from_chunks(chunks: list[TextChunk], api_key: str) -> SourceNote:
    combined = "\n\n".join(c.text for c in chunks[:6])
    source   = chunks[0].source if chunks else "uploaded_pdf"
    prompt   = textwrap.dedent(f"""
        Analyse this PDF excerpt and extract research value.

        Source: {source}
        Content: {combined[:4000]}

        Return JSON:
        {{
          "key_points": ["..."],       // 4-7 substantive points
          "human_voices": ["..."]      // direct quotes, case studies, specific examples — preserve original wording
        }}
        Return ONLY valid JSON, no markdown fences.
    """)
    import json
    try:
        raw  = _llm(prompt, api_key)
        data = json.loads(raw)
    except Exception:
        data = {"key_points": [c.text[:150] for c in chunks[:3]], "human_voices": []}

    return SourceNote(
        source_type="pdf",
        title=source,
        url=f"file://{source}",
        key_points=data.get("key_points", []),
        human_voices=data.get("human_voices", []),
        citation=source,
    )


# ── Main synthesis ─────────────────────────────────────────────────────────────

def synthesize(
    topic: str,
    mode_name: str,
    web_results:   list[SearchResult]   = (),
    papers:        list[Paper]          = (),
    videos:        list[VideoTranscript]= (),
    repos:         list[RepoSummary]    = (),
    pdf_chunks:    list[TextChunk]      = (),
    api_key: str = "",
) -> ResearchBundle:
    """
    Convert all raw source results into a structured ResearchBundle.
    """
    key = api_key or os.getenv("GOOGLE_API_KEY", "")
    notes: list[SourceNote] = []

    for r in web_results:
        try:    notes.append(_extract_note_from_web(r, key))
        except Exception as e: print(f"[synthesizer] web note failed: {e}")

    for p in papers:
        notes.append(_extract_note_from_paper(p))

    for v in videos:
        try:    notes.append(_extract_note_from_video(v, key))
        except Exception as e: print(f"[synthesizer] video note failed: {e}")

    for repo in repos:
        notes.append(_extract_note_from_repo(repo))

    if pdf_chunks:
        # Group chunks by source file
        from itertools import groupby
        sorted_chunks = sorted(pdf_chunks, key=lambda c: c.source)
        for source, group in groupby(sorted_chunks, key=lambda c: c.source):
            chunk_list = list(group)
            try:    notes.append(_extract_note_from_chunks(chunk_list, key))
            except Exception as e: print(f"[synthesizer] pdf note failed: {e}")

    # High-level synthesis: cluster, identify contradictions, gaps, analogies
    all_points = [pt for n in notes for pt in n.key_points]
    all_voices = [v  for n in notes for v  in n.human_voices]

    cluster_prompt = textwrap.dedent(f"""
        Topic: {topic}

        Here are research notes from multiple sources:
        {chr(10).join(f'- {pt}' for pt in all_points[:60])}

        Return JSON with these keys:
        {{
          "topic_clusters": {{          // group points into 4-7 thematic clusters
            "Cluster Name": ["point 1", "point 2"]
          }},
          "contradictions": ["..."],    // 2-4 genuine tensions or disagreements found
          "analogies": ["..."],         // 2-4 useful metaphors or comparisons from the sources
          "gaps": ["..."],              // 2-4 questions the sources don't fully answer
          "suggested_queries": ["..."]  // 3-5 follow-up search queries to fill the gaps
        }}
        Return ONLY valid JSON, no markdown fences.
    """)

    import json
    try:
        raw  = _llm(cluster_prompt, key)
        meta = json.loads(raw)
    except Exception:
        meta = {
            "topic_clusters": {"General": all_points[:10]},
            "contradictions": [],
            "analogies": [],
            "gaps": [],
            "suggested_queries": [],
        }

    # Deduplicate human voices
    seen_voices, deduped_voices = set(), []
    for v in all_voices:
        key_v = v[:80].lower()
        if key_v not in seen_voices:
            seen_voices.add(key_v)
            deduped_voices.append(v)

    return ResearchBundle(
        topic=topic,
        mode_name=mode_name,
        source_notes=notes,
        topic_clusters=meta.get("topic_clusters", {}),
        human_voices=deduped_voices,
        contradictions=meta.get("contradictions", []),
        analogies=meta.get("analogies", []),
        gaps=meta.get("gaps", []),
        suggested_queries=meta.get("suggested_queries", []),
    )
