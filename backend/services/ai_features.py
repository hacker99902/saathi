
import json
import re

from backend.services.llm_service import _chat_completion


def _complete(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    return _chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _json_from_response(raw: str, expected_type):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("The AI returned an empty JSON response.")

    cleaned = raw.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, expected_type):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()

    for index, character in enumerate(cleaned):
        if character not in "[{":
            continue

        try:
            parsed, _ = decoder.raw_decode(cleaned[index:])
            if isinstance(parsed, expected_type):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError(
        "The AI returned an invalid JSON response. Please try again."
    )


def summarize(text: str, summary_type: str = "short") -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Document text cannot be empty.")

    prompts = {
        "short": (
            "Summarize this document in 3-4 sentences. Capture its "
            "main topic, key points, and conclusion."
        ),
        "detailed": (
            "Write a comprehensive summary covering the main topic, "
            "key arguments, evidence, conclusions, and significance."
        ),
        "bullets": (
            "Create a structured bullet-point summary with Main Topic, "
            "Key Points, Insights, and Conclusion."
        ),
    }

    if summary_type not in prompts:
        summary_type = "short"

    return _complete(
        "You are Saathi, an expert document analyst. Create clear, "
        "accurate summaries grounded in the document.",
        f"{prompts[summary_type]}\n\nDocument:\n{text[:8000]}",
        temperature=0.3,
        max_tokens=1500,
    )


def compare_documents(texts: list[str], names: list[str]) -> str:
    if not isinstance(texts, list) or len(texts) < 2:
        raise ValueError("At least two documents are required.")

    if not isinstance(names, list) or len(names) != len(texts):
        raise ValueError(
            "Each document must have a corresponding name."
        )

    documents = []

    for index, (text, name) in enumerate(zip(texts, names), start=1):
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"Document {index} contains no extractable text."
            )

        safe_name = (
            name.strip()
            if isinstance(name, str) and name.strip()
            else f"Document {index}"
        )
        documents.append(f"=== {safe_name} ===\n{text[:3000]}")

    return _complete(
        "You are a document analyst. Compare the documents, explaining "
        "their similarities, differences, and overall synthesis.",
        "Compare these documents:\n\n" + "\n\n".join(documents),
        temperature=0.3,
        max_tokens=2000,
    )


def generate_flashcards(text: str, count: int = 10) -> list:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Document text cannot be empty.")

    if isinstance(count, bool):
        raise ValueError("count must be an integer.")

    try:
        count = int(count)
    except (TypeError, ValueError) as exc:
        raise ValueError("count must be an integer.") from exc

    count = max(1, min(count, 20))

    raw = _complete(
        f"Generate exactly {count} flashcards as a JSON array. "
        'Return only JSON in this format: '
        '[{"q":"question","a":"answer",'
        '"difficulty":"easy|medium|hard","topic":"topic"}].',
        f"Generate {count} flashcards from this document:\n\n{text[:8000]}",
        temperature=0.5,
        max_tokens=3000,
    )

    cards = _json_from_response(raw, list)

    if len(cards) != count:
        raise ValueError(
            f"The AI returned {len(cards)} flashcards; expected {count}."
        )

    for card in cards:
        if not isinstance(card, dict):
            raise ValueError("A generated flashcard has an invalid format.")

        if not isinstance(card.get("q"), str) or not card["q"].strip():
            raise ValueError("A flashcard is missing its question.")

        if not isinstance(card.get("a"), str) or not card["a"].strip():
            raise ValueError("A flashcard is missing its answer.")

    return cards


def generate_exam(text: str, count: int = 5) -> list:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Document text cannot be empty.")

    if isinstance(count, bool):
        raise ValueError("count must be an integer.")

    try:
        count = int(count)
    except (TypeError, ValueError) as exc:
        raise ValueError("count must be an integer.") from exc

    count = max(1, min(count, 10))

    raw = _complete(
        f"Generate exactly {count} exam questions as a JSON array. "
        "Mix MCQ and short_answer. Return only JSON using objects such as "
        '{"type":"mcq","question":"...","options":'
        '["A) ...","B) ...","C) ...","D) ..."],'
        '"correct":"A","explanation":"..."} or '
        '{"type":"short_answer","question":"...","model_answer":"..."}.',
        f"Generate {count} exam questions from this document:\n\n{text[:6000]}",
        temperature=0.4,
        max_tokens=2500,
    )

    questions = _json_from_response(raw, list)

    if len(questions) != count:
        raise ValueError(
            f"The AI returned {len(questions)} questions; expected {count}."
        )

    for item in questions:
        if not isinstance(item, dict):
            raise ValueError("An exam question has an invalid format.")

        if (
            not isinstance(item.get("question"), str)
            or not item["question"].strip()
        ):
            raise ValueError("An exam question is missing its question text.")

        if item.get("type") not in {"mcq", "short_answer"}:
            raise ValueError("An exam question has an unsupported type.")

        if item["type"] == "mcq":
            options = item.get("options")
            if (
                not isinstance(options, list)
                or len(options) < 2
                or not all(
                    isinstance(option, str) and option.strip()
                    for option in options
                )
            ):
                raise ValueError(
                    "An MCQ must contain at least two valid options."
                )

            correct = item.get("correct")
            if not isinstance(correct, str) or not correct.strip():
                raise ValueError("An MCQ is missing its correct answer.")

        else:
            model_answer = item.get("model_answer")
            if (
                not isinstance(model_answer, str)
                or not model_answer.strip()
            ):
                raise ValueError(
                    "A short-answer question needs a model answer."
                )

    return questions


def evaluate_answer(
    question: str,
    user_answer: str,
    model_answer: str = "",
) -> dict:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question cannot be empty.")

    if not isinstance(user_answer, str) or not user_answer.strip():
        raise ValueError("Student answer cannot be empty.")

    if not isinstance(model_answer, str):
        raise ValueError("Model answer must be a string.")

    raw = _complete(
        "Evaluate the student answer using the question and model answer. "
        'Return only a JSON object: '
        '{"score":0,"feedback":"...","missed":["..."]}. '
        "Score must be between 0 and 100.",
        f"Question: {question}\n"
        f"Model answer: {model_answer}\n"
        f"Student answer: {user_answer}",
        temperature=0.2,
        max_tokens=500,
    )

    result = _json_from_response(raw, dict)

    try:
        score = float(result.get("score", 0))
        if not 0 <= score <= 100:
            raise ValueError
        result["score"] = round(score)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "The AI returned an invalid evaluation score."
        ) from exc

    feedback = result.get("feedback", "")
    missed = result.get("missed", [])

    if not isinstance(feedback, str):
        raise ValueError("The AI returned invalid evaluation feedback.")

    if not isinstance(missed, list) or not all(
        isinstance(item, str) for item in missed
    ):
        raise ValueError("The AI returned an invalid missed-points list.")

    result["feedback"] = feedback
    result["missed"] = missed

    return result
