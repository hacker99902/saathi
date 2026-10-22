from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
from typing import Annotated
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
from backend.services.supabase_client import supabase

# =========================================================
# FastAPI Application
# =========================================================

app = FastAPI(
    title="Saathi AI",
    description="AI-powered document intelligence backend",
    version="1.0.0"
)

@app.get("/debug-upload-schema")
def debug_upload_schema():
    schema = app.openapi()
    return schema["components"]["schemas"].get(
        "Body_upload_pdf_upload_post",
        {}
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
    file: UploadFile = File(..., description="PDF file to upload"),
    requested_document_id: Optional[str] = None
):
    document_id = requested_document_id or str(uuid.uuid4())
    file_path = None
    storage_path = f"{document_id}.pdf"
    storage_uploaded = False
    metadata_saved = False  

    try:
        # Prevent overwriting an existing document.
        if metadata_store.exists(document_id):
            raise HTTPException(
                status_code=409,
                detail="A document with this ID already exists."
            )
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is missing.")

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported."
            )

        safe_filename = Path(file.filename).name
        stored_filename = f"{document_id}.pdf"
        file_path = UPLOAD_DIR / stored_filename

        # Save temporarily so the existing PDF processor can read it.
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Upload the original PDF to the private Supabase Storage bucket.
        with open(file_path, "rb") as pdf_file:
            supabase.storage.from_("saathi-documents").upload(
                path=storage_path,
                file=pdf_file.read(),
                file_options={
                    "content-type": "application/pdf",
                    "upsert": "true"
                }
            )
        storage_uploaded = True

        # Keep the existing Qdrant processing pipeline.
        result = retriever.process_pdf(
            file_path=str(file_path),
            document_id=document_id
        )

        metadata = {
            "document_id": document_id,
            "filename": safe_filename,
            "stored_filename": stored_filename,
            "storage_path": storage_path,
            "storage_bucket": "saathi-documents",
            "page_count": result["page_count"],
            "chunk_count": result["chunk_count"],
            "vector_count": result["vector_count"]
        }

        metadata_store.save(metadata)
        metadata_saved = True

        return {
            "message": "Upload processing completed",
            "uploaded": [metadata],
            "errors": []
        }

    except HTTPException:
        raise

    
    except Exception as error:
        # Remove Qdrant data created by this failed upload.
        try:
            retriever.load_document(document_id).delete()
        except Exception as cleanup_error:
            print(f"Qdrant cleanup failed for {document_id}: {cleanup_error}")

        # Only remove cloud data if this request uploaded it.
        if storage_uploaded:
            try:
                supabase.storage.from_("saathi-documents").remove([storage_path])
            except Exception as cleanup_error:
                print(f"Supabase file cleanup failed: {cleanup_error}")

        # Only remove metadata if this request saved it.
        if metadata_saved:
            try:
                metadata_store.delete(document_id)
            except Exception as cleanup_error:
                print(f"Metadata cleanup failed for {document_id}: {cleanup_error}")

        raise HTTPException(status_code=500, detail=str(error)) from error




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
    metadata = metadata_store.get(document_id)

    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    document_id_deleted = False

    try:
        # 1. Delete vectors from Qdrant.
        retriever.load_document(document_id).delete()

        # 2. Delete the PDF from Supabase Storage.
        storage_path = metadata.get("storage_path")
        storage_bucket = metadata.get(
            "storage_bucket",
            "saathi-documents"
        )

        if storage_path:
            supabase.storage.from_(storage_bucket).remove(
                [storage_path]
            )

        # 3. Delete metadata from Supabase.
        metadata_store.delete(document_id)
        document_id_deleted = True

        return {
            "ok": True,
            "document_id": document_id,
            "message": "Document and associated data deleted."
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Document deletion failed: {error}"
        ) from error