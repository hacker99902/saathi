from pathlib import Path

from .vector_store import VectorStore


class DocumentStore:

    def __init__(
        self,
        base_directory: str = "backend/data/vector_store"
    ):
        self.base_directory = Path(
            base_directory
        )

        self.base_directory.mkdir(
            parents=True,
            exist_ok=True
        )


    # --------------------------------------------------
    # Get document directory
    # --------------------------------------------------

    def get_document_directory(
        self,
        document_id: str
    ) -> Path:

        document_directory = (
            self.base_directory / document_id
        )

        document_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        return document_directory


    # --------------------------------------------------
    # Get document file paths
    # --------------------------------------------------

    def get_paths(
        self,
        document_id: str
    ):

        document_directory = (
            self.get_document_directory(
                document_id
            )
        )

        index_path = (
            document_directory / "index.faiss"
        )

        metadata_path = (
            document_directory / "chunks.json"
        )

        return index_path, metadata_path


    # --------------------------------------------------
    # Save document
    # --------------------------------------------------

    def save_document(
        self,
        document_id: str,
        vector_store: VectorStore
    ):

        index_path, metadata_path = (
            self.get_paths(document_id)
        )

        vector_store.save(
            str(index_path),
            str(metadata_path)
        )


    # --------------------------------------------------
    # Load document
    # --------------------------------------------------

    def load_document(
        self,
        document_id: str,
        dimension: int = 384
    ) -> VectorStore:

        index_path, metadata_path = (
            self.get_paths(document_id)
        )

        # ----------------------------------------------
        # Check that the persisted files exist
        # ----------------------------------------------

        if not index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found for document: "
                f"{document_id}"
            )

        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Chunk metadata not found for document: "
                f"{document_id}"
            )


        # ----------------------------------------------
        # IMPORTANT:
        #
        # VectorStore.load() is a classmethod.
        # It returns the loaded VectorStore.
        #
        # We MUST return that object.
        # ----------------------------------------------

        vector_store = VectorStore.load(
            str(index_path),
            str(metadata_path),
            dimension=dimension
        )

        return vector_store


    # --------------------------------------------------
    # Check document existence
    # --------------------------------------------------

    def document_exists(
        self,
        document_id: str
    ) -> bool:

        document_directory = (
            self.base_directory / document_id
        )

        index_path = (
            document_directory / "index.faiss"
        )

        metadata_path = (
            document_directory / "chunks.json"
        )

        return (
            index_path.exists()
            and metadata_path.exists()
        )


    # --------------------------------------------------
    # Delete document
    # --------------------------------------------------

    def delete_document(
        self,
        document_id: str
    ):

        import shutil

        document_directory = (
            self.base_directory / document_id
        )

        if document_directory.exists():

            shutil.rmtree(
                document_directory
            )
