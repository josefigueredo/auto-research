"""Lightweight claim and citation extraction helpers.

These helpers do not attempt full scholarly parsing. They provide a
machine-readable first pass over research output so runs can capture
claims, cited URLs, and confidence markers for later analysis.
"""

from __future__ import annotations

import re
from typing import Any


_URL_PATTERN = re.compile(r"https?://[^\s)>\]]+")
_MD_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CONFIDENCE_PATTERNS = {
    "high": re.compile(r"\bhigh confidence\b", re.IGNORECASE),
    "medium": re.compile(r"\bmedium confidence\b", re.IGNORECASE),
    "low": re.compile(r"\blow confidence\b", re.IGNORECASE),
    "unresolved": re.compile(r"\bunresolved\b|\bunknown\b", re.IGNORECASE),
}


def extract_citations(text: str, *, scope: str, retrieved_at: str) -> list[dict[str, Any]]:
    """Extract citation-like URL references from text."""
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()

    for match in _MD_LINK_PATTERN.finditer(text):
        title, url = match.groups()
        if url in seen:
            continue
        seen.add(url)
        citations.append(
            {
                "id": f"cite-{len(citations) + 1:03d}",
                "scope": scope,
                "title": title.strip(),
                "url": url,
                "source_type": infer_source_type(url),
                "source_quality_weight": source_quality_weight(infer_source_type(url)),
                "retrieved_at": retrieved_at,
            }
        )

    for url in _URL_PATTERN.findall(text):
        if url in seen:
            continue
        seen.add(url)
        citations.append(
            {
                "id": f"cite-{len(citations) + 1:03d}",
                "scope": scope,
                "title": "",
                "url": url,
                "source_type": infer_source_type(url),
                "source_quality_weight": source_quality_weight(infer_source_type(url)),
                "retrieved_at": retrieved_at,
            }
        )

    return citations


def extract_claims(text: str, *, scope: str, dimension: str = "") -> list[dict[str, Any]]:
    """Extract simple claim records from prose and bullet lists."""
    claims: list[dict[str, Any]] = []
    pending_confidence: str | None = None
    for raw_claim in _iter_claim_candidates(text):
        claim = raw_claim.strip()
        inferred_confidence = infer_confidence(claim)
        if inferred_confidence != "unlabeled" and len(claim) < 40:
            pending_confidence = inferred_confidence
            continue
        if len(claim) < 40:
            continue
        cited_urls = _URL_PATTERN.findall(claim)
        confidence = inferred_confidence
        if confidence == "unlabeled" and pending_confidence is not None:
            confidence = pending_confidence
            pending_confidence = None
        claims.append(
            {
                "id": f"claim-{len(claims) + 1:03d}",
                "scope": scope,
                "dimension": dimension,
                "text": claim,
                "claim_type": infer_claim_type(claim),
                "confidence": confidence,
                "cited_urls": cited_urls,
            }
        )
    return claims


