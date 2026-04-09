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
        for url in claim.get("cited_urls", []):
            citation = citation_by_url.get(url)
            if citation:
                matched_ids.append(citation["id"])
                matched_types.append(citation["source_type"])

        support_strength = infer_support_strength(
            claim,
            matched_citation_count=len(matched_ids),
            matched_source_types=matched_types,
        )
        links.append(
            {
                "claim_id": claim["id"],
                "citation_ids": matched_ids,
                "support_strength": support_strength,
                "has_direct_citation": bool(matched_ids),
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
