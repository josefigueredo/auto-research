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
