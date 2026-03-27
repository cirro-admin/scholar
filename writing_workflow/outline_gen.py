"""
writing_workflow/outline_gen.py
────────────────────────────────
Mode-aware outline generator.
"""

from __future__ import annotations
import textwrap
from dataclasses import dataclass, field

from utils.llm import generate_json
from config.modes import OutputModeConfig
from research_agent.synthesizer import ResearchBundle


@dataclass
class SectionPlan:
    key:          str
    title:        str
    brief:        str
    word_target:  int
    source_urls:  list[str]
    human_voices: list[str]
    cluster_keys: list[str]
    order:        int


@dataclass
class Outline:
    topic:    str
    mode:     str
    title:    str
    sections: list[SectionPlan]


def _assign_voices(sections: list[str], voices: list[str]) -> dict[str, list[str]]:
    body = [s for s in sections if s not in
            ("title_page","table_of_contents","references","appendices","acknowledgements","changelog")]
    result: dict[str, list[str]] = {s: [] for s in sections}
    for i, v in enumerate(voices):
        target = body[i % len(body)] if body else sections[0]
        result[target].append(v)
    return result


def generate_outline(bundle: ResearchBundle, mode: OutputModeConfig, api_key: str = "") -> Outline:
    cluster_summary = "\n".join(
        f"  [{name}]: {'; '.join(pts[:3])}" for name, pts in bundle.topic_clusters.items()
    )
    contradictions = "\n".join(f"  - {c}" for c in bundle.contradictions[:4])

    prompt = textwrap.dedent(f"""
        You are an expert editor creating a {mode.display_name} outline.
        Topic: {bundle.topic}
        Required sections (in order): {', '.join(mode.structure_template)}

        Research clusters:
        {cluster_summary}

        Tensions found:
        {contradictions}

        For each section write a specific 2-3 sentence editorial brief.
        Also suggest a compelling document title.

        Return ONLY valid JSON:
        {{"title": "...",
          "sections": [{{"key": "introduction", "title": "1. Introduction",
                         "brief": "...", "cluster_keys": ["Cluster 1"]}}]}}
    """)

    try:
        data = generate_json(prompt)
    except Exception as e:
        print(f"[outline_gen] failed ({e}), using default outline")
        data = {
            "title": bundle.topic,
            "sections": [{"key": s, "title": s.replace("_"," ").title(),
                          "brief": mode.section_prompts.get(s, f"Write the {s} section."),
                          "cluster_keys": list(bundle.topic_clusters.keys())[:2]}
                         for s in mode.structure_template]
        }

    voice_map = _assign_voices([s["key"] for s in data["sections"]], bundle.human_voices)
    all_urls  = [n.url for n in bundle.source_notes]
    chunk     = max(1, len(all_urls) // max(1, len(data["sections"])))

    plans = []
    for i, sec in enumerate(data["sections"]):
        k = sec["key"]
        plans.append(SectionPlan(
            key=k, title=sec.get("title", k.replace("_"," ").title()),
            brief=sec.get("brief", mode.section_prompts.get(k, "")),
            word_target=mode.target_words_per_section,
            source_urls=all_urls[i*chunk:(i+1)*chunk],
            human_voices=voice_map.get(k, []),
            cluster_keys=sec.get("cluster_keys", []),
            order=i,
        ))

    return Outline(topic=bundle.topic, mode=mode.name,
                   title=data.get("title", bundle.topic), sections=plans)
