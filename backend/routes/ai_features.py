from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pypdf import PdfReader

from backend.services.ai_features import (
    summarize,
    compare_documents,
    generate_flashcards,
    generate_exam,
    evaluate_answer,
)
from backend.services.document_metadata import DocumentMetadataStore

router = APIRouter()
metadata_store = DocumentMetadataStore()
UPLOAD_DIR = Path("backend/uploads")


class SummaryRequest(BaseModel):
    docId: str
    type: str = "short"


class CompareRequest(BaseModel):
    docIds: list[str] = Field(min_length=2)


class FlashcardRequest(BaseModel):
    docId: str
    count: int = 10


class ExamRequest(BaseModel):
    docId: str
    count: int = 5


class EvaluateRequest(BaseModel):
    question: str
    userAnswer: str
    modelAnswer: str = ""


def get_document_text(document_id: str):
    metadata = metadata_store.get(document_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Document not found")

    stored_filename = metadata.get("stored_filename")
    if not stored_filename or Path(stored_filename).name != stored_filename:
        raise HTTPException(status_code=404, detail="Stored PDF not found")

    file_path = UPLOAD_DIR / stored_filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored PDF not found")

    try:
        reader = PdfReader(str(file_path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Could not extract text from this PDF") from exc

    if not text.strip():
        raise HTTPException(status_code=422, detail="No extractable text found in this PDF")

    return text, metadata


def run_ai(operation, *args):
    try:
        return operation(*args)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/summary")
def create_summary(request: SummaryRequest):
    text, metadata = get_document_text(request.docId)
    result = run_ai(summarize, text, request.type)
    return {
        "summary": result,
        "type": request.type if request.type in {"short", "detailed", "bullets"} else "short",
        "docName": metadata.get("filename", "Document"),
    }


@router.post("/summary/compare")
def compare_summaries(request: CompareRequest):
    texts, names = [], []
    for document_id in request.docIds:
        text, metadata = get_document_text(document_id)
        texts.append(text)
        names.append(metadata.get("filename", "Document"))

    result = run_ai(compare_documents, texts, names)
    return {"comparison": result, "documents": names}


@router.post("/flashcards")
def create_flashcards(request: FlashcardRequest):
    text, metadata = get_document_text(request.docId)
    cards = run_ai(generate_flashcards, text, request.count)
    return {
        "flashcards": cards,
        "count": len(cards),
        "docName": metadata.get("filename", "Document"),
    }


@router.post("/flashcards/exam")
def create_exam(request: ExamRequest):
    text, metadata = get_document_text(request.docId)
    questions = run_ai(generate_exam, text, request.count)
    return {
        "questions": questions,
        "count": len(questions),
        "docName": metadata.get("filename", "Document"),
    }


@router.post("/flashcards/evaluate")
def evaluate_exam_answer(request: EvaluateRequest):
    if not request.question.strip() or not request.userAnswer.strip():
        raise HTTPException(
            status_code=400,
            detail="question and userAnswer required",
        )

    return run_ai(
        evaluate_answer,
        request.question,
        request.userAnswer,
        request.modelAnswer,
    )
