from libspec.agent_config import get_agent_config, list_supported_agents

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
