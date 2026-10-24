
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Depends,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.routes.auth import router as auth_router
from backend.routes.document_history import router as document_history_router
from backend.routes.podcast import router as podcast_router
from backend.routes.ai_features import router as ai_features_router

from backend.services.auth_dependencies import get_current_user
from backend.services.rag_service import rag_service
from backend.services.rag_retriever import RAGRetriever
from backend.services.document_metadata import DocumentMetadataStore
from backend.services.supabase_client import supabase


# =========================================================
# FastAPI Application
# =========================================================

app = FastAPI(
    title="Saathi AI",
    description="AI-powered document intelligence backend",
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://saathi-five-umber.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# API Prefix Compatibility
# =========================================================

@app.middleware("http")
async def support_api_prefix(request: Request, call_next):
    path = request.scope["path"]

    if path == "/api":
        request.scope["path"] = "/"
    elif path.startswith("/api/"):
        request.scope["path"] = path[4:]

    return await call_next(request)


# =========================================================
# Error Handling
# =========================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)},
    )


# =========================================================
# Routers
# =========================================================

app.include_router(auth_router)
app.include_router(document_history_router)
app.include_router(podcast_router)
app.include_router(ai_features_router)


# =========================================================
# Directories and Services
# =========================================================

UPLOAD_DIR = Path("backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

retriever = RAGRetriever()
metadata_store = DocumentMetadataStore()

# Use the shared RAG service instance used by other routes.
# This keeps chat sessions accessible to the history endpoints.


# =========================================================
# Request Models
# =========================================================

class ChatRequest(BaseModel):
    document_id: Optional[str] = None
    question: Optional[str] = None
    session_id: Optional[str] = None
    query: Optional[str] = None
    docIds: list[str] = Field(default_factory=list)


# =========================================================
# Root
# =========================================================

@app.get("/")
def root():
    return {
        "message": "Saathi AI backend is running"
    }


# =========================================================
# Health Check
# =========================================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


# =========================================================
# Chat
# =========================================================


@app.post("/chat")
def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        question = (request.question or request.query or "").strip()

        if not question:
            raise HTTPException(
                status_code=422,
                detail="Question cannot be empty.",
            )

        # Support both single-document and multi-document chat.
        document_ids = request.docIds or (
            [request.document_id] if request.document_id else []
        )

        # Remove duplicate and empty document IDs.
        document_ids = list(dict.fromkeys(
            doc_id.strip()
            for doc_id in document_ids
            if isinstance(doc_id, str) and doc_id.strip()
        ))

        if not document_ids:
            raise HTTPException(
                status_code=422,
                detail="At least one document must be selected.",
            )

        user_id = str(current_user["id"])

        # Verify ownership of every requested document first.
        for document_id in document_ids:
            metadata = metadata_store.get(document_id, user_id)

            if metadata is None:
                raise HTTPException(
                    status_code=404,
                    detail="Document not found.",
                )

        results = []

        for document_id in document_ids:
            # Use a separate session for each document.
            session_id = f"{request.session_id or 'default'}_{document_id}"

            result = rag_service.ask(
                document_id=document_id,
                question=question,
                session_id=session_id,
                user_id=user_id,
            )

            # Preserve original fields and add consistent aliases
            # for frontend source rendering.
            normalized_sources = []

            for source in result.get("sources", []):
                source = dict(source)

                page = source.get(
                    "page",
                    source.get("page_number"),
                )
                quote = source.get(
                    "quote",
                    source.get("text", ""),
                )

                source["page"] = page
                source["quote"] = quote

                normalized_sources.append(source)

            results.append({
                **result,
                "sources": normalized_sources,
            })

        if len(results) == 1:
            answer = results[0]["answer"]
            sources = results[0]["sources"]
        else:
            answer = "\n\n".join(
                result["answer"] for result in results
            )
            sources = [
                source
                for result in results
                for source in result["sources"]
            ]

        return {
            "document_id": (
                document_ids[0]
                if len(document_ids) == 1
                else document_ids
            ),
            "question": question,
            "answer": answer,
            "sources": sources,
        }

    except HTTPException:
        raise

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail="Document data was not found.",
        ) from error

    except Exception as error:
        # Keep document contents and user questions out of logs.
        print(f"Chat processing failed: {type(error).__name__}")

        raise HTTPException(
            status_code=500,
            detail="Chat processing failed. Please try again.",
        ) from error

# =========================================================
# Clear Chat Session
# =========================================================

