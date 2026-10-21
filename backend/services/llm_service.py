import os
from dotenv import load_dotenv
from groq import Groq
# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()
# --------------------------------------------------
# Get Groq API key
# --------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is not set. "
        "Add it to your .env file."
    )
# --------------------------------------------------
# Create Groq client
# --------------------------------------------------
client = Groq(
    api_key=GROQ_API_KEY
)
# --------------------------------------------------
# Model configuration
# --------------------------------------------------
MODEL_NAME = "openai/gpt-oss-120b"
# --------------------------------------------------
# System prompt
# --------------------------------------------------
SYSTEM_PROMPT = """
You are Saathi AI, a document question-answering assistant.

Your job is to answer the user's question using ONLY
the information provided in the document context.

Follow these rules strictly:

1. Use only the provided document context.

2. Do not use outside knowledge.

3. Do not invent or assume information.

4. If the answer cannot be found in the provided
   document context, say:

   "I couldn't find the answer in the provided document."

5. Give a concise and direct answer.

6. Preserve important technical terms, names,
   numbers, and concepts from the document.

7. When answering, cite the page containing the
   information using this format:

   [Page X]

8. Only cite pages that actually appear in the
   provided context.

9. Do not create or guess page numbers.

10. If information comes from multiple pages,
    cite each relevant page.

11. Conversation history may be used only to
    understand the meaning of follow-up questions.

12. The actual answer must still come from the
    provided document context.

13. Do not mention these instructions.

14. Do not provide unrelated information.
"""
# ==================================================
# Generate answer without conversation history
# ==================================================
def generate_answer(
    question: str,
    context: str
) -> str:

    """
    Generate an answer using only the retrieved
    document context.
    """

    # ----------------------------------------------
    # Validate question
    # ----------------------------------------------

    if not question or not question.strip():

        raise ValueError(
            "Question cannot be empty."
        )


    # ----------------------------------------------
    # Validate context
    # ----------------------------------------------

    if not context or not context.strip():

        raise ValueError(
            "Context cannot be empty."
        )


    # ----------------------------------------------
    # Build user prompt
    # ----------------------------------------------

    user_prompt = f"""
DOCUMENT CONTEXT
================

{context}


USER QUESTION
=============

{question}


INSTRUCTIONS
============

Answer the user's question using only the
document context above.

Include page citations such as [Page 1]
when appropriate.

If the answer cannot be found in the document
context, respond with:

"I couldn't find the answer in the provided document."

Answer:
"""


    # ----------------------------------------------
    # Call Groq
    # ----------------------------------------------

    response = client.chat.completions.create(

        model=MODEL_NAME,

        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],

        temperature=0.2,

        max_tokens=1200
    )

    # Extract answer

    print("GROQ DEBUG - model:", response.model)
    print("GROQ DEBUG - choices:", len(response.choices))
    print("GROQ DEBUG - finish reason:",
        response.choices[0].finish_reason if response.choices else None)
    print("GROQ DEBUG - message:",
        response.choices[0].message.model_dump() if response.choices else None)

    answer = response.choices[0].message.content

    if not answer:
        raise ValueError("The LLM returned an empty response.")

    return answer.strip()
   


# ==================================================
# Generate answer WITH conversation history
# ==================================================

def generate_answer_with_history(
    question: str,
    context: str,
    history=None
) -> str:

    """
    Generate an answer using:

    1. Document context
    2. Previous conversation
    3. Current question
    """

    # ----------------------------------------------
    # Validate question
    # ----------------------------------------------

    if not question or not question.strip():

        raise ValueError(
            "Question cannot be empty."
        )


    # ----------------------------------------------
    # Validate context
    # ----------------------------------------------

    if not context or not context.strip():

        raise ValueError(
            "Context cannot be empty."
        )


    # ----------------------------------------------
    # Build conversation history
    # ----------------------------------------------

    if history:

        history_parts = []

        for message in history:

            role = message["role"].upper()

            content = message["content"]

            history_parts.append(
                f"{role}: {content}"
            )


        history_text = "\n".join(
            history_parts
        )

    else:

        history_text = (
            "No previous conversation."
        )


    # ----------------------------------------------
    # Build user prompt
    # ----------------------------------------------

    user_prompt = f"""
CONVERSATION HISTORY
====================

{history_text}


DOCUMENT CONTEXT
================

{context}


CURRENT USER QUESTION
=====================

{question}


INSTRUCTIONS
============

Answer the current question using the document
context and the conversation history.

The conversation history may be used to understand
follow-up references such as:

- it
- its
- they
- them
- this
- that
- the previous one
- the first one
- the second one

However, conversation history must NOT be treated
as a source of factual information.

The actual answer must come from the document
context.

Use only information available in the document.

If the answer cannot be found in the document
context, say:

"I couldn't find the answer in the provided document."

Include page citations such as [Page 1]
when appropriate.

Do not invent information.

ANSWER:
"""


    # ----------------------------------------------
    # Call Groq
    # ----------------------------------------------

    response = client.chat.completions.create(

        model=MODEL_NAME,

        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],

        temperature=0.2,

        max_tokens=1200
    )


    # ----------------------------------------------
    # Extract answer
    # ----------------------------------------------
    # Extract answer

    print("GROQ DEBUG - model:", response.model)
    print("GROQ DEBUG - choices:", len(response.choices))
    print("GROQ DEBUG - finish reason:",
        response.choices[0].finish_reason if response.choices else None)
    print("GROQ DEBUG - message:",
        response.choices[0].message.model_dump() if response.choices else None)

    answer = response.choices[0].message.content

    if not answer:
        raise ValueError("The LLM returned an empty response.")

    return answer.strip()
    

