"""Tests for src.provenance — claim and citation extraction."""

from src.provenance import (
    detect_claim_conflicts,
    extract_citations,
    extract_claims,
    infer_claim_type,
    infer_confidence,
    infer_source_type,
    link_claims_to_citations,
    source_quality_weight,
    summarize_evidence_quality,
)


SAMPLE_TEXT = """
### Findings

Python 3.11 improved performance by about 1.25x on average according to
https://docs.python.org/3/whatsnew/3.11.html. High confidence.

- Recommend Python for orchestration-heavy workloads.
- This suggests Python is weaker for latency-critical hot paths.

See [AWS pricing](https://aws.amazon.com/lambda/pricing/) for request costs.
"""


def test_extract_citations():
    citations = extract_citations(SAMPLE_TEXT, scope="test", retrieved_at="2026-04-09T00:00:00Z")
    urls = [citation["url"] for citation in citations]
    assert "https://docs.python.org/3/whatsnew/3.11.html." in urls or "https://docs.python.org/3/whatsnew/3.11.html" in urls
    assert "https://aws.amazon.com/lambda/pricing/" in urls


def test_extract_claims():
    claims = extract_claims(SAMPLE_TEXT, scope="test", dimension="Performance")
    assert any("Recommend Python for orchestration-heavy workloads." in claim["text"] for claim in claims)
    assert any(claim["confidence"] == "high" for claim in claims)


def test_infer_source_type():
    assert infer_source_type("https://docs.aws.amazon.com/lambda/latest/dg/welcome.html") == "official_docs"
    assert infer_source_type("https://arxiv.org/abs/1234.5678") == "paper"
    assert source_quality_weight("official_docs") > source_quality_weight("community")


def test_infer_claim_type_and_confidence():
    assert infer_claim_type("Recommend using Python for internal tooling.") == "recommendation"
    assert infer_claim_type("This suggests a trade-off in performance.") == "interpretive"
    assert infer_confidence("High confidence: use the official docs.") == "high"


def test_link_claims_to_citations():
    claims = extract_claims(SAMPLE_TEXT, scope="test", dimension="Performance")
    citations = extract_citations(SAMPLE_TEXT, scope="test", retrieved_at="2026-04-09T00:00:00Z")
    links = link_claims_to_citations(claims, citations)
    assert len(links) == len(claims)
    assert any(link["support_strength"] in {"moderate", "strong", "basic"} for link in links)
    assert all("evidence_quality_score" in link for link in links)


def test_detect_claim_conflicts():
    claims = [
        {
            "id": "claim-001",
            "claim_type": "recommendation",
            "text": "Recommend Python for orchestration-heavy workloads.",
        },
        {
            "id": "claim-002",
            "claim_type": "recommendation",
            "text": "Avoid Python for orchestration-heavy workloads.",
        },
    ]
    conflicts = detect_claim_conflicts(claims)
    assert len(conflicts) == 1
    assert conflicts[0]["left_claim_id"] == "claim-001"


def test_summarize_evidence_quality():
    claims = extract_claims(SAMPLE_TEXT, scope="test", dimension="Performance")
    citations = extract_citations(SAMPLE_TEXT, scope="test", retrieved_at="2026-04-09T00:00:00Z")
    links = link_claims_to_citations(claims, citations)
    summary = summarize_evidence_quality(claims, links)
    assert "average_evidence_quality_score" in summary
    assert summary["claims_with_direct_citations"] >= 1
