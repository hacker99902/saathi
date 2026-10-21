from typing import List, Dict


class HybridRetriever:

    def __init__(
        self,
        semantic_weight: float = 0.70,
        keyword_weight: float = 0.30
    ):

        if semantic_weight < 0:
            raise ValueError(
                "semantic_weight cannot be negative."
            )

        if keyword_weight < 0:
            raise ValueError(
                "keyword_weight cannot be negative."
            )

        if semantic_weight + keyword_weight == 0:
            raise ValueError(
                "At least one retrieval weight must be greater than 0."
            )

        total = (
            semantic_weight
            + keyword_weight
        )

        self.semantic_weight = (
            semantic_weight / total
        )

        self.keyword_weight = (
            keyword_weight / total
        )

    # ==================================================
    # HYBRID SEARCH
    # ==================================================

    def combine(
        self,
        semantic_results: List[Dict],
        keyword_results: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:

        if top_k <= 0:
            return []

        combined = {}

        # ----------------------------------------------
        # Add semantic results
        # ----------------------------------------------

        for result in semantic_results:

            chunk_id = result["chunk_id"]

            semantic_score = float(
                result["similarity_score"]
            )

            combined[chunk_id] = {
                **result,

                "semantic_score": semantic_score,

                "keyword_score": 0.0,

                "hybrid_score": (
                    self.semantic_weight
                    * semantic_score
                )
            }

        # ----------------------------------------------
        # Find maximum positive BM25 score
        # ----------------------------------------------

        positive_keyword_scores = [
            float(result["keyword_score"])
            for result in keyword_results
            if float(result["keyword_score"]) > 0
        ]

        max_keyword_score = (
            max(positive_keyword_scores)
            if positive_keyword_scores
            else 0.0
        )

        # ----------------------------------------------
        # Add keyword results
        # ----------------------------------------------

        for result in keyword_results:

            chunk_id = result["chunk_id"]

            raw_keyword_score = float(
                result["keyword_score"]
            )

            # Normalize BM25 against the strongest
            # keyword result.
            if (
                max_keyword_score > 0
                and raw_keyword_score > 0
            ):

                keyword_score = (
                    raw_keyword_score
                    /
                    max_keyword_score
                )

            else:

                keyword_score = 0.0

            if chunk_id not in combined:

                combined[chunk_id] = {
                    **result,

                    "semantic_score": 0.0,

                    "keyword_score": raw_keyword_score,

                    "hybrid_score": (
                        self.keyword_weight
                        * keyword_score
                    )
                }

            else:

                combined[chunk_id][
                    "keyword_score"
                ] = raw_keyword_score

                semantic_score = combined[
                    chunk_id
                ]["semantic_score"]

                combined[chunk_id][
                    "hybrid_score"
                ] = (
                    self.semantic_weight
                    * semantic_score
                    +
                    self.keyword_weight
                    * keyword_score
                )

        # ----------------------------------------------
        # Sort by hybrid score
        # ----------------------------------------------

        results = list(
            combined.values()
        )

        results.sort(
            key=lambda result:
                result["hybrid_score"],
            reverse=True
        )

        return results[:top_k]
