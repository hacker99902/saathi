from fastapi import APIRouter, HTTPException
from pydantic import BaseModel  
from backend.services.llm_service import client, MODEL_NAME
from backend.services.cloud_document_service import get_document_text

router = APIRouter()


class PodcastRequest(BaseModel):
    docId: str


@router.post("/podcast")
def create_podcast(request: PodcastRequest):
    text, metadata = get_document_text(request.docId)

    try:
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
                        "Create an educational podcast based on this document. "
                        f"Document name: {metadata.get('filename', 'Document')}\n\n"
                        f"{text[:10000]}"
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=3500,
        )

        podcast = response.choices[0].message.content or ""

        if not podcast.strip():
            raise HTTPException(
                status_code=502,
                detail="The AI returned an empty podcast script."
            )

        return {
            "podcast": podcast,
            "docName": metadata.get("filename", "Document"),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Podcast generation failed."
        ) from exc
