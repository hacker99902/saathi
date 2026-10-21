import json
from pathlib import Path
from typing import Dict, List, Optional


class DocumentMetadataStore:

    def __init__(
        self,
        base_directory: str = "backend/data/documents"
    ):
        self.base_directory = Path(base_directory)

        self.base_directory.mkdir(
            parents=True,
            exist_ok=True
        )

    # --------------------------------------------------
    # Get metadata file path
    # --------------------------------------------------

    def get_metadata_path(
        self,
        document_id: str
    ) -> Path:

        return (
            self.base_directory
            / f"{document_id}.json"
        )

    # --------------------------------------------------
    # Save metadata
    # --------------------------------------------------

    def save(
        self,
        metadata: Dict
    ):

        if "document_id" not in metadata:
            raise ValueError(
                "document_id is required."
            )

        document_id = metadata["document_id"]

        metadata_path = self.get_metadata_path(
            document_id
        )

        with open(
            metadata_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                metadata,
                file,
                ensure_ascii=False,
                indent=2
            )

    # --------------------------------------------------
    # Load metadata
    # --------------------------------------------------

    def get(
        self,
        document_id: str
    ) -> Optional[Dict]:

        metadata_path = self.get_metadata_path(
            document_id
        )

        if not metadata_path.exists():
            return None

        with open(
            metadata_path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    # --------------------------------------------------
    # Check document exists
    # --------------------------------------------------

    def exists(
        self,
        document_id: str
    ) -> bool:

        return self.get_metadata_path(
            document_id
        ).exists()

    # --------------------------------------------------
    # Get all documents
    # --------------------------------------------------

    def get_all(self) -> List[Dict]:

        documents = []

        for metadata_file in self.base_directory.glob(
            "*.json"
        ):

            with open(
                metadata_file,
                "r",
                encoding="utf-8"
            ) as file:

                documents.append(
                    json.load(file)
                )

        return documents

    # --------------------------------------------------
    # Delete document metadata
    # --------------------------------------------------

    def delete(
        self,
        document_id: str
    ):

        metadata_path = self.get_metadata_path(
            document_id
        )

        if metadata_path.exists():
            metadata_path.unlink()