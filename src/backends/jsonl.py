"""Shared JSONL parsing helper for backends that emit newline-delimited JSON."""

from __future__ import annotations

import json

from .types import AgentResponse


def parse_jsonl_last_result(stdout: str, *, cost_key: str = "cost_usd") -> AgentResponse:
    """Parse JSONL output, returning the last agent message or result.

    Handles multiple JSONL formats:
    - Codex: ``item.completed`` events with ``item.text``
    - Generic: events with ``result``, ``response``, or ``message`` keys

    Falls back to raw text if no structured data is found.
    """
    if not stdout.strip():
        return AgentResponse(text="", cost_usd=0.0, is_error=True)

    lines = stdout.strip().splitlines()
    last_text = ""
    cost = 0.0
    in_tok = 0
    out_tok = 0

    # Forward pass: accumulate token counts from usage events.
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("type") == "turn.completed":
                usage = obj.get("usage", {})
                in_tok += usage.get("input_tokens", 0) + usage.get("cached_input_tokens", 0)
                out_tok += usage.get("output_tokens", 0)
        except json.JSONDecodeError:
            continue

    # Reverse pass: find the last text result.
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue

            # Codex format: {"type": "item.completed", "item": {"text": "..."}}
            item = obj.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text", "")
                if text:
                    last_text = text
                    break

            # Generic: top-level result/response/message
            text = obj.get("result", obj.get("response", obj.get("message", "")))
            if text and obj.get("type") not in ("error", "turn.failed"):
                last_text = text
                cost = obj.get(cost_key, obj.get("total_cost_usd", 0.0))
                break
        except json.JSONDecodeError:
            continue

    if not last_text:
        return AgentResponse(text=stdout.strip(), cost_usd=0.0, is_error=False, input_tokens=in_tok, output_tokens=out_tok)

    return AgentResponse(text=last_text, cost_usd=cost, is_error=False, input_tokens=in_tok, output_tokens=out_tok)
