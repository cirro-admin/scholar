"""
config/modes.py
───────────────
OutputModeConfig dataclass + all built-in mode presets.

To add a new mode, add one entry to MODES at the bottom of this file.
See docs/ADDING_MODES.md for a full walkthrough.
"""

from dataclasses import dataclass, field
from typing import Literal


DepthLevel    = Literal["shallow", "standard", "deep"]
ToneProfile   = Literal["formal", "academic", "conversational", "precise", "formal_persuasive"]
OutputFmt     = Literal["docx", "markdown", "pdf", "html"]
CitationStyle = Literal["APA", "MLA", "IEEE", "inline_links", "none"]


@dataclass
class OutputModeConfig:
    """
    Single config object that controls the entire pipeline behaviour.
    Swap this and the research + writing pipeline adapts automatically.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    name: str
    display_name: str

    # ── Document structure ────────────────────────────────────────────────────
    structure_template: list[str]
    section_prompts: dict[str, str]

    # ── Style ─────────────────────────────────────────────────────────────────
    citation_style: CitationStyle
    tone_profile: ToneProfile
    depth_level: DepthLevel

    # ── Output ────────────────────────────────────────────────────────────────
    output_format: OutputFmt
    file_extension: str

    # ── Research agent tuning ─────────────────────────────────────────────────
    max_research_rounds: int = 3
    preferred_sources: list[str] = field(default_factory=lambda: [
        "web", "arxiv", "youtube", "github", "pdf"
    ])

    # ── Writing workflow tuning ───────────────────────────────────────────────
    eval_threshold: float = 0.78
    max_draft_iterations: int = 3
    target_words_per_section: int = 600


# ── Built-in mode presets ─────────────────────────────────────────────────────

MODES: dict[str, OutputModeConfig] = {

    "thesis": OutputModeConfig(
        name="thesis",
        display_name="Academic Thesis / Dissertation",
        structure_template=[
            "title_page", "abstract", "acknowledgements", "table_of_contents",
            "introduction", "literature_review", "methodology",
            "results", "discussion", "conclusion", "references", "appendices",
        ],
        section_prompts={
            "abstract": (
                "Write a structured abstract (150-300 words) covering: background, "
                "objectives, methods, key results, and conclusions. Use past tense."
            ),
            "introduction": (
                "Open with broader context, narrow to the specific gap this work "
                "addresses, state research questions clearly, outline chapter structure. "
                "Use formal academic register."
            ),
            "literature_review": (
                "Synthesise existing literature thematically, not chronologically. "
                "Identify agreements, contradictions, and gaps. Every claim must cite a source."
            ),
            "methodology": (
                "Describe research design, data collection, and analysis methods "
                "with enough detail for replication. Justify every methodological choice."
            ),
            "results": (
                "Report findings objectively without interpretation. Use precise "
                "quantitative language. Reference figures/tables inline."
            ),
            "discussion": (
                "Interpret results in light of research questions and existing literature. "
                "Address limitations honestly."
            ),
            "conclusion": (
                "Summarise key contributions, state implications for theory and practice, "
                "suggest concrete directions for future research."
            ),
        },
        citation_style="APA",
        tone_profile="academic",
        depth_level="deep",
        output_format="docx",
        file_extension=".docx",
        max_research_rounds=5,
        preferred_sources=["arxiv", "web", "pdf", "youtube", "github"],
        eval_threshold=0.80,
        max_draft_iterations=3,
        target_words_per_section=900,
    ),

    "article": OutputModeConfig(
        name="article",
        display_name="Research Article / Paper",
        structure_template=[
            "abstract", "introduction", "related_work", "methodology",
            "experiments_or_results", "discussion", "conclusion", "references",
        ],
        section_prompts={
            "abstract": (
                "Write a single-paragraph abstract (200 words max) following IMRaD: "
                "Introduction, Methods, Results and Discussion."
            ),
            "introduction": (
                "Motivate the problem, survey prior work briefly, state the paper's "
                "contributions as a bulleted list, and outline the paper structure."
            ),
            "related_work": (
                "Position this work relative to 3-5 closely related clusters of "
                "prior work. Be precise about what this work does differently."
            ),
            "methodology": (
                "Describe methods formally. Use equations where appropriate. "
                "Distinguish clearly between novel contributions and adopted baselines."
            ),
            "experiments_or_results": (
                "Present quantitative results with statistical rigour. "
                "Compare against baselines. Include ablations if relevant."
            ),
            "discussion": (
                "Analyse what the results mean, acknowledge limitations, "
                "discuss broader implications."
            ),
            "conclusion": (
                "Concisely restate contributions and their significance. "
                "Identify the single most important direction for future work."
            ),
        },
        citation_style="IEEE",
        tone_profile="academic",
        depth_level="deep",
        output_format="markdown",
        file_extension=".md",
        max_research_rounds=4,
        preferred_sources=["arxiv", "web", "pdf", "github"],
        eval_threshold=0.82,
        max_draft_iterations=3,
        target_words_per_section=700,
    ),

    "blog": OutputModeConfig(
        name="blog",
        display_name="Blog Post / Newsletter",
        structure_template=[
            "hook", "context", "main_body", "key_takeaways", "call_to_action",
        ],
        section_prompts={
            "hook": (
                "Open with a surprising statistic, provocative question, or brief "
                "compelling anecdote. Max 3 sentences. No jargon."
            ),
            "context": (
                "Give just enough background to understand why this topic matters. "
                "Write as if explaining to a smart, curious non-specialist."
            ),
            "main_body": (
                "Develop 3-5 main points. Each should have a short punchy subheading, "
                "a concrete example or data point, and a practical implication. "
                "Keep paragraphs under 4 sentences."
            ),
            "key_takeaways": (
                "List 3-5 bullet points the reader should remember. "
                "Each bullet is one crisp sentence."
            ),
            "call_to_action": (
                "End with one clear next step the reader can take, "
                "or a question that invites comments/replies."
            ),
        },
        citation_style="inline_links",
        tone_profile="conversational",
        depth_level="standard",
        output_format="markdown",
        file_extension=".md",
        max_research_rounds=2,
        preferred_sources=["web", "youtube", "arxiv"],
        eval_threshold=0.72,
        max_draft_iterations=2,
        target_words_per_section=350,
    ),

    "tech_doc": OutputModeConfig(
        name="tech_doc",
        display_name="Technical Documentation",
        structure_template=[
            "overview", "prerequisites", "architecture", "installation_or_setup",
            "usage", "api_reference", "examples", "troubleshooting", "changelog",
        ],
        section_prompts={
            "overview": (
                "State in one paragraph: what this system does, who it is for, "
                "and what problem it solves. Include a one-line summary at the top."
            ),
            "prerequisites": (
                "List every dependency with version constraints. "
                "Separate required from optional. Include links to install guides."
            ),
            "architecture": (
                "Describe the system's key components and how they interact. "
                "Include a Mermaid diagram block if appropriate."
            ),
            "installation_or_setup": (
                "Write step-by-step setup instructions. Every command must be "
                "in a code block. Include expected output where helpful."
            ),
            "usage": (
                "Show the most common use cases first. Every code example must "
                "be runnable as-is. Annotate non-obvious lines with comments."
            ),
            "api_reference": (
                "Document every public function/endpoint: signature, "
                "parameter types, return type, and a minimal example."
            ),
            "troubleshooting": (
                "List the 5 most common errors with their exact error message, "
                "cause, and fix."
            ),
        },
        citation_style="none",
        tone_profile="precise",
        depth_level="standard",
        output_format="markdown",
        file_extension=".md",
        max_research_rounds=2,
        preferred_sources=["github", "web", "pdf"],
        eval_threshold=0.80,
        max_draft_iterations=3,
        target_words_per_section=500,
    ),

    "report": OutputModeConfig(
        name="report",
        display_name="Business Report",
        structure_template=[
            "executive_summary", "background", "findings",
            "analysis", "recommendations", "appendices",
        ],
        section_prompts={
            "executive_summary": (
                "Write a half-page summary a C-suite reader can act on without "
                "reading the rest. Cover: situation, key findings, top recommendation, "
                "and expected impact."
            ),
            "background": (
                "Provide the business context: market situation, what prompted "
                "this analysis, and the scope/limitations of the report."
            ),
            "findings": (
                "Present data-backed findings. Use bullet points for scannability. "
                "Each finding needs a supporting data point or source."
            ),
            "analysis": (
                "Interpret the findings. Apply a recognised framework (SWOT, Porter's "
                "Five Forces, etc.) where appropriate. Be direct about cause and effect."
            ),
            "recommendations": (
                "State 3-5 prioritised, actionable recommendations. For each: "
                "what to do, why, who owns it, and a rough timeline."
            ),
        },
        citation_style="none",
        tone_profile="formal",
        depth_level="standard",
        output_format="docx",
        file_extension=".docx",
        max_research_rounds=3,
        preferred_sources=["web", "pdf", "arxiv"],
        eval_threshold=0.78,
        max_draft_iterations=3,
        target_words_per_section=500,
    ),
}


def get_mode(name: str) -> OutputModeConfig:
    """Return a mode config by name, raising a clear error if not found."""
    if name not in MODES:
        available = ", ".join(MODES.keys())
        raise ValueError(f"Unknown mode '{name}'. Available modes: {available}")
    return MODES[name]


def list_modes() -> list[str]:
    """Return all available mode names."""
    return list(MODES.keys())
