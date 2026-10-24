
from io import BytesIO

from pypdf import PdfReader
from fastapi import HTTPException

from backend.services.supabase_client import supabase
from backend.services.document_metadata import DocumentMetadataStore

metadata_store = DocumentMetadataStore()
BUCKET_NAME = "saathi-documents"


def get_document_text(document_id: str, user_id: str):
    metadata = metadata_store.get(document_id, user_id)

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="Document metadata not found."
        )

    storage_path = metadata.get("storage_path")
    storage_bucket = metadata.get("storage_bucket", BUCKET_NAME)

    if not storage_path:
        raise HTTPException(
            status_code=404,
            detail="This document has not been migrated to cloud storage."
        )

    try:
        pdf_bytes = (
            supabase.storage
            .from_(storage_bucket)
            .download(storage_path)
        )

        reader = PdfReader(BytesIO(pdf_bytes))
        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve or read the stored PDF."
        ) from exc

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in this PDF."
        )

    return text, metadata
