import os

import pytest


@pytest.fixture(autouse=True)
def isolated_spec_store(tmp_path):
    """
    Automatically isolate every test's SpecStore to a temporary directory.
    This prevents tests from polluting the main .libspec/libspec.jsonl log.
    """
    test_jsonl = tmp_path / "test_libspec.jsonl"
    os.environ["LIBSPEC_DATABASE_URL"] = f"jsonl://{test_jsonl}"
    yield
    if "LIBSPEC_DATABASE_URL" in os.environ:
        del os.environ["LIBSPEC_DATABASE_URL"]


class _BlockedAgentSubprocess:
    """
    Stand-in for the `subprocess` module inside `libspec.agent_config`
    during tests: simulates every coding-agent CLI being absent, regardless
    of what's actually installed on the host running the suite.
    """

    @staticmethod
    def run(*args, **kwargs):
        raise FileNotFoundError(
            "blocked in tests: real agent CLI subprocess calls are disabled"
        )


@pytest.fixture(autouse=True)
def block_real_agent_cli_calls(monkeypatch):
    """
    `AgentConfig.configure()` implementations (Claude, Gemini, Codex,
    Copilot, Antigravity) shell out to their native CLI via
    `subprocess.run` and, on success, mutate the developer's REAL global
    agent configuration (e.g. `~/.claude.json`). If the corresponding CLI
    happens to be installed on the machine running tests, `cmd_init` and
    `check_and_heal_skills` would trigger real, uncontrolled writes there.

    This patches only the `subprocess` name inside `libspec.agent_config`
    (not the global `subprocess` module, which git/diff code elsewhere
    legitimately needs) so every such call raises `FileNotFoundError` —
    exactly what each `configure()` already treats as "CLI absent" and
    handles via its report-only fallback path.
    """
    import libspec.agent_config as agent_config

    monkeypatch.setattr(agent_config, "subprocess", _BlockedAgentSubprocess)
