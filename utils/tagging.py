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


def extract_tags(text: str, max_tags: int = 5) -> list:
    """
    Extract topic tags from the given text.
    
    Strategy:
      1. Use RAKE for keyword extraction (NLP-based) with capitalization rules.
      2. Exclude highly generic terms like 'Research'.

    Args:
        text: Input text to analyse.
        max_tags: Maximum number of tags to return.

    Returns:
        List of tag strings, e.g. ["Recombinant GDF11", "Machine Learning"]
    """
    if not text or not text.strip():
        return []

    try:
        rake_tags = _rake_extract(text, max_tags + 2)
    except Exception:
        rake_tags = []

    # Prioritize RAKE results natively. Don't crowd with domain hints.
    combined = []
    
    for tag in rake_tags:
        if tag not in combined and len(tag) > 3:
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


GENERIC_STOP_WORDS = {
    "research", "healthcare", "article", "study", "investigation", 
    "paper", "analysis", "data", "results", "methods", "conclusion",
    "background", "overview", "introduction"
}

def _rake_extract(text: str, max_tags: int) -> list:
    """
    Use RAKE-NLTK to extract key phrases from the text.
    Filters out noisy generic nouns and properly formats acronyms.
    """
    from rake_nltk import Rake

    r = Rake(
        min_length=1,
        max_length=3,
        include_repeated_phrases=False,
    )
    r.extract_keywords_from_text(text)
    phrases = r.get_ranked_phrases()

    cleaned_tags = []
    for phrase in phrases:
        # Filter out purely generic words
        if phrase.lower().strip() in GENERIC_STOP_WORDS:
            continue
        # Check if the phrase is just numbers
        if phrase.replace(".", "").isdigit():
            continue
            
        # Capitalize acronyms (e.g., tgfβ, gdf11) and title-case the rest
        formatted = " ".join(word.upper() if sum(1 for c in word if c.isupper() or c.isdigit()) > 0 
                             else word.title() for word in phrase.split())
        
        if len(formatted) > 2 and formatted not in cleaned_tags:
            cleaned_tags.append(formatted)

    return cleaned_tags[:max_tags]


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