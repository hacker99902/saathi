import re
import uuid
from typing import List, Dict
from backend.services.text_utils import clean_text

def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences.

    This is a simple sentence splitter designed for
    general documents.
    """

    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return []

    # Split after ., !, or ?
    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


def chunk_document(
    pages: List[Dict],
    chunk_size: int = 500,
    overlap: int = 60
) -> List[Dict]:
    """
    Split a document into meaningful chunks while
    preserving page numbers.

    Strategy:
        1. Process one page at a time.
        2. Split page text into sentences.
        3. Combine sentences until chunk_size is reached.
        4. Add overlap between chunks.
        5. Never intentionally cut a sentence in half.
    """

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than 0."
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative."
        )

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size."
        )

    chunks = []

    for page in pages:

        page_number = page["page_number"]
        text = clean_text(page["text"])

        if not text:
            continue

        # ----------------------------------------------
        # Split page into sentences
        # ----------------------------------------------

        sentences = split_into_sentences(text)

        current_sentences = []
        current_length = 0

        for sentence in sentences:

            sentence_length = len(sentence)

            # ------------------------------------------
            # Normal case:
            # sentence fits inside current chunk
            # ------------------------------------------

            if (
                current_length + sentence_length + 1
                <= chunk_size
            ):

                current_sentences.append(sentence)

                current_length += (
                    sentence_length + 1
                )

                continue


            # ------------------------------------------
            # Current chunk is full
            # ------------------------------------------

            if current_sentences:

                chunk_text = " ".join(
                    current_sentences
                ).strip()

                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "text": chunk_text,
                    "page_number": page_number
                })


            # ------------------------------------------
            # Create overlap
            # ------------------------------------------

            overlap_sentences = []
            overlap_length = 0

            for previous_sentence in reversed(
                current_sentences
            ):

                sentence_length = len(
                    previous_sentence
                )

                if (
                    overlap_length
                    + sentence_length
                    + 1
                    <= overlap
                ):

                    overlap_sentences.insert(
                        0,
                        previous_sentence
                    )

                    overlap_length += (
                        sentence_length + 1
                    )

                else:
                    break


            # ------------------------------------------
            # Start new chunk with overlap
            # ------------------------------------------

            current_sentences = (
                overlap_sentences
                + [sentence]
            )

            current_length = sum(
                len(item) + 1
                for item in current_sentences
            )


        # ----------------------------------------------
        # Add final chunk from this page
        # ----------------------------------------------

        if current_sentences:

            chunk_text = " ".join(
                current_sentences
            ).strip()

            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "text": chunk_text,
                "page_number": page_number
            })

    return chunks


# ======================================================
# TEST
# ======================================================

if __name__ == "__main__":

    sample_pages = [

        {
            "page_number": 1,
            "text": """
            Machine Learning is a branch of Artificial
            Intelligence that enables computers to learn
            patterns from data.

            Instead of writing rules manually, we provide
            examples and allow algorithms to learn
            relationships.

            Machine learning can then use these learned
            relationships to make predictions on new data.
            """
        },

        {
            "page_number": 2,
            "text": """
            Supervised learning uses labelled data.
            Classification predicts categories while
            regression predicts continuous numerical values.

            Unsupervised learning works with data that does
            not have predefined labels.
            """
        }
    ]


    chunks = chunk_document(
        sample_pages,
        chunk_size=250,
        overlap=60
    )


    print(
        f"Total chunks: {len(chunks)}"
    )


    for i, chunk in enumerate(
        chunks,
        start=1
    ):

        print(
            "\n===================================="
        )

        print(
            f"Chunk {i}"
        )

        print(
            "===================================="
        )

        print(
            f"Chunk ID: {chunk['chunk_id']}"
        )

        print(
            f"Page: {chunk['page_number']}"
        )

        print(
            f"Characters: {len(chunk['text'])}"
        )

        print(
            "\nText:"
        )

        print(
            chunk["text"]
        )
