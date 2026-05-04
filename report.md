# Short Report: Data Scraping & Trust Scoring System

**Author:** Manu Kesharwani  
**Date:** May 2026

---

## 1. Scraping Strategy

The pipeline uses a **source-specific scraper** for each content type, all sharing common utilities for language detection, topic tagging, and text chunking (sentence-aligned, word-based chunks for retrieval stability).

### Blog Posts
Blogs are fetched as static HTML using the `requests` library with a realistic browser `User-Agent`. The extraction pipeline follows a priority cascade:

1. **JSON-LD structured data** (`application/ld+json`) — the most reliable source for author, date, and article body on modern blogs.
2. **`<meta>` tags** — `article:author`, `article:published_time`, `og:description`.
3. **DOM heuristics** — `<article>`, `<main>` containers, then `class` patterns matching `content|article|post`.
4. **Cleanup** — navigation, ads, footers, and sidebars are stripped before text is extracted.

### YouTube Videos
YouTube embeds a large JSON blob (`ytInitialPlayerResponse`) directly in the page HTML. The scraper parses this to extract the channel name, publish date, and video description without needing the YouTube Data API. Full transcripts are retrieved using `youtube-transcript-api`; the video description is used as a fallback when transcripts are unavailable.

### PubMed Article
The NCBI E-Utilities REST API is used — specifically:
- **`efetch`** returns structured XML with title, authors, abstract, journal, and year.
- **`elink`** counts inbound citations (`pubmed_pubmed_citedin`), which feeds directly into the trust score's citation factor.

---

## 2. Topic Tagging Method

Topic tagging combines two approaches:

**Domain-hint matching** scans the text for keywords belonging to predefined categories (AI, Machine Learning, Healthcare, Data Science, Web Scraping, Research, Technology, Security, Finance, YouTube). Categories are ranked by the number of keyword hits; those with at least one hit are included as tags.

**RAKE (Rapid Automatic Keyword Extraction)** from `rake-nltk` extracts multi-word key phrases using word co-occurrence scoring from the full text. Up to 8 phrases are extracted, cleaned, and title-cased.

The final tag list merges both sources (domain-hint tags first for higher confidence), capped at 8 tags.

---

## 3. Trust Score Algorithm

The trust score is a **weighted average of five factors**, each independently scored on [0, 1]:

| Factor | Weight | Description |
|---|---|---|
| Author credibility | 25% | Cross-checked against a whitelist of known institutions |
| Citation count | 20% | PubMed elink data; neutral default (0.5) for other types |
| Domain authority | 25% | TLD/hostname analysis; spam hosts penalised |
| Recency | 15% | Exponentially penalises older content |
| Medical disclaimer | 15% | Penalises healthcare content without a disclaimer |

The two highest-weight factors (author credibility and domain authority) jointly reflect **source trustworthiness**, which is the most robust signal available without external verification services.

---

## 4. Edge Case Handling

| Scenario | Handling |
|---|---|
| Missing author | Credibility score = 0.2 (low, not zero — article may still be credible) |
| Missing publish date | Recency score = 0.4 (neutral penalty) |
| Multiple authors | Average credibility score across all authors |
| No transcript (YouTube) | Fall back to video description for content; apply a small trust penalty if content is shallow |
| Empty content | Trust score = 0.0 (no content, no reliability signal) |
| Non-English content | Language detection flags it; scoring is language-agnostic |
| Very short text | Language detection returns "Unknown"; chunker returns empty/single list |

---

## 5. Abuse Prevention Logic

| Threat | Prevention |
|---|---|
| **Fake authors** | Unknown/missing → 0.2 credibility; not on whitelist → 0.6 max |
| **SEO spam blogs** | Domains on free hosts (WordPress.com, Blogspot, Wix) → domain score 0.2 |
| **Misleading medical content** | Healthcare keywords present but no disclaimer → disclaimer score 0.2 |
| **Outdated misinformation** | Articles > 5 years → recency score 0.25 (15% weight impact) |
| **Citation inflation** | Citation count is fetched from third-party NCBI; source cannot self-report |
