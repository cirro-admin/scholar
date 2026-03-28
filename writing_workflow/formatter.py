"""
writing_workflow/formatter.py
──────────────────────────────
Renders completed draft + rich elements to the final output format.
Supports: Markdown (.md), DOCX (.docx), PDF (.pdf), HTML (.html)

Rich element rendering per format:
  Markdown : mermaid fences, MD tables, $$LaTeX$$, PNG image refs, code fences
  DOCX     : embedded PNG images, native tables, monospace code blocks
  PDF      : fully rendered via WeasyPrint (mermaid/latex as PNG)
  HTML     : interactive Plotly, live Mermaid.js, MathJax, highlight.js
"""

from __future__ import annotations
import os, re, json, textwrap
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from config.modes import OutputModeConfig
from writing_workflow.outline_gen import Outline
from writing_workflow.section_drafter import DraftedSection
from writing_workflow.rich_content_generator import RichElement


@dataclass
class FormattedOutput:
    file_path:     str
    format:        str
    word_count:    int
    section_count: int
    figure_count:  int


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60]


def _label_elements(sections: list[DraftedSection]) -> None:
    """Assign Figure/Table/Equation labels across all sections sequentially."""
    fig_n = table_n = eq_n = code_n = 1
    for sec in sections:
        for el in sec.rich_elements:
            if el.type in ("mermaid", "chart"):
                el.label = f"Figure {fig_n}"
                fig_n += 1
            elif el.type == "table":
                el.label = f"Table {table_n}"
                table_n += 1
            elif el.type == "latex":
                el.label = f"Equation {eq_n}"
                eq_n += 1
            elif el.type == "code":
                el.label = f"Listing {code_n}"
                code_n += 1


# ── Markdown renderer ─────────────────────────────────────────────────────────

def _rich_to_markdown(el: RichElement) -> str:
    label_line = f"*{el.label}: {el.caption}*\n\n" if el.label else ""
    if el.type == "mermaid":
        return f"\n\n{label_line}```mermaid\n{el.source}\n```\n"
    elif el.type == "table":
        return f"\n\n{label_line}{el.source}\n"
    elif el.type == "latex":
        return f"\n\n{label_line}$$\n{el.source}\n$$\n"
    elif el.type == "chart":
        if el.image_path and Path(el.image_path).exists():
            return f"\n\n{label_line}![{el.caption}]({el.image_path})\n"
        return f"\n\n*[Chart: {el.caption}]*\n"
    elif el.type == "code":
        return f"\n\n{label_line}{el.source}\n"
    return ""


def _build_markdown(title, sections, mode, topic):
    lines = [f"# {title}", ""]
    if mode.name in ("thesis", "article"):
        lines += [f"*Generated: {datetime.now().strftime('%B %d, %Y')}*",
                  f"*Topic: {topic}*", "", "---", ""]
    for sec in sections:
        if sec.key in ("title_page", "table_of_contents"):
            continue
        lines.append(f"## {sec.title}")
        lines.append("")
        lines.append(sec.content)
        for el in sec.rich_elements:
            lines.append(_rich_to_markdown(el))
        lines.append("")
    return "\n".join(lines)


# ── DOCX renderer ─────────────────────────────────────────────────────────────

def _rich_to_docx(el: RichElement, doc) -> None:
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    if el.type in ("mermaid", "chart", "latex") and el.image_path and Path(el.image_path).exists():
        doc.add_paragraph()
        run = doc.add_paragraph().add_run()
        run.add_picture(el.image_path, width=Inches(5.5))
        cap = doc.add_paragraph(f"{el.label}: {el.caption}" if el.label else el.caption)
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.runs[0].font.size = Pt(9)
        cap.runs[0].italic    = True

    elif el.type == "table":
        # Parse markdown table and create native DOCX table
        rows = [r for r in el.source.strip().splitlines() if r.strip().startswith("|")]
        rows = [r for r in rows if not re.match(r"^\|[-:| ]+\|$", r.strip())]
        if rows:
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            ncols = max(len(row) for row in cells)
            table = doc.add_table(rows=len(cells), cols=ncols)
            table.style = "Table Grid"
            for i, row in enumerate(cells):
                for j, cell_text in enumerate(row[:ncols]):
                    cell = table.rows[i].cells[j]
                    cell.text = cell_text
                    if i == 0:
                        for run in cell.paragraphs[0].runs:
                            run.bold = True
            cap = doc.add_paragraph(f"{el.label}: {el.caption}" if el.label else el.caption)
            cap.runs[0].font.size = Pt(9)
            cap.runs[0].italic    = True

    elif el.type == "code":
        code_text = re.sub(r"^```\w*\n?", "", el.source).rstrip("`").strip()
        p = doc.add_paragraph(style="No Spacing")
        run = p.add_run(code_text)
        run.font.name = "Courier New"
        run.font.size = Pt(8)


