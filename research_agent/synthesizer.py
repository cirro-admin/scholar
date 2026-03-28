"""
research_agent/synthesizer.py
──────────────────────────────
Converts raw multi-source results into structured research notes (ResearchBundle).

Performance notes:
- Web notes: one batched LLM call for all results combined (not one per result)
- Papers: no LLM call needed — abstract is already structured text
- Videos/PDFs: one batched call per source type
- Clustering: one final LLM call
- Total LLM calls: 4 regardless of how many sources were fetched
"""

from __future__ import annotations
import textwrap
from dataclasses import dataclass, field

from utils.llm import generate_json
from research_agent.tools.web_search import SearchResult
from research_agent.tools.arxiv import Paper
from research_agent.tools.youtube import VideoTranscript
from research_agent.tools.github import RepoSummary
from research_agent.tools.pdf_reader import TextChunk

# Max items to include per source type — prevents context overflow
MAX_WEB     = 8
MAX_PAPERS  = 12
MAX_VIDEOS  = 4
MAX_REPOS   = 3
MAX_CHUNKS  = 6   # PDF chunks


@dataclass
class SourceNote:
    source_type:  str
    title:        str
    url:          str
    key_points:   list[str]
    human_voices: list[str]
    year:         int = 0
    citation:     str = ""


@dataclass
class ResearchBundle:
    topic:             str
    mode_name:         str
    source_notes:      list[SourceNote]
    topic_clusters:    dict[str, list[str]]
    human_voices:      list[str]
    contradictions:    list[str]
    analogies:         list[str]
    gaps:              list[str]
    suggested_queries: list[str]


# ── Batched extraction — one LLM call per source type ────────────────────────

def _notes_from_web_batch(results: list[SearchResult], chunk_size: int = 6) -> list[SourceNote]:
    """Extract notes from web results in chunks to avoid truncation."""
    if not results:
        return []
    notes = []
    batch = results[:MAX_WEB]
    for start in range(0, len(batch), chunk_size):
        chunk = batch[start:start + chunk_size]
        items = "\n\n".join(
            f"[{i+1}] Title: {r.title[:80]}\nURL: {r.url[:80]}\nContent: {r.snippet[:400]}"
            for i, r in enumerate(chunk)
        )
        prompt = textwrap.dedent(f"""
            Analyse these {len(chunk)} web search results. Be concise.

            {items}

            Return a JSON array with exactly {len(chunk)} objects:
            [{{"index": 1,
               "key_points": ["max 2 points, max 15 words each"],
               "human_voices": ["one short direct quote if present, else empty array"],
               "citation": "Author (Year) short title — max 80 chars total"}}]

            Rules: max 2 key_points per item, max 15 words per point.
            Return ONLY valid JSON array, no markdown fences, no extra text.
        """)
        try:
            data = generate_json(prompt, fast=True)
            if not isinstance(data, list):
                data = []
            for i, item in enumerate(data):
                r = chunk[i] if i < len(chunk) else chunk[-1]
                notes.append(SourceNote(
                    source_type="web", title=r.title, url=r.url,
                    key_points=item.get("key_points", [r.snippet[:150]]),
                    human_voices=item.get("human_voices", []),
                    citation=item.get("citation", r.url),
                ))
        except Exception as e:
            print(f"[synthesizer] web chunk {start}-{start+chunk_size} failed ({e}), using snippets")
            for r in chunk:
                notes.append(SourceNote("web", r.title, r.url,
                                        [r.snippet[:200]], [], citation=r.url))
    return notes


def _notes_from_papers(papers: list[Paper]) -> list[SourceNote]:
    """Papers don't need an LLM call — abstracts are already structured."""
    notes = []
    for paper in papers[:MAX_PAPERS]:
        points = [s.strip() for s in paper.abstract.split(". ") if len(s.strip()) > 40][:6]
        authors = ", ".join(paper.authors[:3]) + (" et al." if len(paper.authors) > 3 else "")
        notes.append(SourceNote(
            source_type="arxiv", title=paper.title, url=paper.url,
            key_points=points, human_voices=[],
            year=paper.year,
            citation=f"{authors} ({paper.year}). {paper.title}. {paper.url}",
        ))
    return notes


def _notes_from_videos_batch(videos: list[VideoTranscript]) -> list[SourceNote]:
    """Extract notes from all videos in a single LLM call."""
    if not videos:
        return []
    items = "\n\n".join(
        f"[{i+1}] Title: {v.title} | Channel: {v.channel}\n"
        f"Transcript excerpt: {v.transcript[:600]}"
        for i, v in enumerate(videos[:MAX_VIDEOS])
    )
    prompt = textwrap.dedent(f"""
        Analyse these {len(videos[:MAX_VIDEOS])} YouTube video transcripts.

        {items}

        Return a JSON array, one object per video:
        [{{"index": 1, "key_points": ["2-4 substantive points"],
           "human_voices": ["memorable quotes — keep speaker's own words"]}}]

        Return ONLY valid JSON array, no fences.
    """)
    notes = []
    try:
        data = generate_json(prompt)
        if not isinstance(data, list):
            data = []
        for i, item in enumerate(data):
            v = videos[i] if i < len(videos) else videos[-1]
            notes.append(SourceNote(
                source_type="youtube", title=v.title, url=v.url,
                key_points=item.get("key_points", []),
                human_voices=item.get("human_voices", []),
                citation=f"{v.channel}. {v.title}. YouTube. {v.url}",
            ))
    except Exception as e:
        print(f"[synthesizer] video batch failed ({e})")
    return notes


