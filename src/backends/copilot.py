"""GitHub Copilot CLI backend.

Supports stdin prompt delivery (``-p -``), JSONL output, and autopilot
mode with configurable turn limits.  Budget caps are not available.
"""

from __future__ import annotations

import json
import logging

from .base import Backend
from .jsonl import parse_jsonl_last_result
from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode

log = logging.getLogger("autoresearch")


class CopilotBackend(Backend):

    name = "copilot"
    capabilities = BackendCapabilities(
        default_model="gpt-4.1",
    )

    def cli_executable(self) -> str:
        return "copilot"

    def prompt_mode(self) -> PromptMode:
        return PromptMode.STDIN

    def build_command(self, opts: CallOptions) -> list[str]:
        cmd = ["copilot", "-p", "-"]
        if opts.model:
            cmd.extend(["--model", opts.model])
        cmd.extend(["--output-format", "json", "--silent"])
        if opts.allowed_tools:
            cmd.append("--allow-all")
        cmd.append("--autopilot")
        if opts.max_turns > 0:
            cmd.extend(["--max-autopilot-continues", str(opts.max_turns)])
        return cmd

    def parse_response(self, stdout: str) -> AgentResponse:
        """Parse Copilot JSONL output.

        Copilot emits JSONL with ``assistant.message`` events containing
        a ``data.content`` field, and a final ``result`` event with usage.
        """
        if not stdout.strip():
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        lines = stdout.strip().splitlines()
        last_text = ""

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue

                # Copilot format: {"type": "assistant.message", "data": {"content": "..."}}
                if obj.get("type") == "assistant.message":
                    data = obj.get("data", {})
                    content = data.get("content", "")
                    if content:
                        last_text = content
                        break

            except json.JSONDecodeError:
                continue

        if not last_text:
            # Fallback to generic JSONL parser
            return parse_jsonl_last_result(stdout, cost_key="cost_usd")

        return AgentResponse(text=last_text, cost_usd=0.0, is_error=False)
