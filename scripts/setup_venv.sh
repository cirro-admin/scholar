#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_venv.sh — create virtual environment and install all dependencies
# Run from repo root: bash scripts/setup_venv.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

echo "── Creating virtual environment ──"
python3 -m venv .venv

echo "── Activating ──"
source .venv/bin/activate

echo "── Upgrading pip ──"
pip install --upgrade pip --quiet

echo "── Installing project dependencies ──"
pip install -r requirements.txt --quiet

echo "── Installing dev tools ──"
pip install pre-commit detect-secrets --quiet

echo ""
echo "✅ Done. To activate in future sessions run:"
echo "   source .venv/bin/activate"
echo ""
echo "── Setting up pre-commit hooks ──"
pre-commit install
echo "✅ Pre-commit hooks installed"
