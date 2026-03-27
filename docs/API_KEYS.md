# API Keys Setup Guide

## Required keys

### 1. Google Gemini (LLM backbone)
- Go to: https://aistudio.google.com/app/apikey
- Free tier: 15 req/min, 1M tokens/day
- Add to `.env` as `GOOGLE_API_KEY`

### 2. Perplexity (web search)
- Go to: https://www.perplexity.ai/settings/api
- Free tier: limited; $5 credit on sign-up
- Add to `.env` as `PERPLEXITY_API_KEY`

### 3. YouTube Data API v3
- Go to: https://console.cloud.google.com → Enable YouTube Data API v3
- Free tier: 10,000 units/day
- Add to `.env` as `YOUTUBE_API_KEY`

### 4. GitHub Personal Access Token
- Go to: https://github.com/settings/tokens → Generate new token (classic)
- Scopes needed: repo (read-only is fine)
- Add to `.env` as `GITHUB_TOKEN`

## Optional keys

### SerpAPI (fallback web search)
- https://serpapi.com — 100 free searches/month
- Add as `SERPAPI_KEY`

### Semantic Scholar
- https://www.semanticscholar.org/product/api — unauthenticated works but rate-limited
- Add as `SEMANTIC_SCHOLAR_API_KEY`

### Firecrawl (enhanced web crawling)
- https://firecrawl.dev — 500 free credits
- Add as `FIRECRAWL_API_KEY`
