from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import uuid
from pydantic import BaseModel, AliasChoices, Field
from typing import Optional
from pydantic import BaseModel
from fastapi import Request
from fastapi.responses import JSONResponse
from backend.routes.auth import router as auth_router
from backend.routes.document_history import router as document_history_router
from backend.routes.podcast import router as podcast_router
from backend.routes.ai_features import router as ai_features_router
from backend.services.rag_service import RAGService
from backend.services.rag_retriever import RAGRetriever
from backend.services.document_metadata import DocumentMetadataStore


# =========================================================
# FastAPI Application
# =========================================================

app = FastAPI(
    title="Saathi AI",
    description="AI-powered document intelligence backend",
    version="1.0.0"
)

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
@app.middleware("http")
async def support_api_prefix(request: Request, call_next):
    path = request.scope["path"]
    if path == "/api":
        request.scope["path"] = "/"
    elif path.startswith("/api/"):
        request.scope["path"] = path[4:]
    return await call_next(request)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)}
    )


app.include_router(auth_router)
app.include_router(document_history_router)
app.include_router(podcast_router)
app.include_router(ai_features_router)


# =========================================================
# Directories
# =========================================================

UPLOAD_DIR = Path("backend/uploads")

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# Services
# =========================================================

retriever = RAGRetriever()

rag_service = RAGService()

metadata_store = DocumentMetadataStore()


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
def chat(request: ChatRequest):
    try:
        question = (request.question or request.query or "").strip()

        if not question:
            raise HTTPException(
                status_code=422,
                detail="Question cannot be empty."
            )

        document_ids = request.docIds or (
            [request.document_id] if request.document_id else []
        )

        if not document_ids:
            raise HTTPException(
                status_code=422,
                detail="At least one document must be selected."
            )

        results = []

        for document_id in document_ids:
            result = rag_service.ask(
                document_id=document_id,
                question=question,
                session_id=request.session_id or "default"
            )

            results.append(result)

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
                document_ids[0] if len(document_ids) == 1 else document_ids
            ),
            "question": question,
            "answer": answer,
            "sources": sources
        }


    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

# =========================================================
# Phase 9G
# Clear Chat Session
# =========================================================

@app.delete("/chat/sessions/{session_id}")
def clear_chat_session(
    session_id: str
):

    if not session_id or not session_id.strip():

        raise HTTPException(
            status_code=400,
            detail="Session ID cannot be empty."
        )

    try:

        # Clear conversation from ChatMemory
        rag_service.chat_memory.clear_session(
            session_id
        )

        return {
            "message": "Chat session cleared successfully",
            "session_id": session_id
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# =========================================================
# Upload PDF
# =========================================================

@app.post("/upload")
async def upload_pdf(
    files: list[UploadFile] = File(
        ...,
        description="PDF files to upload",
        json_schema_extra={
            "items": {
                "type": "string",
                "format": "binary"
            }
        }
    )
):
    uploaded = []
    errors = []

    for file in files:
        file_path = None
        document_id = str(uuid.uuid4())

        try:
            if not file.filename:
                errors.append({
                    "filename": "unknown",
                    "error": "Filename is missing."
                })
                continue

            if not file.filename.lower().endswith(".pdf"):
                errors.append({
                    "filename": file.filename,
                    "error": "Only PDF files are supported."
                })
                continue

            safe_filename = Path(file.filename).name
            stored_filename = f"{document_id}.pdf"
            file_path = UPLOAD_DIR / stored_filename

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            result = retriever.process_pdf(
                file_path=str(file_path),
                document_id=document_id
            )

            metadata = {
                "document_id": document_id,
                "filename": safe_filename,
                "stored_filename": stored_filename,
                "page_count": result["page_count"],
                "chunk_count": result["chunk_count"],
                "vector_count": result["vector_count"]
            }

            metadata_store.save(metadata)

            uploaded.append({
                **metadata
            })

        except Exception as error:
            if file_path and file_path.exists():
                file_path.unlink()

            errors.append({
                "filename": file.filename or "unknown",
                "error": str(error)
            })

        finally:
            await file.close()

    return {
        "message": "Upload processing completed",
        "uploaded": uploaded,
        "errors": errors
    }


# =========================================================
# Get All Documents
# =========================================================

@app.get("/documents")
def get_documents():

    try:

        documents = metadata_store.get_all()

        return {
            "documents": documents,
            "count": len(documents)
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# =========================================================
# Get One Document
# =========================================================

@app.get("/documents/{document_id}")
def get_document(
    document_id: str
):

    metadata = metadata_store.get(
        document_id
    )

    if metadata is None:

        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    return {"document": metadata}


# =========================================================
# Delete Document
# =========================================================

@app.delete("/documents/{document_id}")
def delete_document(document_id: str):
    # Check whether the document exists.
    metadata = metadata_store.get(document_id)

    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    try:
        # Delete this document's FAISS data.
        retriever.document_store.delete_document(document_id)

        # Delete this document's metadata.
        metadata_store.delete(document_id)

        # Delete the PDF safely.
        stored_filename = metadata.get("stored_filename")

        if stored_filename:
            # New uploads have unique filenames.
            file_path = UPLOAD_DIR / stored_filename

            if file_path.exists():
                file_path.unlink()

        else:
            # Legacy documents may share the same physical PDF.
            original_filename = metadata.get("filename")

            if original_filename:
                other_legacy_documents = [
                    doc
                    for doc in metadata_store.get_all()
                    if doc.get("document_id") != document_id
                    and doc.get("filename") == original_filename
                    and not doc.get("stored_filename")
                ]

                # Delete the legacy PDF only when no other
                # legacy document record references it.
                if not other_legacy_documents:
                    file_path = UPLOAD_DIR / Path(original_filename).name

                    if file_path.exists():
                        file_path.unlink()

        return {"ok": True}

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
