import os

from libspec.agent_config import (
    AGENTS_MD_POINTER_MARKER,
    ensure_agents_md_pointer,
    get_agent_config,
    list_supported_agents,
)


def test_list_supported_agents():
    res = list_supported_agents()
    assert "antigravity" in res.lower()
    assert "gemini" in res.lower()


def test_antigravity_render_skill(tmp_path):
    config = get_agent_config("antigravity", str(tmp_path))
    skill_content = config._render_skill()

    assert skill_content is not None
    assert "antigravity" in skill_content
    assert "Antigravity" in skill_content
    assert "Navigation" in skill_content


def test_skill_drift_and_auto_heal(tmp_path):
    # Setup paths for an active agent (e.g. gemini config path)
    gemini_dir = tmp_path / ".gemini"
    gemini_dir.mkdir(parents=True, exist_ok=True)
    settings_file = gemini_dir / "settings.json"
    with open(settings_file, "w") as f:
        f.write("{}")

    config = get_agent_config("gemini", str(tmp_path))
    assert config.is_active is True

    # Initially the skill should not be up-to-date since it doesn't exist
    assert config.is_skill_up_to_date() is False

    # Run check_and_heal_skills to trigger auto-healing
    from libspec.agent_config import check_and_heal_skills

    messages = check_and_heal_skills(str(tmp_path), auto_heal=True)
    assert any("Auto-healed" in m and "gemini" in m for m in messages)

    # Now the skill should be up-to-date
    assert config.is_skill_up_to_date() is True

    # Mutate/corrupt the skill file to simulate drift
    skill_file = gemini_dir / "skills" / "libspec" / "SKILL.md"
    assert skill_file.exists()
    with open(skill_file, "w") as f:
        f.write("outdated skill content")

    assert config.is_skill_up_to_date() is False

    # Check and heal without auto_heal should only warn
    messages = check_and_heal_skills(str(tmp_path), auto_heal=False)
    assert any("Warning: Skill for agent 'gemini' is outdated" in m for m in messages)
    assert config.is_skill_up_to_date() is False

    # Run with auto_heal to restore it
    messages = check_and_heal_skills(str(tmp_path), auto_heal=True)
    assert any("Auto-healed" in m and "gemini" in m for m in messages)
    assert config.is_skill_up_to_date() is True


def test_agents_config_discovery_and_healing(tmp_path):
    from libspec.agent_config import check_and_heal_skills

    res = list_supported_agents()
    assert "agents" in res.lower()

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    config = get_agent_config("agents", str(tmp_path))
    assert config.is_active is True
    assert config.is_skill_up_to_date() is False

    messages = check_and_heal_skills(str(tmp_path), auto_heal=True)
    assert any("Auto-healed" in m and "agents" in m for m in messages)
    assert config.is_skill_up_to_date() is True

    skill_file = agents_dir / "skills" / "libspec" / "SKILL.md"
    assert skill_file.exists()

    # Verify custom opt-out directive disables auto-heal
    with open(skill_file, "w") as f:
        f.write("# libspec: disable-auto-heal\nCustom skill content")

    assert config.is_skill_up_to_date() is True


def test_ensure_agents_md_pointer_creates_file(tmp_path):
    # spec.agents.AgentsMdCreateOrAppendReq
    msg = ensure_agents_md_pointer(str(tmp_path))
    agents_md = tmp_path / "AGENTS.md"

    assert agents_md.exists()
    content = agents_md.read_text()
    assert AGENTS_MD_POINTER_MARKER in content
    assert ".agents/skills/libspec/SKILL.md" in content
    assert "Created" in msg


def test_ensure_agents_md_pointer_appends_without_disturbing_existing_content(
    tmp_path,
):
    # spec.agents.AgentsMdPointerReq
    # spec.agents.AgentsMdCreateOrAppendReq
    agents_md = tmp_path / "AGENTS.md"
    existing = "# My Project\n\nSome pre-existing instructions for agents.\n"
    agents_md.write_text(existing)

    msg = ensure_agents_md_pointer(str(tmp_path))
    content = agents_md.read_text()

    assert content.startswith(existing)
    assert AGENTS_MD_POINTER_MARKER in content
    assert "Appended" in msg

    # Re-running must be idempotent: no second pointer section appended.
    msg2 = ensure_agents_md_pointer(str(tmp_path))
    content2 = agents_md.read_text()
    assert content2.count(AGENTS_MD_POINTER_MARKER) == 2  # opening + closing marker
    assert "already contains" in msg2


