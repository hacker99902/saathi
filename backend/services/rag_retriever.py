from typing import List, Dict

from backend.services.pdf_service import extract_text_from_pdf
from backend.services.chunker import chunk_document
from backend.services.qdrant_vector_store import QdrantVectorStore
from backend.services.text_utils import normalize_query
from backend.services.keyword_retriever import KeywordRetriever


class RAGRetriever:

    def __init__(
        self,
        embedding_dimension: int = 384,
        batch_size: int = 4
    ):
        self.embedding_dimension = embedding_dimension
        self.batch_size = batch_size

    # ==================================================
    # PROCESS PDF
    # ==================================================

    def process_pdf(
        self,
        file_path: str,
        document_id: str
    ) -> Dict:

        extracted = extract_text_from_pdf(file_path)

        chunks = chunk_document(
            pages=extracted["pages"],
            chunk_size=500,
            overlap=60
        )

        if not chunks:
            raise ValueError(
                "No text chunks were created from the PDF."
            )

        # Qdrant generates embeddings remotely.
        vector_store = QdrantVectorStore(document_id)
        vector_store.add(chunks)

        return {
            "document_id": document_id,
            "page_count": extracted["page_count"],
            "chunk_count": len(chunks),
            "vector_count": vector_store.count()
        }

    # ==================================================
    # LOAD DOCUMENT
    # ==================================================

    def load_document(
        self,
        document_id: str
    ) -> QdrantVectorStore:

        return QdrantVectorStore(document_id)

    # ==================================================
    # SEMANTIC SEARCH
    # ==================================================

    def search(
        self,
        document_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:

        normalized_query = normalize_query(query)

        vector_store = self.load_document(document_id)

        return vector_store.search(
            query=normalized_query,
            top_k=top_k
        )

    # ==================================================
    # KEYWORD SEARCH - BM25
    # ==================================================

    def keyword_search(
        self,
        document_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:

        vector_store = self.load_document(document_id)

        keyword_retriever = KeywordRetriever()
        keyword_retriever.build_index(vector_store.chunks)

        normalized_query = normalize_query(query)

        return keyword_retriever.search(
            query=normalized_query,
            top_k=top_k
        )