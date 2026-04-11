"""Anthropic Claude Code CLI backend.

Fully featured: stdin prompt delivery, JSON output, per-call budget
and turn limits, rate limit detection with automatic backoff, result
salvage from budget-exceeded calls.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time

from .base import Backend
from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode

log = logging.getLogger("autoresearch")

RATE_LIMIT_BACKOFF_SECONDS = 120
RATE_LIMIT_WARN_THRESHOLD = 0.80
RATE_LIMIT_COOLDOWN_SECONDS = 30


class ClaudeBackend(Backend):

    name = "claude"
    capabilities = BackendCapabilities(
        supports_json_schema=True,
        supports_budget_cap=True,
        supports_rate_limit_detection=True,
        default_model="sonnet",
    )

    def cli_executable(self) -> str:
        return "claude"

    def prompt_mode(self) -> PromptMode:
        return PromptMode.STDIN

    def build_command(self, opts: CallOptions) -> list[str]:
        cmd = ["claude", "-p", "-", "--output-format", "json"]
        if opts.model:
            cmd.extend(["--model", opts.model])
        if opts.max_budget_usd > 0:
            cmd.extend(["--max-budget-usd", str(opts.max_budget_usd)])
        if opts.allowed_tools:
            cmd.extend(["--allowedTools", opts.allowed_tools])
        if opts.max_turns > 0:
            cmd.extend(["--max-turns", str(opts.max_turns)])
        if opts.json_schema:
            cmd.extend(["--json-schema", json.dumps(opts.json_schema)])
        return cmd

    def parse_response(self, stdout: str) -> AgentResponse:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return AgentResponse(text=stdout, cost_usd=0.0, is_error=False)

        if isinstance(payload, dict):
            return AgentResponse(
                text=payload.get("result", ""),
                cost_usd=payload.get("cost_usd", 0.0),
                is_error=payload.get("is_error", False),
            )

        # Array format: find the last "result" event.
        text = ""
        cost = 0.0
        in_tok = 0
        out_tok = 0
        for event in reversed(payload):
            if isinstance(event, dict) and event.get("type") == "result":
                text = event.get("result", "")
                cost = event.get("total_cost_usd", event.get("cost_usd", 0.0))
                usage = event.get("usage", {})
                in_tok = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                out_tok = usage.get("output_tokens", 0)
                break

        return AgentResponse(text=text, cost_usd=cost, is_error=False, input_tokens=in_tok, output_tokens=out_tok)

    def post_invoke(self, stdout: str) -> None:
        """Proactive rate limit backoff on successful responses."""
        utilization = self._extract_utilization(stdout)
        if utilization >= RATE_LIMIT_WARN_THRESHOLD:
            wait = RATE_LIMIT_BACKOFF_SECONDS if utilization >= 0.90 else RATE_LIMIT_COOLDOWN_SECONDS
            log.info("Rate limit at %.0f%%, cooling down %ds...", utilization * 100, wait)
            time.sleep(wait)

    def _handle_error(self, result: subprocess.CompletedProcess[str]) -> None:
        """Handle Claude CLI errors with rate limit detection."""
        rate_wait = self._check_rate_limit(result.stdout)
        if rate_wait > 0:
            log.warning("Rate limited. Waiting %d seconds...", rate_wait)
            time.sleep(rate_wait)
        else:
            super()._handle_error(result)

    def _try_salvage_response(self, stdout: str) -> AgentResponse | None:
        """Try to extract a usable result from a failed CLI call.

        The CLI returns rc=1 on budget exceeded but the JSON output may
        still contain a partial result that is usable.
        """
        if not stdout:
            return None
        try:
            payload = json.loads(stdout)
            if not isinstance(payload, list):
                return None
            for event in reversed(payload):
                if isinstance(event, dict) and event.get("type") == "result":
                    text = event.get("result", "")
                    if text:
                        cost = event.get("total_cost_usd", 0.0)
                        usage = event.get("usage", {})
                        in_tok = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                        out_tok = usage.get("output_tokens", 0)
                        errors = event.get("errors", [])
                        if errors:
                            log.warning("Claude CLI completed with errors: %s", errors)
                        return AgentResponse(text=text, cost_usd=cost, is_error=False, input_tokens=in_tok, output_tokens=out_tok)
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    def invoke(self, prompt: str, opts: CallOptions, timeout: int = 300) -> AgentResponse:
        """Claude-specific invoke that salvages results from budget-exceeded calls."""
        cmd = self.build_command(opts)
        exe = self._resolve_executable()
        if exe and cmd and cmd[0] == self.cli_executable():
            cmd[0] = exe
        env = self.build_process_env(sanitize=opts.sanitize_environment)
        cwd = opts.working_directory or None

        log.debug(
            "%s CLI: %s (prompt: %d chars)",
            self.name, " ".join(cmd[:6]), len(prompt),
        )

        try:
            result = self._run_process(cmd, input=prompt, timeout=timeout, cwd=cwd, env=env)
        except subprocess.TimeoutExpired:
            log.warning("%s CLI timed out after %ds.", self.name, timeout)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        if result.returncode != 0:
            salvaged = self._try_salvage_response(result.stdout)
            if salvaged is not None:
                log.info("Salvaged result from failed CLI call (rc=%d).", result.returncode)
                self.post_invoke(result.stdout)
                return salvaged
            self._handle_error(result)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        response = self.parse_response(result.stdout)
        self.post_invoke(result.stdout)
        return response

    @staticmethod
    def _check_rate_limit(stdout: str) -> int:
        """Return seconds to wait if rate limited, else ``0``."""
        if not stdout:
            return 0
        try:
            payload = json.loads(stdout)
            events = payload if isinstance(payload, list) else [payload]
            for event in events:
                if not isinstance(event, dict):
                    continue
                if event.get("type") == "rate_limit_event":
                    info = event.get("rate_limit_info", {})
                    utilization = info.get("utilization", 0)
                    if utilization >= 0.90:
                        return RATE_LIMIT_BACKOFF_SECONDS
                    if utilization >= RATE_LIMIT_WARN_THRESHOLD:
                        return RATE_LIMIT_COOLDOWN_SECONDS
        except (json.JSONDecodeError, TypeError):
            pass
        return 0

    @staticmethod
    def _extract_utilization(stdout: str) -> float:
        """Extract rate limit utilization from Claude CLI output."""
        if not stdout:
            return 0.0
        try:
            payload = json.loads(stdout)
            events = payload if isinstance(payload, list) else [payload]
            for event in events:
                if isinstance(event, dict) and event.get("type") == "rate_limit_event":
                    return event.get("rate_limit_info", {}).get("utilization", 0.0)
        except (json.JSONDecodeError, TypeError):
            pass
        return 0.0