def link_claims_to_citations(
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create heuristic links from claims to citations with support strength."""
    links: list[dict[str, Any]] = []
    citation_by_url = {citation["url"]: citation for citation in citations}

    for claim in claims:
        matched_ids: list[str] = []
        matched_types: list[str] = []
        matched_weights: list[float] = []
        for url in claim.get("cited_urls", []):
            citation = citation_by_url.get(url)
            if citation:
                matched_ids.append(citation["id"])
                matched_types.append(citation["source_type"])
                matched_weights.append(float(citation.get("source_quality_weight", 0.4)))

        support_strength = infer_support_strength(
            claim,
            matched_citation_count=len(matched_ids),
            matched_source_types=matched_types,
        )
        evidence_quality_score = score_evidence_quality(
            claim,
            matched_citation_count=len(matched_ids),
            matched_source_types=matched_types,
            matched_weights=matched_weights,
        )
        links.append(
            {
                "claim_id": claim["id"],
                "citation_ids": matched_ids,
                "support_strength": support_strength,
                "has_direct_citation": bool(matched_ids),
                "evidence_quality_score": evidence_quality_score,
            }
        )
    return links


def detect_claim_conflicts(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect coarse contradictions between recommendation claims.

    This intentionally uses a lightweight heuristic: claims that share
    a normalized object phrase but opposite recommendation verbs are
    flagged for human review.
    """
    conflicts: list[dict[str, Any]] = []
    recommendation_claims = [claim for claim in claims if claim.get("claim_type") == "recommendation"]

    for i, left in enumerate(recommendation_claims):
        for right in recommendation_claims[i + 1 :]:
            left_norm = _normalized_recommendation_object(left["text"])
            right_norm = _normalized_recommendation_object(right["text"])
            if not left_norm or not right_norm or left_norm != right_norm:
                continue
            left_polarity = _recommendation_polarity(left["text"])
            right_polarity = _recommendation_polarity(right["text"])
            if left_polarity and right_polarity and left_polarity != right_polarity:
                conflicts.append(
                    {
                        "left_claim_id": left["id"],
                        "right_claim_id": right["id"],
                        "reason": "opposing recommendations about similar object",
                        "object": left_norm,
                    }
                )
    return conflicts


def infer_source_type(url: str) -> str:
    """Infer a coarse source type from a URL."""
    lowered = url.lower()
    if any(host in lowered for host in ("docs.", "developer.", "learn.microsoft.", "docs.aws.", "cloud.google.")):
        return "official_docs"
    if any(host in lowered for host in ("arxiv.org", "doi.org", "acm.org", "ieee.org", "springer.com")):
        return "paper"
    if any(host in lowered for host in ("github.com", "gitlab.com")):
        return "repository"
    if any(host in lowered for host in ("stackoverflow.com", "reddit.com", "news.ycombinator.com")):
        return "community"
    return "web"


def source_quality_weight(source_type: str) -> float:
    """Return a coarse evidence-quality weight for a source type."""
    return {
        "official_docs": 1.0,
        "paper": 0.95,
        "repository": 0.75,
        "web": 0.6,
        "community": 0.35,
    }.get(source_type, 0.5)


def infer_claim_type(claim: str) -> str:
    """Infer a coarse claim class."""
    lowered = claim.lower()
    if re.search(r"\b(use|recommend|should|prefer|avoid)\b", lowered):
        return "recommendation"
    if re.search(r"\b(because|therefore|suggests|implies|trade-off)\b", lowered):
        return "interpretive"
    return "factual"


def infer_confidence(claim: str) -> str:
    """Infer confidence from explicit wording, else mark unlabeled."""
    for label, pattern in _CONFIDENCE_PATTERNS.items():
        if pattern.search(claim):
            return label
    return "unlabeled"


def infer_support_strength(
    claim: dict[str, Any],
    *,
    matched_citation_count: int,
    matched_source_types: list[str],
) -> str:
    """Infer a coarse support strength label for a claim."""
    confidence = claim.get("confidence", "unlabeled")
    if matched_citation_count >= 2 and any(source == "official_docs" for source in matched_source_types):
        return "strong"
    if matched_citation_count >= 1:
        return "moderate" if confidence in {"high", "medium"} else "basic"
    return "weak" if confidence != "high" else "moderate"


def score_evidence_quality(
    claim: dict[str, Any],
    *,
    matched_citation_count: int,
    matched_source_types: list[str],
    matched_weights: list[float],
) -> float:
    """Score claim evidence quality from 0.0 to 1.0."""
    confidence_bonus = {
        "high": 0.15,
        "medium": 0.1,
        "low": 0.03,
        "unresolved": -0.05,
        "unlabeled": 0.0,
    }.get(claim.get("confidence", "unlabeled"), 0.0)

    if not matched_citation_count:
        return round(max(0.0, 0.15 + confidence_bonus), 2)

    avg_weight = sum(matched_weights) / len(matched_weights) if matched_weights else 0.5
    diversity_bonus = 0.1 if len(set(matched_source_types)) >= 2 else 0.0
    corroboration_bonus = min(0.2, 0.08 * matched_citation_count)
    score = avg_weight * 0.55 + diversity_bonus + corroboration_bonus + confidence_bonus
    return round(min(1.0, max(0.0, score)), 2)


def summarize_evidence_quality(
    claims: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize evidence quality over the run."""
    if not claims:
        return {
            "average_evidence_quality_score": 0.0,
            "claims_with_direct_citations": 0,
            "claims_without_direct_citations": 0,
            "support_strength_counts": {},
            "weak_claim_ids": [],
        }

    scores = [float(link.get("evidence_quality_score", 0.0)) for link in evidence_links]
    support_counts: dict[str, int] = {}
    weak_claim_ids: list[str] = []
    direct = 0
    for link in evidence_links:
        strength = link.get("support_strength", "unknown")
        support_counts[strength] = support_counts.get(strength, 0) + 1
        if link.get("has_direct_citation"):
            direct += 1
        if strength == "weak":
            weak_claim_ids.append(link["claim_id"])

    return {
        "average_evidence_quality_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "claims_with_direct_citations": direct,
        "claims_without_direct_citations": len(claims) - direct,
        "support_strength_counts": support_counts,
        "weak_claim_ids": weak_claim_ids,
    }


def score_research_rubric(
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    *,
    goal: str = "",
    lightweight_mode: bool = False,
) -> dict[str, Any]:
    """Produce a lightweight research-quality rubric from run artifacts."""
    lightweight = lightweight_mode or _is_lightweight_goal(goal)
    synthesis_claims = [claim for claim in claims if claim.get("scope") == "synthesis"]
    if not synthesis_claims:
        return {
            "overall_score": 0.0,
            "grade": "insufficient",
            "dimensions": {
                "evidence_quality": 0.0,
                "citation_coverage": 0.0,
                "source_diversity": 0.0,
                "uncertainty_reporting": 0.0,
                "actionability": 0.0,
                "contradiction_handling": 1.0 if not contradictions else 0.3,
            },
            "summary": {
                "synthesis_claim_count": 0,
                "synthesis_citation_count": 0,
                "contradiction_count": len(contradictions),
                "high_confidence_claims": 0,
                "unresolved_claims": 0,
                "recommendation_claims": 0,
            },
        }

    synthesis_claim_ids = {claim["id"] for claim in synthesis_claims}
    synthesis_citations = [citation for citation in citations if citation.get("scope") == "synthesis"]
    synthesis_links = [link for link in evidence_links if link.get("claim_id") in synthesis_claim_ids]
    synthesis_contradictions = [
        conflict
        for conflict in contradictions
        if conflict.get("left_claim_id") in synthesis_claim_ids
        or conflict.get("right_claim_id") in synthesis_claim_ids
    ]

    average_evidence = (
        sum(float(link.get("evidence_quality_score", 0.0)) for link in synthesis_links) / len(synthesis_links)
        if synthesis_links
        else 0.0
    )
    direct_citation_count = sum(1 for link in synthesis_links if link.get("has_direct_citation"))
    citation_target = max(1, min(len(synthesis_claims), 2 if lightweight else len(synthesis_claims)))
    citation_coverage = direct_citation_count / citation_target if synthesis_claims else 0.0
    source_types = {citation.get("source_type", "web") for citation in synthesis_citations}
    diversity_target = 1 if lightweight else 3
    source_diversity = min(1.0, len(source_types) / diversity_target) if source_types else 0.0

    confidence_labels = [str(claim.get("confidence", "unlabeled")) for claim in synthesis_claims]
    labeled = [label for label in confidence_labels if label != "unlabeled"]
    uncertainty_target = max(1, min(len(synthesis_claims), 2 if lightweight else len(synthesis_claims)))
    uncertainty_reporting = len(labeled) / uncertainty_target if synthesis_claims else 0.0
    recommendation_count = sum(1 for claim in synthesis_claims if claim.get("claim_type") == "recommendation")
    actionability_target = max(1, min(len(synthesis_claims), 3 if lightweight else len(synthesis_claims)))
    actionability = recommendation_count / actionability_target if synthesis_claims else 0.0
    contradiction_handling = max(0.0, 1.0 - min(1.0, len(synthesis_contradictions) / max(1, len(synthesis_claims))))

    dimensions = {
        "evidence_quality": round(average_evidence, 2),
        "citation_coverage": round(min(1.0, citation_coverage), 2),
        "source_diversity": round(min(1.0, source_diversity), 2),
        "uncertainty_reporting": round(min(1.0, uncertainty_reporting), 2),
        "actionability": round(min(1.0, actionability), 2),
        "contradiction_handling": round(contradiction_handling, 2),
    }
    if lightweight:
        weights = {
            "evidence_quality": 0.3,
            "citation_coverage": 0.2,
            "source_diversity": 0.1,
            "uncertainty_reporting": 0.1,
            "actionability": 0.2,
            "contradiction_handling": 0.1,
        }
        overall_score = round(sum(dimensions[key] * weight for key, weight in weights.items()), 2)
    else:
        overall_score = round(sum(dimensions.values()) / len(dimensions), 2)
    if overall_score >= 0.8:
        grade = "strong"
    elif overall_score >= 0.6:
        grade = "good"
    elif overall_score >= 0.4:
        grade = "developing"
    else:
        grade = "insufficient"

    return {
        "overall_score": overall_score,
        "grade": grade,
        "dimensions": dimensions,
        "summary": {
            "synthesis_claim_count": len(synthesis_claims),
            "synthesis_citation_count": len(synthesis_citations),
            "contradiction_count": len(synthesis_contradictions),
            "high_confidence_claims": sum(1 for label in confidence_labels if label == "high"),
            "unresolved_claims": sum(1 for label in confidence_labels if label == "unresolved"),
            "recommendation_claims": recommendation_count,
            "lightweight_mode": lightweight,
        },
    }


def _is_lightweight_goal(goal: str) -> bool:
    """Return True when the goal clearly asks for a short-form deliverable."""
    lowered = goal.lower()
    return any(
        phrase in lowered
        for phrase in (
            "under 100 words",
            "under 150 words",
            "under 200 words",
            "bullet-point list",
            "bullet point list",
            "brief answer",
            "short answer",
            "smoke test",
            "sanity check",
        )
    )


def _iter_claim_candidates(text: str) -> list[str]:
    """Return bullet items and sentences as candidate claims."""
    candidates: list[str] = []
    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            candidates.append(stripped[2:].strip())

    prose = "\n".join(
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith(("#", "- ", "* ", "|", "```"))
    )
    candidates.extend(_SENTENCE_SPLIT.split(prose))
    return candidates


def _recommendation_polarity(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\b(avoid|do not use|don't use)\b", lowered):
        return "negative"
    if re.search(r"\b(recommend|use|prefer|should use)\b", lowered):
        return "positive"
    return ""


def _normalized_recommendation_object(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"\b(recommend|use|prefer|should|avoid|do not|don't)\b", " ", lowered)
    lowered = re.sub(r"[^a-z0-9\s-]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    tokens = [token for token in lowered.split() if token not in {"for", "the", "a", "an", "to", "and", "or"}]
    return " ".join(tokens[:6])
