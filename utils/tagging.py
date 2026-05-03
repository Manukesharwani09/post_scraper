"""
utils/tagging.py
----------------
Extracts topic tags from text using RAKE (Rapid Automatic Keyword Extraction).
Falls back to simple frequency-based extraction if RAKE is unavailable.
"""

import re
import string
from collections import Counter


# Domain-specific keyword hints to boost common topics
DOMAIN_HINTS = {
    "AI": ["artificial intelligence", "ai", "neural network", "deep learning", "machine learning",
           "nlp", "computer vision", "gpt", "bert", "llm"],
    "Machine Learning": ["machine learning", "supervised", "unsupervised", "training", "model",
                         "classification", "regression", "clustering", "prediction"],
    "Healthcare": ["healthcare", "medical", "clinical", "patient", "hospital", "diagnosis",
                   "treatment", "disease", "drug", "therapy", "health"],
    "Data Science": ["data", "dataset", "analysis", "analytics", "visualization", "statistics",
                     "pandas", "numpy", "pipeline", "feature engineering"],
    "Web Scraping": ["scraping", "scraper", "crawler", "beautifulsoup", "selenium", "requests",
                     "html", "parsing", "extraction"],
    "Research": ["study", "research", "journal", "publication", "abstract", "findings",
                 "methodology", "experiment", "results", "conclusion"],
    "YouTube": ["youtube", "video", "channel", "subscribe", "views", "watch", "creator",
                "content creator", "vlog"],
    "Technology": ["technology", "software", "programming", "developer", "code", "algorithm",
                   "cloud", "api", "platform", "digital"],
    "Security": ["cybersecurity", "security", "encryption", "privacy", "vulnerability",
                 "attack", "breach", "authentication"],
    "Finance": ["finance", "investment", "stock", "market", "economy", "trading", "crypto",
                "blockchain", "defi"],
}


def extract_tags(text: str, max_tags: int = 8) -> list:
    """
    Extract topic tags from the given text.
    
    Strategy:
      1. Try RAKE for keyword extraction (NLP-based).
      2. Fall back to domain hint matching + word frequency.

    Args:
        text: Input text to analyse.
        max_tags: Maximum number of tags to return.

    Returns:
        List of tag strings, e.g. ["AI", "Healthcare", "machine learning"]
    """
    if not text or not text.strip():
        return []

    text_lower = text.lower()
    matched_domain_tags = _match_domain_hints(text_lower)

    try:
        rake_tags = _rake_extract(text, max_tags)
    except Exception:
        rake_tags = []

    # Combine domain tags (high confidence) with RAKE tags
    combined = matched_domain_tags.copy()
    for tag in rake_tags:
        if tag not in combined:
            combined.append(tag)

    return combined[:max_tags]


def _match_domain_hints(text_lower: str) -> list:
    """
    Check which domain categories have keyword matches in the text.
    Returns category names sorted by number of keyword hits (most relevant first).
    """
    scores = {}
    for category, keywords in DOMAIN_HINTS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > 0:
            scores[category] = hits

    # Sort by hit count descending
    sorted_cats = sorted(scores, key=scores.get, reverse=True)
    return sorted_cats


def _rake_extract(text: str, max_tags: int) -> list:
    """
    Use RAKE-NLTK to extract key phrases from the text.
    """
    from rake_nltk import Rake

    r = Rake(
        min_length=1,
        max_length=3,
        include_repeated_phrases=False,
    )
    r.extract_keywords_from_text(text)
    phrases = r.get_ranked_phrases()

    # Clean and filter
    cleaned = []
    for phrase in phrases[:max_tags * 2]:
        phrase = phrase.strip().title()
        if len(phrase) > 2 and phrase not in cleaned:
            cleaned.append(phrase)

    return cleaned[:max_tags]


def _frequency_fallback(text: str, max_tags: int) -> list:
    """
    Simple word-frequency fallback when RAKE is not available.
    """
    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "was", "are", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "can", "not",
        "it", "its", "this", "that", "these", "those", "i", "we", "you",
        "he", "she", "they", "as", "so", "if", "than", "then", "also",
    }
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    filtered = [w for w in words if w not in STOP_WORDS]
    common = Counter(filtered).most_common(max_tags * 2)
    return [word.title() for word, _ in common[:max_tags]]