
from fastapi import APIRouter, Depends, HTTPException

from backend.services.auth_dependencies import get_current_user
from backend.services.document_metadata import metadata_store
from backend.services.rag_service import rag_service


router = APIRouter()



def _sessions_for_document(document_id: str, user_id: str):
    """Find persisted sessions belonging to this user and document."""
    chat_memory = rag_service.chat_memory
    matching_sessions = []

    for session_id in chat_memory.get_all_sessions():
        session = chat_memory.sessions.get(session_id)

        if session is None:
            session = chat_memory._load_session(session_id)

            if session is not None:
                chat_memory.sessions[session_id] = session

        if not session:
            continue

        if (
            session.get("document_id") == document_id
            and session.get("user_id") == user_id
        ):
            matching_sessions.append(session_id)

    return matching_sessions

@router.get("/documents/{document_id}/history")
def get_document_history(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])

    metadata = metadata_store.get(document_id, user_id)
    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    history = []

    for session_id in _sessions_for_document(document_id, user_id):
        messages = rag_service.chat_memory.get_history(
            session_id=session_id,
            document_id=document_id,
        )

        history.append({
            "sessionId": session_id,
            "messages": messages,
        })

    return {"documentId": document_id, "history": history}


@router.delete("/documents/{document_id}/history")
def delete_document_history(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])

    metadata = metadata_store.get(document_id, user_id)
    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    session_ids = _sessions_for_document(document_id, user_id)

    for session_id in session_ids:
        rag_service.chat_memory.clear_session(session_id)

    return {
        "message": "Document chat history deleted successfully.",
        "documentId": document_id,
        "deletedSessions": len(session_ids),
    }
