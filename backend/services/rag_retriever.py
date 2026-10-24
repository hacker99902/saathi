
from typing import Dict, List

from backend.services.pdf_service import extract_text_from_pdf
from backend.services.chunker import chunk_document
from backend.services.qdrant_vector_store import QdrantVectorStore
from backend.services.text_utils import normalize_query
from backend.services.keyword_retriever import KeywordRetriever


class RAGRetriever:
    def __init__(
        self,
        embedding_dimension: int = 384,
        batch_size: int = 4,
    ):
        if (
            not isinstance(embedding_dimension, int)
            or isinstance(embedding_dimension, bool)
            or embedding_dimension < 1
        ):
            raise ValueError(
                "embedding_dimension must be a positive integer."
            )

        if (
            not isinstance(batch_size, int)
            or isinstance(batch_size, bool)
            or batch_size < 1
        ):
            raise ValueError(
                "batch_size must be a positive integer."
            )

        # Retained for compatibility with existing callers.
        self.embedding_dimension = embedding_dimension
        self.batch_size = batch_size

    @staticmethod
    def _validate_document_id(document_id: str) -> str:
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("Document ID cannot be empty.")

        return document_id.strip()

    @staticmethod
    def _validate_top_k(top_k: int) -> int:
        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or top_k < 1
        ):
            raise ValueError("top_k must be a positive integer.")

        return top_k

    @staticmethod
    def _validate_query(query: str) -> str:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Search query cannot be empty.")

        normalized_query = normalize_query(query.strip())

        if not normalized_query:
            raise ValueError("Search query cannot be empty.")

        return normalized_query

    def process_pdf(
        self,
        file_path: str,
        document_id: str,
    ) -> Dict:
        """
        Extract, chunk, and index a PDF in Qdrant.

        If indexing fails after partial insertion, attempt to remove
        the document's vectors before re-raising the original error.
        """
        document_id = self._validate_document_id(document_id)

        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("PDF file path cannot be empty.")

        extracted = extract_text_from_pdf(file_path)

        chunks = chunk_document(
            pages=extracted["pages"],
            chunk_size=500,
            overlap=60,
        )

        if not chunks:
            raise ValueError(
                "No text chunks were created from the PDF."
            )

        vector_store = QdrantVectorStore(document_id)

        try:
            vector_store.add(chunks)
        except Exception:
            # Best-effort cleanup of partially inserted vectors.
            # Preserve the original indexing exception.
            try:
                vector_store.delete()
            except Exception:
                pass

            raise

        return {
            "document_id": document_id,
            "page_count": extracted["page_count"],
            "chunk_count": len(chunks),
            "vector_count": vector_store.count(),
        }

    def load_document(
        self,
        document_id: str,
    ) -> QdrantVectorStore:
        document_id = self._validate_document_id(document_id)
        return QdrantVectorStore(document_id)

    def search(
        self,
        document_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict]:
        document_id = self._validate_document_id(document_id)
        query = self._validate_query(query)
        top_k = self._validate_top_k(top_k)

        vector_store = self.load_document(document_id)

        return vector_store.search(
            query=query,
            top_k=top_k,
        )

    def keyword_search(
        self,
        document_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict]:
        document_id = self._validate_document_id(document_id)
        query = self._validate_query(query)
        top_k = self._validate_top_k(top_k)

        vector_store = self.load_document(document_id)

        keyword_retriever = KeywordRetriever()
        keyword_retriever.build_index(vector_store.chunks)

        return keyword_retriever.search(
            query=query,
            top_k=top_k,
        )
