# Multi-Source Scraper & Trust Scoring System

A Python pipeline that scrapes structured content from **3 blog posts**, **2 YouTube videos**, and **1 PubMed article**, then evaluates each source with a rule-based **Trust Score**.

---

## Project Structure

```
post_scraper/
├── scraper/
│   ├── blog_scraper.py       # Scrapes 3 blog posts
│   ├── youtube_scraper.py    # Scrapes 2 YouTube videos
│   └── pubmed_scraper.py     # Scrapes 1 PubMed article (NCBI API)
├── scoring/
│   └── trust_score.py        # Trust score algorithm
├── utils/
│   ├── chunking.py           # Content chunking
│   ├── tagging.py            # Automatic topic tagging (RAKE + domain hints)
│   └── language_detect.py    # Language detection (langdetect)
├── output/
│   ├── blogs.json
│   ├── youtube.json
│   ├── pubmed.json
│   └── scraped_data.json     # All 6 sources merged
├── main.py                   # Pipeline orchestrator
├── report.md                 # Short written report
└── requirements.txt
```

---

## Tools & Libraries

| Library | Purpose |
|---|---|
| `requests` | HTTP requests |
| `beautifulsoup4` | HTML parsing |
| `youtube-transcript-api` | YouTube transcript extraction |
| `langdetect` | Language detection |
| `rake-nltk` | Keyword/topic extraction (RAKE) |
| `nltk` | NLP support for RAKE |
| `python-dateutil` | Date parsing |
| `tqdm` | Progress bars |

---

## How to Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the full pipeline

```bash
python main.py
```

This will:
- Scrape all 6 sources
- Apply trust scores
- Write `output/blogs.json`, `output/youtube.json`, `output/pubmed.json`
- Merge all into `output/scraped_data.json`

### 3. Run individual scrapers

```bash
python scraper/blog_scraper.py
python scraper/youtube_scraper.py
python scraper/pubmed_scraper.py
```

---

## Output Schema

Every scraped record follows this JSON schema:

```json
{
  "source_url": "https://...",
  "source_type": "blog | youtube | pubmed",
  "author": "Author Name",
  "published_date": "YYYY-MM-DD",
  "language": "English",
  "region": "Global | US | UK",
  "topic_tags": ["AI", "Machine Learning"],
  "trust_score": 0.72,
  "content_chunks": ["Paragraph 1...", "Paragraph 2..."]
}
```

---

## Scraping Approach

### Blogs
- Fetch HTML with `requests`
- Extract author/date from JSON-LD structured data, then `<meta>` tags, then DOM heuristics
- Strip navigation, ads, footers; collect `<p>`/`<li>`/`<h2>`/`<h3>`/`<code>` text from `<article>` / `<main>` containers
- Fallback to description meta-tag if no body found

### YouTube
- Fetch page HTML with a browser-like `User-Agent`
- Parse `ytInitialPlayerResponse` JSON blob embedded in the page for channel name, publish date, description
- Pull full transcript via `youtube-transcript-api`; fall back to description if unavailable

### PubMed
- Use **NCBI E-Utilities** REST API (no API key required for low-volume requests)
- `efetch` → XML for title, authors, abstract, journal, year
- `elink` → citations count (pubmed_pubmed_citedin)

---

## Trust Score Design

```
Trust Score = weighted_average(
    author_credibility   × 0.25
    citation_count       × 0.20
    domain_authority     × 0.25
    recency              × 0.15
    medical_disclaimer   × 0.15
)
```

| Factor | Rules |
|---|---|
| **Author credibility** | Known institutions → 0.9; Unknown → 0.2; Generic → 0.6 |
| **Citation count** | PubMed only; 0 cites → 0.1; 200+ cites → 1.0; others → 0.5 |
| **Domain authority** | .edu/.gov/ncbi → 0.9; known tech → 0.7; spam hosts → 0.2 |
| **Recency** | <1yr → 1.0; 1-3yr → 0.75; 3-5yr → 0.5; >5yr → 0.25; Unknown → 0.4 |
| **Medical disclaimer** | Disclaimer present → 1.0; healthcare + no disclaimer → 0.2; non-medical → 0.8 |

Additional adjustments:
- **YouTube transcript availability**: short or shallow extracted content receives a small penalty.

See `scoring/trust_score.py` for full implementation including abuse prevention logic.

---

## Limitations

- **YouTube transcripts**: Some videos may not have transcripts; description is used as fallback
- **Dynamic JS sites**: Blog scraper uses static HTML only; sites requiring JS rendering may yield empty content
- **Citation count**: NCBI elink counts only PubMed cross-references, not Google Scholar or Web of Science
- **Author credibility**: Limited to a manually curated whitelist; unknown authors receive neutral-low scores
- **Region detection**: Currently inferred from TLD only (`.edu` → US, `.uk` → UK)
