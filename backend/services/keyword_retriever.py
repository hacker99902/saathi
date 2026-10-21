import re
from typing import List, Dict

from rank_bm25 import BM25Okapi


class KeywordRetriever:

    def __init__(self):

        self.documents = []

        self.tokenized_documents = []

        self.bm25 = None

    # ==================================================
    # Tokenization
    # ==================================================

    def _tokenize(
        self,
        text: str
    ) -> List[str]:

        if not text:
            return []

        text = text.lower()

        tokens = re.findall(
            r"\b\w+\b",
            text
        )

        return tokens

    # ==================================================
    # Build index
    # ==================================================

    def build_index(
        self,
        chunks: List[Dict]
    ):

        self.documents = chunks

        self.tokenized_documents = [
            self._tokenize(
                chunk["text"]
            )
            for chunk in chunks
        ]

        if not self.tokenized_documents:

            self.bm25 = None

            return

        self.bm25 = BM25Okapi(
            self.tokenized_documents
        )

    # ==================================================
    # Search
    # ==================================================

    def search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:

        if not self.bm25:

            return []

        query_tokens = self._tokenize(
            query
        )

        if not query_tokens:

            return []

        scores = self.bm25.get_scores(
            query_tokens
        )

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True
        )

        results = []

        for index in ranked_indices[:top_k]:

            result = self.documents[
                index
            ].copy()

            result[
                "keyword_score"
            ] = float(
                scores[index]
            )

            results.append(
                result
            )

        return results