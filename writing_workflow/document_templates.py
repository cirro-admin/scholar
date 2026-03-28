"""
writing_workflow/document_templates.py
────────────────────────────────────────
Format-native document templates for each output mode.

Each mode gets a DocumentTemplate that controls:
  - Front page / title block layout
  - Page margins, fonts, line spacing
  - Header / footer content
  - Section heading styles
  - Citation format
  - Any mode-specific metadata fields

Supported modes and their native formats:
  thesis    → University thesis (APA 7, double-spaced, TOC, front page with institution)
  article   → IEEE / APA journal article (two-column option, abstract box, keywords)
  blog      → Clean web article (no formal structure, pull quotes, byline)
  tech_doc  → Technical documentation (monospace code, version header, changelog)
  report    → Business report (executive summary box, company branding placeholder)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DocumentMeta:
    """User-supplied metadata — passed at run time via CLI or web form."""
    # Universal
    author:      str = "Author Name"
    date:        str = ""          # defaults to today if empty

    # Thesis specific
    university:  str = ""
    department:  str = ""
    supervisor:  str = ""
    student_id:  str = ""
    degree:      str = ""          # e.g. "Master of Science", "Doctor of Philosophy"
    submission_date: str = ""      # e.g. "May 2025"
    submission_statement: str = "" # auto-generated from degree if empty

    # Article specific
    affiliation:   str = ""
    email:         str = ""
    keywords:      list[str] = field(default_factory=list)
    journal_name:  str = ""
    journal_style: str = "nature"  # nature | ieee | apa | acm

    # Blog / report specific
    organisation: str = ""
    tagline:      str = ""

    def get_submission_statement(self) -> str:
        if self.submission_statement:
            return self.submission_statement
        if self.degree:
            return (f"A dissertation submitted in partial fulfilment of the requirements "
                    f"for the degree of {self.degree}")
        return "Submitted in partial fulfilment of the degree requirements"

    def get_submission_date(self) -> str:
        from datetime import datetime
        return self.submission_date or self.date or datetime.now().strftime("%B %Y")


@dataclass
class DocumentTemplate:
    mode:             str
    page_width_cm:    float = 21.0    # A4
    page_height_cm:   float = 29.7
    margin_top_cm:    float = 2.54
    margin_bottom_cm: float = 2.54
    margin_left_cm:   float = 3.81   # APA 7 thesis: 1.5" left for binding
    margin_right_cm:  float = 2.54
    line_spacing:     float = 2.0    # 1=single, 1.5=one-half, 2.0=double
    font_name:        str   = "Times New Roman"
    font_size_pt:     int   = 12
    header_text:      str   = ""
    footer_text:      str   = ""
    page_numbers:     bool  = True
    page_number_position: str = "bottom_center"  # top_right for APA running head
    has_running_head: bool  = False
    column_count:     int   = 1


TEMPLATES: dict[str, DocumentTemplate] = {

    "thesis": DocumentTemplate(
        mode="thesis",
        margin_left_cm=3.81,    # 1.5 inches for binding
        margin_right_cm=2.54,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        line_spacing=2.0,       # APA 7: double-spaced throughout
        font_name="Times New Roman",
        font_size_pt=12,
        has_running_head=False,
        page_numbers=True,
        page_number_position="bottom_center",
    ),

    "article": DocumentTemplate(
        mode="article",
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        line_spacing=1.5,
        font_name="Times New Roman",
        font_size_pt=11,
        has_running_head=True,   # IEEE/APA: running head at top
        page_numbers=True,
        page_number_position="top_right",
    ),

    "blog": DocumentTemplate(
        mode="blog",
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        margin_top_cm=2.0,
        margin_bottom_cm=2.0,
        line_spacing=1.5,
        font_name="Calibri",
        font_size_pt=11,
        page_numbers=False,
    ),

    "tech_doc": DocumentTemplate(
        mode="tech_doc",
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        margin_top_cm=2.54,
        margin_bottom_cm=2.54,
        line_spacing=1.15,
        font_name="Calibri",
        font_size_pt=11,
        page_numbers=True,
        page_number_position="bottom_right",
    ),

    "report": DocumentTemplate(
        mode="report",
        margin_left_cm=2.54,
        margin_right_cm=2.54,
        margin_top_cm=3.0,
        margin_bottom_cm=2.54,
        line_spacing=1.15,
        font_name="Calibri",
        font_size_pt=11,
        page_numbers=True,
        page_number_position="bottom_right",
    ),
}


def get_template(mode: str) -> DocumentTemplate:
    return TEMPLATES.get(mode, TEMPLATES["report"])
