"""Review-aware RAG measurements. Quote presence is not factual entailment."""

import re

from app.rag.corpus import canonical_url, is_official_url
from app.response.grounded import normalized


def validate_cases(cases: list[dict]) -> None:
    ids = set()
    for case in cases:
        if not case.get("id") or case["id"] in ids or not case.get("question", "").strip():
            raise ValueError("Cases require unique IDs and nonblank questions")
        ids.add(case["id"])
        if case.get("expected_behavior") not in {"answer", "abstain", "clarify", "private"}:
            raise ValueError(f"Invalid expected behavior: {case['id']}")
        if case.get("review_status") == "approved":
            if not case.get("reviewer") or not case.get("reviewed_at"):
                raise ValueError(f"Approved case lacks reviewer/date: {case['id']}")
            if case["expected_behavior"] == "answer":
                if not case.get("reference_answer") or not case.get("relevant_sources"):
                    raise ValueError(
                        f"Approved answer lacks reference or source labels: {case['id']}"
                    )
                for source in case["relevant_sources"]:
                    if (
                        not is_official_url(source.get("source_url", ""))
                        or not source.get("quote", "").strip()
                    ):
                        raise ValueError(f"Source label lacks URL/exact quote: {case['id']}")


def retrieval_metrics(hits, relevant_sources: list[dict], k: int) -> dict:
    """Document precision/recall/MRR within the top-k retrieved passages.

    Deduplicate source URL/version identities before scoring. Exact supporting
    quotes constrain relevance to the labelled passage. P@k uses denominator k,
    so returning fewer than k documents does not artificially inflate precision.
    """
    if k < 1 or not relevant_sources:
        raise ValueError("Positive k and nonempty relevance labels are required")
    unique, groups = [], {}
    for hit in hits[:k]:
        key = (canonical_url(hit.chunk.source_url), hit.chunk.source_version_id)
        if key not in groups:
            unique.append(hit)
            groups[key] = []
        groups[key].append(hit.chunk.content)
    relevant_ranks, matched_labels = [], set()
    for rank, hit in enumerate(unique, 1):
        matched = []
        for i, source in enumerate(relevant_sources):
            if canonical_url(source["source_url"]) != canonical_url(hit.chunk.source_url):
                continue
            if (
                source.get("source_version_id")
                and source["source_version_id"] != hit.chunk.source_version_id
                and not (
                    source.get("source_sha256")
                    and source["source_sha256"] == hit.chunk.source_sha256
                )
            ):
                continue
            contents = groups[(canonical_url(hit.chunk.source_url), hit.chunk.source_version_id)]
            if not any(normalized(source["quote"]) in normalized(content) for content in contents):
                continue
            matched.append(i)
        if matched:
            relevant_ranks.append(rank)
            matched_labels.update(matched)
    return {
        "precision_at_k": len(relevant_ranks) / k,
        "source_recall_at_k": len(matched_labels) / len(relevant_sources),
        "reciprocal_rank": 1 / relevant_ranks[0] if relevant_ranks else 0.0,
        "hit_at_k": bool(relevant_ranks),
    }


def rouge_l_f1(answer: str, reference: str) -> float:
    """Token-level ROUGE-L F1, without stemming; not a correctness score."""
    left, right = (re.findall(r"\w+", value.lower())[:2000] for value in (answer, reference))
    if not left or not right:
        return 0.0
    previous = [0] * (len(right) + 1)
    for token in left:
        current = [0]
        for i, other in enumerate(right, 1):
            current.append(previous[i - 1] + 1 if token == other else max(current[-1], previous[i]))
        previous = current
    return 2 * previous[-1] / (len(left) + len(right))


def citation_integrity(citations: list[dict], hits) -> dict:
    """Check IDs, version provenance and exact quotes against retrieved context."""
    by_id = {h.chunk.chunk_id: h.chunk for h in hits}
    valid = 0
    for citation in citations:
        chunk = by_id.get(citation.get("chunk_id"))
        if chunk is None:
            continue
        if canonical_url(citation.get("source_url", "")) != canonical_url(chunk.source_url):
            continue
        if citation.get("source_version_id", "") != chunk.source_version_id:
            continue
        if citation.get("source_sha256", "") != chunk.source_sha256:
            continue
        quotes = citation.get("quotes") or citation.get("supporting_quotes") or []
        if (
            isinstance(quotes, list)
            and quotes
            and all(
                isinstance(q, str) and q.strip() and normalized(q) in normalized(chunk.content)
                for q in quotes
            )
        ):
            valid += 1
    return {
        "citations": len(citations),
        "valid_citations": valid,
        "citation_integrity": valid / len(citations) if citations else None,
        "limitation": (
            "Checks provenance and quote presence; factual entailment requires human review."
        ),
    }
