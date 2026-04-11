"""Abstract base class for AI CLI backends."""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode

log = logging.getLogger("autoresearch")

# Maximum prompt length (chars) before switching to tempfile for
# backends that pass prompts as CLI arguments.
_ARG_PROMPT_LIMIT = 30_000


class Backend(ABC):
    """Abstract interface for an AI CLI backend.

    Subclasses auto-register in the global registry via ``__init_subclass__``.
    """

    name: str
    capabilities: BackendCapabilities = BackendCapabilities()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "name") and isinstance(cls.name, str):
            from .registry import _register
            _register(cls.name, cls)

    @abstractmethod
    def cli_executable(self) -> str:
        """Return the CLI executable name (e.g. ``"claude"``)."""

    @abstractmethod
    def prompt_mode(self) -> PromptMode:
        """How this backend receives prompts."""

    @abstractmethod
    def build_command(self, opts: CallOptions) -> list[str]:
        """Build the CLI command (without the prompt argument)."""

    @abstractmethod
    def parse_response(self, stdout: str) -> AgentResponse:
        """Parse the CLI's stdout into an ``AgentResponse``."""

    def post_invoke(self, stdout: str) -> None:
        """Hook called after a successful invocation.  Default is a no-op."""

    def _resolve_executable(self) -> str | None:
        """Resolve the full path to the CLI executable.

        Uses ``shutil.which`` to find ``.cmd``/``.bat`` shims on Windows.
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
    def build_process_env(*, sanitize: bool) -> dict[str, str] | None:
        """Return a sanitized subprocess environment when requested."""
        if not sanitize:
            return None

        keep = {
            "PATH",
            "PATHEXT",
            "SYSTEMROOT",
            "SYSTEMDRIVE",
            "WINDIR",
            "COMSPEC",
            "HOME",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
            "APPDATA",
            "LOCALAPPDATA",
            "PROGRAMDATA",
            "TEMP",
            "TMP",
            "TMPDIR",
            "LANG",
            "LC_ALL",
            "TERM",
            "NO_COLOR",
            "FORCE_COLOR",
            "SSL_CERT_FILE",
            "REQUESTS_CA_BUNDLE",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "USERNAME",
            "USER",
            "LOGNAME",
            "SHELL",
            "NUMBER_OF_PROCESSORS",
            "OS",
            "PROCESSOR_ARCHITECTURE",
            "PROCESSOR_IDENTIFIER",
            "PROCESSOR_LEVEL",
            "PROCESSOR_REVISION",
            "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME",
            "XDG_DATA_HOME",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GITHUB_TOKEN",
            "GH_TOKEN",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "COPILOT_TOKEN",
        }
        # Windows env var names are case-insensitive at the OS level but
        # Python's os.environ preserves whatever case Windows reports (usually
        # uppercase).  Match case-insensitively so the keep list survives
        # regardless of how each variable is actually stored.
        keep_upper = {k.upper() for k in keep}
        return {
            key: value
            for key, value in os.environ.items()
            if key.upper() in keep_upper
        }

    @staticmethod
    def _run_process(
        cmd: list[str],
        *,
        input: str | None = None,
        timeout: int = 300,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
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
            cwd=cwd,
            env=env,
        )
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(cmd, **kwargs)
        try:
            stdout_data, stderr_data = proc.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                kill_result = subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                )
                if kill_result.returncode != 0:
                    log.warning(
                        "taskkill failed for PID %d (rc=%d), falling back to proc.kill().",
                        proc.pid, kill_result.returncode,
                    )
                    try:
                        proc.kill()
                    except OSError:
                        pass
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
            stdout=stdout_data or "",
            stderr=stderr_data or "",
        )

    def invoke(self, prompt: str, opts: CallOptions, timeout: int = 300) -> AgentResponse:
        """Run the CLI with *prompt* and return a parsed response."""
        cmd = self.build_command(opts)
        exe = self._resolve_executable()
        if exe and cmd and cmd[0] == self.cli_executable():
            cmd[0] = exe

        stdin_input: str | None = None
        env = self.build_process_env(sanitize=opts.sanitize_environment)
        cwd = opts.working_directory or None

        if self.prompt_mode() == PromptMode.STDIN:
            stdin_input = prompt
        else:
            if len(prompt) > _ARG_PROMPT_LIMIT:
                return self._invoke_via_tempfile(prompt, cmd, timeout, cwd=cwd, env=env)
            cmd.append(prompt)

        log.debug(
            "%s CLI: %s (prompt: %d chars)",
            self.name, " ".join(cmd[:6]), len(prompt),
        )

        try:
            result = self._run_process(cmd, input=stdin_input, timeout=timeout, cwd=cwd, env=env)
        except subprocess.TimeoutExpired:
            log.warning("%s CLI timed out after %ds.", self.name, timeout)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        if result.returncode != 0:
            self._handle_error(result)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        response = self.parse_response(result.stdout)
        self.post_invoke(result.stdout)
        return response

    def _invoke_via_tempfile(
        self, prompt: str, base_cmd: list[str], timeout: int, *, cwd: str | None = None, env: dict[str, str] | None = None
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
                "%s CLI (tempfile): %s (prompt: %d chars -> %s)",
                self.name, " ".join(cmd[:6]), len(prompt), tmp_path,
            )

            result = self._run_process(cmd, timeout=timeout, cwd=cwd, env=env)

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
            self.name, result.returncode, stderr or "(empty stderr)",
        )
        if result.stdout:
            log.debug("%s CLI stdout (last 1000 chars): %s", self.name, result.stdout[-1000:])
