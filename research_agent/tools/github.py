"""
research_agent/tools/github.py
────────────────────────────────
GitHub repo ingestion via gitingest + GitHub API fallback.
Returns RepoSummary objects with README, file tree, and key code snippets.
"""

from __future__ import annotations
import os, re, requests
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RepoSummary:
    owner:       str
    repo:        str
    url:         str
    description: str
    stars:       int
    readme:      str
    file_tree:   list[str]
    key_files:   dict[str, str]   # filename → content (truncated)
    topics:      list[str] = field(default_factory=list)


def _github_headers(token: Optional[str] = None) -> dict:
    tok = token or os.getenv("GITHUB_TOKEN", "")
    if tok:
        return {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    return {"Accept": "application/vnd.github+json"}


def _get_repo_meta(owner: str, repo: str, token: Optional[str]) -> dict:
    url  = f"https://api.github.com/repos/{owner}/{repo}"
    resp = requests.get(url, headers=_github_headers(token), timeout=20)
    resp.raise_for_status()
    return resp.json()


def _get_readme(owner: str, repo: str, token: Optional[str]) -> str:
    url  = f"https://api.github.com/repos/{owner}/{repo}/readme"
    resp = requests.get(url, headers={**_github_headers(token), "Accept": "application/vnd.github.raw"}, timeout=20)
    if resp.status_code == 404:
        return ""
    resp.raise_for_status()
    return resp.text[:8000]   # cap at 8k chars


def _get_file_tree(owner: str, repo: str, token: Optional[str]) -> list[str]:
    url  = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    resp = requests.get(url, headers=_github_headers(token), timeout=20)
    resp.raise_for_status()
    return [item["path"] for item in resp.json().get("tree", []) if item["type"] == "blob"]


def _fetch_key_files(
    owner: str, repo: str, tree: list[str], token: Optional[str],
    patterns: list[str] = ("requirements.txt", "pyproject.toml", "setup.py",
                           "Makefile", "Dockerfile", "docker-compose.yml"),
    max_chars: int = 2000,
) -> dict[str, str]:
    """Fetch a handful of config/setup files that reveal the project structure."""
    key_files = {}
    for path in tree:
        fname = path.split("/")[-1]
        if fname in patterns:
            url  = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
            resp = requests.get(url, headers=_github_headers(token), timeout=15)
            if resp.status_code == 200:
                key_files[path] = resp.text[:max_chars]
    return key_files


def ingest_repo(
    repo_url: str,
    token: Optional[str] = None,
) -> RepoSummary:
    """
    Ingest a GitHub repository from its URL.
    repo_url: e.g. 'https://github.com/owner/repo'
    """
    # Parse owner/repo from URL
    match = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$", repo_url.rstrip("/"))
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {repo_url}")
    owner, repo = match.group(1), match.group(2)

    tok  = token or os.getenv("GITHUB_TOKEN", "")
    meta = _get_repo_meta(owner, repo, tok)
    tree = _get_file_tree(owner, repo, tok)

    return RepoSummary(
        owner=owner,
        repo=repo,
        url=repo_url,
        description=meta.get("description") or "",
        stars=meta.get("stargazers_count", 0),
        readme=_get_readme(owner, repo, tok),
        file_tree=tree[:200],          # cap at 200 entries
        key_files=_fetch_key_files(owner, repo, tree, tok),
        topics=meta.get("topics", []),
    )


def search_repos(
    query: str,
    token: Optional[str] = None,
    max_results: int = 5,
    min_stars: int = 50,
) -> list[RepoSummary]:
    """Search GitHub for repos matching a query and ingest each one."""
    tok    = token or os.getenv("GITHUB_TOKEN", "")
    params = {"q": f"{query[:60]} stars:>={min_stars}", "sort": "stars", "per_page": max_results}
    resp   = requests.get(
        "https://api.github.com/search/repositories",
        params=params, headers=_github_headers(tok), timeout=20,
    )
    resp.raise_for_status()

    summaries = []
    for item in resp.json().get("items", []):
        try:
            s = ingest_repo(item["html_url"], tok)
            summaries.append(s)
        except Exception as e:
            print(f"[github] Failed to ingest {item['html_url']}: {e}")
    return summaries
