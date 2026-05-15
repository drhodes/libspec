import os
import shutil
import toml
import json
from libspec.agent_config import get_agent_config

def test_backups():
    project_root = "test_project_backups"
    if os.path.exists(project_root):
        shutil.rmtree(project_root)
    os.makedirs(project_root)
    
    try:
        # Test Codex Backup
        codex = get_agent_config("codex", project_root)
        config_path = os.path.join(project_root, ".codex", "config.toml")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Create initial file
        with open(config_path, "w") as f:
            toml.dump({"initial": "data"}, f)
            
        print("Configuring Codex (should create backup)...")
        codex.configure()
        
        backup_path = config_path + ".bak"
        assert os.path.exists(backup_path), "Backup file was not created!"
        with open(backup_path, "r") as f:
            backup_data = toml.load(f)
        assert backup_data["initial"] == "data", "Backup content is incorrect!"
        
        # Test Antigravity Backup
        antigravity = get_agent_config("antigravity", project_root)
        config_path = os.path.join(project_root, ".gemini", "antigravity", "mcp_config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, "w") as f:
            json.dump({"initial": "json"}, f)
            
        print("Configuring Antigravity (should create backup)...")
        antigravity.configure()
        
        backup_path = config_path + ".bak"
        assert os.path.exists(backup_path), "Backup file was not created!"
        with open(backup_path, "r") as f:
            backup_data = json.load(f)
        assert backup_data["initial"] == "json", "Backup content is incorrect!"
        
        print("Backup tests passed!")
    finally:
        shutil.rmtree(project_root)

if __name__ == "__main__":
    test_backups()
