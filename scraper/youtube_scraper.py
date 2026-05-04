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


# ── Content cleaning ────────────────────────────────────────────────────────────

PROMO_KEYWORDS = [
    "subscribe", "patreon", "click", "link", "follow", "twitter", "facebook",
    "instagram", "reddit", "website", "download", "stream", "playlist", "course",
    "certificate", "program", "specialization", "bootcamp", "career", "jobassist",
    "learn more", "watch more", "sign up", "buy", "sponsor", "donation",
]


def _looks_promotional(text: str) -> bool:
    lowered = text.lower()
    if re.search(r'https?://\S+', lowered):
        return True
    return any(k in lowered for k in PROMO_KEYWORDS)


def _strip_promotional_lines(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    kept = [ln for ln in lines if not _looks_promotional(ln)]
    return "\n".join(kept)


def _dedupe_sentences(text: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    seen = set()
    kept = []
    for sentence in sentences:
        norm = re.sub(r'\W+', ' ', sentence.lower()).strip()
        if len(norm.split()) < 4:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        kept.append(sentence.strip())
    return " ".join(kept)


def clean_text(text: str) -> str:
    """
    Remove noise from YouTube description or transcript:
      - URLs
      - Hashtags
      - Timestamps (e.g., 10:24, 1:23:45)
      - Emojis and non-text symbols
      - Promotional / marketing lines
    """
    if not text:
        return ""

    # Remove promotional or link-heavy lines before token cleanup
    text = _strip_promotional_lines(text)

    # Replace URLs with spaces to safely prevent word-merging
    text = re.sub(r'https?://[^\s]+', ' ', text)

    # Remove timestamps and timeline markers
    text = re.sub(r'\b\d{1,2}:\d{2}(:\d{2})?\b', ' ', text)
    text = re.sub(r'\b\d{1,2}\s*-\s*', ' ', text)

    # Remove hashtags but leave space
    text = re.sub(r'#[a-zA-Z0-9_]+', ' ', text)

    # Remove generic bracketed sounds (e.g. [Music], (Applause))
    text = re.sub(r'\[.*?\]|\(.*?\)', ' ', text)

    # Remove emojis and non-text symbols
    text = re.sub(r'[^\w\s.,?!;:\-\'\"]', ' ', text)

    # Collapse multiple spaces safely
    text = re.sub(r'\s+', ' ', text).strip()

    # Drop repeated / boilerplate sentences
    text = _dedupe_sentences(text)
    return text


def chunk_text_by_words(text: str, min_words: int = 100, max_words: int = 300) -> List[str]:
    if not text:
        return []

    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        if current_len + len(words) <= max_words:
            current.append(sentence)
            current_len += len(words)
        else:
            if current:
                chunks.append(" ".join(current).strip())
            current = [sentence]
            current_len = len(words)

    if current:
        chunks.append(" ".join(current).strip())

    # Merge short trailing chunk to keep 100-300 words as much as possible
    if len(chunks) >= 2 and len(chunks[-1].split()) < min_words:
        chunks[-2] = (chunks[-2] + " " + chunks[-1]).strip()
        chunks.pop()

    return [c for c in chunks if len(c.split()) >= min_words or len(chunks) == 1]


def refine_tags(text: str, tags: List[str]) -> List[str]:
    specific_tags = []
    text_lower = text.lower()

    tag_rules = {
        "Neural Networks": ["neural network", "neurons", "layers"],
        "Weights and Biases": ["weights", "biases"],
        "Activation Functions": ["relu", "sigmoid", "activation function"],
        "Linear Algebra Notation": ["linear algebra", "matrix", "vector"],
        "Edge Detection": ["edge detection"],
        "Supervised Learning": ["supervised learning"],
        "Unsupervised Learning": ["unsupervised learning"],
        "Reinforcement Learning": ["reinforcement learning"],
        "Machine Learning Applications": ["applications", "used in", "industries"],
        "Pattern Recognition": ["pattern recognition"],
    }

    for tag, keywords in tag_rules.items():
        if any(kw in text_lower for kw in keywords):
            specific_tags.append(tag)

    # Remove generic / low-signal tags
    drop = {"ai", "technology", "research", "data science", "youtube"}
    cleaned = [t for t in tags if t.lower() not in drop]

    combined = []
    for t in specific_tags + cleaned:
        if t not in combined:
            combined.append(t)

    return combined[:8]


# ── Record builder ────────────────────────────────────────────────────────────

def build_record(url: str, meta: Dict[str, Optional[str]], transcript: str) -> Dict[str, Any]:
    raw_desc = meta.get("description") or ""
    
    if transcript:
        clean_content = clean_text(transcript)
        # Safely split standard 'timeline' layout descriptions and grab essential context
        desc_head = raw_desc.split("Timeline")[0] if "Timeline" in raw_desc else raw_desc
        clean_desc = clean_text(desc_head)
        if clean_desc:
            clean_content += " " + clean_desc[:500]
    else:
        # Aggressive desc formatting handled by clean_text natively
        clean_content = clean_text(raw_desc)
    
    lang = detect_language(clean_content) if clean_content else "Unknown"
    
    # Optional: we can use pubmed_extract_tags for high-quality Nouns but normal extract_tags is fine if text is clean
    tags = extract_tags(clean_content) if clean_content else []
    tags = refine_tags(clean_content, tags) if clean_content else []
    chunks = chunk_text_by_words(clean_content) if clean_content else []

    # Normalize Date
    raw_date = meta.get("publish_date") or "Unknown"
    iso_date_match = re.search(r'\d{4}-\d{2}-\d{2}', raw_date)
    norm_date = iso_date_match.group(0) if iso_date_match else raw_date

    from scoring.trust_score import calculate_trust_score

    record = {
        "source_url": url,
        "source_type": "youtube",
        "author": meta.get("channel") or "Unknown",
        "published_date": norm_date,
        "language": lang,
        "region": "Global",
        "topic_tags": tags,
        "content_chunks": chunks,
        "title": meta.get("title") or "Unknown",
        "description": meta.get("description") or "",
    }
    record["trust_score"] = calculate_trust_score(record)
    # Transcript presence raises trust; missing transcript slightly lowers it
    if transcript:
        record["trust_score"] = min(record["trust_score"] + 0.05, 1.0)
    else:
        record["trust_score"] = max(record["trust_score"] - 0.08, 0.0)
    return record


def scrape_youtube(url: str) -> Dict[str, Any]:
    html = fetch_html(url)
    meta = extract_metadata(html, url)
    transcript = get_transcript(url)
    return build_record(url, meta, transcript)


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
