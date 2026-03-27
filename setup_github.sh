#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Scholar — one-command GitHub repo setup
#
# Usage:
#   chmod +x setup_github.sh
#   ./setup_github.sh YOUR_GITHUB_USERNAME scholar
#
# Prerequisites:
#   - git installed
#   - GitHub CLI installed: https://cli.github.com  (brew install gh / apt install gh)
#   - Authenticated: run  gh auth login  first
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

GITHUB_USER="${1:?Usage: ./setup_github.sh GITHUB_USERNAME REPO_NAME}"
REPO_NAME="${2:-scholar}"

echo "── Creating GitHub repo: $GITHUB_USER/$REPO_NAME ──"

# 1. Init local git repo
git init
git add .
git commit -m "feat: initial Scholar project scaffold

- Full folder structure: config/, research_agent/, writing_workflow/, hitl/, utils/, docs/
- OutputModeConfig adaptability layer (5 modes: thesis, article, blog, tech_doc, report)
- ReAct research agent skeleton with 5 source tools
- LangGraph writing workflow skeleton with eval-optimizer pattern
- Two HITL checkpoints
- README with architecture diagrams, quick start, and API key table
- docs/: API_KEYS.md, ARCHITECTURE.md, ADDING_MODES.md"

# 2. Create GitHub repo (public — change to --private if preferred)
gh repo create "$REPO_NAME" \
  --public \
  --description "Adaptive agentic research & writing system — thesis, articles, blogs, docs, reports" \
  --source=. \
  --remote=origin \
  --push

echo ""
echo "✅ Done! Your repo is live at:"
echo "   https://github.com/$GITHUB_USER/$REPO_NAME"
echo ""
echo "── Next steps ───────────────────────────────────────────────────────────"
echo "  1. cd into the repo folder"
echo "  2. cp .env.example .env  →  fill in your API keys (see docs/API_KEYS.md)"
echo "  3. pip install -r requirements.txt"
echo "  4. Tell Claude: 'Let's populate config/modes.py first'"
echo "─────────────────────────────────────────────────────────────────────────"
