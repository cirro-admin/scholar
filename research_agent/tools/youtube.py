"""
research_agent/tools/youtube.py
────────────────────────────────
YouTube search + transcript fetcher.
Compatible with youtube-transcript-api >= 0.6.0 (instance-based API).
"""

from __future__ import annotations
import os, requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoTranscript:
    video_id:   str
    title:      str
    channel:    str
    url:        str
    duration:   int
    transcript: str
    language:   str = "en"


def _search_videos(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    params = {
        "part": "snippet", "q": query, "type": "video",
        "maxResults": max_results, "relevanceLanguage": "en", "key": api_key,
    }
    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params=params, timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def _get_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript — works with both old (class-method) and new (instance) API."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        # New API (>= 0.6.3): instantiate then call fetch()
        try:
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id, languages=["en"])
            return " ".join(s.text for s in transcript)
        except TypeError:
            # Older API: class method
            segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
            return " ".join(s["text"] for s in segments)
    except Exception as e:
        print(f"[youtube] Transcript fetch failed for {video_id}: {e}")
        return None


def search_and_fetch(
    query: str,
    api_key: Optional[str] = None,
    max_results: int = 5,
) -> list[VideoTranscript]:
    key = api_key or os.getenv("YOUTUBE_API_KEY", "")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY not set in .env")

    videos  = _search_videos(query, key, max_results * 2)
    results = []

    for item in videos:
        if len(results) >= max_results:
            break
        video_id = item["id"].get("videoId", "")
        snippet  = item.get("snippet", {})
        text     = _get_transcript(video_id)
        if not text:
            continue
        results.append(VideoTranscript(
            video_id=video_id,
            title=snippet.get("title", ""),
            channel=snippet.get("channelTitle", ""),
            url=f"https://www.youtube.com/watch?v={video_id}",
            duration=0,
            transcript=text,
        ))

    return results
