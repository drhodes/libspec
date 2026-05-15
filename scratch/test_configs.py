import os
import shutil
import toml
from libspec.agent_config import get_agent_config

def test_configs():
    project_root = "test_project"
    if os.path.exists(project_root):
        shutil.rmtree(project_root)
    os.makedirs(project_root)
    
    try:
        # Test Copilot
        copilot = get_agent_config("copilot", project_root)
        print(copilot.configure())
        assert os.path.exists(os.path.join(project_root, ".github", "mcp.json"))
        
        # Test Codex
        codex = get_agent_config("codex", project_root)
        print(codex.configure())
        config_path = os.path.join(project_root, ".codex", "config.toml")
        assert os.path.exists(config_path)
        
        # Verify TOML content
        with open(config_path, "r") as f:
            config = toml.load(f)
            
        assert "mcp_servers" in config
        assert "libspec" in config["mcp_servers"]
        libspec = config["mcp_servers"]["libspec"]
        assert libspec["command"] == shutil.which("uv") or "uv"
        assert libspec["args"] == ["run", "libspec", "mcp"]
        assert libspec["cwd"] == os.path.abspath(project_root)
        
        # Test preservation of existing settings
        with open(config_path, "w") as f:
            toml.dump({"other": "setting", "mcp_servers": {"libspec": "old"}}, f)
            
        print("Running configure on existing file...")
        print(codex.configure())
        
        with open(config_path, "r") as f:
            config = toml.load(f)
            
        assert config["other"] == "setting"
        assert config["mcp_servers"]["libspec"]["command"] == (shutil.which("uv") or "uv")
        
        print("Tests passed!")
    finally:
        shutil.rmtree(project_root)

if __name__ == "__main__":
    test_configs()
