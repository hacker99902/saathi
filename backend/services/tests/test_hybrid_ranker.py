from backend.services.rag_retriever import RAGRetriever
from backend.services.hybrid_retriever import HybridRetriever


DOCUMENT_ID = "c62e2ab3-7c81-4d6c-a170-89609794e4b7"

QUERY = "What is machine learning?"


retriever = RAGRetriever()

hybrid_retriever = HybridRetriever(
    semantic_weight=0.70,
    keyword_weight=0.30
)


print("\n================================")
print("PHASE 9I - HYBRID RANKING TEST")
print("================================")


# ==================================================
# Semantic retrieval
# ==================================================

semantic_results = retriever.search(
    document_id=DOCUMENT_ID,
    query=QUERY,
    top_k=5
)


# ==================================================
# Keyword retrieval
# ==================================================

keyword_results = retriever.keyword_search(
    document_id=DOCUMENT_ID,
    query=QUERY,
    top_k=5
)


# ==================================================
# Hybrid ranking
# ==================================================

hybrid_results = hybrid_retriever.combine(
    semantic_results=semantic_results,
    keyword_results=keyword_results,
    top_k=5
)


print("\nHYBRID RESULTS")
print("--------------------------------")


for index, result in enumerate(
    hybrid_results,
    start=1
):

    print(
        f"\nRank: {index}"
    )

    print(
        f"Page: {result['page_number']}"
    )

    print(
        f"Semantic Score: "
        f"{result['semantic_score']:.4f}"
    )

    print(
        f"Keyword Score: "
        f"{result['keyword_score']:.4f}"
    )

    print(
    f"Hybrid Score: "
    f"{result['hybrid_score']:.4f}"
)

    print(
        f"Hybrid Score: "
        f"{result['hybrid_score']:.4f}"
    )

    print(
        f"Text: "
        f"{result['text'][:200]}"
    )


print("\n================================")
print("HYBRID RANKING TEST PASSED")
print("================================")
