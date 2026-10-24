
from typing import Dict, List
import math


class HybridRetriever:
    def __init__(
        self,
        semantic_weight: float = 0.70,
        keyword_weight: float = 0.30,
    ):
        if (
            not isinstance(semantic_weight, (int, float))
            or isinstance(semantic_weight, bool)
            or not math.isfinite(semantic_weight)
            or semantic_weight < 0
        ):
            raise ValueError(
                "semantic_weight must be a finite, non-negative number."
            )

        if (
            not isinstance(keyword_weight, (int, float))
            or isinstance(keyword_weight, bool)
            or not math.isfinite(keyword_weight)
            or keyword_weight < 0
        ):
            raise ValueError(
                "keyword_weight must be a finite, non-negative number."
            )

        total = semantic_weight + keyword_weight

        if total <= 0 or not math.isfinite(total):
            raise ValueError(
                "At least one retrieval weight must be greater than zero."
            )

        self.semantic_weight = semantic_weight / total
        self.keyword_weight = keyword_weight / total

    @staticmethod
    def _valid_score(value) -> float:
        """Convert a valid numeric score to a finite float."""
        if isinstance(value, bool):
            return 0.0

        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0

        return score if math.isfinite(score) else 0.0

    @staticmethod
    def _valid_chunk_id(result):
        if not isinstance(result, dict):
            return None

        chunk_id = result.get("chunk_id")

        if chunk_id is None or str(chunk_id).strip() == "":
            return None

        return str(chunk_id)

    def combine(
        self,
        semantic_results: List[Dict],
        keyword_results: List[Dict],
        top_k: int = 5,
    ) -> List[Dict]:
        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or top_k < 1
        ):
            raise ValueError("top_k must be a positive integer.")

        combined = {}

        # Normalize keyword scores relative to the strongest positive
        # BM25 result returned for this query.
        valid_keyword_results = []

        for result in keyword_results or []:
            chunk_id = self._valid_chunk_id(result)

            if chunk_id is None:
                continue

            raw_score = self._valid_score(
                result.get("keyword_score")
            )

            valid_keyword_results.append(
                (chunk_id, result, raw_score)
            )

        max_keyword_score = max(
            (
                score
                for _, _, score in valid_keyword_results
                if score > 0
            ),
            default=0.0,
        )

        # Add semantic candidates.
        for result in semantic_results or []:
            chunk_id = self._valid_chunk_id(result)

            if chunk_id is None:
                continue

            semantic_score = self._valid_score(
                result.get("similarity_score")
            )

            combined[chunk_id] = {
                **result,
                "chunk_id": chunk_id,
                "semantic_score": semantic_score,
                "keyword_score": 0.0,
                "keyword_raw_score": 0.0,
                "hybrid_score": (
                    self.semantic_weight * semantic_score
                ),
            }

        # Merge keyword candidates with semantic candidates.
        for chunk_id, result, raw_score in valid_keyword_results:
            normalized_keyword_score = (
                raw_score / max_keyword_score
                if max_keyword_score > 0 and raw_score > 0
                else 0.0
            )

            if chunk_id not in combined:
                combined[chunk_id] = {
                    **result,
                    "chunk_id": chunk_id,
                    "semantic_score": 0.0,
                    "similarity_score": 0.0,
                    "keyword_score": normalized_keyword_score,
                    "keyword_raw_score": raw_score,
                    "hybrid_score": (
                        self.keyword_weight
                        * normalized_keyword_score
                    ),
                }
            else:
                item = combined[chunk_id]

                # Keep the best positive keyword score if duplicates
                # exist in the keyword result list.
                if normalized_keyword_score > item["keyword_score"]:
                    item["keyword_score"] = normalized_keyword_score
                    item["keyword_raw_score"] = raw_score

                item["hybrid_score"] = (
                    self.semantic_weight * item["semantic_score"]
                    + self.keyword_weight * item["keyword_score"]
                )

        results = list(combined.values())

        results.sort(
            key=lambda item: item["hybrid_score"],
            reverse=True,
        )

        return results[:top_k]
