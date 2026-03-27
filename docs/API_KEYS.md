# API Keys Setup Guide

## Overview — what you need and why

| Key | Required? | Used for | Free tier |
|-----|-----------|----------|-----------|
| `GOOGLE_API_KEY` | YES | LLM backbone (Gemini 1.5 Pro + Flash) | 15 req/min, 1M tokens/day |
| `PERPLEXITY_API_KEY` | YES (recommended) | Web search with citations | $5 credit on signup |
| `YOUTUBE_API_KEY` | YES (for video source) | Search + transcript fetch | 10,000 units/day |
| `GITHUB_TOKEN` | Recommended | Repo ingestion (higher rate limits) | Free |
| `SERPAPI_KEY` | Optional | Fallback web search if Perplexity fails | 100 searches/month |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional | Higher rate limits on paper search | Free |
| `FIRECRAWL_API_KEY` | Optional | Enhanced web crawling | 500 credits free |

---

## Step-by-step setup

### 1. Google Gemini — REQUIRED

1. Go to: https://aistudio.google.com/app/apikey
2. Click **"Create API key"**
3. Copy the key
4. Add to `.env`:
   ```
   GOOGLE_API_KEY=AIza...
   ```

**Tip:** The free tier is generous enough to run full thesis-length runs.
Flash is used for fast tasks (query gen, evaluation), Pro for actual drafting.

---

### 2. Perplexity — REQUIRED for web source

1. Go to: https://www.perplexity.ai/settings/api
2. Sign up / log in → go to **API** tab
3. Click **"Generate"** under API Keys
4. Add to `.env`:
   ```
   PERPLEXITY_API_KEY=pplx-...
   ```

**Cost:** ~$0.001 per query. A full thesis run uses ~20-30 queries = $0.02–$0.03.

---

### 3. YouTube Data API v3 — REQUIRED for video source

1. Go to: https://console.cloud.google.com
2. Create a new project (or use existing)
3. Search **"YouTube Data API v3"** → Enable it
4. Go to **Credentials** → **Create Credentials** → **API Key**
5. Add to `.env`:
   ```
   YOUTUBE_API_KEY=AIza...
   ```

**Note:** This is a different key from your Gemini key, even though both start with `AIza`.

---

### 4. GitHub Personal Access Token — Recommended

1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Set expiration: 90 days (or no expiration for personal use)
4. Scopes: tick **`public_repo`** only (read-only is enough)
5. Click **Generate token** — copy it immediately (shown only once)
6. Add to `.env`:
   ```
   GITHUB_TOKEN=ghp_...
   ```

**Why bother?** Without it, GitHub limits you to 60 API requests/hour.
With a token: 5,000/hour.

---

### 5. SerpAPI — Optional fallback

1. Go to: https://serpapi.com/users/sign_up
2. Your API key is on the dashboard
3. Add to `.env`:
   ```
   SERPAPI_KEY=...
   ```

Only needed if Perplexity is down or you exhaust its credits.

---

### 6. Semantic Scholar — Optional

1. Go to: https://www.semanticscholar.org/product/api/tutorial
2. Request a free API key (instant approval)
3. Add to `.env`:
   ```
   SEMANTIC_SCHOLAR_API_KEY=...
   ```

Works unauthenticated too, but rate-limited to 1 req/sec.
With a key: 10 req/sec.

---

## Verify your setup

Run this after filling in `.env`:

```bash
python scripts/check_keys.py
```

Expected output:
```
Checking API keys...
  GOOGLE_API_KEY       ✓  Gemini 1.5 Flash responded
  PERPLEXITY_API_KEY   ✓  Search returned 3 results
  YOUTUBE_API_KEY      ✓  Found 5 videos
  GITHUB_TOKEN         ✓  Rate limit: 4987/5000 remaining
  SERPAPI_KEY          -  Not set (optional)
  SEMANTIC_SCHOLAR     -  Not set (unauthenticated OK)

Ready to run Scholar.
```

---

## Minimum viable setup (cheapest / fastest to get started)

If you just want to test Scholar quickly with minimum setup:

```env
GOOGLE_API_KEY=your_gemini_key
PERPLEXITY_API_KEY=your_perplexity_key
```

Then run with sources limited to web + arxiv only:

```bash
python main.py run \
  --topic "Your topic here" \
  --mode blog \
  --sources web,arxiv
```

This skips YouTube and GitHub entirely and uses only Gemini + Perplexity.
A blog post run costs roughly $0.01–0.05 total.
