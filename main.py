"""
main.py
-------
Orchestrates all scrapers, applies trust scores, and writes output JSON files.

Usage:
    python main.py

Outputs:
    output/blogs.json
    output/youtube.json
    output/pubmed.json
    output/scraped_data.json   ← merged file with all 6 sources
"""

import json
import os
import sys
import traceback

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper.blog_scraper import main as run_blog_scraper, BLOG_URLS, scrape_blog, build_record as blog_build_record
from scraper.youtube_scraper import YOUTUBE_URLS, scrape_youtube, build_record as yt_build_record
from scraper.pubmed_scraper import PUBMED_IDS, scrape_pubmed, build_record as pm_build_record
from scoring.trust_score import apply_trust_scores

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def run_blogs() -> list:
    print("\n── Blog Scraper ─────────────────────────────────────────────")
    results = []
    for url in BLOG_URLS:
        print(f"  Scraping: {url}")
        try:
            data = scrape_blog(url)
        except Exception as e:
            print(f"  ⚠ Error scraping {url}: {e}")
            data = blog_build_record(url, "Unknown", "Unknown", "", "Unknown", "")
        results.append(data)
    print(f"  ✓ {len(results)} blog entries scraped.")
    return results


def run_youtube() -> list:
    print("\n── YouTube Scraper ──────────────────────────────────────────")
    results = []
    for url in YOUTUBE_URLS:
        print(f"  Scraping: {url}")
        try:
            data = scrape_youtube(url)
        except Exception as e:
            print(f"  ⚠ Error scraping {url}: {e}")
            data = yt_build_record(url, {"channel": "Unknown", "publish_date": "Unknown",
                                         "description": "", "title": "Unknown"}, "")
        results.append(data)
    print(f"  ✓ {len(results)} YouTube entries scraped.")
    return results


def run_pubmed() -> list:
    print("\n── PubMed Scraper ───────────────────────────────────────────")
    results = []
    for pmid in PUBMED_IDS:
        print(f"  Scraping PMID {pmid}")
        try:
            data = scrape_pubmed(pmid)
        except Exception as e:
            print(f"  ⚠ Error scraping PMID {pmid}: {e}")
            data = pm_build_record(pmid, {
                "title": "Unknown", "authors": "Unknown",
                "journal": "Unknown", "abstract": "",
                "date": "Unknown", "region": "Global"
            }, 0)
        results.append(data)
    print(f"  ✓ {len(results)} PubMed entries scraped.")
    return results


def save_json(data: list, filename: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def main():
    print("=" * 62)
    print("  Multi-Source Scraper + Trust Score Pipeline")
    print("=" * 62)

    # Step 1: Scrape all sources
    blogs = run_blogs()
    youtube = run_youtube()
    pubmed = run_pubmed()

    # Step 2: Apply trust scores
    print("\n── Applying Trust Scores ────────────────────────────────────")
    blogs   = apply_trust_scores(blogs)
    youtube = apply_trust_scores(youtube)
    pubmed  = apply_trust_scores(pubmed)

    for r in blogs + youtube + pubmed:
        src = r.get("source_url", "?")
        ts  = r.get("trust_score", 0.0)
        print(f"  {ts:.4f}  {src[:70]}")

    # Step 3: Save individual files
    print("\n── Saving Output Files ──────────────────────────────────────")
    p1 = save_json(blogs,   "blogs.json")
    p2 = save_json(youtube, "youtube.json")
    p3 = save_json(pubmed,  "pubmed.json")

    all_records = blogs + youtube + pubmed
    p4 = save_json(all_records, "scraped_data.json")

    print(f"  ✓ {p1}")
    print(f"  ✓ {p2}")
    print(f"  ✓ {p3}")
    print(f"  ✓ {p4}")

    # Step 4: Quick schema validation
    print("\n── Schema Validation ────────────────────────────────────────")
    required = {"source_url", "source_type", "author", "published_date",
                 "language", "region", "topic_tags", "trust_score", "content_chunks"}
    errors = 0
    for r in all_records:
        missing = required - r.keys()
        if missing:
            print(f"  ✗ MISSING FIELDS {missing} in {r.get('source_url', '?')}")
            errors += 1
        ts = r.get("trust_score", -1)
        if not (0.0 <= ts <= 1.0):
            print(f"  ✗ TRUST SCORE OUT OF RANGE ({ts}) for {r.get('source_url', '?')}")
            errors += 1

    if errors == 0:
        print(f"  ✓ All {len(all_records)} records pass schema validation.")
    else:
        print(f"  ✗ {errors} validation error(s) found.")

    print("\n" + "=" * 62)
    print(f"  Done!  {len(all_records)} sources scraped and scored.")
    print("=" * 62)


if __name__ == "__main__":
    main()
