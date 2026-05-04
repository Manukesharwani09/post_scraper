"""
scraper/blog_scraper.py
-----------------------
Scrapes a small set of real blog posts and outputs a normalized schema.
Outputs JSON to output/blogs.json
"""

import json
import os
import re
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from utils.chunking import chunk_text_by_words
from utils.language_detect import detect_language
from utils.tagging import extract_tags
BLOG_URLS = [
    "https://www.scrapingbee.com/blog/web-scraping-101-with-python/",
    "https://huggingface.co/blog/bert-101",
    "https://upplabs.com/blog/how-we-built-clinical-ai-assistant/",
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def parse_json_ld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for script in scripts:
        if not script.string:
            continue
        raw = script.string.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        if isinstance(data, list):
            items.extend([d for d in data if isinstance(d, dict)])
        elif isinstance(data, dict):
            if isinstance(data.get("@graph"), list):
                items.extend([d for d in data["@graph"] if isinstance(d, dict)])
            items.append(data)

    return items


def extract_from_json_ld(items: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    for item in items:
        item_type = item.get("@type")
        if isinstance(item_type, list):
            item_type = item_type[0] if item_type else None

        if item_type in {"Article", "NewsArticle", "BlogPosting"}:
            author = None
            author_data = item.get("author")
            if isinstance(author_data, dict):
                author = author_data.get("name")
            elif isinstance(author_data, list) and author_data:
                first_author = author_data[0]
                if isinstance(first_author, dict):
                    author = first_author.get("name")
                elif isinstance(first_author, str):
                    author = first_author
            elif isinstance(author_data, str):
                author = author_data

            return {
                "author": author,
                "date": item.get("datePublished"),
                "title": item.get("headline"),
                "body": item.get("articleBody"),
            }

    return {"author": None, "date": None, "title": None, "body": None}


def extract_author(soup: BeautifulSoup, json_ld: Dict[str, Optional[str]]) -> str:
    if json_ld.get("author"):
        return str(json_ld["author"]).strip()

    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        return meta_author["content"].strip()

    meta_article_author = soup.find("meta", property="article:author")
    if meta_article_author and meta_article_author.get("content"):
        return meta_article_author["content"].strip()

    meta_parsely = soup.find("meta", attrs={"name": "parsely-author"})
    if meta_parsely and meta_parsely.get("content"):
        return meta_parsely["content"].strip()

    byline = soup.find(class_=re.compile(r"byline|author", re.I))
    if byline and byline.get_text(strip=True):
        return byline.get_text(strip=True).replace("By ", "").strip()

    return "Unknown"


def extract_date(soup: BeautifulSoup, json_ld: Dict[str, Optional[str]]) -> str:
    if json_ld.get("date"):
        return str(json_ld["date"]).strip()

    meta_date = soup.find("meta", property="article:published_time")
    if meta_date and meta_date.get("content"):
        return meta_date["content"].strip()

    meta_pubdate = soup.find("meta", attrs={"name": "pubdate"})
    if meta_pubdate and meta_pubdate.get("content"):
        return meta_pubdate["content"].strip()

    itemprop_date = soup.find(attrs={"itemprop": "datePublished"})
    if itemprop_date and itemprop_date.get("content"):
        return itemprop_date["content"].strip()

    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        return time_tag["datetime"].strip()

    if time_tag and time_tag.get_text(strip=True):
        return time_tag.get_text(strip=True)

    return "Unknown"


def extract_description(soup: BeautifulSoup) -> str:
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        return meta_desc["content"].strip()
    return ""


def extract_title(soup: BeautifulSoup, json_ld: Dict[str, Optional[str]]) -> str:
    if json_ld.get("title"):
        return str(json_ld["title"]).strip()

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)

    return "Unknown"


def strip_unwanted_sections(soup: BeautifulSoup) -> None:
    for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
        tag.decompose()

    pattern = re.compile(
        r"nav|footer|header|aside|ads|advert|promo|subscribe|breadcrumb|share|cookie|banner|related|social",
        re.I,
    )
    for element in soup.find_all(attrs={"class": pattern}):
        element.decompose()
    for element in soup.find_all(attrs={"id": pattern}):
        element.decompose()


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def collect_paragraphs(container: BeautifulSoup) -> List[str]:
    paragraphs: List[str] = []
    for tag in container.find_all(["p", "li", "h2", "h3", "pre", "code"]):
        text = normalize_whitespace(tag.get_text(" ", strip=True))
        if len(text) < 30:
            continue
        paragraphs.append(text)
    return paragraphs


def dedupe_paragraphs(paragraphs: List[str]) -> List[str]:
    seen = set()
    unique: List[str] = []
    for paragraph in paragraphs:
        key = paragraph.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(paragraph)
    return unique


def extract_body(soup: BeautifulSoup, json_ld: Dict[str, Optional[str]]) -> str:
    if json_ld.get("body"):
        raw_body = str(json_ld["body"])
        if "<" in raw_body and ">" in raw_body:
            raw_body = BeautifulSoup(raw_body, "html.parser").get_text(" ")
        body = normalize_whitespace(raw_body)
        if len(body) >= 200:
            return body

    strip_unwanted_sections(soup)

    for selector in ["article", "main"]:
        container = soup.find(selector)
        if container:
            paragraphs = dedupe_paragraphs(collect_paragraphs(container))
            if paragraphs:
                return "\n\n".join(paragraphs)

    content_div = soup.find(class_=re.compile(r"content|article|post", re.I))
    if content_div:
        paragraphs = dedupe_paragraphs(collect_paragraphs(content_div))
        if paragraphs:
            return "\n\n".join(paragraphs)

    paragraphs = dedupe_paragraphs(collect_paragraphs(soup))
    return "\n\n".join(paragraphs)


def normalize_date(raw_date: str) -> str:
    if not raw_date or raw_date == "Unknown":
        return "Unknown"

    trimmed = raw_date.strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(trimmed[:32], fmt).date().isoformat()
        except Exception:
            continue

    return trimmed


def detect_region(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower()
    if hostname.endswith(".edu"):
        return "US"
    if hostname.endswith(".uk"):
        return "UK"
    return "Global"


def build_record(
    url: str,
    author: str,
    published_date: str,
    body: str,
    title: str,
    description: str,
) -> Dict[str, Any]:
    language = detect_language(body) if body else "Unknown"
    tags = extract_tags(body) if body else []
    chunks = chunk_text_by_words(body) if body else []

    from scoring.trust_score import calculate_trust_score
    record = {
        "source_url": url,
        "source_type": "blog",
        "author": author or "Unknown",
        "published_date": published_date or "Unknown",
        "language": language,
        "region": detect_region(url),
        "topic_tags": tags,
        "content_chunks": chunks,
        "title": title or "Unknown",
        "description": description or "",
    }
    record["trust_score"] = calculate_trust_score(record)
    return record


def scrape_blog(url: str) -> Dict[str, Any]:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    json_ld_items = parse_json_ld(soup)
    json_ld = extract_from_json_ld(json_ld_items)

    author = extract_author(soup, json_ld)
    raw_date = extract_date(soup, json_ld)
    published_date = normalize_date(raw_date)
    description = extract_description(soup)
    title = extract_title(soup, json_ld)
    body = extract_body(soup, json_ld)

    if not body and description:
        body = description

    if not author:
        author = "Unknown"
    if not published_date:
        published_date = "Unknown"

    return build_record(url, author, published_date, body, title, description)


def main() -> None:
    results: List[Dict[str, Any]] = []

    for url in BLOG_URLS:
        try:
            data = scrape_blog(url)
        except Exception:
            data = build_record(url, "Unknown", "Unknown", "", "Unknown", "")
        results.append(data)

    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "blogs.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(results)} blog entries to {output_path}")


if __name__ == "__main__":
    main()
