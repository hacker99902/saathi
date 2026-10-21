import re


# --------------------------------------------------
# Common AI / ML abbreviations
# --------------------------------------------------

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
    "pca": "principal component analysis"
}


# --------------------------------------------------
# Clean extracted PDF text
# --------------------------------------------------

def clean_text(text: str) -> str:
    """
    Clean common PDF extraction problems.

    This does not try to rewrite the document.
    It only fixes whitespace and obvious formatting issues.
    """

    if not text:
        return ""

    # Replace non-breaking spaces
    text = text.replace("\xa0", " ")

    # Remove excessive whitespace
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # Remove spaces before punctuation
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)

    return text.strip()


# --------------------------------------------------
# Normalize user query
# --------------------------------------------------

def normalize_query(query: str) -> str:
    """
    Expand common AI/ML abbreviations in a user query.

    Example:

        What is ML?
        ↓
        What is machine learning?
    """

    if not query:
        return ""

    query = clean_text(query)

    words = query.split()

    normalized_words = []

    for word in words:

        # Remove punctuation temporarily
        clean_word = re.sub(
            r"[^\w]",
            "",
            word.lower()
        )

        if clean_word in ABBREVIATIONS:

            replacement = ABBREVIATIONS[
                clean_word
            ]

            # Preserve punctuation
            punctuation = ""

            if word.endswith("?"):
                punctuation = "?"

            normalized_words.append(
                replacement + punctuation
            )

        else:

            normalized_words.append(word)


    return " ".join(normalized_words)
