
from sentence_transformers import SentenceTransformer
from typing import List

# Load the model only when first needed
_model = None


def get_model() -> SentenceTransformer:
    global _model

    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")

    return _model


def generate_embedding(text: str) -> List[float]:
    """Generate an embedding for one piece of text."""

    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    embedding = get_model().encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    return embedding.tolist()


def generate_embeddings(
    texts: List[str],
    batch_size: int = 32
) -> List[List[float]]:
    """Generate embeddings for multiple texts."""

    if not texts:
        return []

    cleaned_texts = [
        text.strip()
        for text in texts
        if text and text.strip()
    ]

    if not cleaned_texts:
        return []

    embeddings = get_model().encode(
        cleaned_texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    return embeddings.tolist()


if __name__ == "__main__":
    texts = [
        "Machine learning learns patterns from data.",
        "Supervised learning uses labelled data.",
        "Classification predicts categories.",
        "Regression predicts numerical values."
    ]

    print("Generating embeddings...\n")

    embeddings = generate_embeddings(texts, batch_size=4)

    print("\nEmbedding generation completed!")
    print("Total texts:", len(texts))
    print("Total embeddings:", len(embeddings))

    if embeddings:
        print("Vector dimensions:", len(embeddings[0]))
        print("First 10 values:", embeddings[0][:10])
