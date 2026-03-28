"""
writing_workflow/journal_styles.py
────────────────────────────────────
Journal article style presets.
Each style controls citation format, heading style, abstract format,
line spacing, font, and section naming conventions.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class JournalStyle:
    name:             str
    display_name:     str
    citation_format:  str       # "author_year" | "numbered" | "superscript"
    abstract_format:  str       # "single_block" | "structured" | "highlights"
    line_spacing:     float
    font_name:        str
    font_size_pt:     int
    heading_style:    str       # "bold_left" | "bold_center" | "italic_left"
    max_abstract_words: int
    keywords_label:   str       # "Keywords:" | "Key words:" | "Index Terms:"
    section_names:    dict[str, str]  # override default section names
    notes:            str = ""


JOURNAL_STYLES: dict[str, JournalStyle] = {

    "nature": JournalStyle(
        name="nature",
        display_name="Nature / Springer",
        citation_format="superscript",        # Smith et al.¹
        abstract_format="single_block",       # one unstructured paragraph
        line_spacing=1.5,
        font_name="Times New Roman",
        font_size_pt=11,
        heading_style="bold_left",
        max_abstract_words=200,
        keywords_label="Keywords:",
        section_names={
            "introduction":          "Introduction",
            "methodology":           "Methods",
            "experiments_or_results":"Results",
            "discussion":            "Discussion",
            "conclusion":            "Conclusions",
            "related_work":          "Related work",
        },
        notes="Nature: no bold/italic in abstract, methods after results, online methods for detail.",
    ),

    "ieee": JournalStyle(
        name="ieee",
        display_name="IEEE",
        citation_format="numbered",           # [1], [2]
        abstract_format="single_block",
        line_spacing=1.0,                     # IEEE: single spaced, two-column
        font_name="Times New Roman",
        font_size_pt=10,
        heading_style="bold_center",
        max_abstract_words=250,
        keywords_label="Index Terms:",
        section_names={
            "introduction":          "I. Introduction",
            "related_work":          "II. Related Work",
            "methodology":           "III. Methodology",
            "experiments_or_results":"IV. Results",
            "discussion":            "V. Discussion",
            "conclusion":            "VI. Conclusion",
        },
        notes="IEEE: Roman numeral section numbering, Index Terms not Keywords.",
    ),

    "apa": JournalStyle(
        name="apa",
        display_name="APA 7",
        citation_format="author_year",        # (Smith, 2023)
        abstract_format="structured",         # Background / Objective / Method / Results / Conclusions
        line_spacing=2.0,                     # APA: double-spaced
        font_name="Times New Roman",
        font_size_pt=12,
        heading_style="bold_center",
        max_abstract_words=250,
        keywords_label="Keywords:",
        section_names={
            "introduction":          "Introduction",
            "methodology":           "Method",
            "experiments_or_results":"Results",
            "discussion":            "Discussion",
            "conclusion":            "Conclusion",
        },
        notes="APA 7: running head top-left, page number top-right, bold centred level-1 headings.",
    ),

    "acm": JournalStyle(
        name="acm",
        display_name="ACM",
        citation_format="numbered",
        abstract_format="single_block",
        line_spacing=1.15,
        font_name="Linux Libertine",
        font_size_pt=10,
        heading_style="bold_left",
        max_abstract_words=300,
        keywords_label="CCS Concepts:",
        section_names={
            "introduction":          "Introduction",
            "related_work":          "Related Work",
            "methodology":           "Approach",
            "experiments_or_results":"Evaluation",
            "discussion":            "Discussion",
            "conclusion":            "Conclusion",
        },
        notes="ACM: CCS concepts + keywords, acknowledgements before references.",
    ),
}


def get_journal_style(name: str) -> JournalStyle:
    if name not in JOURNAL_STYLES:
        print(f"[journal_styles] Unknown style '{name}', defaulting to Nature/Springer")
        return JOURNAL_STYLES["nature"]
    return JOURNAL_STYLES[name]


def list_journal_styles() -> list[str]:
    return list(JOURNAL_STYLES.keys())
