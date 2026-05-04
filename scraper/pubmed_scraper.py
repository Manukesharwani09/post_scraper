"""
scraper/pubmed_scraper.py
--------------------------
Scrapes 1 PubMed article using the NCBI E-Utilities API (no API key required).
Extracts: title, authors, journal, abstract, publication date, and region.
Outputs JSON to output/pubmed.json
"""

import html
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import Any, Dict, List, Optional

import requests

from utils.chunking import chunk_text
from utils.language_detect import detect_language
from utils.tagging import extract_tags
from scoring.trust_score import calculate_trust_score

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
    # Respect NCBI limit of 3 requests/sec without API key
    time.sleep(0.4)
    return resp.text


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
        time.sleep(0.4)
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


# ── XML parsing ───────────────────────────────────────────────────────────────

def _parse_month(month: str) -> str:
    months = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06", 
              "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
    return months.get(month, month)

def _extract_region(affil: str) -> str:
    """Extract country from an affiliation string efficiently."""
    if not affil:
        return "Global"
    import re
    parts = affil.split(',')
    for part in reversed(parts):
        p = re.sub(r'\d+', '', part).strip().strip('.')
        if '@' in p or p.lower() in ("inc", "llc", "ltd"):
            continue
        if any(w in p.lower() for w in ("university", "department", "hospital", "institute", "school", "center", "centre")):
            continue
        if len(p) > 2:
            return p
    return "Global"

def parse_article_xml(xml_data: str) -> Dict[str, Any]:
    """Parse the XML efetch response using ElementTree into a structured dict."""
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return {"title": "Unknown", "authors": "Unknown", "journal": "Unknown", "abstract": "", "date": "Unknown", "region": "Global"}

    title = root.findtext('.//ArticleTitle') or "Unknown"
    title = html.unescape(title.strip())

    abstract_parts = []
    for node in root.findall('.//AbstractText'):
        if node.text:
            text = html.unescape(node.text.strip())
            label = node.get('Label', '')
            if label:
                text = f"{label}: {text}"
            abstract_parts.append(text)
    abstract = "\n\n".join(abstract_parts) if abstract_parts else ""

    authors = []
    for author_node in root.findall('.//Author'):
        last = author_node.findtext('LastName')
        first = author_node.findtext('ForeName')
        if last and first:
            authors.append(f"{last}, {first}")
        else:
            collective = author_node.findtext('CollectiveName')
            if collective:
                authors.append(collective)
    author_str = "; ".join(authors) if authors else "Unknown"

    affil_node = root.find('.//Affiliation')
    region = _extract_region(affil_node.text) if affil_node is not None else "Global"

    journal = root.findtext('.//Title') or root.findtext('.//ISOAbbreviation') or "Unknown"
    journal = html.unescape(journal.strip())

    pub_date = root.find('.//PubDate')
    date_str = "Unknown"
    if pub_date is not None:
        year = pub_date.findtext('Year')
        if year:
            month = pub_date.findtext('Month', '01')
            month = _parse_month(month)
            day = pub_date.findtext('Day', '01').zfill(2)
            date_str = f"{year}-{month}-{day}"

    return {
        "title": title,
        "authors": author_str,
        "journal": journal,
        "abstract": abstract,
        "date": date_str,
        "region": region,
    }


# ── Record builder ────────────────────────────────────────────────────────────

def build_record(pmid: str, parsed: Dict[str, Any], citation_count: int) -> Dict[str, Any]:
    url = f"{PUBMED_BASE}{pmid}/"
    content = parsed["abstract"]
    lang = detect_language(content) if content else "Unknown"
    from utils.tagging import pubmed_extract_tags
    tags = pubmed_extract_tags(content) if content else []
    chunks = chunk_text(content) if content else []

    record = {
        "source_url": url,
        "source_type": "pubmed",
        "author": parsed["authors"],
        "published_date": parsed["date"],
        "language": lang,
        "region": parsed["region"],
        "topic_tags": tags,
        "content_chunks": chunks,
        "title": parsed["title"],
        "journal": parsed["journal"],
        "abstract": parsed["abstract"],
        "citation_count": citation_count,
    }
    record["trust_score"] = calculate_trust_score(record)
    return record


def scrape_pubmed(pmid: str) -> Dict[str, Any]:
    print(f"  Fetching PMID {pmid} XML …")
    xml_data = fetch_xml(pmid)
    parsed = parse_article_xml(xml_data)

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
                "journal": "Unknown", "abstract": "", "date": "Unknown", "region": "Global"
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
