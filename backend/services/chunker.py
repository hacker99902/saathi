import re
import uuid
from typing import Dict, List

from backend.services.text_utils import clean_text


def split_into_sentences(text: str) -> List[str]:
    """Split normalized text into sentences."""
    if not isinstance(text, str):
        raise ValueError("text must be a string.")

    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


def _split_long_sentence(
    sentence: str,
    chunk_size: int,
) -> List[str]:
    """
    Split a sentence exceeding chunk_size into word-based pieces.

    Normal sentences remain intact. This fallback prevents a single
    extremely long sentence from creating an oversized chunk.
    """
    if len(sentence) <= chunk_size:
        return [sentence]

    words = sentence.split()
    pieces = []
    current_words = []
    current_length = 0

    for word in words:
        # A single token can itself exceed the configured size.
        if len(word) > chunk_size:
            if current_words:
                pieces.append(" ".join(current_words))
                current_words = []
                current_length = 0

            for start in range(0, len(word), chunk_size):
                pieces.append(word[start:start + chunk_size])

            continue

        added_length = len(word) + (1 if current_words else 0)

        if current_length + added_length > chunk_size:
            pieces.append(" ".join(current_words))
            current_words = [word]
            current_length = len(word)
        else:
            current_words.append(word)
            current_length += added_length

    if current_words:
        pieces.append(" ".join(current_words))

    return pieces


def _validate_settings(chunk_size: int, overlap: int) -> None:
    """Validate chunking configuration."""
    if (
        not isinstance(chunk_size, int)
        or isinstance(chunk_size, bool)
        or chunk_size <= 0
    ):
        raise ValueError("chunk_size must be a positive integer.")

    if (
        not isinstance(overlap, int)
        or isinstance(overlap, bool)
        or overlap < 0
    ):
        raise ValueError("overlap must be a non-negative integer.")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")


def chunk_document(
    pages: List[Dict],
    chunk_size: int = 500,
    overlap: int = 60,
) -> List[Dict]:
    """
    Split page-wise PDF text into chunks.

    Each chunk contains:
        chunk_id: Unique chunk identifier.
        text: Chunk content.
        page_number: Original PDF page number.

    Pages are processed independently, so chunks do not cross
    page boundaries.
    """
    if not isinstance(pages, list):
        raise ValueError("pages must be a list.")

    _validate_settings(chunk_size, overlap)

    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("Each page must be a dictionary.")

        if "page_number" not in page or "text" not in page:
            raise ValueError(
                "Each page must contain page_number and text."
            )

        page_number = page["page_number"]

        if (
            not isinstance(page_number, int)
            or isinstance(page_number, bool)
            or page_number <= 0
        ):
            raise ValueError("page_number must be a positive integer.")

        if not isinstance(page["text"], str):
            raise ValueError("Page text must be a string.")

    chunks = []

    for page in pages:
        page_number = page["page_number"]
        text = clean_text(page["text"])

        if not text or not text.strip():
            continue

        sentences = split_into_sentences(text)

        # Preserve ordinary sentences, but split oversized ones.
        units = []

        for sentence in sentences:
            units.extend(
                _split_long_sentence(sentence, chunk_size)
            )

        current_units = []
        current_length = 0

        for unit in units:
            added_length = len(unit) + (
                1 if current_units else 0
            )

            if current_length + added_length <= chunk_size:
                current_units.append(unit)
                current_length += added_length
                continue

            # Save the current chunk before starting another.
            if current_units:
                chunk_text = " ".join(current_units).strip()

                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "text": chunk_text,
                    "page_number": page_number,
                })

            # Build overlap from previous units, keeping it within
            # both the overlap limit and the next chunk's size.
            overlap_units = []
            overlap_length = 0

            for previous_unit in reversed(current_units):
                proposed_length = (
                    overlap_length
                    + len(previous_unit)
                    + (1 if overlap_units else 0)
                )

                if proposed_length > overlap:
                    break

                overlap_units.insert(0, previous_unit)
                overlap_length = proposed_length

            # Remove the oldest overlap units if the next unit
            # would make the new chunk exceed chunk_size.
            while (
                overlap_units
                and overlap_length + 1 + len(unit) > chunk_size
            ):
                removed = overlap_units.pop(0)
                overlap_length -= len(removed)

                if overlap_units:
                    overlap_length -= 1

            current_units = overlap_units + [unit]
            current_length = sum(
                len(item) for item in current_units
            ) + max(0, len(current_units) - 1)

        # Save the final chunk for this page.
        if current_units:
            chunk_text = " ".join(current_units).strip()

            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "text": chunk_text,
                "page_number": page_number,
            })

    return chunks


if __name__ == "__main__":
    sample_pages = [
        {
            "page_number": 1,
            "text": (
                "Machine Learning is a branch of Artificial "
                "Intelligence that enables computers to learn "
                "patterns from data. Instead of writing rules "
                "manually, we provide examples and allow "
                "algorithms to learn relationships. Machine "
                "learning can use these relationships to make "
                "predictions on new data."
            ),
        },
        {
            "page_number": 2,
            "text": (
                "Supervised learning uses labelled data. "
                "Classification predicts categories, while "
                "regression predicts continuous numerical values. "
                "Unsupervised learning works with data that does "
                "not have predefined labels."
            ),
        },
    ]

    result = chunk_document(
        sample_pages,
        chunk_size=250,
        overlap=60,
    )

    print(f"Total chunks: {len(result)}")

    for index, chunk in enumerate(result, start=1):
        print("\n" + "=" * 40)
        print(f"Chunk {index}")
        print(f"ID: {chunk['chunk_id']}")
        print(f"Page: {chunk['page_number']}")
        print(f"Characters: {len(chunk['text'])}")
        print(chunk["text"])