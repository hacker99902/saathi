"""
Retrieval-quality evaluation for Saathi AI.

Run from the project root while FastAPI is running:
    python tests/evaluate_retrieval.py

Optional environment variables:
    RAG_BASE_URL=http://127.0.0.1:8000
    RAG_DOCUMENT_ID=6d6a7b00-5ba7-4e0d-942f-da9a62c48a77

The expected evidence phrases are manually labelled evaluation data. They should
be reviewed whenever the source document or retrieval behavior changes.
"""

import os
import re
import statistics
import time
import uuid

import requests

BASE_URL = os.getenv("RAG_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DOCUMENT_ID = os.getenv(
    "RAG_DOCUMENT_ID",
    "6d6a7b00-5ba7-4e0d-942f-da9a62c48a77",
)
TOP_K = 3
HEALTH_TIMEOUT = (5, 30)
CHAT_TIMEOUT = (5, 180)

EVALUATION_CASES = [
    {
        "name": "project_objective",
        "question": "What is the objective of this project?",
        "evidence_groups": [
            ["executable system-level architecture", "executable system level architecture"],
            ["heterogeneous specialist models"],
            ["shared video-processing framework", "shared video processing framework"],
        ],
    },
    {
        "name": "three_roles_and_orchestrator",
        "question": "What are the three specialist roles, and what does the central orchestrator do?",
        "evidence_groups": [
            ["safety officer"],
            ["quality inspector"],
            ["production manager"],
            ["task routing", "adaptive frame sampling", "event normalization"],
        ],
    },
    {
        "name": "role_technologies",
        "question": "What technologies are used by the Safety Officer, Quality Inspector, and Production Manager?",
        "evidence_groups": [
            ["bytetrack"],
            ["event-triggered roi", "industrial anomaly detection"],
            ["virtual boundaries", "counting and throughput"],
        ],
    },
    {
        "name": "safety_officer",
        "question": "What does the Safety Officer do?",
        "evidence_groups": [
            ["detects people and ppe items", "person and personal protective equipment"],
            ["worker tracks", "multi-object tracking"],
        ],
    },
    {
        "name": "keyword_heavy_quality_inspection",
        "question": "Which dataset is used as the primary benchmark for industrial quality inspection?",
        "evidence_groups": [
            ["mvtec ad"],
            ["primary benchmark"],
        ],
    },
]

FOLLOW_UP_CASE = {
    "name": "follow_up_context",
    "setup_question": "What does the Safety Officer do?",
    "question": "Explain that in simpler words.",
    "evidence_groups": [
        ["safety officer"],
        ["ppe", "personal protective equipment"],
        ["worker tracks", "tracking"],
    ],
}