def test_agents_config_configure_wires_agents_md_pointer(tmp_path):
    # spec.agents.AgentsMdPointerReq: AgentsConfig.configure() must ensure
    # the pointer exists, not just install the .agents skill.
    config = get_agent_config("agents", str(tmp_path))
    config.configure()

    agents_md = tmp_path / "AGENTS.md"
    assert agents_md.exists()
    assert AGENTS_MD_POINTER_MARKER in agents_md.read_text()


def test_cli_binary_name_mapping(tmp_path):
    # spec.cli.AgentCliPresenceSignalReq
    assert get_agent_config("claude", str(tmp_path)).cli_binary_name == "claude"
    assert get_agent_config("gemini", str(tmp_path)).cli_binary_name == "gemini"
    assert get_agent_config("codex", str(tmp_path)).cli_binary_name == "codex"
    assert get_agent_config("opencode", str(tmp_path)).cli_binary_name == "opencode"
    assert get_agent_config("copilot", str(tmp_path)).cli_binary_name == "copilot"
    assert (
        get_agent_config("antigravity", str(tmp_path)).cli_binary_name == "antigravity"
    )
    # The generic workspace configurator has no native CLI to detect.
    assert get_agent_config("agents", str(tmp_path)).cli_binary_name is None


def test_agent_configure_without_cli_never_hand_authors_config_file(tmp_path):
    """
    spec.mcp.AgentConfigDelegatesToHarnessReq
    spec.mcp.AgentConfigCliAbsentFallbackReq

    With the real agent CLI unavailable (blocked globally in conftest.py's
    block_real_agent_cli_calls fixture), Gemini/Antigravity/Copilot/Codex
    must only install the skill and report instructions -- never hand-write
    their harness's own config file (settings.json, mcp_config.json,
    mcp.json, config.toml).
    """
    relative_config_paths = {
        "gemini": (".gemini", "settings.json"),
        "antigravity": (".gemini", "antigravity", "mcp_config.json"),
        "copilot": (".github", "mcp.json"),
        "codex": (".codex", "config.toml"),
    }
    for agent_id, relative_parts in relative_config_paths.items():
        agent_root = os.path.join(str(tmp_path), agent_id)
        config = get_agent_config(agent_id, agent_root)
        message = config.configure()

        config_path = os.path.join(agent_root, *relative_parts)
        assert not os.path.exists(config_path), (
            f"{agent_id} hand-authored its config file with no CLI present"
        )
        assert "SKILL.md" in message
        assert os.path.exists(os.path.join(config.skill_dir_path, "SKILL.md"))


def test_auto_configure_detected_agents_no_cli_present(tmp_path, monkeypatch, capsys):
    # spec.cli.InitNoAgentDetectedReq
    monkeypatch.setattr("shutil.which", lambda _name: None)
    from libspec.cli import _auto_configure_detected_agents

    _auto_configure_detected_agents(str(tmp_path))
    out = capsys.readouterr().out
    assert "No coding-agent CLI detected" in out


def test_auto_configure_detected_agents_detects_and_configures(
    tmp_path, monkeypatch, capsys
):
    # spec.cli.InitAgentAutoDetectionReq
    # spec.cli.AgentCliPresenceSignalReq
    monkeypatch.setattr(
        "shutil.which", lambda name: f"/usr/bin/{name}" if name == "claude" else None
    )
    from libspec.cli import _auto_configure_detected_agents

    _auto_configure_detected_agents(str(tmp_path))
    out = capsys.readouterr().out
    assert "Configured claude" in out
    assert os.path.exists(
        os.path.join(str(tmp_path), ".claude", "skills", "libspec", "SKILL.md")
    )
    # Only the detected agent is touched.
    assert not os.path.exists(os.path.join(str(tmp_path), ".gemini"))


def test_auto_configure_detected_agents_isolates_per_agent_failures(
    tmp_path, monkeypatch, capsys
):
    # spec.cli.InitAgentConfigureFailureIsolationReq
    # spec.cli.InitMultiAgentConfigureReq
    import libspec.agent_config as agent_config

    monkeypatch.setattr(
        "shutil.which",
        lambda name: f"/usr/bin/{name}" if name in ("claude", "gemini") else None,
    )

    def _boom(self):
        raise RuntimeError("simulated failure for claude")

    monkeypatch.setattr(agent_config.ClaudeConfig, "configure", _boom)

    from libspec.cli import _auto_configure_detected_agents

    _auto_configure_detected_agents(str(tmp_path))
    out = capsys.readouterr().out

    assert "Warning: failed to auto-configure agent 'claude'" in out
    assert "Configured gemini" in out
    # gemini's install still succeeded despite claude's failure
    assert os.path.exists(
        os.path.join(str(tmp_path), ".gemini", "skills", "libspec", "SKILL.md")
    )
