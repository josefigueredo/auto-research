"""Tests for src.backends.jsonl — parse_jsonl_last_result."""

import json

from src.backends.jsonl import parse_jsonl_last_result


class TestParseJsonlLastResult:
    def test_empty(self):
        resp = parse_jsonl_last_result("")
        assert resp.is_error is True

    def test_single_result(self):
        stdout = json.dumps({"result": "output", "cost_usd": 0.03})
        resp = parse_jsonl_last_result(stdout)
        assert resp.text == "output"
        assert resp.cost_usd == 0.03

    def test_multiple_lines(self):
        lines = [
            json.dumps({"message": "thinking..."}),
            json.dumps({"result": "final answer", "cost_usd": 0.10}),
        ]
        resp = parse_jsonl_last_result("\n".join(lines))
        assert resp.text == "final answer"

    def test_plain_text_fallback(self):
        resp = parse_jsonl_last_result("just plain text")
        assert resp.text == "just plain text"
        assert resp.is_error is False

    def test_codex_agent_message(self):
        stdout = json.dumps({
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "codex reply"},
        })
        resp = parse_jsonl_last_result(stdout)
        assert resp.text == "codex reply"