def _build_docx(title, sections, mode, output_path):
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    title_para = doc.add_heading(title, level=0)
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}")
    doc.add_page_break()

    for sec in sections:
        if sec.key == "title_page":
            continue
        if sec.key == "table_of_contents":
            # APA 7: ToC on its own page, centred heading, no bold/italic
            doc.add_page_break()
            toc_heading = doc.add_heading("Table of Contents", level=1)
            toc_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # Remove bold from heading to match APA 7 style
            for run in toc_heading.runs:
                run.bold = False
            doc.add_paragraph()  # blank line after heading
            for s in sections:
                if s.key not in ("title_page", "table_of_contents"):
                    # APA 7 ToC: section title left, page number right (dotted leader)
                    toc_para = doc.add_paragraph(style="No Spacing")
                    toc_run  = toc_para.add_run(s.title)
                    toc_run.font.size  = Pt(12)
                    # Add tab stop for right-aligned page numbers
                    toc_para.add_run("\t")
            doc.add_page_break()
            continue

        doc.add_heading(sec.title, level=1)
        for para_text in sec.content.split("\n\n"):
            para_text = para_text.strip()
            if not para_text:
                continue
            if para_text.startswith("## "):
                doc.add_heading(para_text[3:], level=2)
            elif para_text.startswith("### "):
                doc.add_heading(para_text[4:], level=3)
            elif para_text.startswith(("- ", "* ")):
                for item in para_text.split("\n"):
                    item = item.lstrip("-* ").strip()
                    if item:
                        doc.add_paragraph(item, style="List Bullet")
            else:
                doc.add_paragraph(para_text)

        for el in sec.rich_elements:
            _rich_to_docx(el, doc)

    doc.save(str(output_path))


# ── HTML renderer ─────────────────────────────────────────────────────────────

def _rich_to_html(el: RichElement) -> str:
    label_html = f'<p class="caption"><em>{el.label}: {el.caption}</em></p>' if el.label else ""

    if el.type == "mermaid":
        return textwrap.dedent(f"""
            <div class="rich-block">
              <div class="mermaid">{el.source}</div>
              {label_html}
            </div>""")

    elif el.type == "table":
        return f'<div class="rich-block">{label_html}<div class="md-table">{el.source}</div></div>'

    elif el.type == "latex":
        return f'<div class="rich-block"><div class="math">\\[{el.source}\\]</div>{label_html}</div>'

    elif el.type == "chart":
        try:
            spec = json.loads(el.source)
            data_js = json.dumps(spec)
            uid  = abs(hash(el.source)) % 100000
            return textwrap.dedent(f"""
                <div class="rich-block">
                  <div id="chart_{uid}" style="width:100%;height:400px;"></div>
                  {label_html}
                  <script>
                  (function(){{
                    var spec = {data_js};
                    var traces = spec.data.map(function(s){{
                      return {{x: spec.x_labels, y: s.values, name: s.series,
                               type: spec.type === 'line' ? 'scatter' : spec.type,
                               mode: spec.type === 'line' ? 'lines+markers' : undefined}};
                    }});
                    Plotly.newPlot('chart_{uid}', traces,
                      {{title: spec.title, xaxis:{{title:spec.x_label}},
                        yaxis:{{title:spec.y_label}}, margin:{{t:40}}}});
                  }})();
                  </script>
                </div>""")
        except Exception:
            return f'<div class="rich-block"><p>[Chart: {el.caption}]</p></div>'

    elif el.type == "code":
        lang = "python"
        code = el.source
        m    = re.match(r"^```(\w+)\n(.*?)```$", el.source, re.DOTALL)
        if m:
            lang, code = m.group(1), m.group(2)
        safe_code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return textwrap.dedent(f"""
            <div class="rich-block">
              {label_html}
              <pre><code class="language-{lang}">{safe_code}</code></pre>
            </div>""")
    return ""


