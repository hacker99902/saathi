from sentence_transformers import SentenceTransformer
from typing import List


# --------------------------------------------------
# Load the embedding model ONCE
# --------------------------------------------------

model = SentenceTransformer("all-MiniLM-L6-v2")


# --------------------------------------------------
# Generate embedding for ONE piece of text
# --------------------------------------------------

def generate_embedding(text: str) -> List[float]:
    """
    Convert a single piece of text into
    a numerical embedding vector.
    """

    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    embedding = model.encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    return embedding.tolist()


# --------------------------------------------------
# Generate embeddings for MULTIPLE texts
# --------------------------------------------------

def generate_embeddings(
    texts: List[str],
    batch_size: int = 32
) -> List[List[float]]:
    """
    Convert multiple texts into embedding vectors.

    batch_size controls how many texts are processed
    at one time.

    Example:
        1000 chunks with batch_size=32

        32 chunks → batch 1
        32 chunks → batch 2
        32 chunks → batch 3
        ...
    """

    if not texts:
        return []

    # Remove empty texts
    cleaned_texts = [
        text.strip()
        for text in texts
        if text and text.strip()
    ]

    if not cleaned_texts:
        return []

    embeddings = model.encode(
        cleaned_texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    return embeddings.tolist()


# --------------------------------------------------
# TEST
# --------------------------------------------------

if __name__ == "__main__":

    texts = [
        """
        Machine learning is a branch of artificial intelligence
        that enables computers to learn patterns from data.
        """,

        """
        Supervised learning uses labelled data to train
        machine learning models.
        """,

        """
        Classification is a machine learning task where
        the model predicts categories or classes.
        """,

        """
        Regression is used to predict continuous numerical
        values from input data.
        """
    ]

    print("Generating embeddings...\n")

    embeddings = generate_embeddings(
        texts,
        batch_size=32
    )

    print("\nEmbedding generation completed!")

    print("Total texts:", len(texts))
    print("Total embeddings:", len(embeddings))

    if embeddings:
        print("Vector dimensions:", len(embeddings[0]))

        print("\nFirst 10 values of first embedding:")
        print(embeddings[0][:10])
