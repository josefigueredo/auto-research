"""OpenAI Codex CLI backend.

Supports stdin prompt delivery and JSONL output.  Budget and turn
limits are configured globally (not per-call).
"""

from __future__ import annotations

from .base import Backend
from .jsonl import parse_jsonl_last_result
from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode


class CodexBackend(Backend):

    name = "codex"
    capabilities = BackendCapabilities(
        default_model="o4-mini",
    )

    def cli_executable(self) -> str:
        return "codex"

    def prompt_mode(self) -> PromptMode:
        return PromptMode.STDIN

    def build_command(self, opts: CallOptions) -> list[str]:
        cmd = ["codex", "exec", "--json"]
        if opts.model:
            cmd.extend(["--model", opts.model])
        if opts.allowed_tools:
            cmd.extend(["--sandbox", "workspace-write"])
            cmd.append("--full-auto")
        else:
            cmd.extend(["--sandbox", "read-only"])
        return cmd

    def parse_response(self, stdout: str) -> AgentResponse:
        return parse_jsonl_last_result(stdout, cost_key="cost_usd")
