
from typing import Dict, List, Optional

from backend.services.supabase_client import supabase


class DocumentMetadataStore:
    TABLE_NAME = "documents"

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{field_name} must be a non-empty string."
            )

    def save(self, metadata: Dict) -> Dict:
        """Insert document metadata without overwriting ownership."""
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary.")

        document_id = metadata.get("document_id")
        user_id = metadata.get("user_id")

        self._validate_id(document_id, "document_id")
        self._validate_id(user_id, "user_id")

        result = (
            supabase.table(self.TABLE_NAME)
            .insert(metadata)
            .execute()
        )

        return result.data[0] if result.data else metadata

    def get(
        self,
        document_id: str,
        user_id: str,
    ) -> Optional[Dict]:
        """Retrieve a document only if it belongs to this user."""
        self._validate_id(document_id, "document_id")
        self._validate_id(user_id, "user_id")

        result = (
            supabase.table(self.TABLE_NAME)
            .select("*")
            .eq("document_id", document_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        return result.data[0] if result.data else None

    def exists(self, document_id: str) -> bool:
        """Check whether a document ID is already registered."""
        self._validate_id(document_id, "document_id")

        result = (
            supabase.table(self.TABLE_NAME)
            .select("document_id")
            .eq("document_id", document_id)
            .limit(1)
            .execute()
        )

        return bool(result.data)

    def get_all(self, user_id: str) -> List[Dict]:
        """List only the documents owned by this user."""
        self._validate_id(user_id, "user_id")

        result = (
            supabase.table(self.TABLE_NAME)
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return result.data or []

    def delete(
        self,
        document_id: str,
        user_id: str,
    ) -> None:
        """Delete metadata only for the specified owner's document."""
        self._validate_id(document_id, "document_id")
        self._validate_id(user_id, "user_id")

        (
            supabase.table(self.TABLE_NAME)
            .delete()
            .eq("document_id", document_id)
            .eq("user_id", user_id)
            .execute()
        )
# Shared metadata store used by routes and services
metadata_store = DocumentMetadataStore()