"""AI CLI backend abstraction layer.

Provides a uniform interface for invoking AI coding assistants in headless
mode.  Each backend encapsulates the CLI-specific command building, prompt
delivery, and response parsing for one provider.

Supported backends:
- **claude** — Anthropic Claude Code CLI (fully featured)
- **codex** — OpenAI Codex CLI
- **gemini** — Google Gemini CLI
- **copilot** — GitHub Copilot CLI
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("autoresearch")

# Maximum prompt length (chars) before switching to tempfile for
# backends that pass prompts as CLI arguments.
_ARG_PROMPT_LIMIT = 30_000

# Rate limit thresholds (Claude-specific, but defined here for clarity)
RATE_LIMIT_BACKOFF_SECONDS = 120
RATE_LIMIT_WARN_THRESHOLD = 0.80
RATE_LIMIT_COOLDOWN_SECONDS = 30


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

class PromptMode(Enum):
    """How the backend delivers prompts to the CLI process."""

    STDIN = "stdin"
    ARGUMENT = "argument"


@dataclass(frozen=True)
class CallOptions:
    """Options for a single CLI invocation.

    Backends map these to their CLI-specific flags.  Fields that a
    backend does not support are silently ignored.

    Attributes:
        model: Model name (backend-specific, e.g. ``"sonnet"``).
        allowed_tools: Comma-separated tool names to pre-approve.
        max_turns: Maximum agent turns per call.
        max_budget_usd: Per-call budget cap in USD (``0`` = no cap).
        json_schema: Optional JSON schema for structured output.
    """

    model: str = ""
    allowed_tools: str = ""
    max_turns: int = 10
    max_budget_usd: float = 0.0
    json_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class AgentResponse:
    """Result of a single CLI invocation.

    Attributes:
        text: The assistant's text output.
        cost_usd: Cost of this invocation in USD (``0.0`` if the backend
            does not report cost).
        is_error: ``True`` if the invocation failed.
        raw: Backend-specific metadata (rate limit info, session ID, etc.).
    """

    text: str
    cost_usd: float
    is_error: bool
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

VALID_BACKENDS = ("claude", "codex", "gemini", "copilot")

_REGISTRY: dict[str, type[Backend]] = {}


def get_backend(name: str) -> Backend:
    """Instantiate a backend by name.

    Args:
        name: One of ``"claude"``, ``"codex"``, ``"gemini"``, ``"copilot"``.

    Raises:
        ValueError: If the name is not recognised.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown backend '{name}'. Must be one of: {', '.join(VALID_BACKENDS)}"
        )
    return cls()


