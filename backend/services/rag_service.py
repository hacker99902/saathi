
from .rag_retriever import RAGRetriever
from .llm_service import (
    generate_answer_with_history,
    rewrite_question_for_retrieval,
)
from .chat_memory import ChatMemory
from .text_utils import normalize_query
from .hybrid_retriever import HybridRetriever


class RAGService:
    def __init__(self):
        self.retriever = RAGRetriever()

        self.chat_memory = ChatMemory(max_messages=10)

        self.hybrid_retriever = HybridRetriever(
            semantic_weight=0.70,
            keyword_weight=0.30,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.lower().split())

    def _remove_duplicate_sources(self, results):
        unique_results = []
        seen_texts = set()

        for result in results:
            text = result.get("text", "")

            if not isinstance(text, str) or not text.strip():
                continue

            normalized_text = self._normalize_text(text)

            if normalized_text in seen_texts:
                continue

            seen_texts.add(normalized_text)
            unique_results.append(result)

        return unique_results

    def _select_diverse_sources(self, results, max_sources=3):
        """
        Select the highest-ranked distinct text chunks.

        Note: this removes duplicate text but does not perform
        embedding-based maximal marginal relevance (MMR).
        """
        if not isinstance(max_sources, int) or max_sources < 1:
            raise ValueError("max_sources must be a positive integer.")

        ranked_results = sorted(
            results,
            key=lambda result: result.get("hybrid_score", 0.0),
            reverse=True,
        )

        return self._remove_duplicate_sources(ranked_results)[:max_sources]

    def ask(
        self,
        document_id: str,
        question: str,
        session_id: str,
        user_id: str,
        top_k: int = 5,
        similarity_threshold: float = 0.40,
    ):
        # 1. Validate request inputs.
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("Document ID cannot be empty.")

        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("User ID cannot be empty.")

        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question cannot be empty.")

        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("Session ID cannot be empty.")

        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or top_k < 1
        ):
            raise ValueError("top_k must be a positive integer.")

        if (
            not isinstance(similarity_threshold, (int, float))
            or isinstance(similarity_threshold, bool)
            or not 0.0 <= similarity_threshold <= 1.0
        ):
            raise ValueError(
                "similarity_threshold must be between 0 and 1."
            )

        document_id = document_id.strip()
        user_id = user_id.strip()
        question = question.strip()
        session_id = session_id.strip()

        # 2. Verify session ownership.
        session_matches_document = self.chat_memory.ensure_session(
            session_id=session_id,
            document_id=document_id,
            user_id=user_id,
        )

        if not session_matches_document:
            raise ValueError(
                "This chat session does not belong to this user "
                "or document. Please start a new chat session."
            )

        # 3. Get conversation history.
        history = self.chat_memory.get_history(
            session_id=session_id,
            document_id=document_id,
        )

        # 4. Rewrite follow-up questions for better retrieval.
        retrieval_query = rewrite_question_for_retrieval(
            question=question,
            history=history,
        )

        # 5. Normalize the query.
        normalized_query = normalize_query(retrieval_query)

        if not normalized_query:
            raise ValueError("Search query cannot be empty.")

        # 6. Load the document's vector store.
        vector_store = self.retriever.load_document(document_id)

        # 7. Retrieve semantic and keyword candidates.
        retrieval_top_k = max(top_k * 4, 20)

        semantic_candidates = vector_store.search(
            query=normalized_query,
            top_k=retrieval_top_k,
        )

        keyword_candidates = self.retriever.keyword_search(
            document_id=document_id,
            query=normalized_query,
            top_k=retrieval_top_k,
        )

        # 8. Combine candidates.
        candidates = self.hybrid_retriever.combine(
            semantic_results=semantic_candidates,
            keyword_results=keyword_candidates,
            top_k=retrieval_top_k,
        )

        # 9. Filter semantic and keyword-only results separately.
        #
        # The hybrid score for a keyword-only candidate is bounded
        # by the keyword weight (0.30), so applying a 0.40 threshold
        # to every candidate would eliminate all keyword-only matches.
        semantic_threshold = 0.25
        keyword_threshold = min(
            float(similarity_threshold),
            self.hybrid_retriever.keyword_weight * 0.5,
        )

        filtered_candidates = []

        for result in candidates:
            hybrid_score = result.get("hybrid_score", 0.0)
            semantic_score = result.get("semantic_score", 0.0)
            keyword_score = result.get("keyword_score", 0.0)

            has_semantic_match = (
                semantic_score >= semantic_threshold
                and hybrid_score >= similarity_threshold
            )

            has_keyword_match = (
                keyword_score > 0.0
                and hybrid_score >= keyword_threshold
            )

            if has_semantic_match or has_keyword_match:
                filtered_candidates.append(result)

        candidates = self._remove_duplicate_sources(
            filtered_candidates
        )

        # 10. Record the user's question before generating the answer.
        self.chat_memory.add_message(
            session_id=session_id,
            role="user",
            content=question,
        )

        # Keep the history passed to the model as the prior history.
        # The current question is already supplied separately.
        if not candidates:
            answer = (
                "I couldn't find enough relevant information "
                "in the document to answer that question."
            )

            self.chat_memory.add_message(
                session_id=session_id,
                role="assistant",
                content=answer,
            )

            return {
                "document_id": document_id,
                "question": question,
                "answer": answer,
                "sources": [],
            }

        # 11. Select top sources.
        selected_sources = self._select_diverse_sources(
            candidates,
            max_sources=min(top_k, 3),
        )

        # 12. Build context and source metadata.
        context_parts = []
        sources = []

        for source_id, result in enumerate(selected_sources, start=1):
            page_number = result.get(
                "page_number",
                result.get("page", 1),
            )
            text = result["text"]

            context_parts.append(
                f"[Source {source_id}] Page {page_number}\n{text}"
            )

            sources.append({
                "source_id": source_id,
                "page_number": page_number,
                "similarity_score": round(
                    result.get("semantic_score", 0.0), 4
                ),
                "keyword_score": round(
                    result.get("keyword_score", 0.0), 4
                ),
                "hybrid_score": round(
                    result.get("hybrid_score", 0.0), 4
                ),
                "text": text,
            })

        context = "\n\n".join(context_parts)

        # 13. Generate the document-grounded answer.
        try:
            answer = generate_answer_with_history(
                question=question,
                context=context,
                history=history,
            )
        except Exception:
            # Preserve the user's message in history but do not store
            # a fabricated answer when the provider request fails.
            raise

        # 14. Store the assistant response.
        self.chat_memory.add_message(
            session_id=session_id,
            role="assistant",
            content=answer,
        )

        # 15. Keep the established response structure.
        return {
            "document_id": document_id,
            "question": question,
            "answer": answer,
            "sources": sources,
        }


# Shared instance used by main.py and document_history.py
rag_service = RAGService()
