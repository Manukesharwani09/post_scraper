## Data Scraping & Trust Scoring System Report

**Author:** Manu Kesharwani  
**Date:** May 2026

---

## 1. Scraping Strategy

### Blog scraping
- Uses `requests` with a browser-like `User-Agent`.
- Extraction priority:
	1. JSON-LD (`application/ld+json`)
	2. `<meta>` tags (author, published_time, description)
	3. DOM heuristics (`article`, `main`, class patterns)
- Cleanup removes: `script`, `style`, `nav`, `footer`, `aside`, `header`, plus class/id patterns for nav/ads/subscribe/social.

### YouTube scraping
- Extracts metadata from `ytInitialPlayerResponse` in HTML.
- Uses regex fallback if needed for channel and publish date.
- Attempts transcript extraction via `youtube-transcript-api`.
- Falls back to description when transcript is unavailable.

### PubMed scraping
- Uses NCBI E-Utilities (`efetch`, `elink`).
- XML parsed with `ElementTree`.
- Citation count retrieved from `elink`.

Notes:
- No JavaScript rendering is implemented.
- Transcript availability is not guaranteed.
- Extraction reliability depends on source HTML structure.

---

## 2. Chunking Strategy

- Blog + YouTube: `chunk_text_by_words` (sentence-aligned, word-based, 100–300 words).
- PubMed: `chunk_text` (character-based paragraph splitting).

Chunking differs by source type; there is no unified chunking system.

---

## 3. Topic Tagging

Tagging uses:
- Domain keyword matching (`DOMAIN_HINTS`).
- POS-based tagging (NLTK).
- PubMed-specific extractor (`pubmed_extract_tags`).

Fallback:
- Frequency-based extraction when NLTK data is unavailable.

No semantic or embedding-based tagging is used.

---

## 4. Trust Score

Trust score is computed by the external function `calculate_trust_score(record)`.

Inputs passed from scrapers:
- `author`
- `published_date`
- `source_url` / domain signals
- `citation_count` (PubMed only)

Scoring logic is handled in the external scoring module.

---

## 5. Edge Cases

- Missing author → stored as `"Unknown"`.
- Missing date → stored as `"Unknown"`.
- Missing transcript → falls back to description (YouTube only).
- Empty content → minimal record created.

No scraper-layer numeric penalties are applied.

---

## 6. Abuse Prevention

No explicit abuse-prevention system exists in the scraper layer.
Only indirect signals exist via collected metadata.

---

## 7. YouTube Processing

- Metadata from `ytInitialPlayerResponse`.
- Regex fallback used if needed.
- Transcript extraction is optional.
- Promotional filtering is keyword-based heuristics only.

---

## 8. Schema Consistency

All sources output:
- `source_url`
- `source_type`
- `author`
- `published_date`
- `language`
- `region`
- `topic_tags`
- `content_chunks`
- `title`
- `description` (if available)

Notes:
- Tagging logic differs per source.
- Chunking logic differs per source.
