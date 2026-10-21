import json
from pathlib import Path
from typing import List, Dict

import faiss
import numpy as np


class VectorStore:

    def __init__(self, dimension: int = 384):

        self.dimension = dimension

        # FAISS Inner Product index.
        #
        # Because our Sentence Transformer embeddings
        # are normalized, Inner Product behaves like
        # cosine similarity.
        self.index = faiss.IndexFlatIP(dimension)

        # Store chunk metadata separately.
        self.chunks = []


    # --------------------------------------------------
    # Add vectors
    # --------------------------------------------------

    def add(
        self,
        embeddings: List[List[float]],
        chunks: List[Dict]
    ):

        if not embeddings:
            return

        if len(embeddings) != len(chunks):
            raise ValueError(
                "Number of embeddings must match "
                "number of chunks."
            )

        vectors = np.array(
            embeddings,
            dtype=np.float32
        )

        if vectors.shape[1] != self.dimension:
            raise ValueError(
                f"Expected embedding dimension "
                f"{self.dimension}, got "
                f"{vectors.shape[1]}."
            )

        self.index.add(vectors)

        self.chunks.extend(chunks)


    # --------------------------------------------------
    # Search
    # --------------------------------------------------

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Dict]:

        if self.index.ntotal == 0:
            return []

        query_vector = np.array(
            [query_embedding],
            dtype=np.float32
        )

        k = min(
            top_k,
            self.index.ntotal
        )

        scores, indices = self.index.search(
            query_vector,
            k
        )

        results = []

        for score, index in zip(
            scores[0],
            indices[0]
        ):

            if index == -1:
                continue

            result = self.chunks[index].copy()

            result["similarity_score"] = float(
                score
            )

            results.append(result)

        return results


    # --------------------------------------------------
    # Save
    # --------------------------------------------------

    def save(
        self,
        index_path: str,
        chunks_path: str
    ):

        index_path = Path(index_path)
        chunks_path = Path(chunks_path)

        index_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        chunks_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # Save FAISS index
        faiss.write_index(
            self.index,
            str(index_path)
        )

        # Save chunk metadata
        with open(
            chunks_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                self.chunks,
                file,
                ensure_ascii=False,
                indent=2
            )


    # --------------------------------------------------
    # Load
    # --------------------------------------------------

    @classmethod
    def load(
        cls,
        index_path: str,
        chunks_path: str,
        dimension: int = 384
    ):

        index_path = Path(index_path)
        chunks_path = Path(chunks_path)

        if not index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found: {index_path}"
            )

        if not chunks_path.exists():
            raise FileNotFoundError(
                f"Chunks file not found: {chunks_path}"
            )

        store = cls(
            dimension=dimension
        )

        # Load FAISS index
        store.index = faiss.read_index(
            str(index_path)
        )

        # Load chunks
        with open(
            chunks_path,
            "r",
            encoding="utf-8"
        ) as file:

            store.chunks = json.load(file)

        # ----------------------------------------------
        # Safety checks
        # ----------------------------------------------

        if store.index.ntotal != len(
            store.chunks
        ):
            raise ValueError(
                "FAISS vector count does not match "
                "chunk count."
            )

        if store.index.d != dimension:
            raise ValueError(
                f"FAISS dimension mismatch. "
                f"Expected {dimension}, "
                f"got {store.index.d}."
            )

        return store


    # --------------------------------------------------
    # Count
    # --------------------------------------------------

    def count(self) -> int:
        return self.index.ntotal