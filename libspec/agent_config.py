import os
import json
import toml
import abc
import shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from skillkit.core.parser import SkillParser

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

    @property
    @abc.abstractmethod
    def agent_id(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def agent_display_name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def agent_description(self) -> str:
        pass

    def _render_skill(self) -> str:
        """Renders the skill content using the Jinja2 template."""
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("skill.md.j2")
        
        return template.render(
            agent_id=self.agent_id,
            agent_display_name=self.agent_display_name,
            agent_description=self.agent_description
        )

    def _install_skill(self, dir_path: str, content: str):
        """
        Installs a skill in the specified directory after validation.
        spec.mcp.AgentSkillInstallation
        """
        filename = "SKILL.md"
        temp_file = os.path.join(dir_path, f"TEMP_{filename}")
        os.makedirs(dir_path, exist_ok=True)
        
        try:
            # 1. Write to temporary file for validation
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
            
            # 2. Validate using SkillKit's SkillParser
            parser = SkillParser()
            parser.parse_skill_file(Path(temp_file))
            
            # 3. If valid, rename to final SKILL.md
            final_path = os.path.join(dir_path, filename)
            self._backup_if_exists(final_path)
            
            if os.path.exists(final_path):
                os.remove(final_path)
            os.rename(temp_file, final_path)
            
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            # spec.err.Err: The story of the invalid skill
            raise ValueError(f"Skill Integrity Failure: The Libspec skill failed SkillKit validation. "
                           f"Ensure YAML frontmatter (name, description) is present and correctly formatted. {e}")

    def _load_json_config(self, path: str) -> dict:
        """Loads JSON config with error story."""
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            # spec.err.Err: The story of the corrupted config
            raise ValueError(f"Config Corruption: Failed to parse JSON configuration at {path}. "
                           f"The file might be malformed or locked. {e}")

    def _save_json_config(self, path: str, config: dict):
        """Saves JSON config with error story."""
        try:
            with open(path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Config Persistence Failure: Could not write updated configuration to {path}. {e}")

    def _load_toml_config(self, path: str) -> dict:
        """Loads TOML config with error story."""
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r") as f:
                return toml.load(f)
        except Exception as e:
            raise ValueError(f"Config Corruption: Failed to parse TOML configuration at {path}. {e}")

    def _save_toml_config(self, path: str, config: dict):
        """Saves TOML config with error story."""
        try:
            with open(path, "w") as f:
                toml.dump(config, f)
        except Exception as e:
            raise RuntimeError(f"Config Persistence Failure: Could not write updated TOML configuration to {path}. {e}")

class AntigravityConfig(AgentConfig):
    """
    Handles configuration for the Antigravity IDE agent.
    """
    def configure(self) -> str:
        # spec.mcp.AntigravityConfig
        config_dir = os.path.join(self.project_root, ".gemini", "antigravity")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "mcp_config.json")
        
        self._backup_if_exists(config_path)
        config = self._load_json_config(config_path)
        
        config["mcpServers"] = config.get("mcpServers", {})
        config["mcpServers"]["libspec"] = self.mcp_command
        
        self._save_json_config(config_path, config)
        self._install_skill(os.path.join(config_dir, "skills", "libspec"), self._render_skill())
        return f"Successfully configured Antigravity in {config_path}."

    @property
    def agent_id(self) -> str:
        return "antigravity"

    @property
    def agent_display_name(self) -> str:
        return "Antigravity"

    @property
    def agent_description(self) -> str:
        return "Navigation and specification tools for the Antigravity IDE"

class GeminiConfig(AgentConfig):
    """
    Handles configuration for the Gemini CLI agent.
    """
    def configure(self) -> str:
        # spec.mcp.GeminiConfig
        config_dir = os.path.join(self.project_root, ".gemini")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "settings.json")
        
        self._backup_if_exists(config_path)
        config = self._load_json_config(config_path)
        
        config["mcpServers"] = config.get("mcpServers", {})
        config["mcpServers"]["libspec"] = self.mcp_command
        
        self._save_json_config(config_path, config)
        self._install_skill(os.path.join(config_dir, "skills", "libspec"), self._render_skill())
        return f"Successfully configured Gemini CLI in {config_path}."

    @property
    def agent_id(self) -> str:
        return "gemini"

    @property
    def agent_display_name(self) -> str:
        return "Gemini CLI"

    @property
    def agent_description(self) -> str:
        return "Navigation and specification tools for the Gemini CLI agent"