def get_backends(backend_names: set[str]) -> dict[str, Backend]:
    """Instantiate a set of backends by name, deduplicating instances.

    Args:
        backend_names: Set of backend names to instantiate.

    Returns:
        Mapping of backend name to ``Backend`` instance.  Each name is
        instantiated exactly once.

    Raises:
        ValueError: If any name is not recognised.
    """
    return {name: get_backend(name) for name in backend_names}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class Backend(ABC):
    """Abstract interface for an AI CLI backend."""

    name: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and isinstance(cls.name, str):
            _REGISTRY[cls.name] = cls

    @abstractmethod
    def cli_executable(self) -> str:
        """Return the CLI executable name (e.g. ``"claude"``)."""

    @abstractmethod
    def prompt_mode(self) -> PromptMode:
        """How this backend receives prompts."""

    @abstractmethod
    def build_command(self, opts: CallOptions) -> list[str]:
        """Build the CLI command (without the prompt argument).

        The prompt is delivered separately via stdin or as an appended
        argument, depending on ``prompt_mode()``.
        """

    @abstractmethod
    def parse_response(self, stdout: str) -> AgentResponse:
        """Parse the CLI's stdout into an ``AgentResponse``."""

    def post_invoke(self, stdout: str) -> None:
        """Hook called after a successful invocation for provider-specific
        side effects (e.g. rate limit backoff).  Default is a no-op."""

    def _resolve_executable(self) -> str | None:
        """Resolve the full path to the CLI executable.

        Uses ``shutil.which`` to find ``.cmd``/``.bat`` shims on Windows
        (common for npm-installed CLIs like codex and copilot).
        """
        return shutil.which(self.cli_executable())

    def check_available(self) -> bool:
        """Return ``True`` if the CLI is installed and responds."""
        exe = self._resolve_executable()
        if exe is None:
            return False
        try:
            result = subprocess.run(
                [exe, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _run_process(
        cmd: list[str],
        *,
        input: str | None = None,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess with reliable timeout on Windows.

        On Windows, ``subprocess.run(timeout=...)`` kills the top-level
        shell shim but leaves child ``node`` processes alive.  This helper
        uses ``CREATE_NEW_PROCESS_GROUP`` + ``taskkill /T`` to ensure the
        entire process tree is terminated on timeout.
        """
        kwargs: dict[str, Any] = dict(
            stdin=subprocess.PIPE if input is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(cmd, **kwargs)
        try:
            stdout, stderr = proc.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            # Kill the entire process tree
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                )
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    proc.kill()
            proc.wait()
            raise subprocess.TimeoutExpired(cmd, timeout)

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
        )

    def invoke(self, prompt: str, opts: CallOptions, timeout: int = 300) -> AgentResponse:
        """Run the CLI with *prompt* and return a parsed response.

        Handles prompt delivery (stdin vs argument vs tempfile fallback),
        subprocess execution, timeout, and error codes.
        """
        cmd = self.build_command(opts)
        # Resolve the executable to its full path (handles .cmd/.bat shims on Windows)
        exe = self._resolve_executable()
        if exe and cmd and cmd[0] == self.cli_executable():
            cmd[0] = exe

        stdin_input: str | None = None

        if self.prompt_mode() == PromptMode.STDIN:
            stdin_input = prompt
        else:
            if len(prompt) > _ARG_PROMPT_LIMIT:
                return self._invoke_via_tempfile(prompt, cmd, timeout)
            cmd.append(prompt)

        log.debug(
            "%s CLI: %s (prompt: %d chars)",
            self.name,
            " ".join(cmd[:6]),
            len(prompt),
        )

        try:
            result = self._run_process(cmd, input=stdin_input, timeout=timeout)
        except subprocess.TimeoutExpired:
            log.warning("%s CLI timed out after %ds.", self.name, timeout)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        if result.returncode != 0:
            self._handle_error(result)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        response = self.parse_response(result.stdout)
        self.post_invoke(result.stdout)
        return response

    # -- Private helpers ---------------------------------------------------

    def _invoke_via_tempfile(
        self, prompt: str, base_cmd: list[str], timeout: int
    ) -> AgentResponse:
        """Write the prompt to a temp file and pass the path as the last arg."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(prompt)
            tmp_path = f.name

        try:
            cmd = base_cmd + [f"@{tmp_path}"]
            log.debug(
                "%s CLI (tempfile): %s (prompt: %d chars → %s)",
                self.name,
                " ".join(cmd[:6]),
                len(prompt),
                tmp_path,
            )

            result = self._run_process(cmd, timeout=timeout)

            if result.returncode != 0:
                self._handle_error(result)
                return AgentResponse(text="", cost_usd=0.0, is_error=True)

            response = self.parse_response(result.stdout)
            self.post_invoke(result.stdout)
            return response

        except subprocess.TimeoutExpired:
            log.warning("%s CLI timed out after %ds.", self.name, timeout)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _handle_error(self, result: subprocess.CompletedProcess[str]) -> None:
        """Log an error from a failed CLI invocation."""
        stderr = result.stderr.strip()
        log.error(
            "%s CLI failed (rc=%d): %s",
            self.name,
            result.returncode,
            stderr or "(empty stderr)",
        )
        if result.stdout:
            log.debug("%s CLI stdout (last 1000 chars): %s", self.name, result.stdout[-1000:])


# ---------------------------------------------------------------------------
# Claude backend
# ---------------------------------------------------------------------------

class ClaudeBackend(Backend):
    """Anthropic Claude Code CLI backend.

    Fully featured: stdin prompt delivery, JSON output, per-call budget
    and turn limits, rate limit detection with automatic backoff.
    """

    name = "claude"

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
        for event in reversed(payload):
            if isinstance(event, dict) and event.get("type") == "result":
                text = event.get("result", "")
                cost = event.get("total_cost_usd", event.get("cost_usd", 0.0))
                break

        return AgentResponse(text=text, cost_usd=cost, is_error=False)

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
        """Try to extract a usable result from a failed Claude CLI call.

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
                        errors = event.get("errors", [])
                        if errors:
                            log.warning("Claude CLI completed with errors: %s", errors)
                        return AgentResponse(text=text, cost_usd=cost, is_error=False)
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    def invoke(self, prompt: str, opts: CallOptions, timeout: int = 300) -> AgentResponse:
        """Claude-specific invoke that salvages results from budget-exceeded calls."""
        cmd = self.build_command(opts)
        exe = self._resolve_executable()
        if exe and cmd and cmd[0] == self.cli_executable():
            cmd[0] = exe

        log.debug(
            "%s CLI: %s (prompt: %d chars)",
            self.name,
            " ".join(cmd[:6]),
            len(prompt),
        )

        try:
            result = self._run_process(cmd, input=prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            log.warning("%s CLI timed out after %ds.", self.name, timeout)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        if result.returncode != 0:
            # Try to salvage a result (e.g. budget exceeded but output exists)
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


# ---------------------------------------------------------------------------
# Codex backend
# ---------------------------------------------------------------------------

_CLAUDE_SHORTNAMES = {"sonnet", "opus", "haiku"}


class CodexBackend(Backend):
    """OpenAI Codex CLI backend.

    Supports stdin prompt delivery and JSONL output.  Budget and turn
    limits are configured globally (not per-call).
    """

    name = "codex"

    def cli_executable(self) -> str:
        return "codex"

    def prompt_mode(self) -> PromptMode:
        return PromptMode.STDIN

    def build_command(self, opts: CallOptions) -> list[str]:
        cmd = ["codex", "exec", "--json"]
        if opts.model and opts.model not in _CLAUDE_SHORTNAMES:
            cmd.extend(["--model", opts.model])
        if opts.allowed_tools:
            cmd.extend(["--sandbox", "workspace-write"])
            cmd.append("--full-auto")
        else:
            cmd.extend(["--sandbox", "read-only"])
        return cmd

    def parse_response(self, stdout: str) -> AgentResponse:
        return _parse_jsonl_last_result(stdout, cost_key="cost_usd")


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

class GeminiBackend(Backend):
    """Google Gemini CLI backend.

    Uses stdin for prompt delivery with ``-p ""``.  The ``-p`` flag
    triggers headless mode while stdin provides the actual prompt text.
    """

    name = "gemini"

    def cli_executable(self) -> str:
        return "gemini"

    def prompt_mode(self) -> PromptMode:
        return PromptMode.STDIN

    def build_command(self, opts: CallOptions) -> list[str]:
        cmd = ["gemini", "-p", ""]
        if opts.model and opts.model not in _CLAUDE_SHORTNAMES:
            cmd.extend(["--model", opts.model])
        cmd.extend(["--output-format", "json"])
        if opts.allowed_tools:
            cmd.append("--yolo")
        return cmd

    def parse_response(self, stdout: str) -> AgentResponse:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return AgentResponse(text=stdout, cost_usd=0.0, is_error=False)

        if isinstance(payload, dict):
            return AgentResponse(
                text=payload.get("response", payload.get("result", "")),
                cost_usd=0.0,
                is_error=payload.get("error") is not None,
            )

        return _parse_jsonl_last_result(stdout, cost_key="cost_usd")


# ---------------------------------------------------------------------------
# Copilot backend
# ---------------------------------------------------------------------------

class CopilotBackend(Backend):
    """GitHub Copilot CLI backend.

    Prompts are passed as CLI arguments (stdin not supported).  For long
    prompts, a tempfile fallback is used.  Budget caps are not available.
    """

    name = "copilot"

    def cli_executable(self) -> str:
        return "copilot"

    def prompt_mode(self) -> PromptMode:
        return PromptMode.ARGUMENT

    def build_command(self, opts: CallOptions) -> list[str]:
        cmd = ["copilot", "-p"]
        if opts.model and opts.model not in _CLAUDE_SHORTNAMES:
            cmd.extend(["--model", opts.model])
        cmd.extend(["--output-format", "json", "--silent"])
        if opts.allowed_tools:
            cmd.append("--allow-all")
        cmd.append("--autopilot")
        if opts.max_turns > 0:
            cmd.extend(["--max-autopilot-continues", str(opts.max_turns)])
        return cmd

    def parse_response(self, stdout: str) -> AgentResponse:
        return _parse_jsonl_last_result(stdout, cost_key="cost_usd")


# ---------------------------------------------------------------------------
# JSONL parsing helper
# ---------------------------------------------------------------------------

def _parse_jsonl_last_result(stdout: str, *, cost_key: str = "cost_usd") -> AgentResponse:
    """Parse JSONL output, returning the last agent message or result.

    Handles multiple JSONL formats:
    - Codex: ``item.completed`` events with ``item.text``
    - Generic: events with ``result``, ``response``, or ``message`` keys
    - Single JSON objects

    Falls back to raw text if no structured data is found.
    """
    if not stdout.strip():
        return AgentResponse(text="", cost_usd=0.0, is_error=True)

    lines = stdout.strip().splitlines()
    last_text = ""
    cost = 0.0

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

            # Codex usage event
            if obj.get("type") == "turn.completed":
                usage = obj.get("usage", {})
                # Codex doesn't report cost directly
                continue

            # Generic: top-level result/response/message
            text = obj.get("result", obj.get("response", obj.get("message", "")))
            if text and obj.get("type") not in ("error", "turn.failed"):
                last_text = text
                cost = obj.get(cost_key, obj.get("total_cost_usd", 0.0))
                break
        except json.JSONDecodeError:
            continue

    if not last_text:
        return AgentResponse(text=stdout.strip(), cost_usd=0.0, is_error=False)

    return AgentResponse(text=last_text, cost_usd=cost, is_error=False)
