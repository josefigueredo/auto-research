"""GitHub Copilot CLI backend.

Prompts are passed as CLI arguments (stdin not supported).  For long
prompts, a tempfile fallback is used.  Budget caps are not available.
"""

from __future__ import annotations

from .base import Backend
from .jsonl import parse_jsonl_last_result
from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode


class CopilotBackend(Backend):

    name = "copilot"
    capabilities = BackendCapabilities(
        default_model="claude-sonnet-4-6",
    )

    def cli_executable(self) -> str:
        return "copilot"

    def prompt_mode(self) -> PromptMode:
        return PromptMode.ARGUMENT

    def build_command(self, opts: CallOptions) -> list[str]:
        cmd = ["copilot", "-p"]
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
        return parse_jsonl_last_result(stdout, cost_key="cost_usd")
