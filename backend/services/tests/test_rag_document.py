from backend.services.rag_service import RAGService


rag = RAGService()

document_id = "f269876d-e8da-4761-916a-54f1bf260357"

question = "What is machine learning?"

print("================================")
print("DOCUMENT RAG TEST")
print("================================")

result = rag.ask(
    document_id=document_id,
    question=question,
    session_id="test-rag-document"
)

print("\nANSWER:")
print(result["answer"])

print("\nSOURCES:")

for source in result["sources"]:

    print(
        f"\nPage: {source['page_number']}"
    )

    print(
        f"Score: "
        f"{source['similarity_score']:.4f}"
    )

    print(
        source["text"][:300]
    )