from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.cloud_document_service import get_document_text
from backend.services.groq_service import podcast as generate_podcast

router = APIRouter()


class PodcastRequest(BaseModel):
    docId: str


@router.post("/podcast")
async def create_podcast(request: PodcastRequest):
    try:
        text, metadata = get_document_text(request.docId)

        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="The document contains no readable text."
            )

        doc_name = metadata.get("filename", "Document")

        script = await generate_podcast(
            text=text,
            name=doc_name
        )

        if not script or not script.strip():
            raise HTTPException(
                status_code=502,
                detail="The AI returned an empty podcast script."
            )

        # Keep the response compatible with the existing frontend.
        return {
            "podcast": script,
            "docName": doc_name
        }

    except HTTPException:
        raise

    except Exception as exc:
        print(f"Podcast generation failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Podcast generation failed."
        ) from exc