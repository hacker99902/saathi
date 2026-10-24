
import os
import uuid
import math
from typing import Dict, List

from qdrant_client import QdrantClient, models


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "saathi_documents"
VECTOR_SIZE = 384

_client = None


def get_qdrant_client() -> QdrantClient:
    """Create and reuse the Qdrant Cloud client."""
    global _client

    if _client is None:
        url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")

        if not url or not api_key:
            raise RuntimeError(
                "QDRANT_URL and QDRANT_API_KEY must be configured."
            )

        _client = QdrantClient(
            url=url,
            api_key=api_key,
            cloud_inference=True,
            timeout=60,
        )

    return _client


class QdrantVectorStore:
    """Store and retrieve document chunks using Qdrant Cloud inference."""

    def __init__(self, document_id: str):
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id cannot be empty.")

        self.document_id = document_id.strip()
        self.client = get_qdrant_client()
        self._ensure_collection()

    def _ensure_collection(self):
        """Create the collection and required payload index if necessary."""
        if not self.client.collection_exists(COLLECTION_NAME):
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
            )

        collection_info = self.client.get_collection(
            collection_name=COLLECTION_NAME
        )

        payload_schema = collection_info.payload_schema or {}

        if "document_id" not in payload_schema:
            self.client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="document_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )

    @staticmethod
    def _validate_top_k(top_k: int) -> int:
        if (
            not isinstance(top_k, int)
            or isinstance(top_k, bool)
            or top_k < 1
        ):
            raise ValueError("top_k must be a positive integer.")

        return top_k

    def add(self, chunks: List[Dict]):
        """Store chunks with deterministic point IDs and hosted embeddings."""
        if not isinstance(chunks, list):
            raise ValueError("chunks must be a list.")

        points = []

        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue

            text = chunk.get("text")

            if not isinstance(text, str) or not text.strip():
                continue

            chunk_id = str(
                chunk.get("chunk_id") or uuid.uuid4()
            )

            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{self.document_id}:{chunk_id}",
                )
            )

            payload = {
                **chunk,
                "text": text.strip(),
                "document_id": self.document_id,
                "chunk_id": chunk_id,
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=models.Document(
                        text=text.strip(),
                        model=MODEL_NAME,
                    ),
                    payload=payload,
                )
            )

        if points:
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True,
            )

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict]:
        """Search only the current document using hosted inference."""
        if not isinstance(query, str) or not query.strip():
            return []

        top_k = self._validate_top_k(top_k)

        response = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=models.Document(
                text=query.strip(),
                model=MODEL_NAME,
            ),
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(
                            value=self.document_id
                        ),
                    )
                ]
            ),
            limit=top_k,
            with_payload=True,
        )

        matches = []

        for point in response.points:
            payload = dict(point.payload or {})

            score = float(point.score)

            if not math.isfinite(score):
                continue

            payload["similarity_score"] = score
            matches.append(payload)

        return matches

    def count(self) -> int:
        """Count vectors belonging to this document."""
        result = self.client.count(
            collection_name=COLLECTION_NAME,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(
                            value=self.document_id,
                        ),
                    )
                ]
            ),
            exact=True,
        )

        return result.count

    @property
    def chunks(self) -> List[Dict]:
        """Retrieve every stored chunk for BM25 indexing."""
        scroll_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(
                        value=self.document_id,
                    ),
                )
            ]
        )

        chunks = []
        offset = None

        while True:
            response = self.client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=scroll_filter,
                offset=offset,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )

            points, next_offset = response

            for point in points:
                payload = dict(point.payload or {})

                # Ignore malformed records that cannot be indexed.
                if not isinstance(payload.get("text"), str):
                    continue

                if not payload["text"].strip():
                    continue

                if not payload.get("chunk_id"):
                    continue

                chunks.append(payload)

            if next_offset is None:
                break

            offset = next_offset

        return chunks

    def delete(self):
        """Delete only vectors belonging to this document."""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=self.document_id,
                            ),
                        )
                    ]
                )
            ),
            wait=True,
        )