def _build_html(title, sections, mode):
    body_parts = []
    for sec in sections:
        if sec.key in ("title_page", "table_of_contents"):
            continue
        safe_content = sec.content.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        paras = [f"<p>{p.strip()}</p>" for p in safe_content.split("\n\n") if p.strip()]
        body_parts.append(f'<section id="{sec.key}"><h2>{sec.title}</h2>')
        body_parts.extend(paras)
        for el in sec.rich_elements:
            body_parts.append(_rich_to_html(el))
        body_parts.append("</section>")
    body = "\n".join(body_parts)

    return textwrap.dedent(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <!-- Plotly for interactive charts -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.32.0/plotly.min.js"></script>
  <!-- Mermaid for diagrams -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.0/mermaid.min.js"></script>
  <!-- MathJax for LaTeX -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.min.js"></script>
  <!-- Highlight.js for code -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
  <style>
    body {{ font-family: Georgia, serif; max-width: 860px; margin: 60px auto;
            line-height: 1.8; color: #222; padding: 0 20px; }}
    h1   {{ font-size: 2rem; margin-bottom: 0.25em; }}
    h2   {{ font-size: 1.35rem; margin-top: 2.5em; border-bottom: 1px solid #ddd; padding-bottom: 0.3em; }}
    p    {{ margin: 1em 0; text-align: justify; }}
    .rich-block {{ margin: 2em 0; padding: 1em; background: #f9f9f9;
                   border-left: 3px solid #ccc; border-radius: 4px; }}
    .caption {{ font-size: 0.9em; color: #555; text-align: center; margin-top: 0.5em; }}
    pre  {{ background: #f5f5f5; padding: 1em; overflow-x: auto;
            border-radius: 4px; font-size: 0.85em; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    th {{ background: #f0f0f0; font-weight: bold; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p><em>Generated: {datetime.now().strftime('%B %d, %Y')}</em></p>
  <hr>
  {body}
  <script>
    mermaid.initialize({{startOnLoad: true, theme: 'default'}});
    document.addEventListener('DOMContentLoaded', function() {{
      document.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
    }});
  </script>
</body>
</html>""").strip()


# ── Public interface ──────────────────────────────────────────────────────────

def render(outline: Outline, sections: list[DraftedSection],
           mode: OutputModeConfig, output_dir: str = "./outputs") -> FormattedOutput:
    out_dir  = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Assign sequential labels across all sections
    _label_elements(sections)

    slug      = _slugify(outline.title)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename  = f"{slug}_{timestamp}{mode.file_extension}"
    out_path  = out_dir / filename
    total_words = sum(s.word_count for s in sections)
    total_figs  = sum(len(s.rich_elements) for s in sections)

    if mode.output_format == "markdown":
        content = _build_markdown(outline.title, sections, mode, outline.topic)
        out_path.write_text(content, encoding="utf-8")

    elif mode.output_format == "docx":
        _build_docx(outline.title, sections, mode, out_path)

    elif mode.output_format == "html":
        content = _build_html(outline.title, sections, mode)
        out_path.write_text(content, encoding="utf-8")

    elif mode.output_format == "pdf":
        html_content = _build_html(outline.title, sections, mode)
        try:
            from weasyprint import HTML
            HTML(string=html_content).write_pdf(str(out_path))
        except ImportError:
            md_path = out_path.with_suffix(".md")
            md_content = _build_markdown(outline.title, sections, mode, outline.topic)
            md_path.write_text(md_content, encoding="utf-8")
            print(f"[formatter] weasyprint not installed — saved as {md_path}")
            out_path = md_path

    print(f"[formatter] Saved → {out_path} ({total_words:,} words, {total_figs} figures)")
    return FormattedOutput(file_path=str(out_path), format=mode.output_format,
                           word_count=total_words, section_count=len(sections),
                           figure_count=total_figs)
