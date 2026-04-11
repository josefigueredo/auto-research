"""Tests for backend isolation helpers."""

from src.backends.base import Backend
from src.config import ExecutionConfig, ResearchConfig, ScoringConfig
from src.orchestrator import AutoResearcher


class StubBackend(Backend):
    name = "stub-isolation"

    def cli_executable(self) -> str:
        return "stub"

    def prompt_mode(self):
        from src.backends import PromptMode

        return PromptMode.STDIN

    def build_command(self, opts):
        return ["stub"]

    def parse_response(self, stdout):
        from src.backends import AgentResponse

        return AgentResponse(text=stdout, cost_usd=0.0, is_error=False)

    def check_available(self) -> bool:
        return True

    def invoke(self, prompt, opts, timeout=300):
        from src.backends import AgentResponse

        return AgentResponse(text="ok", cost_usd=0.0, is_error=False)


def test_sanitized_env_preserves_essentials_and_drops_noise(monkeypatch):
    monkeypatch.setenv("PATH", "C:\\bin")
    monkeypatch.setenv("HOME", "C:\\Users\\me")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("MCP_SERVER_URL", "http://example")
    monkeypatch.setenv("CODEX_HOME", "C:\\custom-codex")

    env = Backend.build_process_env(sanitize=True)
    assert env is not None
    assert env["PATH"] == "C:\\bin"
    assert env["HOME"] == "C:\\Users\\me"
    assert env["OPENAI_API_KEY"] == "secret"
    assert "MCP_SERVER_URL" not in env
    assert "CODEX_HOME" not in env


def test_unsanitized_env_returns_none():
    assert Backend.build_process_env(sanitize=False) is None


def test_sanitized_env_preserves_systemroot_regardless_of_case(monkeypatch):
    """Regression: Windows reports %SYSTEMROOT% in uppercase, so the keep
    list must match case-insensitively — otherwise dnsapi.dll fails to
    initialize in child processes and DNS lookups return os error 11003.
    """
    # Clear any case variants that may already be present
    for variant in ("SystemRoot", "SYSTEMROOT", "systemroot"):
        monkeypatch.delenv(variant, raising=False)
    monkeypatch.setenv("SYSTEMROOT", "C:\\Windows")

    env = Backend.build_process_env(sanitize=True)
    assert env is not None
    assert env.get("SYSTEMROOT") == "C:\\Windows"


def test_sanitized_env_keep_list_is_case_insensitive(monkeypatch):
    """Any case variant of a keep-list entry must survive sanitization.

    Windows stores env var names uppercase in ``os.environ`` regardless of
    the case used at set-time, so the filter must compare case-insensitively
    to preserve variables listed in the keep set as camelCase.
    """
    for variant in ("ComSpec", "COMSPEC", "comspec"):
        monkeypatch.delenv(variant, raising=False)
    monkeypatch.setenv("ComSpec", "C:\\Windows\\system32\\cmd.exe")

    env = Backend.build_process_env(sanitize=True)
    assert env is not None
    # Match case-insensitively — the key survives, whatever case Windows used.
    matched = {k.upper(): v for k, v in env.items()}
    assert matched.get("COMSPEC") == "C:\\Windows\\system32\\cmd.exe"


def test_orchestrator_only_isolates_compatible_backends(tmp_path):
    backend = StubBackend()
    cfg = ResearchConfig(
        topic="Topic",
        goal="Goal",
        dimensions=("DX",),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(
            isolate_backend_context=True,
            sanitize_backend_env=True,
        ),
    )
    researcher = AutoResearcher(config=cfg, backend=backend, output_dir=tmp_path / "output")
    assert researcher._should_isolate_backend(backend) is True

    from src.backends.claude import ClaudeBackend

    claude = ClaudeBackend()
    assert researcher._should_isolate_backend(claude) is False
