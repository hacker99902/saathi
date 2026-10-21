
from typing import List, Dict

from backend.services.pdf_service import extract_text_from_pdf
from backend.services.chunker import chunk_document
from backend.services.embedding_service import (
    generate_embedding,
    generate_embeddings
)
from backend.services.document_store import DocumentStore
from backend.services.vector_store import VectorStore
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

        self.document_store = DocumentStore()

    # ==================================================
    # PROCESS PDF
    # ==================================================

    def process_pdf(
        self,
        file_path: str,
        document_id: str
    ) -> Dict:

        # 1. Extract text from PDF
        extracted = extract_text_from_pdf(
            file_path
        )

        pages = extracted["pages"]

        # 2. Split document into chunks
        chunks = chunk_document(
            pages=pages,
            chunk_size=500,
            overlap=60
        )

        if not chunks:
            raise ValueError(
                "No text chunks were created from the PDF."
            )

        # 3. Get chunk text
        texts = [
            chunk["text"]
            for chunk in chunks
        ]

        # 4. Generate embeddings
        embeddings = generate_embeddings(
            texts=texts,
            batch_size=self.batch_size
        )

        # 5. Create FAISS vector store
        vector_store = VectorStore(
            dimension=self.embedding_dimension
        )

        # 6. Add embeddings + chunks
        vector_store.add(
            embeddings=embeddings,
            chunks=chunks
        )

        # 7. Persist document
        self.document_store.save_document(
            document_id=document_id,
            vector_store=vector_store
        )

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
    ) -> VectorStore:

        return self.document_store.load_document(
            document_id
        )

    # ==================================================
    # SEMANTIC SEARCH
    # ==================================================

    def search(
        self,
        document_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:

        # Normalize the query
        normalized_query = normalize_query(
            query
        )

        # Convert query into an embedding
        query_embedding = generate_embedding(
            normalized_query
        )

        # Load only the requested document
        vector_store = self.load_document(
            document_id
        )

        # Search FAISS
        results = vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k
        )

        return results

    # ==================================================
    # KEYWORD SEARCH - BM25
    # ==================================================

    def keyword_search(
        self,
        document_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict]:

        # Load only the requested document
        vector_store = self.load_document(
            document_id
        )

        # Get chunks belonging to this document
        chunks = vector_store.chunks

        # Create BM25 retriever
        keyword_retriever = KeywordRetriever()

        # Build BM25 index from document chunks
        keyword_retriever.build_index(
            chunks
        )

        # Normalize the query
        normalized_query = normalize_query(
            query
        )

        # Perform keyword search
        results = keyword_retriever.search(
            query=normalized_query,
            top_k=top_k
        )

        return results

