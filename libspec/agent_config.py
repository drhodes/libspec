import os
import json
import toml
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

    def _backup_if_exists(self, config_path: str):
        """
        Creates a .bak backup of the existing config file if it exists.
        spec.mcp.AgentConfig
        """
        if os.path.exists(config_path):
            backup_path = config_path + ".bak"
            shutil.copy2(config_path, backup_path)

    @abc.abstractmethod
    def configure(self) -> str:
        pass

    def _install_skill(self, agent_name: str, content: str):
        """
        Installs an agent-specific usage skill in .libspec/skills/.
        spec.mcp.AgentSkillInstallation
        """
        skills_dir = os.path.join(self.project_root, ".libspec", "skills")
        os.makedirs(skills_dir, exist_ok=True)
        skill_path = os.path.join(skills_dir, f"{agent_name}.md")
        
        with open(skill_path, "w") as f:
            f.write(content)

class AntigravityConfig(AgentConfig):
    """
    Handles configuration for the Antigravity IDE agent.
    """
    def configure(self) -> str:
        # Antigravity IDE looks for .gemini/antigravity/mcp_config.json
        # spec.mcp.AntigravityConfig
        config_dir = os.path.join(self.project_root, ".gemini", "antigravity")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "mcp_config.json")
        
        self._backup_if_exists(config_path)
        
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
            
        # spec.mcp.AgentSkillInstallation
        self._install_skill("antigravity", self.get_skill_content())
            
        return f"Successfully configured Antigravity in {config_path}."

    def get_skill_content(self) -> str:
        return """# Antigravity + Libspec

You are running in the Antigravity IDE. Use the integrated `libspec` tools 
to maintain spec/code alignment.

- Follow `.libspec/skills/workflow.md` for all edits.
- Use `libspec_search` for semantic lookup.
- Use `libspec_peek` for definitions.
"""

class GeminiConfig(AgentConfig):
    """
    Handles configuration for the Gemini CLI agent.
    """
    def configure(self) -> str:
        # Gemini CLI uses .gemini/settings.json for MCP configuration.
        # spec.mcp.AgentConfig
        config_dir = os.path.join(self.project_root, ".gemini")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "settings.json")
        
        self._backup_if_exists(config_path)
        
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
            
        # spec.mcp.AgentSkillInstallation
        self._install_skill("gemini", self.get_skill_content())
            
        return f"Successfully configured Gemini CLI in {config_path}."

    def get_skill_content(self) -> str:
        return """# Gemini + Libspec

Use the `libspec` MCP tools to navigate this project.
- Prefer `libspec_search` over `grep` for semantic lookup.
- Auto-start the LSP by calling any semantic tool (search, peek, symbols).
"""

class ClaudeConfig(AgentConfig):
    """
    Handles configuration for Claude Desktop.
    """
    def configure(self) -> str:
        claude_config = {
            "libspec": self.mcp_command
        }
        
        # spec.mcp.AgentSkillInstallation
        self._install_skill("claude", self.get_skill_content())

        return (
            "To configure Claude Desktop, add this to your claude_desktop_config.json:\n\n"
            + json.dumps(claude_config, indent=2)
            + "\n\nA project-local skill has been installed in .libspec/skills/claude.md"
        )

    def get_skill_content(self) -> str:
        return """# Claude + Libspec

Your environment is configured to use the `libspec` MCP server.
- Use `libspec_search` to find Requirements and Features in the `spec/` directory.
- Use `libspec_usage` before making changes to shared code.
"""

class OpenCodeConfig(AgentConfig):
    """
    Handles configuration for the OpenCode agent.
    """
    def configure(self) -> str:
        # OpenCode uses opencode.json in the .opencode directory in the project root.
        # spec.mcp.OpenCodeConfig
        config_dir = os.path.join(self.project_root, ".opencode")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "opencode.json")
        
        self._backup_if_exists(config_path)
        
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
            
        # spec.mcp.AgentSkillInstallation
        self._install_skill("opencode", self.get_skill_content())
            
        return f"Successfully configured OpenCode in {config_path}."

    def get_skill_content(self) -> str:
        return """# OpenCode + Libspec

Your environment is configured to use the `libspec` MCP server.
- Use `libspec_search` to find Requirements and Features in the `spec/` directory.
- Use `libspec_symbols` to orient yourself in complex source files.
"""


class CopilotConfig(AgentConfig):
    """
    Handles configuration for GitHub Copilot.
    """
    def configure(self) -> str:
        # GitHub Copilot looks for .copilot/mcp.json
        # spec.mcp.CopilotConfig
        config_dir = os.path.join(self.project_root, ".copilot")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "mcp.json")
        
        self._backup_if_exists(config_path)
        
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
            
        # spec.mcp.AgentSkillInstallation
        self._install_skill("copilot", self.get_skill_content())
            
        return f"Successfully configured Copilot in {config_path}."

    def get_skill_content(self) -> str:
        return """# Copilot + Libspec

Invoke `libspec` tools via the chat or slash commands.
- Use `libspec_search` to understand the `spec/` directory.
- Use `libspec_usage` before refactoring to see impacted code.
"""


class CodexConfig(AgentConfig):
    """
    Handles configuration for Codex.
    """
    def configure(self) -> str:
        # Codex looks for .codex/config.toml
        # spec.mcp.CodexConfig
        config_dir = os.path.join(self.project_root, ".codex")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "config.toml")
        
        self._backup_if_exists(config_path)
        
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = toml.load(f)
            except Exception:
                # If existing file is invalid TOML, we start fresh to be safe,
                # but in a real scenario we might want to warn the user.
                pass
        
        if "mcp_servers" not in config:
            config["mcp_servers"] = {}
        
        # Use the absolute project root for cwd
        abs_root = os.path.abspath(self.project_root)
        
        config["mcp_servers"]["libspec"] = {
            "command": "uv",
            "args": ["run", "libspec", "mcp"],
            "cwd": abs_root
        }
        
        with open(config_path, "w") as f:
            toml.dump(config, f)
            
        # spec.mcp.AgentSkillInstallation
        self._install_skill("codex", self.get_skill_content())
            
        return f"Successfully configured Codex in {config_path}."

    def get_skill_content(self) -> str:
        return """# Codex + Libspec

You are using the Codex agent. 
- Use the `libspec` tools to verify your implementation against the `spec/` directory.
- `libspec_peek` provides documentation and definitions for components.
"""


AGENT_REGISTRY = {
    "antigravity": AntigravityConfig,
    "gemini": GeminiConfig,
    "claude": ClaudeConfig,
    "opencode": OpenCodeConfig,
    "copilot": CopilotConfig,
    "codex": CodexConfig
}


def list_supported_agents() -> str:
    """
    Returns a formatted list of all supported agent names.
    spec.mcp.McpAgentList
    """
    agents = sorted(AGENT_REGISTRY.keys())
    return "Supported agents for auto-configuration:\n" + "\n".join(f"  - {a}" for a in agents)


def get_agent_config(agent_name: str, project_root: str) -> AgentConfig:
    """Factory to get the appropriate AgentConfig subclass."""
    cls = AGENT_REGISTRY.get(agent_name.lower())
    if not cls:
        raise ValueError(f"Agent '{agent_name}' is not supported for auto-configuration.")
    return cls(project_root)
