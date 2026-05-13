import os
import json
import abc
import shutil

class AgentConfig(abc.ABC):
    """
    Base class for agent-specific MCP configuration.
    """
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        # Prioritize uv in the root directory if it exists, otherwise find it in PATH
        local_uv = os.path.join(self.project_root, "uv")
        if os.path.exists(local_uv):
            self.uv_path = local_uv
        else:
            self.uv_path = shutil.which("uv") or "uv"
        
        self.mcp_command_args = ["run", "libspec", "mcp"]
        self.mcp_command = {
            "command": self.uv_path,
            "args": self.mcp_command_args,
            "cwd": self.project_root
        }

    @abc.abstractmethod
    def configure(self) -> str:
        pass

class AntigravityConfig(AgentConfig):
    """
    Handles configuration for the Antigravity IDE agent.
    """
    def configure(self) -> str:
        # Antigravity IDE looks for .gemini/antigravity/mcp_config.json
        config_dir = os.path.join(self.project_root, ".gemini", "antigravity")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "mcp_config.json")
        
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except Exception:
                pass
        
        if "mcpServers" not in config:
            config["mcpServers"] = {}
        
        config["mcpServers"]["libspec"] = self.mcp_command
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            
        return f"Successfully configured Antigravity IDE in {config_path}."

class GeminiConfig(AgentConfig):
    """
    Handles configuration for the Gemini CLI agent.
    """
    def configure(self) -> str:
        # Gemini CLI uses .gemini/settings.json for MCP configuration.
        config_dir = os.path.join(self.project_root, ".gemini")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "settings.json")
        
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except Exception:
                pass
        
        if "mcpServers" not in config:
            config["mcpServers"] = {}
        
        config["mcpServers"]["libspec"] = self.mcp_command
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            
        return f"Successfully configured Gemini CLI in {config_path}."

class ClaudeConfig(AgentConfig):
    """
    Handles configuration for Claude Desktop.
    """
    def configure(self) -> str:
        claude_config = {
            "libspec": self.mcp_command
        }
        return (
            "To configure Claude Desktop, add this to your claude_desktop_config.json:\n\n"
            + json.dumps(claude_config, indent=2)
        )

class OpenCodeConfig(AgentConfig):
    """
    Handles configuration for the OpenCode agent.
    """
    def configure(self) -> str:
        # OpenCode uses opencode.json in the project root.
        config_path = os.path.join(self.project_root, "opencode.json")
        
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except Exception:
                pass
        
        if "$schema" not in config:
            config["$schema"] = "https://opencode.ai/config.json"
            
        if "mcp" not in config:
            config["mcp"] = {}
        
        # OpenCode specific format per documentation:
        # - command is an array of [executable, ...args]
        # - key is 'mcp'
        # - type is 'local'
        config["mcp"]["libspec"] = {
            "type": "local",
            "command": [self.uv_path] + self.mcp_command_args,
            "enabled": True
        }
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            
        return f"Successfully configured OpenCode in {config_path}."

def get_agent_config(agent_name: str, project_root: str) -> AgentConfig:
    """Factory to get the appropriate AgentConfig subclass."""
    registry = {
        "antigravity": AntigravityConfig,
        "gemini": GeminiConfig,
        "claude": ClaudeConfig,
        "opencode": OpenCodeConfig
    }
    cls = registry.get(agent_name.lower())
    if not cls:
        raise ValueError(f"Agent '{agent_name}' is not supported for auto-configuration.")
    return cls(project_root)
