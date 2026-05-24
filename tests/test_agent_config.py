import os
import pytest
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
