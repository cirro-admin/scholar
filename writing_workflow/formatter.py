"""
writing_workflow/formatter.py
──────────────────────────────
Renders the completed draft to the final output format.
Supports: Markdown (.md), DOCX (.docx), PDF (.pdf), HTML (.html)
Format is determined by the OutputModeConfig.
"""

from __future__ import annotations
import os, re, textwrap
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from config.modes import OutputModeConfig
from writing_workflow.outline_gen import Outline
from writing_workflow.section_drafter import DraftedSection


@dataclass
class FormattedOutput:
    file_path: str
    format:    str
    word_count: int
    section_count: int


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60]


def _build_markdown(
    title: str,
    sections: list[DraftedSection],
    mode: OutputModeConfig,
    topic: str,
) -> str:
    """Assemble sections into a single Markdown document."""
    lines = [f"# {title}", ""]

    # Front matter for academic modes
    if mode.name in ("thesis", "article"):
        lines += [
            f"*Generated: {datetime.now().strftime('%B %d, %Y')}*",
            f"*Topic: {topic}*",
            "",
            "---",
            "",
        ]

    for sec in sections:
        # Skip structural sections that have no prose
        if sec.key in ("title_page", "table_of_contents"):
            continue
        lines.append(f"## {sec.title}")
        lines.append("")
        lines.append(sec.content)
        lines.append("")

    return "\n".join(lines)


def _build_docx(
    title: str,
    sections: list[DraftedSection],
    mode: OutputModeConfig,
    output_path: Path,
) -> None:
    """Write a formatted DOCX using python-docx."""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Title page
    title_para = doc.add_heading(title, level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}")
    doc.add_page_break()

    for sec in sections:
        if sec.key == "title_page":
            continue
        if sec.key == "table_of_contents":
            doc.add_heading("Table of Contents", level=1)
            for s in sections:
                if s.key not in ("title_page", "table_of_contents"):
                    doc.add_paragraph(s.title, style="List Bullet")
            doc.add_page_break()
            continue

        doc.add_heading(sec.title, level=1)

        # Split content into paragraphs and add each
        for para_text in sec.content.split("\n\n"):
            para_text = para_text.strip()
            if not para_text:
                continue
            if para_text.startswith("## "):
                doc.add_heading(para_text[3:], level=2)
            elif para_text.startswith("### "):
                doc.add_heading(para_text[4:], level=3)
            elif para_text.startswith("- ") or para_text.startswith("* "):
                for item in para_text.split("\n"):
                    item = item.lstrip("-* ").strip()
                    if item:
                        doc.add_paragraph(item, style="List Bullet")
            else:
                doc.add_paragraph(para_text)

    doc.save(str(output_path))


def _build_html(
    title: str,
    sections: list[DraftedSection],
    mode: OutputModeConfig,
) -> str:
    """Build a clean single-file HTML document."""
    body_parts = []
    for sec in sections:
        if sec.key in ("title_page", "table_of_contents"):
            continue
        safe_content = sec.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Convert markdown-style paragraphs to <p> tags
        paragraphs = [f"<p>{p.strip()}</p>" for p in safe_content.split("\n\n") if p.strip()]
        body_parts.append(f'<section id="{sec.key}">')
        body_parts.append(f"<h2>{sec.title}</h2>")
        body_parts.extend(paragraphs)
        body_parts.append("</section>")

    body = "\n".join(body_parts)

    return textwrap.dedent(f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>{title}</title>
          <style>
            body {{ font-family: Georgia, serif; max-width: 860px; margin: 60px auto;
                    line-height: 1.8; color: #222; padding: 0 20px; }}
            h1   {{ font-size: 2rem; margin-bottom: 0.25em; }}
            h2   {{ font-size: 1.35rem; margin-top: 2.5em; border-bottom: 1px solid #ddd;
                    padding-bottom: 0.3em; }}
            p    {{ margin: 1em 0; text-align: justify; }}
            section {{ margin-bottom: 2em; }}
          </style>
        </head>
        <body>
          <h1>{title}</h1>
          <p><em>Generated: {datetime.now().strftime('%B %d, %Y')}</em></p>
          <hr>
          {body}
        </body>
        </html>
    """).strip()


# ── Public interface ──────────────────────────────────────────────────────────

def render(
    outline: Outline,
    sections: list[DraftedSection],
    mode: OutputModeConfig,
    output_dir: str = "./outputs",
) -> FormattedOutput:
    """
    Render all drafted sections into the final output file.
    Creates output_dir if it doesn't exist.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    slug      = _slugify(outline.title)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename  = f"{slug}_{timestamp}{mode.file_extension}"
    out_path  = out_dir / filename

    total_words = sum(s.word_count for s in sections)

    if mode.output_format == "markdown":
        content = _build_markdown(outline.title, sections, mode, outline.topic)
        out_path.write_text(content, encoding="utf-8")

    elif mode.output_format == "docx":
        _build_docx(outline.title, sections, mode, out_path)

    elif mode.output_format == "html":
        content = _build_html(outline.title, sections, mode)
        out_path.write_text(content, encoding="utf-8")

    elif mode.output_format == "pdf":
        # Build HTML first, then convert to PDF via weasyprint
        html_content = _build_html(outline.title, sections, mode)
        try:
            from weasyprint import HTML
            HTML(string=html_content).write_pdf(str(out_path))
        except ImportError:
            # Fallback to markdown if weasyprint not installed
            md_path = out_path.with_suffix(".md")
            md_content = _build_markdown(outline.title, sections, mode, outline.topic)
            md_path.write_text(md_content, encoding="utf-8")
            print(f"[formatter] weasyprint not installed — saved as {md_path}")
            out_path = md_path

    print(f"[formatter] Saved → {out_path} ({total_words:,} words)")

    return FormattedOutput(
        file_path=str(out_path),
        format=mode.output_format,
        word_count=total_words,
        section_count=len(sections),
    )