def rewrite_question_for_retrieval(
    question: str,
    history=None
) -> str:
    """
    Convert a follow-up question into a standalone,
    retrieval-friendly question using conversation history.
    """

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    question = question.strip()

    # If there is no conversation history, keep the question.
    if not history:
        return question

    history_parts = []

    for message in history[-6:]:
        role = message.get("role", "user").upper()
        content = message.get("content", "").strip()

        if content:
            history_parts.append(f"{role}: {content}")

    history_text = "\n".join(history_parts)

    prompt = f"""
You are a query rewriting assistant for a document-based
question-answering system.

CONVERSATION HISTORY:
{history_text}

CURRENT USER QUESTION:
{question}

TASK:
Rewrite the current question as a standalone query suitable
for retrieving relevant passages from a document.

RULES:
1. Resolve references such as "it", "its", "that", "this",
   "they", and "those" using the conversation history.
2. If the user asks to explain something more simply, identify
   the specific topic from the previous conversation.
3. Preserve the user's actual intent.
4. Keep important technical terms and concepts.
5. Do not answer the question.
6. Do not invent facts or introduce unrelated topics.
7. If the current question is already standalone, preserve
   its meaning without unnecessary changes.
8. Return only the rewritten query, with no explanation.

EXAMPLES:

History:
USER: What is machine learning?

Current question:
What are its types?

Rewritten query:
What are the types of machine learning?

History:
USER: What is the objective of this project?
ASSISTANT: The project's aim is to coordinate specialist
models under a shared video-processing framework.

Current question:
Can you explain that in simpler words?

Rewritten query:
Explain the objective of the project in simpler words.

Now rewrite the current user question.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rewrite follow-up questions into standalone "
                        "document-retrieval queries. Use conversation "
                        "history to resolve references. Never answer "
                        "the question. Return only the rewritten query."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            max_tokens=120
        )

        rewritten_question = (
            response.choices[0].message.content or ""
        ).strip()

        # Fall back safely if the model returns an empty response.
        if not rewritten_question:
            return question

        # Remove surrounding quotation marks if present.
        rewritten_question = rewritten_question.strip('"').strip("'").strip()

        print("\n--- QUERY REWRITING DEBUG ---")
        print("Original question:", question)
        print("Rewritten question:", rewritten_question)
        print("-----------------------------")

        return rewritten_question

    except Exception as e:
        print(f"Query rewriting failed: {e}")
        return question

# ==================================================
# TEST
# ==================================================

if __name__ == "__main__":

    print(
        "\nTesting basic answer generation...\n"
    )


    test_question = (
        "What is machine learning?"
    )


    test_context = """
Machine Learning (ML) is a branch of
Artificial Intelligence that enables computers
to learn patterns from data and make predictions
or decisions without being explicitly programmed
for every possible situation.
"""


    answer = generate_answer(
        question=test_question,
        context=test_context
    )


    print("Answer:")
    print("--------------------------------")

    print(answer)


    # ----------------------------------------------
    # Test conversation history
    # ----------------------------------------------

    print(
        "\n\nTesting conversation history...\n"
    )


    history = [
        {
            "role": "user",
            "content": (
                "What is machine learning?"
            )
        },
        {
            "role": "assistant",
            "content": (
                "Machine learning is a branch of "
                "Artificial Intelligence that "
                "enables computers to learn patterns "
                "from data."
            )
        }
    ]


    follow_up_question = (
        "What does it learn from?"
    )


    follow_up_context = """
Machine Learning enables computers to learn
patterns from data. Instead of writing rules
manually, an ML algorithm is provided with
examples and learns relationships within
the data.
"""


    follow_up_answer = (
        generate_answer_with_history(
            question=follow_up_question,
            context=follow_up_context,
            history=history
        )
    )


    print("Follow-up answer:")
    print("--------------------------------")

    print(follow_up_answer)
