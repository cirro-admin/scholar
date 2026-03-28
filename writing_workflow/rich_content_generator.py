"""
writing_workflow/rich_content_generator.py
───────────────────────────────────────────
Generates rich content elements (figures, tables, equations, code, diagrams)
that are embedded alongside section prose.

Design:
  1. LLM analyses the drafted section and research notes
  2. Decides which rich elements to generate (type, placement, data)
  3. Generates each element using the appropriate renderer
  4. Returns a list of RichElement objects with rendered artifacts

Supported types:
  - mermaid    : flowcharts, sequence diagrams, ER diagrams
  - table      : markdown-compatible comparison/results tables
  - latex      : mathematical equations and formulas
  - chart      : matplotlib bar/line/scatter charts (saved as PNG)
  - code       : syntax-highlighted code snippets
"""

from __future__ import annotations
import os, json, textwrap, tempfile, hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from utils.llm import generate_json, generate

RichType = Literal["mermaid", "table", "latex", "chart", "code"]


@dataclass
class RichElement:
    type:        RichType
    caption:     str            # figure/table caption
    placement:   str            # "after_paragraph_1", "end_of_section" etc.
    source:      str            # raw source (mermaid code, LaTeX, python code, etc.)
    image_path:  str = ""       # path to rendered PNG (for chart, latex, mermaid in DOCX/PDF)
    label:       str = ""       # Figure 1, Table 2, Equation 3 etc. — filled by formatter


# ── Mermaid ───────────────────────────────────────────────────────────────────

def _render_mermaid_to_png(source: str, output_dir: str) -> str:
    """Render Mermaid diagram to PNG using mmdc CLI."""
    h        = hashlib.md5(source.encode()).hexdigest()[:8]
    mmd_path = Path(output_dir) / f"mermaid_{h}.mmd"
    png_path = Path(output_dir) / f"mermaid_{h}.png"
    mmd_path.write_text(source)
    ret = os.system(f"mmdc -i {mmd_path} -o {png_path} -b transparent -w 800 2>/dev/null")
    if ret != 0 or not png_path.exists():
        return ""   # mmdc not installed — markdown fallback used
    return str(png_path)


# ── LaTeX ─────────────────────────────────────────────────────────────────────

def _render_latex_to_png(latex: str, output_dir: str) -> str:
    """Render LaTeX equation to PNG using matplotlib's mathtext engine."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use("Agg")

        h        = hashlib.md5(latex.encode()).hexdigest()[:8]
        png_path = Path(output_dir) / f"latex_{h}.png"

        fig, ax = plt.subplots(figsize=(6, 1.2))
        ax.axis("off")
        # Ensure it's wrapped in $$ for display math
        expr = latex.strip()
        if not expr.startswith("$"):
            expr = f"$${expr}$$"
        ax.text(0.5, 0.5, expr, fontsize=16, ha="center", va="center",
                transform=ax.transAxes)
        fig.savefig(str(png_path), dpi=150, bbox_inches="tight",
                    facecolor="white", transparent=False)
        plt.close(fig)
        return str(png_path)
    except Exception as e:
        print(f"[rich] LaTeX render failed: {e}")
        return ""


# ── Chart ─────────────────────────────────────────────────────────────────────

def _render_chart_to_png(chart_spec: dict, output_dir: str) -> str:
    """
    Execute a chart spec and save as PNG.
    chart_spec: {type, title, x_label, y_label, data: [{label, values}]}
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        h        = hashlib.md5(json.dumps(chart_spec).encode()).hexdigest()[:8]
        png_path = Path(output_dir) / f"chart_{h}.png"

        fig, ax  = plt.subplots(figsize=(8, 5))
        chart_type = chart_spec.get("type", "bar")
        data       = chart_spec.get("data", [])
        labels     = chart_spec.get("x_labels", [d.get("label", f"Item {i}") for i, d in enumerate(data)])

        if chart_type == "bar":
            n_series = max(len(d.get("values", [])) for d in data) if data else 1
            x = np.arange(len(labels))
            width = 0.8 / max(n_series, 1)
            for i, series in enumerate(data):
                vals = series.get("values", [])
                if isinstance(vals, list):
                    ax.bar(x + i * width - (n_series - 1) * width / 2,
                           vals[:len(x)], width, label=series.get("series", ""))
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)

        elif chart_type == "line":
            for series in data:
                vals = series.get("values", [])
                ax.plot(labels[:len(vals)], vals, marker="o",
                        label=series.get("series", ""))

        elif chart_type == "scatter":
            for series in data:
                pts = series.get("points", [])
                if pts:
                    ax.scatter([p[0] for p in pts], [p[1] for p in pts],
                               label=series.get("series", ""), alpha=0.7)

        ax.set_title(chart_spec.get("title", ""), fontsize=12, fontweight="bold")
        ax.set_xlabel(chart_spec.get("x_label", ""), fontsize=10)
        ax.set_ylabel(chart_spec.get("y_label", ""), fontsize=10)
        if any(d.get("series") for d in data):
            ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(str(png_path), dpi=150, bbox_inches="tight")
        plt.close(fig)
        return str(png_path)
    except Exception as e:
        print(f"[rich] Chart render failed: {e}")
        return ""


