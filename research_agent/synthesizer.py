"""
research_agent/synthesizer.py
──────────────────────────────
Converts raw multi-source results into structured research notes (ResearchBundle).
Uses utils.llm for all LLM calls — no direct SDK imports here.
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


def _note_from_web(result: SearchResult) -> SourceNote:
    prompt = textwrap.dedent(f"""
        Analyse this web search result and extract structured notes.
        Title: {result.title}
        URL: {result.url}
        Content: {result.snippet[:3000]}

        Return JSON with exactly these keys:
        {{"key_points": ["3-6 factual points"],
          "human_voices": ["direct quotes, specific examples, anecdotes — preserve original wording"],
          "citation": "APA-style citation"}}
    """)
    try:
        data = generate_json(prompt)
        return SourceNote(source_type="web", title=result.title, url=result.url,
                          key_points=data.get("key_points", [result.snippet[:200]]),
                          human_voices=data.get("human_voices", []),
                          citation=data.get("citation", result.url))
    except Exception as e:
        print(f"[synthesizer] web note failed: {e}")
        return SourceNote("web", result.title, result.url, [result.snippet[:200]], [], citation=result.url)


def _note_from_paper(paper: Paper) -> SourceNote:
    points = [s.strip() for s in paper.abstract.split(". ") if len(s) > 40][:6]
    authors = ", ".join(paper.authors[:3]) + (" et al." if len(paper.authors) > 3 else "")
    return SourceNote("arxiv", paper.title, paper.url, points, [],
                      year=paper.year, citation=f"{authors} ({paper.year}). {paper.title}. {paper.url}")


def _note_from_video(video: VideoTranscript) -> SourceNote:
    prompt = textwrap.dedent(f"""
        Analyse this YouTube transcript and extract research value.
        Title: {video.title} | Channel: {video.channel}
        Transcript: {video.transcript[:3000]}

        Return JSON:
        {{"key_points": ["3-5 substantive points"],
          "human_voices": ["memorable quotes or specific stories — keep speaker's own words"]}}
    """)
    try:
        data = generate_json(prompt)
        return SourceNote("youtube", video.title, video.url,
                          data.get("key_points", []), data.get("human_voices", []),
                          citation=f"{video.channel}. {video.title}. YouTube. {video.url}")
    except Exception as e:
        print(f"[synthesizer] video note failed: {e}")
        return SourceNote("youtube", video.title, video.url, [], [])


def _note_from_repo(repo: RepoSummary) -> SourceNote:
    points = [p for p in [repo.description,
               f"Topics: {', '.join(repo.topics)}" if repo.topics else "",
               (repo.readme.split("\n\n")[0].strip())[:300] if repo.readme else "",
               f"Stars: {repo.stars:,}"] if p]
    return SourceNote("github", f"{repo.owner}/{repo.repo}", repo.url, points, [],
                      citation=f"{repo.owner}. {repo.repo}. GitHub. {repo.url}")


def _note_from_chunks(chunks: list[TextChunk]) -> SourceNote:
    combined = "\n\n".join(c.text for c in chunks[:6])
    source   = chunks[0].source if chunks else "uploaded_pdf"
    prompt   = textwrap.dedent(f"""
        Analyse this PDF excerpt.
        Source: {source}
        Content: {combined[:4000]}

        Return JSON:
        {{"key_points": ["4-7 substantive points"],
          "human_voices": ["direct quotes or case studies — preserve original wording"]}}
    """)
    try:
        data = generate_json(prompt)
        return SourceNote("pdf", source, f"file://{source}",
                          data.get("key_points", []), data.get("human_voices", []))
    except Exception as e:
        print(f"[synthesizer] pdf note failed: {e}")
        return SourceNote("pdf", source, f"file://{source}", [], [])


def synthesize(
    topic: str, mode_name: str,
    web_results: list[SearchResult] = (),
    papers: list[Paper] = (),
    videos: list[VideoTranscript] = (),
    repos: list[RepoSummary] = (),
    pdf_chunks: list[TextChunk] = (),
    api_key: str = "",        # kept for backwards-compat; ignored (uses env)
) -> ResearchBundle:
    notes: list[SourceNote] = []
    for r in web_results:  notes.append(_note_from_web(r))
    for p in papers:       notes.append(_note_from_paper(p))
    for v in videos:       notes.append(_note_from_video(v))
    for repo in repos:     notes.append(_note_from_repo(repo))

    if pdf_chunks:
        from itertools import groupby
        for _, grp in groupby(sorted(pdf_chunks, key=lambda c: c.source), key=lambda c: c.source):
            notes.append(_note_from_chunks(list(grp)))

    all_points = [pt for n in notes for pt in n.key_points]
    all_voices = list({v[:80]: v for n in notes for v in n.human_voices}.values())

    cluster_prompt = textwrap.dedent(f"""
        Topic: {topic}
        Research points:
        {chr(10).join(f'- {pt}' for pt in all_points[:60])}

        Return JSON:
        {{"topic_clusters": {{"Cluster Name": ["point 1", "point 2"]}},
          "contradictions": ["2-4 genuine tensions"],
          "analogies": ["2-4 useful metaphors from sources"],
          "gaps": ["2-4 unanswered questions"],
          "suggested_queries": ["3-5 follow-up queries"]}}
    """)
    try:
        meta = generate_json(cluster_prompt)
    except Exception as e:
        print(f"[synthesizer] clustering failed: {e}")
        meta = {"topic_clusters": {"General": all_points[:10]},
                "contradictions": [], "analogies": [], "gaps": [], "suggested_queries": []}

    return ResearchBundle(
        topic=topic, mode_name=mode_name, source_notes=notes,
        topic_clusters=meta.get("topic_clusters", {}),
        human_voices=all_voices,
        contradictions=meta.get("contradictions", []),
        analogies=meta.get("analogies", []),
        gaps=meta.get("gaps", []),
        suggested_queries=meta.get("suggested_queries", []),
    )
