"""
utils/chunking.py
-----------------
Splits long text content into smaller, manageable chunks.
Each chunk is a paragraph or a fixed-size segment.
"""

def chunk_text(text: str, max_chunk_size: int = 800) -> list:
    """
    Split text into chunks.
    Strategy:
      1. First try splitting by double newlines (paragraphs).
      2. If a paragraph is still too long, split by sentence boundaries.
    
    Args:
        text: The raw text to chunk.
        max_chunk_size: Maximum number of characters per chunk.

    Returns:
        List of text chunk strings.
    """
    if not text or not text.strip():
        return []

    # Step 1: Split on paragraph breaks
    raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    chunks = []
    current_chunk = ""

    for para in raw_paragraphs:
        # If adding this paragraph keeps us under the limit, append it
        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            current_chunk = (current_chunk + "\n\n" + para).strip()
        else:
            # Save the current chunk if it has content
            if current_chunk:
                chunks.append(current_chunk)
            # If the paragraph itself is too big, split by sentences
            if len(para) > max_chunk_size:
                sentence_chunks = _split_by_sentences(para, max_chunk_size)
                chunks.extend(sentence_chunks[:-1])
                current_chunk = sentence_chunks[-1] if sentence_chunks else ""
            else:
                current_chunk = para

    # Don't forget the last accumulated chunk
    if current_chunk:
        chunks.append(current_chunk)

    return [c for c in chunks if c.strip()]


def _split_by_sentences(text: str, max_size: int) -> list:
    """
    Fallback: split a large paragraph by sentence-ending punctuation.
    """
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_size:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks