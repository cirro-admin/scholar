"""
writing_workflow/section_drafter.py
─────────────────────────────────────
Chain-of-thought section writer with enforced humanization.

Humanization strategy (baked into every draft prompt):
  1. Seed with real human voices — quotes, examples, anecdotes from research
  2. Vary sentence length intentionally — mix short punchy sentences with longer ones
  3. Use transitional phrases that feel earned, not templated
  4. Include at least one concrete specific detail per paragraph
  5. Introduce controlled imperfection — hedged claims, acknowledged uncertainty
  6. Avoid AI-signature patterns: no "In conclusion,", no "It is worth noting that",
     no "In today's rapidly evolving landscape", no em-dash overuse
  7. Write as if one specific expert is speaking, not an averaged voice
"""

from __future__ import annotations
import os, textwrap
from dataclasses import dataclass
from utils.llm import generate
from writing_workflow.rich_content_generator import RichElement, generate_rich_elements

from config.modes import OutputModeConfig
from writing_workflow.outline_gen import SectionPlan
from research_agent.synthesizer import ResearchBundle


@dataclass
class DraftedSection:
    key:          str
    title:        str
    content:      str
    word_count:   int
    sources_used: list[str]
    rich_elements: list[RichElement] = None

    def __post_init__(self):
        if self.rich_elements is None:
            self.rich_elements = []


# ── Humanization system prompt ─────────────────────────────────────────────────
# This is injected into EVERY section draft — it is non-negotiable.

HUMANIZATION_SYSTEM_PROMPT = """
You are a skilled human writer — a subject-matter expert who has spent years
in this field and writes with genuine authority, not synthetic confidence.

CORE WRITING RULES (follow every single one):

Voice and authenticity:
- Write from a clear point of view. Do not hedge everything — take positions.
- Use the first person sparingly but naturally when appropriate to the mode.
- Vary your sentence length deliberately. Short sentences land hard. Longer ones
  build context, add nuance, and let ideas breathe before the next point hits.
- Start sentences with conjunctions occasionally (And, But, Yet) — real writers do this.
- Include one specific, concrete detail per paragraph that could only come from
  someone who actually researched this (a number, a name, a date, an anecdote).

What to avoid (AI detection red flags):
- Never open with "In today's...", "In the realm of...", "It is worth noting...", "It is clear that..."
- Never use: "delve", "multifaceted", "nuanced", "comprehensive", "it's important to note",
  "straightforward", "robust", "leverage" (verb), "utilize", "pivotal", "crucial", "significant"
  "underscore", "highlight" (as verb), "shed light on", "paint a picture", "navigate" (metaphorically),
  "interrogates" (unless quoting someone), "examines", "explores" — these are academic jargon signals
- Never end with "In conclusion, this shows..." or "Overall, it is clear that..."
- Do not use em-dashes (—). Use commas, colons, or parentheses instead. Em-dashes are a strong AI detection signal when overused.
- Avoid perfectly parallel list structures — real prose is messier
- Do not pad with summaries of what you just said
- Avoid nominalisations: prefer "we found" over "our finding was that", "this fails" over "this represents a failure of"
- Never use "this paper argues/contends/posits/interrogates" — just make the argument directly

Structural authenticity:
- Paragraphs should range from 2 to 6 sentences — not all the same length
- Transitions should feel motivated, not formulaic ("This matters because..." not "Furthermore,")
- Let contradictions and open questions into the text — uncertainty is human
- When you cite a source, integrate it naturally, not as a parenthetical afterthought
- Read your draft back and ask: would a colleague say this out loud? If not, rewrite it.
- Replace every Latinate abstract noun with a concrete verb where possible:
  "demonstrates a lack of" → "fails to", "provides support for" → "supports", "is indicative of" → "suggests"
- One short sentence (under 10 words) per paragraph minimum — they land harder than long ones

Human voices:
- If you are given quotes or examples from real sources, USE THEM.
  Weave them into the prose. Do not paraphrase when the original wording is strong.
- Specific real-world examples beat generic claims every time.
"""