UNSUPPORTED_CASE = {
    "name": "unsupported_pca",
    "question": "What is Principal Component Analysis (PCA), and how does it work mathematically?",
    "expect_no_sources": True,
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def source_matches_evidence(source: dict, evidence_groups: list[list[str]]) -> bool:
    text = normalize(str(source.get("text", "")))
    return any(
        normalize(phrase) in text
        for group in evidence_groups
        for phrase in group
    )


def count_matched_evidence_groups(
    sources: list[dict], evidence_groups: list[list[str]]
) -> int:
    combined_text = normalize(
        " ".join(str(source.get("text", "")) for source in sources)
    )
    return sum(
        any(normalize(phrase) in combined_text for phrase in group)
        for group in evidence_groups
    )


def evaluate_per_fact_sources(sources: list[dict], fact_groups: dict[str, list[str]]) -> dict:
    """Find each required fact in the returned sources and report its first rank."""
    facts = {}
    for fact_name, phrases in fact_groups.items():
        first_rank = None
        matched_phrase = None
        for rank, source in enumerate(sources, start=1):
            source_text = normalize(str(source.get("text", "")))
            for phrase in phrases:
                if normalize(phrase) in source_text:
                    first_rank = rank
                    matched_phrase = phrase
                    break
            if first_rank is not None:
                break
        facts[fact_name] = {
            "supported": first_rank is not None,
            "first_rank": first_rank,
            "matched_phrase": matched_phrase,
        }

    supported_count = sum(item["supported"] for item in facts.values())
    total_count = len(facts)
    return {
        "facts": facts,
        "supported_count": supported_count,
        "total_count": total_count,
        "support_rate": supported_count / total_count if total_count else 0.0,
    }


MULTI_PART_FACTS = {
    "safety_officer": ["safety officer", "bytetrack", "real-time detection"],
    "quality_inspector": [
        "quality inspector",
        "event-triggered roi inspection",
        "industrial anomaly detection",
    ],
    "production_manager": [
        "production manager",
        "virtual boundaries",
        "counting and throughput",
    ],
    "central_orchestrator": [
        "task routing",
        "adaptive frame sampling",
        "model management",
        "event normalization",
    ],
}


def request_chat(question: str, session_id: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "document_id": DOCUMENT_ID,
            "question": question,
            "session_id": session_id,
        },
        timeout=CHAT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def evaluate_evidence_case(case: dict, session_id: str | None = None) -> dict:
    if session_id is None:
        session_id = f"retrieval-eval-{case['name']}-{uuid.uuid4().hex[:8]}"

    start = time.perf_counter()
    payload = request_chat(case["question"], session_id)
    latency = time.perf_counter() - start

    sources = payload.get("sources", [])[:TOP_K]
    groups = case["evidence_groups"]
    relevant_ranks = [
        rank for rank, source in enumerate(sources, start=1)
        if source_matches_evidence(source, groups)
    ]
    matched_groups = count_matched_evidence_groups(sources, groups)

    return {
        "name": case["name"],
        "hit": 1.0 if relevant_ranks else 0.0,
        "recall": matched_groups / len(groups) if groups else 0.0,
        "reciprocal_rank": 1.0 / relevant_ranks[0] if relevant_ranks else 0.0,
        "rank1_hit": 1.0 if 1 in relevant_ranks else 0.0,
        "latency": latency,
        "sources": sources,
        "answer": payload.get("answer", ""),
    }


def evaluate_follow_up() -> dict:
    session_id = f"retrieval-eval-followup-{uuid.uuid4().hex[:8]}"

    # Establish context in the same session before asking the follow-up.
    first_payload = request_chat(FOLLOW_UP_CASE["setup_question"], session_id)
    start = time.perf_counter()
    payload = request_chat(FOLLOW_UP_CASE["question"], session_id)
    latency = time.perf_counter() - start

    sources = payload.get("sources", [])[:TOP_K]
    groups = FOLLOW_UP_CASE["evidence_groups"]
    relevant_ranks = [
        rank for rank, source in enumerate(sources, start=1)
        if source_matches_evidence(source, groups)
    ]
    matched_groups = count_matched_evidence_groups(sources, groups)

    return {
        "name": FOLLOW_UP_CASE["name"],
        "hit": 1.0 if relevant_ranks else 0.0,
        "recall": matched_groups / len(groups) if groups else 0.0,
        "reciprocal_rank": 1.0 / relevant_ranks[0] if relevant_ranks else 0.0,
        "rank1_hit": 1.0 if 1 in relevant_ranks else 0.0,
        "latency": latency,
        "sources": sources,
        "answer": payload.get("answer", ""),
        "setup_answer": first_payload.get("answer", ""),
    }


def evaluate_unsupported_case() -> dict:
    session_id = f"retrieval-eval-unsupported-{uuid.uuid4().hex[:8]}"
    start = time.perf_counter()
    payload = request_chat(UNSUPPORTED_CASE["question"], session_id)
    latency = time.perf_counter() - start
    sources = payload.get("sources", [])
    answer = payload.get("answer", "")
    no_sources = len(sources) == 0
    fallback = "couldn't find enough relevant information" in normalize(answer)

    return {
        "name": UNSUPPORTED_CASE["name"],
        "passed": no_sources and fallback,
        "no_sources": no_sources,
        "fallback": fallback,
        "latency": latency,
        "sources": sources,
        "answer": answer,
    }



def extract_cited_pages(answer: str) -> set[int]:
    """Extract page numbers from citations such as [Page 6] or [Pages 6, 8]."""
    pages = set()
    for match in re.finditer(r"\[Pages?\s+([0-9,\s]+)\]", answer, flags=re.IGNORECASE):
        pages.update(int(value) for value in re.findall(r"\d+", match.group(1)))
    return pages


def evaluate_citation_consistency(answer: str, sources: list[dict]) -> dict:
    """Compare cited page numbers with page numbers returned in sources."""
    cited_pages = extract_cited_pages(answer)
    source_pages = {
        int(source["page_number"])
        for source in sources
        if source.get("page_number") is not None
        and str(source.get("page_number")).isdigit()
    }

    unsupported_citations = cited_pages - source_pages
    uncited_source_pages = source_pages - cited_pages

    return {
        "cited_pages": sorted(cited_pages),
        "source_pages": sorted(source_pages),
        "unsupported_citations": sorted(unsupported_citations),
        "uncited_source_pages": sorted(uncited_source_pages),
        "all_citations_match_sources": len(unsupported_citations) == 0,
        "citation_coverage": (
            len(cited_pages & source_pages) / len(source_pages)
            if source_pages else 1.0
        ),
    }



def evaluate_claim_support(sources: list[dict], claims: dict[str, list[str]]) -> dict:
    """
    Lightweight claim-grounding check using explicit evidence phrases.
    A claim is marked supported if one of its evidence phrases occurs in
    the returned source text. This is a heuristic, not semantic entailment.
    """
    combined_source_text = normalize(
        " ".join(str(source.get("text", "")) for source in sources)
    )
    claim_results = {}
    for claim_name, evidence_phrases in claims.items():
        matched = [
            phrase
            for phrase in evidence_phrases
            if normalize(phrase) in combined_source_text
        ]
        claim_results[claim_name] = {
            "supported": bool(matched),
            "matched_evidence": matched,
        }

    supported_count = sum(item["supported"] for item in claim_results.values())
    total_count = len(claim_results)
    return {
        "claims": claim_results,
        "supported_count": supported_count,
        "total_count": total_count,
        "support_rate": supported_count / total_count if total_count else 0.0,
    }


SAFETY_OFFICER_CLAIMS = {
    "detects_people_and_ppe": [
        "detects people and ppe items",
        "person and personal protective equipment",
        "real-time person and ppe detection",
    ],
    "associates_ppe_with_worker_tracks": [
        "associates ppe detections with worker tracks",
        "links the ppe detections to worker tracks",
        "multi-object tracking",
    ],
    "maintains_temporal_compliance_state": [
        "maintains a temporal compliance state",
        "maintains temporal compliance state",
    ],
    "identifies_violations_and_restricted_zone_intrusions": [
        "safety violations and restricted-zone intrusions",
        "restricted-zone intrusions",
        "restricted zone intrusions",
    ],
}


def main():
    health = requests.get(f"{BASE_URL}/health", timeout=HEALTH_TIMEOUT)
    health.raise_for_status()

    results = []
    citation_reports = []
    print(f"Evaluating retrieval against: {BASE_URL}")
    print(f"Document ID: {DOCUMENT_ID}")
    print(f"Evidence metrics use the first {TOP_K} returned sources.\n")

    for case in EVALUATION_CASES:
        result = evaluate_evidence_case(case)
        results.append(result)
        print(f"--- {result['name']} ---")
        print(f"Hit@{TOP_K}: {int(result['hit'])}")
        print(f"Recall@{TOP_K}: {result['recall']:.2f}")
        print(f"First relevant rank reciprocal: {result['reciprocal_rank']:.2f}")
        print(f"Relevant source at rank 1: {int(result['rank1_hit'])}")
        print(f"Latency: {result['latency']:.2f}s")
        print("Returned source pages:", [
            source.get("page_number") for source in result["sources"]
        ])
        print("Answer:", result["answer"].replace("\n", " ")[:250])

        citation_report = evaluate_citation_consistency(
            result["answer"],
            result["sources"],
        )
        citation_reports.append(citation_report)
        print("Citation consistency:")
        print("  Cited pages:", citation_report["cited_pages"])
        print("  Returned source pages:", citation_report["source_pages"])
        print(
            "  Citations missing from returned sources:",
            citation_report["unsupported_citations"],
        )
        print(
            f"  Source-page citation coverage: "
            f"{citation_report['citation_coverage']:.0%}"
        )

        if case["name"] == "safety_officer":
            claim_report = evaluate_claim_support(
                result["sources"],
                SAFETY_OFFICER_CLAIMS,
            )
            print("Claim-level grounding (phrase-based):")
            for claim_name, claim_result in claim_report["claims"].items():
                status = "SUPPORTED" if claim_result["supported"] else "NOT MATCHED"
                print(f"  {claim_name}: {status}")
                if claim_result["matched_evidence"]:
                    print(
                        "    matched:",
                        ", ".join(claim_result["matched_evidence"]),
                    )
            print(
                f"Claim support: {claim_report['supported_count']}/"
                f"{claim_report['total_count']} "
                f"({claim_report['support_rate']:.0%})"
            )

        if case["name"] == "three_roles_and_orchestrator":
            fact_report = evaluate_per_fact_sources(
                result["sources"],
                MULTI_PART_FACTS,
            )
            print("Per-fact evidence:")
            for fact_name, fact_result in fact_report["facts"].items():
                rank_text = (
                    str(fact_result["first_rank"])
                    if fact_result["first_rank"] is not None
                    else "not found"
                )
                status = "FOUND" if fact_result["supported"] else "MISSING"
                print(f"  {fact_name}: {status} (first rank: {rank_text})")
            print(
                f"Per-fact support: {fact_report['supported_count']}/"
                f"{fact_report['total_count']} "
                f"({fact_report['support_rate']:.0%})"
            )
        print()

    follow_up = evaluate_follow_up()
    results.append(follow_up)
    print(f"--- {follow_up['name']} ---")
    print(f"Hit@{TOP_K}: {int(follow_up['hit'])}")
    print(f"Recall@{TOP_K}: {follow_up['recall']:.2f}")
    print(f"First relevant rank reciprocal: {follow_up['reciprocal_rank']:.2f}")
    print(f"Relevant source at rank 1: {int(follow_up['rank1_hit'])}")
    print(f"Latency: {follow_up['latency']:.2f}s")
    print("Returned source pages:", [
        source.get("page_number") for source in follow_up["sources"]
    ])
    print("Follow-up answer:", follow_up["answer"].replace("\n", " ")[:250])
    print()

    unsupported = evaluate_unsupported_case()
    print(f"--- {unsupported['name']} ---")
    print(f"Unsupported-question check: {'PASS' if unsupported['passed'] else 'FAIL'}")
    print(f"Sources empty: {unsupported['no_sources']}")
    print(f"Expected fallback present: {unsupported['fallback']}")
    print(f"Latency: {unsupported['latency']:.2f}s")
    print("Answer:", unsupported["answer"].replace("\n", " ")[:250])
    print()

    hit_rate = statistics.mean(item["hit"] for item in results)
    mean_recall = statistics.mean(item["recall"] for item in results)
    mrr = statistics.mean(item["reciprocal_rank"] for item in results)
    rank1_rate = statistics.mean(item["rank1_hit"] for item in results)
    mean_latency = statistics.mean(item["latency"] for item in results)

    print("========== RETRIEVAL SUMMARY ==========")
    print(f"Evidence questions evaluated: {len(results)}")
    print(f"Hit Rate@{TOP_K}: {hit_rate:.2%}")
    print(f"Mean Recall@{TOP_K}: {mean_recall:.2%}")
    print(f"MRR@{TOP_K}: {mrr:.3f}")
    print(f"Rank-1 relevant-source rate: {rank1_rate:.2%}")
    print(f"Mean chat latency: {mean_latency:.2f}s")
    print(f"Unsupported question: {'PASS' if unsupported['passed'] else 'FAIL'}")
    if citation_reports:
        citation_consistency_rate = statistics.mean(
            1.0 if report["all_citations_match_sources"] else 0.0
            for report in citation_reports
        )
        mean_citation_coverage = statistics.mean(
            report["citation_coverage"] for report in citation_reports
        )
        print(f"Citation-to-source consistency: {citation_consistency_rate:.2%}")
        print(f"Mean source-page citation coverage: {mean_citation_coverage:.2%}")
    print("\nScores depend on the manually defined evidence phrases and this test set.")


if __name__ == "__main__":
    main()
