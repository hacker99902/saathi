import json
import re

from backend.services.llm_service import client, MODEL_NAME


def _complete(system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 2048) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def _json_from_response(raw: str, expected_type):
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, expected_type):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[[\s\S]*\]|\{[\s\S]*\}", cleaned)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, expected_type):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError("The AI returned an invalid JSON response. Please try again.")


def summarize(text: str, summary_type: str = "short") -> str:
    prompts = {
        "short": "Summarize this document in 3-4 sentences. Capture its main topic, key points, and conclusion.",
        "detailed": "Write a comprehensive summary covering the main topic, key arguments, evidence, conclusions, and significance.",
        "bullets": "Create a structured bullet-point summary with Main Topic, Key Points, Insights, and Conclusion.",
    }
    if summary_type not in prompts:
        summary_type = "short"

    return _complete(
        "You are Saathi, an expert document analyst. Create clear, accurate summaries grounded in the document.",
        f"{prompts[summary_type]}\n\nDocument:\n{text[:8000]}",
        temperature=0.3,
        max_tokens=1500,
    )


def compare_documents(texts: list[str], names: list[str]) -> str:
    documents = "\n\n".join(
        f"=== {name} ===\n{text[:3000]}"
        for text, name in zip(texts, names)
    )
    return _complete(
        "You are a document analyst. Compare the documents, explaining their similarities, differences, and overall synthesis.",
        f"Compare these documents:\n\n{documents}",
        temperature=0.3,
        max_tokens=2000,
    )


def generate_flashcards(text: str, count: int = 10) -> list:
    count = max(1, min(int(count), 20))
    raw = _complete(
        f'Generate exactly {count} flashcards as a JSON array. Return only JSON in this format: '
        '[{"q":"question","a":"answer","difficulty":"easy|medium|hard","topic":"topic"}].',
        f"Generate {count} flashcards from this document:\n\n{text[:8000]}",
        temperature=0.5,
        max_tokens=3000,
    )
    return _json_from_response(raw, list)


def generate_exam(text: str, count: int = 5) -> list:
    count = max(1, min(int(count), 10))
    raw = _complete(
        f'Generate {count} exam questions as a JSON array. Mix MCQ and short_answer. '
        'Return only JSON using objects such as '
        '{"type":"mcq","question":"...","options":["A) ...","B) ...","C) ...","D) ..."],"correct":"A","explanation":"..."} '
        'or {"type":"short_answer","question":"...","model_answer":"..."}.',
        f"Generate {count} exam questions from this document:\n\n{text[:6000]}",
        temperature=0.4,
        max_tokens=2500,
    )
    return _json_from_response(raw, list)


def evaluate_answer(question: str, user_answer: str, model_answer: str = "") -> dict:
    raw = _complete(
        'Evaluate the student answer and return only a JSON object: '
        '{"score":0,"feedback":"...","missed":["..."]}. Score must be between 0 and 100.',
        f"Question: {question}\nModel answer: {model_answer}\nStudent answer: {user_answer}",
        temperature=0.2,
        max_tokens=500,
    )
    result = _json_from_response(raw, dict)

    try:
        result["score"] = max(0, min(100, int(result.get("score", 0))))
    except (TypeError, ValueError):
        result["score"] = 0

    result.setdefault("feedback", "")
    result.setdefault("missed", [])
    return result
