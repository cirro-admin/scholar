"""
config/sources.py
─────────────────
Loads API keys from .env and exposes a SourceConfig dataclass
that controls which research sources are active per run.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SourceConfig:
    """Controls which sources are active and holds their credentials."""

    # ── LLM ───────────────────────────────────────────────────────────────────
    google_api_key: str = ""

    # ── Search ────────────────────────────────────────────────────────────────
    perplexity_api_key: str = ""
    serpapi_key: str = ""

    # ── Data sources ──────────────────────────────────────────────────────────
    youtube_api_key: str = ""
    github_token: str = ""
    semantic_scholar_api_key: str = ""
    firecrawl_api_key: str = ""

    # ── Source toggles ────────────────────────────────────────────────────────
    enabled_sources: list[str] = field(default_factory=lambda: [
        "web", "arxiv", "youtube", "github", "pdf"
    ])

    def is_enabled(self, source: str) -> bool:
        return source in self.enabled_sources

    def validate(self) -> list[str]:
        """Return a list of warnings for missing keys."""
        warnings = []
        if not self.google_api_key:
            warnings.append("GOOGLE_API_KEY missing — LLM calls will fail")
        if not self.perplexity_api_key and not self.serpapi_key:
            warnings.append("No web search key (PERPLEXITY_API_KEY or SERPAPI_KEY) — web source disabled")
        if not self.youtube_api_key and "youtube" in self.enabled_sources:
            warnings.append("YOUTUBE_API_KEY missing — YouTube source disabled")
        if not self.github_token and "github" in self.enabled_sources:
            warnings.append("GITHUB_TOKEN missing — GitHub source will use unauthenticated (rate-limited)")
        return warnings


def load_source_config(enabled_sources: list[str] | None = None) -> SourceConfig:
    """Load credentials from environment and return a SourceConfig."""
    cfg = SourceConfig(
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        perplexity_api_key=os.getenv("PERPLEXITY_API_KEY", ""),
        serpapi_key=os.getenv("SERPAPI_KEY", ""),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY", ""),
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY", ""),
    )
    if enabled_sources:
        cfg.enabled_sources = enabled_sources

    # Auto-disable sources with no credentials
    if not cfg.perplexity_api_key and not cfg.serpapi_key:
        cfg.enabled_sources = [s for s in cfg.enabled_sources if s != "web"]
    if not cfg.youtube_api_key:
        cfg.enabled_sources = [s for s in cfg.enabled_sources if s != "youtube"]

    return cfg