def _build_draft_prompt(
    section: SectionPlan,
    bundle: ResearchBundle,
    mode: OutputModeConfig,
    context_so_far: str = "",
) -> str:
    """Build the full chain-of-thought prompt for one section."""

    # Gather relevant research for this section
    relevant_notes = []
    for note in bundle.source_notes:
        if note.source_type in mode.preferred_sources:
            relevant_notes.append(note)
    relevant_notes = relevant_notes[:8]

    notes_block = "\n\n".join(
        f"[{n.source_type.upper()} — {n.title[:60]}]\n" +
        "\n".join(f"  • {pt}" for pt in n.key_points[:4])
        for n in relevant_notes
    )

    voices_block = ""
    if section.human_voices:
        voices_block = "HUMAN VOICES TO WEAVE IN (use these, don't paraphrase):\n" + \
                       "\n".join(f'  "{v}"' for v in section.human_voices[:4])

    contradictions_block = ""
    if bundle.contradictions:
        contradictions_block = "TENSIONS IN THE RESEARCH (acknowledge at least one):\n" + \
                               "\n".join(f"  - {c}" for c in bundle.contradictions[:2])

    context_block = ""
    if context_so_far:
        context_block = f"\nDOCUMENT SO FAR (maintain consistency of voice):\n{context_so_far[-1500:]}\n"

    citation_instruction = {
        "APA":          "Cite sources inline as (Author, Year). ",
        "IEEE":         "Cite sources as [1], [2] etc. in order of first appearance. ",
        "inline_links": "Hyperlink key claims naturally in the prose. ",
        "MLA":          "Cite sources inline as (Author page). ",
        "none":         "No formal citations needed. ",
    }.get(mode.citation_style, "")

    return textwrap.dedent(f"""
        SECTION TO WRITE: {section.title}
        DOCUMENT TYPE: {mode.display_name}
        TONE: {mode.tone_profile}
        WORD TARGET: {section.word_target} words (±15%)
        {citation_instruction}

        WRITING BRIEF:
        {section.brief}

        RESEARCH NOTES:
        {notes_block}

        {voices_block}

        {contradictions_block}

        {context_block}

        CHAIN OF THOUGHT INSTRUCTIONS:
        Before writing, briefly plan (2-3 sentences, prefixed with "PLAN:"):
          - What is the single most important thing this section must do?
          - What specific detail or voice will anchor it?
          - What is the opening sentence (not "In today's...")?

        Then write the section. Mark the start with "DRAFT:".
        Write only the section content — no meta-commentary after the draft.
    """)


def draft_section(
    section: SectionPlan,
    bundle: ResearchBundle,
    mode: OutputModeConfig,
    context_so_far: str = "",
    api_key: str = "",
) -> DraftedSection:
    """Draft a single section using chain-of-thought + humanization prompting."""
    prompt   = _build_draft_prompt(section, bundle, mode, context_so_far)
    response = generate(prompt, system=HUMANIZATION_SYSTEM_PROMPT)

    # Extract just the draft (after "DRAFT:")
    if "DRAFT:" in response:
        content = response.split("DRAFT:", 1)[1].strip()
    else:
        content = response  # fallback: use full response

    # Post-process: remove placeholder example.com links
    import re as _re2
    content = _re2.sub(r'\[([^\]]+)\]\(https?://example\.com[^\)]*\)', r'', content)
    content = _re2.sub(r'\(https?://example\.com[^\)]*\)', '', content)

    # Post-process: remove placeholder example.com links
    import re as _re2
    content = _re2.sub(r'\[([^\]]+)\]\(https?://example\.com[^)]*\)', r'\1', content)
    content = _re2.sub(r'\(https?://example\.com[^)]*\)', '', content)

    # Post-process: reduce em-dashes — keep max 1 per section, replace rest
    import re as _re
    em_dashes = _re.findall(r" — ", content)
    if len(em_dashes) > 1:
        count = [0]
        def _replace_em(m):
            count[0] += 1
            if count[0] == 1:
                return m.group(0)
            return ", " if count[0] % 2 == 0 else "; "
        content = _re.sub(r" — ", _replace_em, content)

    word_count = len(content.split())

    # Generate rich elements (figures, tables, equations, code, charts)
    # Skip for structural sections — they don't need rich content
    SKIP_RICH = {"abstract", "table_of_contents", "references",
                 "acknowledgements", "appendices", "title_page"}
    rich_elements = []
    if section.key not in SKIP_RICH:
        research_notes = "\n".join(
            f"- {pt}" for n in bundle.source_notes for pt in n.key_points[:2]
        )[:1200]
        output_dir = os.path.join(os.getenv("SCHOLAR_OUTPUT_DIR", "./outputs"), "figures")
        rich_elements = generate_rich_elements(
            section_title=section.title,
            section_content=content,
            mode_name=mode.name,
            research_notes=research_notes,
            output_dir=output_dir,
            api_key=api_key,
        )

    return DraftedSection(
        key=section.key,
        title=section.title,
        content=content,
        word_count=word_count,
        sources_used=section.source_urls,
        rich_elements=rich_elements,
    )
