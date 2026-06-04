"""Chunking strategies for the V2 e-commerce RAG system.

Three strategies, each matched to a data type:

1. make_metadata_chunk  → Document-Aware   (structured product fields)
2. recursive_split      → Recursive Char   (long description / features text)
3. make_review_chunk    → Sentence-level   (single customer review = single chunk)

All functions return context-enriched text ready to be embedded.
Context enrichment is template-based (zero LLM cost).
Format: "[{product_title} — {chunk_type}]: {raw_content}"
"""
from __future__ import annotations


def make_metadata_chunk(product: dict) -> str:
    """Document-Aware chunking for structured product fields.

    Returns a single, compact string that encodes all filterable
    attributes. This lets the vector search match queries like
    "cheap moisturizing shampoo under $10" against structured fields.
    """
    title = product.get("title", "Unknown Product")
    category = " > ".join(product.get("categories", [])) or product.get("category", "Unknown")
    price = product.get("price")
    price_str = f"${price:.2f}" if price else "Price not listed"
    avg_rating = product.get("average_rating", 0.0)

    # Extract brand from details dict
    details = product.get("details", {})
    brand = details.get("Brand") or details.get("brand") or "Unknown brand"

    raw = (
        f"Product: {title}\n"
        f"Category: {category}\n"
        f"Brand: {brand}\n"
        f"Price: {price_str}\n"
        f"Rating: {avg_rating}/5"
    )
    return f"[{title} — metadata]: {raw}"


def recursive_split(text: str, max_chars: int = 500, overlap: int = 50) -> list[str]:
    """Recursive Character Splitting for long product descriptions.

    Split order (tries not to break at lower-level separators):
        1. Double newline  (\\n\\n) — paragraph boundary
        2. Single newline  (\\n)    — line boundary
        3. Period + space  (. )     — sentence boundary
        4. Comma + space   (, )     — clause boundary
        5. Space           ( )      — word boundary
        6. Character       (char)   — hard cut (last resort)

    Each chunk always starts with the context prefix so it remains
    meaningful when retrieved in isolation.
    """
    separators = ["\n\n", "\n", ". ", ", ", " ", ""]

    def _split(text: str, seps: list[str]) -> list[str]:
        if not seps:
            # Hard character split
            return [text[i:i + max_chars] for i in range(0, len(text), max_chars - overlap)]

        sep = seps[0]
        parts = text.split(sep) if sep else list(text)

        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = current + (sep if current else "") + part
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                if len(part) > max_chars:
                    # Recursively split this oversized part
                    chunks.extend(_split(part, seps[1:]))
                    current = ""
                else:
                    current = part

        if current.strip():
            chunks.append(current.strip())

        return chunks

    raw_chunks = _split(text.strip(), separators)

    # Add overlap: each chunk except first gets the last `overlap` chars of the previous
    overlapped: list[str] = []
    for i, chunk in enumerate(raw_chunks):
        if i > 0 and overlap > 0:
            prev_tail = raw_chunks[i - 1][-overlap:]
            chunk = prev_tail + " " + chunk
        overlapped.append(chunk.strip())

    return [c for c in overlapped if len(c) > 20]


def make_description_chunks(product: dict) -> list[str]:
    """Combine features + description lists, then recursively split.

    Returns context-enriched chunks with product title prefix.
    """
    title = product.get("title", "Unknown Product")

    features: list = product.get("features", []) or []
    description: list = product.get("description", []) or []

    # Combine into a single text block
    parts = [str(f) for f in features if str(f).strip()]
    parts += [str(d) for d in description if str(d).strip()]
    full_text = "\n".join(parts).strip()

    if not full_text or len(full_text) < 30:
        return []

    raw_chunks = recursive_split(full_text)

    # Context-enrich each chunk
    return [f"[{title} — description]: {chunk}" for chunk in raw_chunks]


def make_review_chunk(product_title: str, review_title: str, review_text: str) -> str:
    """Sentence-level chunking for a single customer review.

    One review = one chunk. No splitting needed since individual
    Amazon reviews rarely exceed 500 chars.
    Context prefix embeds product identity directly in the vector.
    """
    header = f"Review title: {review_title}" if review_title else ""
    body = review_text.strip()
    raw = f"{header}\n{body}".strip() if header else body
    return f"[{product_title} — review]: {raw}"
