from fastapi import APIRouter, HTTPException

from backend.services.document_metadata import DocumentMetadataStore
from backend.services.rag_service import RAGService

router = APIRouter()
metadata_store = DocumentMetadataStore()
rag_service = RAGService()


def _sessions_for_document(document_id: str):
    memory = rag_service.chat_memory
    sessions = []

    for session_id in memory.get_all_sessions():
        stored_document_id = memory.get_document_id(session_id)
        if stored_document_id == document_id:
            sessions.append((session_id, memory.get_history(session_id, document_id)))

    return sessions


@router.get("/documents/{document_id}/history")
def get_document_history(document_id: str):
    if not metadata_store.get(document_id):
        raise HTTPException(status_code=404, detail="Document not found")

    sessions = _sessions_for_document(document_id)
    messages = []

    for session_id, history in sessions:
        for message in history:
            messages.append({
                **message,
                "session_id": session_id,
            })

    return {
        "document_id": document_id,
        "history": messages,
        "count": len(messages),
    }


@router.delete("/documents/{document_id}/history")
def delete_document_history(document_id: str):
    if not metadata_store.get(document_id):
        raise HTTPException(status_code=404, detail="Document not found")

    sessions = _sessions_for_document(document_id)
    memory = rag_service.chat_memory

    for session_id, _ in sessions:
        memory.clear_session(session_id)

    return {
        "message": "Document chat history cleared successfully",
        "document_id": document_id,
        "sessions_cleared": len(sessions),
    }