# ── Decision + generation ─────────────────────────────────────────────────────

DECISION_PROMPT = """
You are an expert academic editor. Analyse this section draft and research context,
then decide which rich elements (figures, tables, equations, code) would strengthen it.

Section title: {title}
Document type: {mode}
Section content (excerpt):
{content}

Research notes available:
{notes}

Decide which rich elements to generate. Only suggest elements that are genuinely
warranted — do not add fluff. A methodology section benefits from a flowchart.
A results section benefits from tables and charts. A theory section benefits from equations.
A technical section benefits from code snippets.

Return a JSON array (empty array if no rich content needed):
[
  {{
    "type": "mermaid|table|latex|chart|code",
    "caption": "Figure/Table caption (concise, specific)",
    "placement": "after_intro|after_paragraph_2|end_of_section",
    "rationale": "why this element is needed here"
  }}
]

Rules:
- Max 3 elements per section
- Only suggest an element if you have enough data from the research notes to populate it
- Prefer tables over prose lists when comparing 3+ items
- Prefer charts when showing quantitative trends or comparisons
- Prefer mermaid for process flows, architectures, sequences
- Prefer latex for any mathematical expressions
- Prefer code only in tech_doc or methodology sections with algorithmic content
Return ONLY a valid JSON array, no fences.
"""

GENERATION_PROMPTS = {
    "mermaid": """
Generate a Mermaid diagram for this figure.
Caption: {caption}
Context: {context}
Research data: {notes}

Return ONLY valid Mermaid diagram source code (no fences, no explanation).
Choose the most appropriate diagram type:
- flowchart TD for processes/pipelines
- sequenceDiagram for interactions
- erDiagram for data relationships
- graph LR for hierarchies
Keep it clear and readable — max 12 nodes.
""",

    "table": """
Generate a Markdown table for this figure.
Caption: {caption}
Context: {context}
Research data: {notes}

Return ONLY a valid Markdown table (| col | col | format).
Rules:
- Include a header row with bold column names
- Max 8 rows, max 5 columns
- Use real data from the research notes — no placeholder values
- Align numeric columns right using :---:
""",

    "latex": """
Generate a LaTeX mathematical expression for this equation.
Caption: {caption}
Context: {context}

Return ONLY the LaTeX expression (no $$ delimiters, no explanation).
Examples of valid output:
  f(x) = \\frac{{1}}{{\\sigma\\sqrt{{2\\pi}}}} e^{{-\\frac{{(x-\\mu)^2}}{{2\\sigma^2}}}}
  \\text{{Accuracy}} = \\frac{{TP + TN}}{{TP + TN + FP + FN}}
""",

    "chart": """
Generate a chart specification for this figure.
Caption: {caption}
Context: {context}
Research data: {notes}

Return ONLY a valid JSON object:
{{
  "type": "bar|line|scatter",
  "title": "chart title",
  "x_label": "x axis label",
  "y_label": "y axis label",
  "x_labels": ["label1", "label2"],
  "data": [
    {{"series": "Series name", "values": [1.0, 2.0, 3.0]}}
  ]
}}
Use ONLY real quantitative data from the research notes.
If insufficient data, return {{"type": "bar", "title": "", "data": []}}.
""",

    "code": """
Generate a code snippet for this example.
Caption: {caption}
Context: {context}

Return JSON:
{{
  "language": "python|bash|javascript|r|sql|etc",
  "code": "the actual code here"
}}
Rules:
- Code must be complete and runnable
- Max 30 lines
- Include inline comments for clarity
- Use realistic variable names, not placeholder_var
""",
}


