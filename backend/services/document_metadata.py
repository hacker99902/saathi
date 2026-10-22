
from typing import Dict, List, Optional

from backend.services.supabase_client import supabase


class DocumentMetadataStore:
    TABLE_NAME = "documents"

    def save(self, metadata: Dict):
        if "document_id" not in metadata:
            raise ValueError("document_id is required.")

        result = (
            supabase.table(self.TABLE_NAME)
            .upsert(metadata, on_conflict="document_id")
            .execute()
        )
        return result.data[0] if result.data else metadata

    def get(self, document_id: str) -> Optional[Dict]:
        result = (
            supabase.table(self.TABLE_NAME)
            .select("*")
            .eq("document_id", document_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def exists(self, document_id: str) -> bool:
        return self.get(document_id) is not None

    def get_all(self) -> List[Dict]:
        result = (
            supabase.table(self.TABLE_NAME)
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    def delete(self, document_id: str):
        (
            supabase.table(self.TABLE_NAME)
            .delete()
            .eq("document_id", document_id)
            .execute()
        )
