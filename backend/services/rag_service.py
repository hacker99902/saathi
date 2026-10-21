
import numpy as np

from .rag_retriever import RAGRetriever

from .llm_service import (
    generate_answer_with_history,
    rewrite_question_for_retrieval
)

from .chat_memory import ChatMemory

from .text_utils import normalize_query

from .hybrid_retriever import HybridRetriever


class RAGService:

    def __init__(self):

        # Retriever used for document processing
        self.retriever = RAGRetriever()

        # Conversation memory
        self.chat_memory = ChatMemory(
            max_messages=10
        )

        # Hybrid semantic + keyword retriever
        self.hybrid_retriever = HybridRetriever(
            semantic_weight=0.70,
            keyword_weight=0.30
        )

    # ==================================================
    # Remove exact duplicate chunks
    # ==================================================

    def _remove_duplicate_sources(
        self,
        results
    ):

        unique_results = []

        seen_texts = set()

        for result in results:

            text = result["text"].strip()

            normalized_text = " ".join(
                text.lower().split()
            )

            if normalized_text in seen_texts:
                continue

            seen_texts.add(
                normalized_text
            )

            unique_results.append(
                result
            )

        return unique_results

    # ==================================================
    # Cosine similarity
    # ==================================================

    def _cosine_similarity(
        self,
        embedding_a,
        embedding_b
    ):

        vector_a = np.array(
            embedding_a,
            dtype=np.float32
        )

        vector_b = np.array(
            embedding_b,
            dtype=np.float32
        )

        denominator = (
            np.linalg.norm(vector_a)
            *
            np.linalg.norm(vector_b)
        )

        if denominator == 0:
            return 0.0

        return float(
            np.dot(
                vector_a,
                vector_b
            )
            /
            denominator
        )

    # ==================================================
    # MMR source selection
    # ==================================================



    def _select_diverse_sources(
    self,
    results,
    max_sources=3,
    diversity_lambda=0.70
):
        """Select the highest-ranked sources without local embeddings."""
        if not results:
            return []

        def relevance_score(result):
            if "hybrid_score" in result:
                return result["hybrid_score"]
            return result.get("similarity_score", 0.0)

        ranked_results = sorted(
            results,
            key=relevance_score,
            reverse=True
        )

        selected = []
        seen_texts = set()

        for result in ranked_results:
            normalized_text = " ".join(
                result["text"].lower().split()
            )

            if normalized_text in seen_texts:
                continue

            seen_texts.add(normalized_text)
            selected.append(result)

            if len(selected) >= max_sources:
                break

        return selected



    # ==================================================
    # Ask question
    # ==================================================

    def ask(
        self,
        document_id: str,
        question: str,
        session_id: str,
        top_k: int = 5,
        similarity_threshold: float = 0.50
    ):

        # ----------------------------------------------
        # Validate question
        # ----------------------------------------------

        if not question or not question.strip():

            raise ValueError(
                "Question cannot be empty."
            )

        # ----------------------------------------------
        # Validate session
        # ----------------------------------------------

        if not session_id or not session_id.strip():

            raise ValueError(
                "Session ID cannot be empty."
            )

        # ----------------------------------------------
        # 1. Phase 9H:
        #    Bind session to document
        # ----------------------------------------------

        session_matches_document = (
            self.chat_memory.ensure_session(
                session_id=session_id,
                document_id=document_id
            )
        )

        if not session_matches_document:

            raise ValueError(
                "This chat session belongs to a "
                "different document. Please start "
                "a new chat session for this document."
            )

        # ----------------------------------------------
        # 2. Get conversation history
        # ----------------------------------------------

        history = self.chat_memory.get_history(
            session_id=session_id,
            document_id=document_id
        )

        print("\n--- CHAT HISTORY DEBUG ---")
        print("Session ID:", session_id)
        print("Document ID:", document_id)
        print("History:", history)
        print("--------------------------")

        # ----------------------------------------------
        # 3. Phase 9F:
        #    Rewrite follow-up question
        #    into standalone retrieval query
        # ----------------------------------------------

        retrieval_query = (
            rewrite_question_for_retrieval(
                question=question,
                history=history
            )
        )

        print(
            "\n========================================"
        )

        print(
            "PHASE 9F + 9I - HISTORY AWARE "
            "HYBRID RETRIEVAL"
        )

        print(
            "========================================"
        )

        print(
            "\nOriginal question:"
        )

        print(question)

        print(
            "\nRetrieval query:"
        )

        print(retrieval_query)

        # ----------------------------------------------
        # 4. Normalize retrieval query
        # ----------------------------------------------

        normalized_query = normalize_query(
            retrieval_query
        )

        # ----------------------------------------------
        # 5. Load document-specific vector store
        # ----------------------------------------------

        vector_store = self.retriever.load_document(
            document_id
        )
        print("\n--- STORED CHUNK ID CHECK ---")

        chunk_ids = [
            chunk.get("chunk_id")
            for chunk in vector_store.chunks
        ]

        print("Total chunks:", len(chunk_ids))
        print("Unique chunk IDs:", len(set(chunk_ids)))
        print("Missing chunk IDs:", chunk_ids.count(None))

        print("-----------------------------")
        # ----------------------------------------------
        # 6. Semantic search using Qdrant hosted inference
        # ----------------------------------------------

        retrieval_top_k = max(top_k * 4, 20)

        semantic_candidates = vector_store.search(
            query=normalized_query,
            top_k=retrieval_top_k
        )

        print("\nQdrant semantic candidates:")

        for candidate in semantic_candidates:
            print(
                f"Page {candidate['page_number']} "
                f"| Semantic Score: "
                f"{candidate['similarity_score']:.4f}"
            )

        # ----------------------------------------------
        # 8. Keyword search - BM25
        # ----------------------------------------------

        keyword_candidates = self.retriever.keyword_search(
            document_id=document_id,
            query=normalized_query,
            top_k=retrieval_top_k
        )

        print("\nBM25 keyword candidates:")

        for candidate in keyword_candidates:
            print(
                f"Page {candidate['page_number']} "
                f"| Keyword Score: "
                f"{candidate['keyword_score']:.4f}"
            )

                # ----------------------------------------------
        # 9. Hybrid ranking
        # ----------------------------------------------

        candidates = self.hybrid_retriever.combine(
            semantic_results=semantic_candidates,
            keyword_results=keyword_candidates,
            top_k=retrieval_top_k
        )

        print("\nHybrid candidates:")

        for candidate in candidates:
            print(
                f"Page {candidate['page_number']} "
                f"| Semantic: "
                f"{candidate.get('semantic_score', 0.0):.4f} "
                f"| Keyword: "
                f"{candidate.get('keyword_score', 0.0):.4f} "
                f"| Hybrid: "
                f"{candidate['hybrid_score']:.4f}"
            )

        # ----------------------------------------------
        # 10. Hybrid threshold + semantic relevance check
        # ----------------------------------------------

        hybrid_threshold = 0.40
        semantic_threshold = 0.25

        candidates = [
            result
            for result in candidates
            if (
                result["hybrid_score"] >= hybrid_threshold
                and result.get("semantic_score", 0.0)
                >= semantic_threshold
            )
        ]

        print(
            f"\nCandidates after filtering "
            f"(hybrid >= {hybrid_threshold}, "
            f"semantic >= {semantic_threshold}): "
            f"{len(candidates)}"
        )

        # ----------------------------------------------
        # No relevant information
        # ----------------------------------------------

        if not candidates:

            return {
                "document_id": document_id,
                "question": question,
                "answer": (
                    "I couldn't find enough relevant "
                    "information in the document "
                    "to answer that question."
                ),
                "sources": []
            }

        # ----------------------------------------------
        # 11. Remove exact duplicates
        # ----------------------------------------------

        candidates = (
            self._remove_duplicate_sources(
                candidates
            )
        )

        print(
            "\nCandidates after duplicate removal: "
            f"{len(candidates)}"
        )

        # ----------------------------------------------
        # 12. MMR diversity selection
        # ----------------------------------------------

        selected_sources = (
            self._select_diverse_sources(
                candidates,
                max_sources=3
            )
        )

        print(
            "\nSelected sources:"
        )

        for source in selected_sources:

            print(
                f"Page {source['page_number']} "
                f"| Hybrid Score: "
                f"{source['hybrid_score']:.4f}"
            )

        # ----------------------------------------------
        # 13. Build context
        # ----------------------------------------------

        context_parts = []

        sources = []

        for source_id, result in enumerate(
            selected_sources,
            start=1
        ):

            context_parts.append(
                f"[Source {source_id}] "
                f"Page {result['page_number']} "
                f"Hybrid Score: "
                f"{result['hybrid_score']:.4f}\n"
                f"{result['text']}"
            )

            sources.append({

                "source_id": source_id,

                "page_number": (
                    result["page_number"]
                ),

                # Keep the old field so the
                # frontend does not break.
                "similarity_score": round(
                    result.get(
                        "semantic_score",
                        0.0
                    ),
                    4
                ),

                # New Phase 9I fields
                "keyword_score": round(
                    result.get(
                        "keyword_score",
                        0.0
                    ),
                    4
                ),

                "hybrid_score": round(
                    result.get(
                        "hybrid_score",
                        0.0
                    ),
                    4
                ),

                "text": result["text"]
            })

        context = "\n\n".join(
            context_parts
        )

        # ----------------------------------------------
        # 14. Print context for debugging
        # ----------------------------------------------

        print(
            "\nContext sent to LLM:"
        )

        print(
            "----------------------------------------"
        )

        print(context)

        print(
            "----------------------------------------"
        )

        # ----------------------------------------------
        # 15. Generate final answer
        # ----------------------------------------------

        answer = generate_answer_with_history(
            question=question,
            context=context,
            history=history
        )

        # ----------------------------------------------
        # 16. Save user message
        # ----------------------------------------------

        self.chat_memory.add_message(
            session_id=session_id,
            role="user",
            content=question
        )

        # ----------------------------------------------
        # 17. Save assistant answer
        # ----------------------------------------------

        self.chat_memory.add_message(
            session_id=session_id,
            role="assistant",
            content=answer
        )

        # ----------------------------------------------
        # 18. Return response
        # ----------------------------------------------

        return {
            "document_id": document_id,
            "question": question,
            "answer": answer,
            "sources": sources
        }
