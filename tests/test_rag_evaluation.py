"""
Black-box evaluation tests for the Saathi AI RAG API.

Prerequisites:
    pip install pytest requests

Start the API before running:
    python -m uvicorn backend.main:app --reload

Run from the project root:
    pytest -v tests/test_rag_evaluation.py

Optional environment variables:
    RAG_BASE_URL=http://127.0.0.1:8000
    RAG_DOCUMENT_ID=6d6a7b00-5ba7-4e0d-942f-da9a62c48a77
"""

import os
import uuid

import pytest
import requests

BASE_URL = os.getenv("RAG_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DOCUMENT_ID = os.getenv(
    "RAG_DOCUMENT_ID",
    "6d6a7b00-5ba7-4e0d-942f-da9a62c48a77",
)
CHAT_URL = f"{BASE_URL}/chat"
TIMEOUT_SECONDS = 120


def new_session(prefix: str) -> str:
    return f"pytest-{prefix}-{uuid.uuid4().hex[:10]}"


def ask(question: str, session_id: str) -> dict:
    response = requests.post(
        CHAT_URL,
        json={
            "document_id": DOCUMENT_ID,
            "question": question,
            "session_id": session_id,
        },
        timeout=TIMEOUT_SECONDS,
    )
    assert response.status_code == 200, (
        f"POST /chat returned {response.status_code}: {response.text}"
    )
    payload = response.json()
    assert payload.get("document_id") == DOCUMENT_ID
    assert payload.get("question") == question
    assert isinstance(payload.get("answer"), str)
    assert isinstance(payload.get("sources"), list)
    return payload


@pytest.fixture(scope="module", autouse=True)
def api_is_available():
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
    except requests.RequestException as exc:
        pytest.fail(
            f"Could not reach {BASE_URL}. Start Uvicorn first. Details: {exc}"
        )
    assert response.status_code == 200, (
        f"Health check failed: {response.status_code} {response.text}"
    )


def test_direct_project_objective_returns_grounded_sources():
    payload = ask(
        "What is the objective of this project?",
        new_session("objective"),
    )
    answer = payload["answer"].lower()
    assert any(term in answer for term in ("objective", "develop", "project"))
    assert payload["sources"], "Expected supporting sources."

    source_text = " ".join(
        str(source.get("text", "")).lower()
        for source in payload["sources"]
    )
    assert any(
        term in source_text
        for term in ("objective", "orchestration", "specialist", "role-specific")
    ), "Returned sources do not appear to support the objective answer."


def test_multi_part_question_covers_all_three_roles_and_orchestrator():
    payload = ask(
        "What are the three specialist roles, and what does the central "
        "orchestrator do?",
        new_session("multipart"),
    )
    answer = payload["answer"].lower()
    for role in ("safety officer", "quality inspector", "production manager"):
        assert role in answer, f"Answer omitted role: {role}"
    assert any(
        term in answer
        for term in ("orchestrator", "orchestration", "task routing", "event normalization")
    ), "Answer did not explain the orchestrator."
    assert payload["sources"], "Expected sources for a supported question."


def test_role_technology_question_mentions_role_specific_methods():
    payload = ask(
        "What technologies are used by the Safety Officer, Quality Inspector, "
        "and Production Manager?",
        new_session("role-tech"),
    )
    answer = payload["answer"].lower()
    expected_groups = {
        "safety": ("safety officer", "bytetrack", "ppe", "detection", "tracking"),
        "quality": ("quality inspector", "roi", "anomaly", "inspection"),
        "production": (
            "production manager", "virtual boundaries", "throughput", "counting"
        ),
    }
    for role, terms in expected_groups.items():
        assert any(term in answer for term in terms), (
            f"Answer appears to omit the {role} role's methods."
        )
    assert payload["sources"], "Expected supporting sources."


def test_follow_up_uses_previous_turn_context():
    session_id = new_session("followup")
    first = ask("What does the Safety Officer do?", session_id)
    second = ask("Explain that in simpler words.", session_id)

    assert first["sources"], "First turn should retrieve supporting sources."
    answer = second["answer"].lower()
    assert any(
        term in answer
        for term in ("safety officer", "worker", "ppe", "safety gear")
    ), "Follow-up did not appear to use conversation history."
    assert second["sources"], "Expected sources for the contextual follow-up."


def test_unsupported_pca_question_uses_fallback_without_sources():
    payload = ask(
        "What is Principal Component Analysis (PCA), and how does it work mathematically?",
        new_session("unsupported-pca"),
    )
    answer = payload["answer"].lower()
    assert any(
        phrase in answer
        for phrase in (
            "couldn't find enough relevant information",
            "could not find enough relevant information",
            "not enough relevant information",
            "couldn't find the answer",
            "could not find the answer",
        )
    ), f"Expected unsupported-question fallback, got: {payload['answer']}"
    assert payload["sources"] == [], (
        "Unsupported question should return no sources under the current fallback behavior."
    )
