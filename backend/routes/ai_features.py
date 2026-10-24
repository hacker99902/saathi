
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.services.ai_features import (
    summarize,
    compare_documents,
    generate_flashcards,
    generate_exam,
    evaluate_answer,
)
from backend.services.cloud_document_service import get_document_text
from backend.services.auth_dependencies import get_current_user


router = APIRouter()


# ---------------------------------------------------------
# Request models
# ---------------------------------------------------------

class SummaryRequest(BaseModel):
    docId: str = Field(min_length=1, max_length=200)
    type: str = Field(
        default="short",
        pattern="^(short|detailed|bullets)$",
    )

    @field_validator("docId")
    @classmethod
    def validate_doc_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Document ID cannot be empty.")
        return value


class CompareRequest(BaseModel):
    docIds: list[str] = Field(min_length=2, max_length=10)

    @field_validator("docIds")
    @classmethod
    def validate_doc_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]

        if any(not value for value in normalized):
            raise ValueError("Document IDs cannot be empty.")

        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate document IDs are not allowed.")

        return normalized


class FlashcardRequest(BaseModel):
    docId: str = Field(min_length=1, max_length=200)
    count: int = Field(default=10, ge=1, le=20)

    @field_validator("docId")
    @classmethod
    def validate_doc_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Document ID cannot be empty.")
        return value


class ExamRequest(BaseModel):
    docId: str = Field(min_length=1, max_length=200)
    count: int = Field(default=5, ge=1, le=10)

    @field_validator("docId")
    @classmethod
    def validate_doc_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Document ID cannot be empty.")
        return value


class EvaluateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    userAnswer: str = Field(min_length=1, max_length=10000)
    modelAnswer: str = Field(default="", max_length=10000)

    @field_validator("question", "userAnswer")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value

    @field_validator("modelAnswer")
    @classmethod
    def normalize_model_answer(cls, value: str) -> str:
        return value.strip()


# ---------------------------------------------------------
# Shared error handler
# ---------------------------------------------------------

def run_ai(operation, *args):
    try:
        return operation(*args)

    except HTTPException:
        raise

    except Exception as exc:
        # Keep internal provider and database errors out of responses.
        raise HTTPException(
            status_code=500,
            detail="AI processing failed. Please try again.",
        ) from exc


# ---------------------------------------------------------
# Document summary
# POST /summary
# ---------------------------------------------------------

@router.post("/summary")
def create_summary(
    request: SummaryRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])

    text, metadata = get_document_text(
        request.docId,
        user_id,
    )

    summary = run_ai(
        summarize,
        text,
        request.type,
    )

    return {
        "summary": summary,
        "type": request.type,
        "docName": metadata.get("filename", "Document"),
    }


# ---------------------------------------------------------
# Compare documents
# POST /summary/compare
# ---------------------------------------------------------

@router.post("/summary/compare")
def compare_documents_route(
    request: CompareRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])

    texts = []
    names = []

    for document_id in request.docIds:
        text, metadata = get_document_text(
            document_id,
            user_id,
        )

        texts.append(text)
        names.append(metadata.get("filename", "Document"))

    comparison = run_ai(
        compare_documents,
        texts,
        names,
    )

    return {"comparison": comparison}


# ---------------------------------------------------------
# Generate flashcards
# POST /flashcards
# ---------------------------------------------------------

@router.post("/flashcards")
def create_flashcards(
    request: FlashcardRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])

    text, metadata = get_document_text(
        request.docId,
        user_id,
    )

    cards = run_ai(
        generate_flashcards,
        text,
        request.count,
    )

    return {
        "flashcards": cards,
        "docName": metadata.get("filename", "Document"),
    }


# ---------------------------------------------------------
# Generate exam questions
# POST /flashcards/exam
# ---------------------------------------------------------

@router.post("/flashcards/exam")
def create_exam(
    request: ExamRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["id"])

    text, metadata = get_document_text(
        request.docId,
        user_id,
    )

    questions = run_ai(
        generate_exam,
        text,
        request.count,
    )

    return {
        "questions": questions,
        "docName": metadata.get("filename", "Document"),
    }


# ---------------------------------------------------------
# Evaluate an answer
# POST /flashcards/evaluate
# ---------------------------------------------------------

@router.post("/flashcards/evaluate")
def evaluate_flashcard_answer(
    request: EvaluateRequest,
    current_user: dict = Depends(get_current_user),
):
    result = run_ai(
        evaluate_answer,
        request.question,
        request.userAnswer,
        request.modelAnswer,
    )

    return result
