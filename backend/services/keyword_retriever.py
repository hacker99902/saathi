
import re
import math
from typing import Dict, List

from rank_bm25 import BM25Okapi


class KeywordRetriever:
    """BM25 keyword retrieval over document text chunks."""

    def __init__(self):
        self.documents: List[Dict] = []
        self.tokenized_documents: List[List[str]] = []
        self.bm25 = None

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        if not isinstance(text, str) or not text.strip():
            return []

        return re.findall(r"\b\w+\b", text.lower())

    def build_index(self, chunks: List[Dict]):
        """Build a BM25 index, ignoring invalid or empty chunks."""
        if not isinstance(chunks, list):
            raise ValueError("chunks must be a list.")

        self.documents = []
        self.tokenized_documents = []
        self.bm25 = None

        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue

            text = chunk.get("text")

            if not isinstance(text, str) or not text.strip():
                continue

            tokens = self._tokenize(text)

            if not tokens:
                continue

            self.documents.append(chunk)
            self.tokenized_documents.append(tokens)

        if not self.tokenized_documents:
            return

        self.bm25 = BM25Okapi(self.tokenized_documents)

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict]:
        """Return the highest-ranked keyword matches."""
        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or top_k < 1
        ):
            raise ValueError("top_k must be a positive integer.")

        if not isinstance(query, str) or not query.strip():
            return []

        if self.bm25 is None:
            return []

        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )

        results = []

        for index in ranked_indices:
            score = float(scores[index])

            if not math.isfinite(score) or score <= 0:
                continue

            result = self.documents[index].copy()
            result["keyword_score"] = score
            results.append(result)

            if len(results) >= top_k:
                break

        return results
