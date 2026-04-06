"""Tests for src.scorer — heuristic scoring, judge parsing, and helpers."""

import json

import pytest

from src.config import ExecutionConfig, ResearchConfig, ScoringConfig
from src.scorer import (
    IterationScore,
    _extract_section,
    _fuzzy_match,
    combine_scores,
    heuristic_score,
    parse_judge_response,
    quality_score_from_judge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config() -> ResearchConfig:
    return ResearchConfig(
        topic="Compare API gateways",
        goal="Comparison report",
        dimensions=("REST vs HTTP API", "WebSocket API", "Authentication"),
        scoring=ScoringConfig(
            min_dimensions_per_iteration=1,
            target_dimensions_total=3,
            evidence_types=(
                "comparison_table",
                "pricing_data",
                "code_example",
                "trade_off_analysis",
            ),
        ),
    )


RICH_FINDINGS = """\
### Findings

REST API costs $3.50 per million requests while HTTP API costs $1.00.

| Feature | REST API | HTTP API |
|---------|----------|----------|
| Caching | Yes      | No       |
| WAF     | Yes      | No       |

```python
import boto3
client = boto3.client('apigateway')
```

However, the trade-off is that REST API is more expensive.

The architecture of the system involves a flow from client to gateway.

### New Questions

- How does AppSync compare?
- What are WebSocket limits?
- VPC link latency?
"""

MINIMAL_FINDINGS = "Some brief text about APIs."


# ---------------------------------------------------------------------------
# IterationScore
# ---------------------------------------------------------------------------

class TestIterationScore:
    def test_defaults(self):
        s = IterationScore()
        assert s.coverage == 0.0
        assert s.quality == 0.0
        assert s.total == 0.0
        assert s.dimensions_covered == []
        assert s.gaps == []

    def test_has_no_status_property(self):
        """status property was removed — keep/discard is decided by orchestrator."""
        s = IterationScore(total=50.0)
        assert not hasattr(s, "status")


# ---------------------------------------------------------------------------
# _fuzzy_match
# ---------------------------------------------------------------------------

class TestFuzzyMatch:
    def test_match_found(self):
        assert _fuzzy_match("REST vs HTTP API", "The REST API and HTTP API differ")

    def test_no_match(self):
        assert not _fuzzy_match("WebSocket API", "nothing relevant here")

    def test_short_words_ignored(self):
        # Words <= 3 chars are filtered out
        assert not _fuzzy_match("a b c d", "a b c d in the text")

    def test_case_insensitive(self):
        assert _fuzzy_match("Authentication Options", "the authentication options are varied")

    def test_empty_dimension(self):
        assert not _fuzzy_match("", "some text")

    def test_partial_keyword_match(self):
        # Needs at least half of keywords
        assert _fuzzy_match(
            "REST API pricing performance differences",
            "REST API has different pricing tiers",
        )


# ---------------------------------------------------------------------------
# _extract_section
# ---------------------------------------------------------------------------

class TestExtractSection:
    def test_extracts_section(self):
        text = "# Intro\nfoo\n## New Questions\n- Q1\n- Q2\n## Next\nbar"
        result = _extract_section(text, "New Questions")
        assert "Q1" in result
        assert "Q2" in result
        assert "bar" not in result

    def test_missing_section(self):
        assert _extract_section("# Only this heading\ncontent", "Missing") == ""

    def test_section_at_end(self):
        text = "# Intro\nfoo\n## New Questions\n- Q1\n- Q2"
        result = _extract_section(text, "New Questions")
        assert "Q1" in result

    def test_case_insensitive(self):
        text = "## new questions\n- item"
        result = _extract_section(text, "New Questions")
        assert "item" in result


# ---------------------------------------------------------------------------
# heuristic_score
# ---------------------------------------------------------------------------

class TestHeuristicScore:
    def test_rich_findings_scores_high(self, sample_config):
        score = heuristic_score(RICH_FINDINGS, sample_config, [])
        assert score >= 70.0  # has table, pricing, code, trade-off, questions

    def test_minimal_findings_scores_low(self, sample_config):
        score = heuristic_score(MINIMAL_FINDINGS, sample_config, [])
        assert score < 30.0

    def test_empty_findings(self, sample_config):
        score = heuristic_score("", sample_config, [])
        assert score == 0.0

    def test_no_dimensions_configured(self):
        cfg = ResearchConfig(topic="t", goal="g", dimensions=())
        score = heuristic_score(RICH_FINDINGS, cfg, [])
        # Should still get points for evidence, questions, length
        assert score > 0.0

    def test_score_range(self, sample_config):
        score = heuristic_score(RICH_FINDINGS, sample_config, [])
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# parse_judge_response
# ---------------------------------------------------------------------------

class TestParseJudgeResponse:
    def test_plain_json(self):
        raw = '{"depth": 7, "accuracy": 8, "novelty": 6, "actionability": 7, "dimensions_covered": ["REST"], "gaps_identified": ["WebSocket"], "reasoning": "good"}'
        result = parse_judge_response(raw)
        assert result["depth"] == 7
        assert result["accuracy"] == 8
        assert result["dimensions_covered"] == ["REST"]

    def test_fenced_json(self):
        raw = 'Here is my evaluation:\n```json\n{"depth": 5, "accuracy": 5, "novelty": 5, "actionability": 5, "dimensions_covered": [], "gaps_identified": [], "reasoning": "ok"}\n```'
        result = parse_judge_response(raw)
        assert result["depth"] == 5

    def test_json_with_surrounding_text(self):
        raw = 'My analysis: {"depth": 9, "accuracy": 8, "novelty": 7, "actionability": 8, "dimensions_covered": ["A"], "gaps_identified": ["B"], "reasoning": "great"} That is all.'
        result = parse_judge_response(raw)
        assert result["depth"] == 9

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_judge_response("not json at all")

    def test_empty_string_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_judge_response("")


# ---------------------------------------------------------------------------
# quality_score_from_judge
# ---------------------------------------------------------------------------

class TestQualityScoreFromJudge:
    def test_perfect_scores(self):
        judge = {"depth": 10, "accuracy": 10, "novelty": 10, "actionability": 10}
        assert quality_score_from_judge(judge) == 100.0

    def test_minimum_scores(self):
        judge = {"depth": 1, "accuracy": 1, "novelty": 1, "actionability": 1}
        assert quality_score_from_judge(judge) == 10.0

    def test_average_scores(self):
        judge = {"depth": 5, "accuracy": 5, "novelty": 5, "actionability": 5}
        assert quality_score_from_judge(judge) == 50.0

    def test_missing_axes_default_to_5(self):
        judge = {"depth": 10}  # others default to 5
        score = quality_score_from_judge(judge)
        assert score == 62.5  # (10+5+5+5) / 40 * 100

    def test_mixed_scores(self):
        judge = {"depth": 8, "accuracy": 7, "novelty": 9, "actionability": 6}
        expected = round((8 + 7 + 9 + 6) / 40 * 100, 1)
        assert quality_score_from_judge(judge) == expected


# ---------------------------------------------------------------------------
# combine_scores
# ---------------------------------------------------------------------------

class TestCombineScores:
    def test_weights(self):
        assert combine_scores(100.0, 100.0) == 100.0
        assert combine_scores(0.0, 0.0) == 0.0

    def test_coverage_weight_40(self):
        assert combine_scores(100.0, 0.0) == 40.0

    def test_quality_weight_60(self):
        assert combine_scores(0.0, 100.0) == 60.0

    def test_mixed(self):
        result = combine_scores(80.0, 70.0)
        expected = round(0.4 * 80.0 + 0.6 * 70.0, 1)
        assert result == expected