@app.delete("/chat/sessions/{session_id}")
def clear_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    if not session_id or not session_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Session ID cannot be empty.",
        )

    try:
        memory = rag_service.chat_memory

        # Load the session so ownership can be verified.
        session = memory.sessions.get(session_id)

        if session is None:
            session = memory._load_session(session_id)

        if not session:
            raise HTTPException(
                status_code=404,
                detail="Chat session not found.",
            )

        document_id = session.get("document_id")
        session_user_id = session.get("user_id")

        if (
            not document_id
            or str(session_user_id) != str(current_user["id"])
        ):
            raise HTTPException(
                status_code=404,
                detail="Chat session not found.",
            )

        # Confirm the user still owns the document.
        metadata = metadata_store.get(
            document_id,
            str(current_user["id"]),
        )

        if metadata is None:
            raise HTTPException(
                status_code=404,
                detail="Chat session not found.",
            )

        memory.clear_session(session_id)

        return {
            "message": "Chat session cleared successfully",
            "session_id": session_id,
        }

    except HTTPException:
        raise

    except Exception as error:
        print(f"Chat session cleanup failed: {type(error).__name__}")

        raise HTTPException(
            status_code=500,
            detail="Unable to clear chat session.",
        ) from error

# =========================================================
# Upload PDF
# =========================================================

@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(..., description="PDF file to upload"),
    requested_document_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    document_id = requested_document_id or str(uuid.uuid4())
    user_id = str(current_user["id"])

    file_path = None
    storage_path = f"{document_id}.pdf"

    storage_uploaded = False
    metadata_saved = False
    processing_started = False

    try:
        # Prevent overwriting an existing document.
        if metadata_store.exists(document_id):
            raise HTTPException(
                status_code=409,
                detail="A document with this ID already exists.",
            )

        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Filename is missing.",
            )

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported.",
            )

        safe_filename = Path(file.filename).name
        stored_filename = f"{document_id}.pdf"
        file_path = UPLOAD_DIR / stored_filename

        # Save temporarily for the existing PDF processor.
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Upload the PDF to Supabase Storage.
        with open(file_path, "rb") as pdf_file:
            supabase.storage.from_("saathi-documents").upload(
                path=storage_path,
                file=pdf_file.read(),
                file_options={
                    "content-type": "application/pdf",
                    "upsert": "false",
                },
            )

        storage_uploaded = True
        processing_started = True

        # Preserve the existing Qdrant processing pipeline.
        result = retriever.process_pdf(
            file_path=str(file_path),
            document_id=document_id,
        )

        metadata = {
            "document_id": document_id,
            "user_id": user_id,
            "filename": safe_filename,
            "stored_filename": stored_filename,
            "storage_path": storage_path,
            "storage_bucket": "saathi-documents",
            "page_count": result["page_count"],
            "chunk_count": result["chunk_count"],
            "vector_count": result["vector_count"],
        }

        metadata_store.save(metadata)
        metadata_saved = True

        return {
            "message": "Upload processing completed",
            "uploaded": [metadata],
            "errors": [],
        }

    except Exception as error:
        # Clean up only resources created by this request.
        if processing_started:
            try:
                retriever.load_document(document_id).delete()
            except Exception as cleanup_error:
                print(f"Qdrant cleanup failed: {cleanup_error}")

        if storage_uploaded:
            try:
                supabase.storage.from_("saathi-documents").remove(
                    [storage_path]
                )
            except Exception as cleanup_error:
                print(f"Supabase cleanup failed: {cleanup_error}")

        if metadata_saved:
            try:
                metadata_store.delete(document_id, user_id)
            except Exception as cleanup_error:
                print(f"Metadata cleanup failed: {cleanup_error}")

        # Remove the temporary local file after a failed upload.
        if file_path is not None:
            try:
                file_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                print(f"Temporary file cleanup failed: {cleanup_error}")

        if isinstance(error, HTTPException):
            raise error

        print(f"Upload processing failed: {error}")
        raise HTTPException(
            status_code=500,
            detail="Upload processing failed. Please try again.",
        ) from error

    finally:
        await file.close()


# =========================================================
# Get All Documents
# =========================================================

@app.get("/documents")
def get_documents(
    current_user: dict = Depends(get_current_user),
):
    try:
        documents = metadata_store.get_all(
            str(current_user["id"])
        )

        return {
            "documents": documents,
            "count": len(documents),
        }

    except Exception as error:
        print(f"Document listing failed: {error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve documents.",
        ) from error


# =========================================================
# Get One Document
# =========================================================

@app.get("/documents/{document_id}")
def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    metadata = metadata_store.get(
        document_id,
        str(current_user["id"]),
    )

    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return {"document": metadata}


# =========================================================
# Delete Document
# =========================================================

@app.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])

    # Verify ownership before deleting any resources.
    metadata = metadata_store.get(document_id, user_id)

    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    try:
        # 1. Delete the document's vectors.
        retriever.load_document(document_id).delete()

        # 2. Delete its stored PDF.
        storage_path = metadata.get("storage_path")
        storage_bucket = metadata.get(
            "storage_bucket",
            "saathi-documents",
        )

        if storage_path:
            supabase.storage.from_(storage_bucket).remove(
                [storage_path]
            )

        # 3. Delete only this user's metadata.
        metadata_store.delete(document_id, user_id)

        return {
            "ok": True,
            "document_id": document_id,
            "message": "Document and associated data deleted.",
        }

    except Exception as error:
        print(f"Document deletion failed: {error}")
        raise HTTPException(
            status_code=500,
            detail="Document deletion failed.",
        ) from error
