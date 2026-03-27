# Scholar — Adaptive Research & Writing Agent

Scholar is a production-grade agentic system that researches any topic and writes
publication-ready documents in multiple formats — from PhD theses to blog posts —
using the same underlying pipeline with swappable output-mode configs.

## Architecture

```
User Input (topic + mode)
        │
        ▼
┌─────────────────────────────────────────────────┐
│           Output Mode Selector                  │
│  thesis / article / blog / tech-doc / report    │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│         Research Agent  (Nova-style)            │
│  Query gen → [HITL: approve] → Multi-source     │
│  crawl → Synthesis → Structured notes           │
│                                                 │
│  Sources: Web · arXiv · YouTube · GitHub · PDF  │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│        Writing Workflow  (Brown-style)          │
│  Outline gen → [HITL: approve] → Section draft  │
│  → Eval-optimizer loop → Format render          │
└─────────────────────────────────────────────────┘
        │
        ▼
  DOCX / Markdown / PDF / HTML


```

## Output Modes

| Mode        | Citation style | Structure              | Tone         | Format      |
|-------------|---------------|------------------------|--------------|-------------|
| `thesis`    | APA / MLA     | Abstract + chapters    | Formal       | DOCX        |
| `article`   | IEEE / APA    | Intro + methods + disc | Academic     | Markdown    |
| `blog`      | Inline links  | Hook + sections        | Conversational | Markdown  |
| `tech_doc`  | Code refs     | Spec + examples        | Precise      | MD / HTML   |
| `report`    | None          | Exec summary + body    | Formal       | DOCX / PDF  |

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/YOUR_USERNAME/scholar.git
cd scholar
pip install -r requirements.txt

# 2. Set up API keys
cp .env.example .env
# Edit .env with your keys (see docs/API_KEYS.md)

# 3. Run
python main.py --topic "Impact of LLMs on scientific publishing" --mode thesis
```

## Project Structure

```
scholar/
├── main.py                    # CLI entry point
├── config/
│   ├── modes.py               # OutputModeConfig dataclass + 5 mode presets
│   └── sources.py             # API key loader + source toggles
├── research_agent/
│   ├── agent.py               # ReAct loop orchestrator
│   ├── synthesizer.py         # Raw results → structured notes
│   └── tools/
│       ├── web_search.py      # Perplexity / SerpAPI
│       ├── arxiv.py           # arXiv + Semantic Scholar
│       ├── youtube.py         # YouTube transcript fetcher
│       ├── github.py          # gitingest wrapper
│       └── pdf_reader.py      # Uploaded PDF ingestion
├── writing_workflow/
│   ├── orchestrator.py        # LangGraph graph definition
│   ├── outline_gen.py         # Mode-aware outline generator
│   ├── section_drafter.py     # Chain-of-thought section writer
│   ├── evaluator.py           # LLM judge + quality scorer
│   └── formatter.py           # Renders to DOCX / MD / PDF
├── hitl/
│   └── checkpoints.py         # User approval gates
├── utils/
│   └── helpers.py             # Shared utilities
├── docs/
│   ├── API_KEYS.md            # API key setup guide
│   ├── ARCHITECTURE.md        # Deep-dive system design
│   └── ADDING_MODES.md        # How to add new output modes
├── .env.example               # API key template
├── requirements.txt           # Python dependencies
└── pyproject.toml             # Project metadata
```

## API Keys Required

| Service             | Used for                    | Free tier? |
|---------------------|-----------------------------|------------|
| Google Gemini       | LLM backbone                | Yes        |
| Perplexity          | Web search                  | Yes        |
| SerpAPI             | Fallback web search         | Limited    |
| YouTube Data API v3 | Video transcript search     | Yes        |

See [docs/API_KEYS.md](docs/API_KEYS.md) for setup instructions.

## Adding a New Output Mode

See [docs/ADDING_MODES.md](docs/ADDING_MODES.md) — it takes ~10 lines of config.

## License

MIT
