
import json
from pathlib import Path

from backend.services.supabase_client import supabase

METADATA_DIR = Path("backend/data/documents")
UPLOAD_DIR = Path("backend/uploads")
BUCKET = "saathi-documents"

# Migrate only documents whose PDF identity has been verified.
VERIFIED_IDS = {
    "6d6a7b00-5ba7-4e0d-942f-da9a62c48a77",
}


def upload_or_reuse_pdf(storage_path: str, pdf_bytes: bytes) -> bool:
    """Upload a PDF, or reuse it if the object already exists."""
    try:
        supabase.storage.from_(BUCKET).upload(
            path=storage_path,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf"},
        )
        print(f"UPLOADED PDF: {storage_path}")
        return True

    except Exception as exc:
        error_text = str(exc).lower()

        if (
            "duplicate" in error_text
            or "already exists" in error_text
            or "409" in error_text
        ):
            print(f"PDF already exists; reusing: {storage_path}")
            return True

        print(f"UPLOAD FAILED: {storage_path}: {exc}")
        return False


def migrate_document(metadata_file: Path) -> None:
    with open(metadata_file, "r", encoding="utf-8") as file:
        metadata = json.load(file)

    document_id = metadata.get("document_id")

    if document_id not in VERIFIED_IDS:
        print(f"SKIP {document_id}: not verified for migration yet")
        return

    if not metadata.get("filename"):
        print(f"SKIP {document_id}: filename missing")
        return

    # Use only the ID-matched PDF for this verified migration.
    pdf_path = UPLOAD_DIR / f"{document_id}.pdf"

    if not pdf_path.is_file():
        print(f"SKIP {document_id}: PDF not found at {pdf_path}")
        return

    storage_path = f"{document_id}.pdf"

    with open(pdf_path, "rb") as file:
        pdf_bytes = file.read()

    if not upload_or_reuse_pdf(storage_path, pdf_bytes):
        return

    record = {
        "document_id": document_id,
        "filename": metadata["filename"],
        "stored_filename": f"{document_id}.pdf",
        "storage_bucket": BUCKET,
        "storage_path": storage_path,
        "page_count": metadata.get("page_count", 0),
        "chunk_count": metadata.get("chunk_count", 0),
        "vector_count": metadata.get("vector_count", 0),
    }

    # This requires INSERT/UPDATE privileges for the configured database role.
    result = (
        supabase.table("documents")
        .upsert(record, on_conflict="document_id")
        .execute()
    )

    if result.data:
        print(f"MIGRATED: {document_id}")
    else:
        print(f"WARNING: No metadata row returned for {document_id}")


def main():
    if not METADATA_DIR.is_dir():
        print(f"Metadata directory not found: {METADATA_DIR}")
        return

    for metadata_file in sorted(METADATA_DIR.glob("*.json")):
        try:
            migrate_document(metadata_file)
        except Exception as exc:
            print(f"ERROR in {metadata_file.name}: {exc}")

    print("Migration attempt finished. Review the output above.")


if __name__ == "__main__":
    main()