def generate_rich_elements(
    section_title: str,
    section_content: str,
    mode_name: str,
    research_notes: str,
    output_dir: str,
    api_key: str = "",
) -> list[RichElement]:
    """
    Auto-detect and generate all rich elements for a section.
    Returns list of RichElement objects ready for the formatter.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: decide what to generate
    decision_prompt = DECISION_PROMPT.format(
        title=section_title,
        mode=mode_name,
        content=section_content[:1500],
        notes=research_notes[:1000],
    )
    try:
        decisions = generate_json(decision_prompt, fast=True)
        if not isinstance(decisions, list):
            decisions = []
    except Exception as e:
        print(f"[rich] Decision failed for {section_title}: {e}")
        return []

    if not decisions:
        return []

    print(f"[rich] {section_title}: generating {len(decisions)} element(s): "
          f"{[d['type'] for d in decisions]}")

    # Step 2: generate each element
    elements: list[RichElement] = []
    for decision in decisions[:3]:
        etype     = decision.get("type", "")
        caption   = decision.get("caption", "")
        placement = decision.get("placement", "end_of_section")

        if etype not in GENERATION_PROMPTS:
            continue

        gen_prompt = GENERATION_PROMPTS[etype].format(
            caption=caption,
            context=section_content[:800],
            notes=research_notes[:800],
        )

        try:
            if etype == "mermaid":
                source = generate(gen_prompt, fast=False)
                source = source.strip().lstrip("```mermaid").rstrip("```").strip()
                img    = _render_mermaid_to_png(source, output_dir)
                elements.append(RichElement(type="mermaid", caption=caption,
                                            placement=placement, source=source,
                                            image_path=img))

            elif etype == "table":
                source = generate(gen_prompt, fast=False)
                # Clean any fences
                source = source.strip().lstrip("```markdown").lstrip("```").rstrip("```").strip()
                elements.append(RichElement(type="table", caption=caption,
                                            placement=placement, source=source))

            elif etype == "latex":
                source = generate(gen_prompt, fast=False).strip()
                img    = _render_latex_to_png(source, output_dir)
                elements.append(RichElement(type="latex", caption=caption,
                                            placement=placement, source=source,
                                            image_path=img))

            elif etype == "chart":
                spec = generate_json(gen_prompt, fast=False)
                if spec and spec.get("data"):
                    source = json.dumps(spec)
                    img    = _render_chart_to_png(spec, output_dir)
                    elements.append(RichElement(type="chart", caption=caption,
                                                placement=placement, source=source,
                                                image_path=img))

            elif etype == "code":
                data   = generate_json(gen_prompt, fast=False)
                lang   = data.get("language", "python")
                code   = data.get("code", "")
                source = f"```{lang}\n{code}\n```"
                elements.append(RichElement(type="code", caption=caption,
                                            placement=placement, source=source))

        except Exception as e:
            print(f"[rich] Failed to generate {etype} for {section_title}: {e}")
            continue

    return elements
