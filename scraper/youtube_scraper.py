"""
scraper/youtube_scraper.py
--------------------------
Scrapes 2 YouTube videos and outputs a normalised schema.
Extracts: channel name, publish date, description, transcript (if available).
Outputs JSON to output/youtube.json
"""

import json
import os
import re
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import Any, Dict, List, Optional

import requests

from utils.chunking import chunk_text
from utils.language_detect import detect_language
from utils.tagging import extract_tags

# ── Target videos ────────────────────────────────────────────────────────────
YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=aircAruvnKk",   # 3Blue1Brown – Neural networks
    "https://www.youtube.com/watch?v=ukzFI9rgwfU",   # AI in Healthcare overview
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


# ── HTML / meta extraction ────────────────────────────────────────────────────

def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _extract_meta(html: str, property_name: str) -> Optional[str]:
    """Extract a meta tag by property or name attribute."""
    pattern = rf'<meta[^>]+(?:property|name)=["\']?{re.escape(property_name)}["\']?[^>]+content=["\']([^"\']+)["\']'
    m = re.search(pattern, html, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Try reversed attribute order
    pattern2 = rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']?{re.escape(property_name)}["\']?'
    m2 = re.search(pattern2, html, re.IGNORECASE)
    return m2.group(1).strip() if m2 else None


def _extract_yt_initial_data(html: str) -> dict:
    """Parse ytInitialData JSON blob from the page."""
    m = re.search(r'var ytInitialData\s*=\s*(\{.+?\});\s*</script>', html, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}


def _extract_yt_player_response(html: str) -> dict:
    """Parse ytInitialPlayerResponse JSON blob from the page."""
    m = re.search(r'var ytInitialPlayerResponse\s*=\s*(\{.+?\});\s*(?:var|</script>)', html, re.DOTALL)
    if not m:
        # broader search
        m = re.search(r'ytInitialPlayerResponse\s*=\s*(\{.+?videoDetails.+?\});', html, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return {}
    return {}


def extract_metadata(html: str, url: str) -> Dict[str, Optional[str]]:
    """Return channel, title, publish_date, description from page HTML."""
    title = _extract_meta(html, "og:title") or _extract_meta(html, "title") or "Unknown"
    description = _extract_meta(html, "og:description") or _extract_meta(html, "description") or ""
    channel = "Unknown"
    publish_date = "Unknown"

    # Try ytInitialPlayerResponse first
    player = _extract_yt_player_response(html)
    video_details = player.get("videoDetails", {})
    if video_details:
        channel = video_details.get("author", channel)
        title = video_details.get("title", title)
        description = video_details.get("shortDescription", description)

    # Publish date from microformat
    microformat = player.get("microformat", {}).get("playerMicroformatRenderer", {})
    if microformat:
        publish_date = microformat.get("publishDate", publish_date)
        channel = microformat.get("ownerChannelName", channel)

    # Fallback: og:video:tag or datePublished from page
    if publish_date == "Unknown":
        m = re.search(r'"publishDate"\s*:\s*"([^"]+)"', html)
        if m:
            publish_date = m.group(1)

    if channel == "Unknown":
        m = re.search(r'"ownerChannelName"\s*:\s*"([^"]+)"', html)
        if m:
            channel = m.group(1)

    return {
        "title": title,
        "channel": channel,
        "publish_date": publish_date,
        "description": description,
    }


# ── Transcript extraction ─────────────────────────────────────────────────────

def get_transcript(video_url: str) -> str:
    """Try youtube-transcript-api. Returns transcript text or empty string."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        video_id_m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", video_url)
        if not video_id_m:
            return ""
        video_id = video_id_m.group(1)
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(entry["text"] for entry in transcript_list)
    except Exception:
        return ""


# ── Record builder ────────────────────────────────────────────────────────────

def build_record(url: str, meta: Dict[str, Optional[str]], content: str) -> Dict[str, Any]:
    lang = detect_language(content) if content else "Unknown"
    tags = extract_tags(content) if content else extract_tags(meta.get("description", "") or "")
    chunks = chunk_text(content) if content else chunk_text(meta.get("description", "") or "")

    return {
        "source_url": url,
        "source_type": "youtube",
        "author": meta.get("channel") or "Unknown",
        "published_date": meta.get("publish_date") or "Unknown",
        "language": lang,
        "region": "Global",
        "topic_tags": tags,
        "trust_score": 0.0,
        "content_chunks": chunks,
        # Extra fields for richer output
        "title": meta.get("title") or "Unknown",
        "description": meta.get("description") or "",
    }


def scrape_youtube(url: str) -> Dict[str, Any]:
    html = fetch_html(url)
    meta = extract_metadata(html, url)
    transcript = get_transcript(url)
    # Use transcript if available, fall back to description
    content = transcript if transcript else (meta.get("description") or "")
    return build_record(url, meta, content)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    results: List[Dict[str, Any]] = []
    for url in YOUTUBE_URLS:
        print(f"Scraping: {url}")
        try:
            data = scrape_youtube(url)
        except Exception as e:
            print(f"  ERROR: {e}")
            data = build_record(url, {"channel": "Unknown", "publish_date": "Unknown",
                                      "description": "", "title": "Unknown"}, "")
        results.append(data)

    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'youtube.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(results)} YouTube entries to {output_path}")


if __name__ == "__main__":
    main()
