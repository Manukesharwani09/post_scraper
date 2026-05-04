"""
scraper/pubmed_scraper.py
--------------------------
Scrapes 1 PubMed article using the NCBI E-Utilities API (no API key required).
Extracts: title, authors, journal, abstract, publication year.
Outputs JSON to output/pubmed.json
"""

import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import Any, Dict, List, Optional

import requests

from utils.chunking import chunk_text
from utils.language_detect import detect_language
from utils.tagging import extract_tags

# ── Target article (PMID) ─────────────────────────────────────────────────────
# "Artificial intelligence in healthcare" – Nature Medicine review
PUBMED_IDS = ["33077875"]

NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
NCBI_ELINK = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"

PUBMED_BASE = "https://pubmed.ncbi.nlm.nih.gov/"

DEFAULT_HEADERS = {
    "User-Agent": "PostScraper/1.0 (student assignment; contact: student@example.com)"
}


# ── NCBI API helpers ──────────────────────────────────────────────────────────

def fetch_xml(pmid: str) -> str:
    """Fetch PubMed article XML via efetch."""
    params = {
        "db": "pubmed",
        "id": pmid,
        "rettype": "xml",
        "retmode": "xml",
    }
    resp = requests.get(NCBI_EFETCH, params=params, headers=DEFAULT_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def fetch_summary(pmid: str) -> dict:
    """Fetch ESummary JSON for citation count and extra metadata."""
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "json",
    }
    resp = requests.get(NCBI_ESUMMARY, params=params, headers=DEFAULT_HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", {}).get(pmid, {})


def get_citation_count(pmid: str) -> int:
    """Use elink to count inbound citations (PubMed Central cited-by)."""
    params = {
        "dbfrom": "pubmed",
        "db": "pubmed",
        "id": pmid,
        "linkname": "pubmed_pubmed_citedin",
        "retmode": "json",
    }
    try:
        resp = requests.get(NCBI_ELINK, params=params, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        linksets = data.get("linksets", [{}])
        if linksets:
            links = linksets[0].get("linksetdbs", [])
            for ldb in links:
                if ldb.get("linkname") == "pubmed_pubmed_citedin":
                    return len(ldb.get("links", []))
    except Exception:
        pass
    return 0


# ── XML parsing (no external XML parser needed) ───────────────────────────────

def _extract_tag(xml: str, tag: str) -> Optional[str]:
    """Naive single-value tag extractor."""
    import re
    m = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', xml, re.DOTALL)
    return m.group(1).strip() if m else None


def _extract_all_tags(xml: str, tag: str) -> List[str]:
    """Extract all values for a repeating tag."""
    import re
    return [m.strip() for m in re.findall(rf'<{tag}[^>]*>(.*?)</{tag}>', xml, re.DOTALL)]


def parse_article_xml(xml: str) -> Dict[str, Any]:
    """Parse the XML efetch response into a structured dict."""
    import re

    title = _extract_tag(xml, "ArticleTitle") or "Unknown"
    # Strip any nested tags inside title
    title = re.sub(r'<[^>]+>', '', title).strip()

    abstract_texts = _extract_all_tags(xml, "AbstractText")
    abstract = " ".join(re.sub(r'<[^>]+>', '', t) for t in abstract_texts).strip()
    if not abstract:
        abstract = ""

    # Authors: collect LastName + ForeName
    last_names = _extract_all_tags(xml, "LastName")
    fore_names = _extract_all_tags(xml, "ForeName")
    if last_names:
        authors = [
            f"{l}, {f}".strip(", ")
            for l, f in zip(
                last_names,
                fore_names + [""] * (len(last_names) - len(fore_names))
            )
        ]
        author_str = "; ".join(authors)
    else:
        author_str = "Unknown"

    journal = _extract_tag(xml, "Title") or _extract_tag(xml, "ISOAbbreviation") or "Unknown"
    journal = re.sub(r'<[^>]+>', '', journal).strip()

    year = _extract_tag(xml, "Year") or "Unknown"

    return {
        "title": title,
        "authors": author_str,
        "journal": journal,
        "abstract": abstract,
        "year": year,
    }


# ── Record builder ────────────────────────────────────────────────────────────

def build_record(pmid: str, parsed: Dict[str, Any], citation_count: int) -> Dict[str, Any]:
    url = f"{PUBMED_BASE}{pmid}/"
    content = parsed["abstract"]
    lang = detect_language(content) if content else "Unknown"
    tags = extract_tags(content) if content else []
    chunks = chunk_text(content) if content else []

    return {
        "source_url": url,
        "source_type": "pubmed",
        "author": parsed["authors"],
        "published_date": parsed["year"],
        "language": lang,
        "region": "Global",
        "topic_tags": tags,
        "trust_score": 0.0,
        "content_chunks": chunks,
        # Extra PubMed-specific fields
        "title": parsed["title"],
        "journal": parsed["journal"],
        "abstract": parsed["abstract"],
        "citation_count": citation_count,
    }


def scrape_pubmed(pmid: str) -> Dict[str, Any]:
    print(f"  Fetching PMID {pmid} XML …")
    xml = fetch_xml(pmid)
    parsed = parse_article_xml(xml)

    print(f"  Fetching citation count for PMID {pmid} …")
    cites = get_citation_count(pmid)

    return build_record(pmid, parsed, cites)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    results: List[Dict[str, Any]] = []
    for pmid in PUBMED_IDS:
        print(f"Scraping PubMed PMID {pmid}")
        try:
            data = scrape_pubmed(pmid)
        except Exception as e:
            print(f"  ERROR: {e}")
            data = build_record(pmid, {
                "title": "Unknown", "authors": "Unknown",
                "journal": "Unknown", "abstract": "", "year": "Unknown"
            }, 0)
        results.append(data)

    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'pubmed.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(results)} PubMed entries to {output_path}")


if __name__ == "__main__":
    main()
