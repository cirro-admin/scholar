"""
writing_workflow/outline_gen.py
────────────────────────────────
Mode-aware outline generator.
Takes an OutputModeConfig + ResearchBundle → returns a structured Outline.

The outline is not just section names — each section gets:
  - A specific writing brief
  - Assigned human_voices to weave in
  - Assigned source notes to draw from
  - A word target
"""

from __future__ import annotations
import os, json, textwrap
from dataclasses import dataclass, field
import google.generativeai as genai

from config.modes import OutputModeConfig
from research_agent.synthesizer import ResearchBundle


@dataclass
class SectionPlan:
    key:          str            # e.g. "introduction"
    title:        str            # display title e.g. "1. Introduction"
    brief:        str            # what to write in this section
    word_target:  int
    source_urls:  list[str]      # which sources to draw from
    human_voices: list[str]      # specific quotes/examples to weave in
    cluster_keys: list[str]      # which topic clusters are relevant
    order:        int            # position in document


@dataclass
class Outline:
    topic:    str
    mode:     str
    title:    str                # suggested document title
    sections: list[SectionPlan]


def _llm(prompt: str, api_key: str) -> str:
    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    return m.generate_content(prompt).text.strip()


def _assign_voices_to_sections(
    sections: list[str],
    voices: list[str],
    clusters: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Distribute human voices across sections roughly by relevance."""
    assignment: dict[str, list[str]] = {s: [] for s in sections}
    if not voices:
        return assignment

    # Simple round-robin with preference for intro/body sections
    body_sections = [s for s in sections if s not in
                     ("title_page", "table_of_contents", "references",
                      "appendices", "acknowledgements", "changelog")]
    for i, voice in enumerate(voices):
        target = body_sections[i % len(body_sections)] if body_sections else sections[0]
        assignment[target].append(voice)
    return assignment


def generate_outline(
    bundle: ResearchBundle,
    mode: OutputModeConfig,
    api_key: str = "",
) -> Outline:
    """Generate a full document outline from research bundle + mode config."""
    key = api_key or os.getenv("GOOGLE_API_KEY", "")

    # Build cluster summary for the prompt
    cluster_summary = "\n".join(
        f"  [{name}]: {'; '.join(pts[:3])}"
        for name, pts in bundle.topic_clusters.items()
    )
    voices_preview = "\n".join(f"  - {v[:120]}" for v in bundle.human_voices[:8])
    contradictions = "\n".join(f"  - {c}" for c in bundle.contradictions[:4])

    prompt = textwrap.dedent(f"""
        You are an expert academic editor creating a detailed document outline.

        Topic: {bundle.topic}
        Document type: {mode.display_name}
        Required sections (in order): {', '.join(mode.structure_template)}

        Research clusters available:
        {cluster_summary}

        Tensions and contradictions found:
        {contradictions}

        For each section, write a specific 2-3 sentence brief describing exactly
        what to cover, what argument to make, and what tone to use.
        The briefs should feel like instructions from a senior editor to a writer —
        specific, opinionated, and grounded in the research above.

        Also suggest a compelling document title.

        Return ONLY valid JSON, no markdown fences:
        {{
          "title": "...",
          "sections": [
            {{
              "key": "introduction",
              "title": "1. Introduction",
              "brief": "...",
              "cluster_keys": ["Cluster Name 1", "Cluster Name 2"]
            }}
          ]
        }}
    """)

    try:
        raw  = _llm(prompt, key)
        data = json.loads(raw)
    except Exception as e:
        print(f"[outline_gen] LLM call failed ({e}), using default outline")
        data = {
            "title": bundle.topic,
            "sections": [
                {"key": s, "title": s.replace("_", " ").title(),
                 "brief": mode.section_prompts.get(s, f"Write the {s} section."),
                 "cluster_keys": list(bundle.topic_clusters.keys())[:2]}
                for s in mode.structure_template
            ]
        }

    voice_map = _assign_voices_to_sections(
        [s["key"] for s in data["sections"]],
        bundle.human_voices,
        bundle.topic_clusters,
    )

    # Map source URLs to sections loosely
    all_urls = [n.url for n in bundle.source_notes]
    chunk    = max(1, len(all_urls) // max(1, len(data["sections"])))

    plans = []
    for i, sec in enumerate(data["sections"]):
        k = sec["key"]
        plans.append(SectionPlan(
            key=k,
            title=sec.get("title", k.replace("_", " ").title()),
            brief=sec.get("brief", mode.section_prompts.get(k, "")),
            word_target=mode.target_words_per_section,
            source_urls=all_urls[i*chunk:(i+1)*chunk],
            human_voices=voice_map.get(k, []),
            cluster_keys=sec.get("cluster_keys", []),
            order=i,
        ))

    return Outline(
        topic=bundle.topic,
        mode=mode.name,
        title=data.get("title", bundle.topic),
        sections=plans,
    )
