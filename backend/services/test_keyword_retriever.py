from backend.services.keyword_retriever import KeywordRetriever


chunks = [
    {
        "chunk_id": "1",
        "text": "Machine learning is a branch of artificial intelligence.",
        "page_number": 1
    },
    {
        "chunk_id": "2",
        "text": "Supervised learning uses labeled training data.",
        "page_number": 2
    },
    {
        "chunk_id": "3",
        "text": "Reinforcement learning is used in robotics and game playing.",
        "page_number": 3
    },
    {
        "chunk_id": "4",
        "text": "Deep learning uses neural networks with multiple layers.",
        "page_number": 4
    }
]


retriever = KeywordRetriever()

retriever.build_index(chunks)


query = "What is machine learning?"


results = retriever.search(
    query=query,
    top_k=3
)


print("\n==============================")
print("BM25 KEYWORD RETRIEVAL TEST")
print("==============================")

print(f"\nQuery: {query}")

print("\nResults:")
print("------------------------------")

for result in results:

    print(
        f"Page: {result['page_number']} | "
        f"Score: {result['keyword_score']:.4f}"
    )

    print(
        f"Text: {result['text']}"
    )

    print()


if results:

    print("==============================")
    print("BM25 TEST PASSED")
    print("==============================")

else:

    print("==============================")
    print("BM25 TEST FAILED")
    print("==============================")