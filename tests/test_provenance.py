"""Tests for src.provenance — claim and citation extraction."""

from src.provenance import (
    detect_claim_conflicts,
    extract_citations,
    extract_claims,
    infer_claim_type,
    infer_confidence,
    infer_source_type,
    link_claims_to_citations,
    score_research_rubric,
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


def test_score_research_rubric():
    claims = extract_claims(SAMPLE_TEXT, scope="synthesis", dimension="Performance")
    citations = extract_citations(SAMPLE_TEXT, scope="synthesis", retrieved_at="2026-04-09T00:00:00Z")
    links = link_claims_to_citations(claims, citations)
    rubric = score_research_rubric(claims, citations, links, contradictions=[])
    assert rubric["overall_score"] >= 0.0
    assert rubric["grade"] in {"strong", "good", "developing", "insufficient"}
    assert rubric["dimensions"]["citation_coverage"] >= 0.0
    assert rubric["summary"]["synthesis_claim_count"] == len(claims)


def test_score_research_rubric_no_lightweight_mode_in_output():
    """The rubric no longer has a lightweight_mode key in its summary."""
    text = """
    - Python is beginner-friendly. High confidence.
    - Large ecosystem. https://docs.python.org/3/
    - Slower for CPU-bound workloads.
    """
    claims = extract_claims(text, scope="synthesis", dimension="Developer experience")
    citations = extract_citations(text, scope="synthesis", retrieved_at="2026-04-09T00:00:00Z")
    links = link_claims_to_citations(claims, citations)
    rubric = score_research_rubric(claims, citations, links, contradictions=[])
    assert "lightweight_mode" not in rubric["summary"]


# ---------------------------------------------------------------------------
# Rubric calibration controls
#
# These fixtures pin the rubric's behavior against known-good, known-bad,
# and mediocre inputs.  If a threshold or target changes, one of these
# tests should break — that's the point.
# ---------------------------------------------------------------------------

_GOOD_SYNTHESIS = """
- Python's readability leads to 40% faster onboarding for junior developers. High confidence. [Stack Overflow 2024](https://survey.stackoverflow.co/2024)
- PyPI hosts 550,000+ packages as of April 2026. High confidence. [PyPI Stats](https://pypi.org/stats/)
- NumPy and pandas dominate data science workflows with 87% adoption. High confidence. [JetBrains Survey](https://www.jetbrains.com/lp/devecosystem-2025/)
- The GIL limits true CPU parallelism; free-threaded CPython 3.13 is experimental. Medium confidence. [PEP 703](https://peps.python.org/pep-0703/)
- Cold-start latency on AWS Lambda averages 1.2s for Python vs 0.8s for Go. Medium confidence. [AWS re:Invent benchmarks](https://github.com/aws-samples/lambda-perf)
- Packaging remains fragmented: pip, poetry, uv, conda compete without a single standard. High confidence. [Python Packaging Authority](https://packaging.python.org/)
- Type checking via mypy catches ~15% of bugs that would otherwise reach production. Medium confidence. [Dropbox engineering blog](https://dropbox.tech/application/our-journey-to-type-checking-4-million-lines-of-python)
- Recommendation: use Python for prototyping and data pipelines where time-to-first-result matters most.
- Recommendation: avoid Python for latency-sensitive microservices unless you can absorb 3-5x compute cost vs Go.
- Recommendation: adopt uv as the packaging tool for new projects.
- Supply chain risk is elevated: PyPI had 12 critical malware incidents in Q1 2026. Low confidence. [Phylum blog](https://blog.phylum.io/)
- Django and FastAPI are production-ready for web APIs with mature async support. High confidence. [TechEmpower benchmarks](https://www.techempower.com/benchmarks/)
"""

_BAD_SYNTHESIS = """
- Python is a popular programming language.
- It is used in many industries.
- There are some performance concerns.
- The ecosystem has many libraries.
- Packaging can be difficult sometimes.
- Some people prefer other languages for certain tasks.
- The community is large and active.
- Python is good for beginners.
"""

_MEDIOCRE_SYNTHESIS = """
- Python is readable and has clean syntax.
- PyPI has over 500k packages. https://pypi.org/
- The GIL is a known limitation for CPU-bound work.
- Cold starts on Lambda are slower than Go. Medium confidence.
- Packaging is fragmented across pip, poetry, and conda.
- Django is a mature web framework. https://www.djangoproject.com/
- Recommendation: consider Python for rapid prototyping.
- Type checking adoption remains uneven across the ecosystem.
- Python 3.13 introduces experimental free-threading. https://docs.python.org/3.13/
- The language is widely used in machine learning.
"""


def _rubric_for(text):
    claims = extract_claims(text, scope="synthesis", dimension="DX")
    citations = extract_citations(text, scope="synthesis", retrieved_at="2026-04-10T00:00:00Z")
    links = link_claims_to_citations(claims, citations)
    return score_research_rubric(claims, citations, links, contradictions=[])


def test_rubric_calibration_good_scores_strong():
    """Well-cited synthesis with confidence labels and recommendations
    should score 'strong' (>= 0.8).
    """
    rubric = _rubric_for(_GOOD_SYNTHESIS)
    assert rubric["grade"] == "strong", f"expected strong, got {rubric['grade']} ({rubric['overall_score']})"
    assert rubric["overall_score"] >= 0.8
    assert rubric["dimensions"]["citation_coverage"] >= 0.6
    assert rubric["dimensions"]["actionability"] >= 0.8


def test_rubric_calibration_bad_scores_insufficient():
    """Vague, uncited synthesis with no labels should score 'insufficient'
    (< 0.4).
    """
    rubric = _rubric_for(_BAD_SYNTHESIS)
    assert rubric["grade"] == "insufficient", f"expected insufficient, got {rubric['grade']} ({rubric['overall_score']})"
    assert rubric["overall_score"] < 0.4
    assert rubric["dimensions"]["citation_coverage"] == 0.0
    assert rubric["dimensions"]["source_diversity"] == 0.0


def test_rubric_calibration_mediocre_scores_developing():
    """Partially cited synthesis with some labels should score 'developing'
    (>= 0.4 and < 0.6).
    """
    rubric = _rubric_for(_MEDIOCRE_SYNTHESIS)
    assert rubric["grade"] == "developing", f"expected developing, got {rubric['grade']} ({rubric['overall_score']})"
    assert 0.4 <= rubric["overall_score"] < 0.6
