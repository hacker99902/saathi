from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader

from backend.services.llm_service import client, MODEL_NAME
from backend.services.document_metadata import DocumentMetadataStore

router = APIRouter()
metadata_store = DocumentMetadataStore()
UPLOAD_DIR = Path("backend/uploads")


class PodcastRequest(BaseModel):
    docId: str


@router.post("/podcast")
def create_podcast(request: PodcastRequest):
    metadata = metadata_store.get(request.docId)
    if not metadata:
        raise HTTPException(status_code=404, detail="Document not found")

    stored_filename = metadata.get("stored_filename", "")
    if not stored_filename or Path(stored_filename).name != stored_filename:
        raise HTTPException(status_code=404, detail="Stored PDF not found")

    file_path = UPLOAD_DIR / stored_filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored PDF not found")

    try:
        reader = PdfReader(str(file_path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not text.strip():
            raise HTTPException(status_code=422, detail="No extractable text found in this PDF")

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Create a natural educational podcast script in which Maya, "
                        "a patient teacher, helps Alex, a student, understand the document. "
                        "Use clear explanations, examples grounded in the document, and "
                        "natural dialogue. Do not invent facts or add unrelated concepts. "
                        "Return the script as plain text."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Create an educational podcast based on this document. "
                        f"Document name: {metadata.get('filename', 'Document')}\n\n"
                        f"{text[:10000]}"
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=3500,
        )
        podcast = response.choices[0].message.content or ""
        return {
            "podcast": podcast,
            "docName": metadata.get("filename", "Document"),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