def _notes_from_repos(repos: list[RepoSummary]) -> list[SourceNote]:
    """Repos don't need LLM — metadata is already structured."""
    notes = []
    for repo in repos[:MAX_REPOS]:
        points = [p for p in [
            repo.description,
            f"Topics: {', '.join(repo.topics)}" if repo.topics else "",
            repo.readme.split("\n\n")[0].strip()[:300] if repo.readme else "",
            f"Stars: {repo.stars:,}",
        ] if p]
        notes.append(SourceNote(
            source_type="github", title=f"{repo.owner}/{repo.repo}", url=repo.url,
            key_points=points, human_voices=[],
            citation=f"{repo.owner}. {repo.repo}. GitHub. {repo.url}",
        ))
    return notes


def _notes_from_pdfs_batch(chunks: list[TextChunk]) -> list[SourceNote]:
    """Extract notes from all PDF chunks in a single LLM call."""
    if not chunks:
        return []
    from itertools import groupby
    notes = []
    sorted_chunks = sorted(chunks, key=lambda c: c.source)
    for source, grp in groupby(sorted_chunks, key=lambda c: c.source):
        chunk_list = list(grp)[:MAX_CHUNKS]
        combined   = "\n\n".join(c.text for c in chunk_list)
        prompt     = textwrap.dedent(f"""
            Analyse this PDF excerpt from "{source}".
            Content: {combined[:3000]}

            Return JSON:
            {{"key_points": ["4-6 substantive points"],
              "human_voices": ["direct quotes or case studies — preserve original wording"]}}

            Return ONLY valid JSON, no fences.
        """)
        try:
            data = generate_json(prompt)
            notes.append(SourceNote(
                source_type="pdf", title=source, url=f"file://{source}",
                key_points=data.get("key_points", []),
                human_voices=data.get("human_voices", []),
            ))
        except Exception as e:
            print(f"[synthesizer] pdf batch failed ({e})")
    return notes


# ── Clustering — one final LLM call ──────────────────────────────────────────

def _cluster(topic: str, notes: list[SourceNote]) -> dict:
    all_points = [pt for n in notes for pt in n.key_points]
    if not all_points:
        return {"topic_clusters": {"General": []}, "contradictions": [],
                "analogies": [], "gaps": [], "suggested_queries": []}

    prompt = textwrap.dedent(f"""
        Topic: {topic}
        Research points from {len(notes)} sources:
        {chr(10).join(f'- {pt}' for pt in all_points[:60])}

        Return JSON:
        {{"topic_clusters": {{"Cluster Name": ["point 1", "point 2"]}},
          "contradictions": ["2-4 genuine tensions or disagreements"],
          "analogies": ["2-4 useful metaphors or comparisons from the sources"],
          "gaps": ["2-4 questions the sources do not fully answer"],
          "suggested_queries": ["3-5 follow-up plain-text search queries"]}}

        Return ONLY valid JSON, no fences.
    """)
    try:
        return generate_json(prompt)
    except Exception as e:
        print(f"[synthesizer] clustering failed ({e})")
        return {"topic_clusters": {"General": all_points[:10]},
                "contradictions": [], "analogies": [], "gaps": [], "suggested_queries": []}


# ── Public interface ──────────────────────────────────────────────────────────

def synthesize(
    topic: str, mode_name: str,
    web_results: list[SearchResult]    = (),
    papers:      list[Paper]           = (),
    videos:      list[VideoTranscript] = (),
    repos:       list[RepoSummary]     = (),
    pdf_chunks:  list[TextChunk]       = (),
    api_key:     str = "",
) -> ResearchBundle:
    """
    Convert all raw source results into a ResearchBundle.
    Makes exactly 4 LLM calls total regardless of source count:
      1. Web batch, 2. Video batch, 3. PDF batch, 4. Clustering
    Papers and repos are processed without LLM calls.
    """
    print(f"[synthesizer] Processing: {len(list(web_results))} web, "
          f"{len(list(papers))} papers, {len(list(videos))} videos, "
          f"{len(list(repos))} repos, {len(list(pdf_chunks))} pdf chunks")

    notes: list[SourceNote] = []
    notes += _notes_from_web_batch(list(web_results))
    notes += _notes_from_papers(list(papers))
    notes += _notes_from_videos_batch(list(videos))
    notes += _notes_from_repos(list(repos))
    notes += _notes_from_pdfs_batch(list(pdf_chunks))

    print(f"[synthesizer] {len(notes)} notes extracted — clustering...")
    meta = _cluster(topic, notes)

    all_voices = list({v[:80]: v for n in notes for v in n.human_voices}.values())

    return ResearchBundle(
        topic=topic, mode_name=mode_name, source_notes=notes,
        topic_clusters=meta.get("topic_clusters", {}),
        human_voices=all_voices,
        contradictions=meta.get("contradictions", []),
        analogies=meta.get("analogies", []),
        gaps=meta.get("gaps", []),
        suggested_queries=meta.get("suggested_queries", []),
    )
