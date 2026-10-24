
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services.auth_dependencies import get_current_user
from backend.services.cloud_document_service import get_document_text
from backend.services.groq_service import podcast as generate_podcast

router = APIRouter()


class PodcastRequest(BaseModel):
    docId: str


@router.post("/podcast")
async def create_podcast(
    request: PodcastRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])

    try:
        text, metadata = get_document_text(request.docId, user_id)

        doc_name = metadata.get("filename", "Document")

        script = await generate_podcast(
            text=text,
            name=doc_name,
        )

        return {
            "podcast": script,
            "docName": doc_name,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Podcast generation failed. Please try again.",
        ) from exc
