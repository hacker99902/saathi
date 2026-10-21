import os
import uuid
from typing import Dict, List

from qdrant_client import QdrantClient, models


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "saathi_documents"
VECTOR_SIZE = 384

_client = None


def get_qdrant_client() -> QdrantClient:
    """Create a Qdrant Cloud client."""
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
    """Qdrant Cloud storage with hosted MiniLM inference."""

    def __init__(self, document_id: str):
        self.document_id = document_id
        self.client = get_qdrant_client()
        self._ensure_collection()

    def _ensure_collection(self):
        if not self.client.collection_exists(COLLECTION_NAME):
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
            )

        self.client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="document_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )

    def add(self, chunks: List[Dict]):
        """Store text chunks; Qdrant generates their embeddings."""
        if not chunks:
            return

        points = []

        for chunk in chunks:
            text = chunk.get("text", "").strip()
            if not text:
                continue

            chunk_id = str(
                chunk.get("chunk_id") or uuid.uuid4()
            )

            points.append(
                models.PointStruct(
                    id=str(uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{self.document_id}:{chunk_id}",
                    )),
                    vector=models.Document(
                        text=text,
                        model=MODEL_NAME,
                    ),
                    payload={
                        **chunk,
                        "document_id": self.document_id,
                        "chunk_id": chunk_id,
                    },
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
        """Search a document using hosted query inference."""
        if not query or not query.strip():
            return []

        results = self.client.query_points(
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

        for point in results.points:
            payload = dict(point.payload or {})
            payload["similarity_score"] = float(point.score)
            matches.append(payload)

        return matches

    def count(self) -> int:
        result = self.client.count(
            collection_name=COLLECTION_NAME,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(
                            value=self.document_id
                        ),
                    )
                ]
            ),
            exact=True,
        )
        return result.count

    @property
    def chunks(self) -> List[Dict]:
        """Load all stored chunks for BM25 retrieval."""
        response = self.client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(
                            value=self.document_id
                        ),
                    )
                ]
            ),
            limit=100,
            with_payload=True,
            with_vectors=False,
        )

        chunks = []

        while True:
            points, next_offset = response
            chunks.extend(
                dict(point.payload or {}) for point in points
            )

            if next_offset is None:
                break

            response = self.client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=self.document_id
                            ),
                        )
                    ]
                ),
                offset=next_offset,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )

        return chunks

    def delete(self):
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=self.document_id
                            ),
                        )
                    ]
                )
            ),
            wait=True,
        )