class ClaudeConfig(AgentConfig):
    """
    Handles configuration for Claude Desktop.
    """
    def configure(self) -> str:
        claude_config = {
            "libspec": self.mcp_command
        }
        
        # spec.mcp.AgentSkillInstallation
        self._install_skill(os.path.join(self.project_root, ".claude", "skills", "libspec"), self._render_skill())

        return (
            "To configure Claude Desktop, add this to your claude_desktop_config.json:\n\n"
            + json.dumps(claude_config, indent=2)
            + "\n\nA project-local skill has been installed in .claude/skills/libspec/SKILL.md"
        )

    @property
    def agent_id(self) -> str:
        return "claude"

    @property
    def agent_display_name(self) -> str:
        return "Claude"

    @property
    def agent_description(self) -> str:
        return "Navigation and specification tools for Claude Desktop"

class OpenCodeConfig(AgentConfig):
    """
    Handles configuration for the OpenCode agent.
    """
    def configure(self) -> str:
        # spec.mcp.OpenCodeConfig
        config_dir = os.path.join(self.project_root, ".opencode")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "opencode.json")
        
        self._backup_if_exists(config_path)
        config = self._load_json_config(config_path)
        
        config["$schema"] = config.get("$schema", "https://opencode.ai/config.json")
        config["mcp"] = config.get("mcp", {})
        config["mcp"]["libspec"] = {
            "type": "local",
            "command": [self.uv_path] + self.mcp_command_args,
            "enabled": True
        }
        
        self._save_json_config(config_path, config)
        self._install_skill(os.path.join(config_dir, "skills", "libspec"), self._render_skill())
        return f"Successfully configured OpenCode in {config_path}."

    @property
    def agent_id(self) -> str:
        return "opencode"

    @property
    def agent_display_name(self) -> str:
        return "OpenCode"

    @property
    def agent_description(self) -> str:
        return "Navigation and specification tools for the OpenCode agent"


class CopilotConfig(AgentConfig):
    """
    Handles configuration for GitHub Copilot.
    """
    def configure(self) -> str:
        # spec.mcp.CopilotConfig
        config_dir = os.path.join(self.project_root, ".github")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "mcp.json")
        
        self._backup_if_exists(config_path)
        config = self._load_json_config(config_path)
        
        config["mcpServers"] = config.get("mcpServers", {})
        config["mcpServers"]["libspec"] = self.mcp_command
        
        self._save_json_config(config_path, config)
        self._install_skill(os.path.join(config_dir, "skills", "libspec"), self._render_skill())
        return f"Successfully configured Copilot in {config_path}."

    @property
    def agent_id(self) -> str:
        return "copilot"

    @property
    def agent_display_name(self) -> str:
        return "GitHub Copilot"

    @property
    def agent_description(self) -> str:
        return "Navigation and specification tools for GitHub Copilot"


class CodexConfig(AgentConfig):
    """
    Handles configuration for Codex.
    """
    def configure(self) -> str:
        # spec.mcp.CodexConfig
        config_dir = os.path.join(self.project_root, ".codex")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "config.toml")
        
        self._backup_if_exists(config_path)
        config = self._load_toml_config(config_path)
        
        config["mcp_servers"] = config.get("mcp_servers", {})
        config["mcp_servers"]["libspec"] = self.mcp_command
        
        self._save_toml_config(config_path, config)
        self._install_skill(os.path.join(config_dir, "skills", "libspec"), self._render_skill())
        return f"Successfully configured Codex in {config_path}."

    @property
    def agent_id(self) -> str:
        return "codex"

    @property
    def agent_display_name(self) -> str:
        return "Codex"

    @property
    def agent_description(self) -> str:
        return "Navigation and specification tools for Codex"


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
