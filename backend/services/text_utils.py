
import re


# Common AI / ML abbreviations
ABBREVIATIONS = {
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "llm": "large language model",
    "rag": "retrieval augmented generation",
    "cnn": "convolutional neural network",
    "rnn": "recurrent neural network",
    "knn": "k nearest neighbors",
    "svm": "support vector machine",
    "pca": "principal component analysis",
}

_ABBREVIATION_PATTERN = re.compile(
    r"\b(" + "|".join(
        re.escape(item)
        for item in sorted(ABBREVIATIONS, key=len, reverse=True)
    ) + r")\b",
    flags=re.IGNORECASE,
)


def clean_text(text: str) -> str:
    """
    Clean common PDF extraction problems without
    changing the document's wording.
    """
    if not isinstance(text, str):
        raise ValueError("text must be a string.")

    if not text:
        return ""

    # Normalize special spaces and line endings.
    text = text.replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing spaces from each line.
    lines = [
        re.sub(r"[ \t]+$", "", line)
        for line in text.split("\n")
    ]
    text = "\n".join(lines)

    # Replace repeated spaces and tabs without removing
    # meaningful line boundaries.
    text = re.sub(r"[ \t]+", " ", text)

    # Normalize runs of blank lines.
    text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)

    # Remove spaces before punctuation.
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)

    return text.strip()


def normalize_query(query: str) -> str:
    """
    Expand common AI/ML abbreviations in a query.

    Example:
        What is ML?
        -> What is machine learning?
    """
    if not isinstance(query, str):
        raise ValueError("query must be a string.")

    query = clean_text(query)

    if not query:
        return ""

    def expand_abbreviation(match: re.Match) -> str:
        return ABBREVIATIONS[match.group(0).lower()]

    return _ABBREVIATION_PATTERN.sub(
        expand_abbreviation,
        query,
    )


if __name__ == "__main__":
    examples = [
        "What is ML?",
        "Explain NLP and RAG.",
        "What is HTML?",
        "How does an LLM work?",
    ]

    for example in examples:
        print(f"Original:   {example}")
        print(f"Normalized: {normalize_query(example)}")
        print()
