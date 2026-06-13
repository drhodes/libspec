import abc
import json
import os
import shutil
import subprocess
from pathlib import Path

import toml
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
            "cwd": self.project_root,
        }

    def _backup_if_exists(self, config_path: str):
        """
        Creates a .bak backup of the existing config file if it exists.
        spec.mcp.AgentConfig
        """
        if os.path.exists(config_path):
            backup_path = config_path + ".bak"
            shutil.copy2(config_path, backup_path)

    _registry: dict[str, type["AgentConfig"]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Register the subclass if it has an agent_id
        if hasattr(cls, "agent_id") and cls.agent_id:
            cls._registry[cls.agent_id.lower()] = cls

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
            agent_description=self.agent_description,
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
            raise ValueError(
                f"Skill Integrity Failure: The Libspec skill failed SkillKit validation. "
                f"Ensure YAML frontmatter (name, description) is present and correctly formatted. {e}"
            )

    def _load_json_config(self, path: str) -> dict:
        """Loads JSON config with error story."""
        if not os.path.exists(path):
            return {}
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            # spec.err.Err: The story of the corrupted config
            raise ValueError(
                f"Config Corruption: Failed to parse JSON configuration at {path}. "
                f"The file might be malformed or locked. {e}"
            )

    def _save_json_config(self, path: str, config: dict):
        """Saves JSON config with error story."""
        try:
            with open(path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            raise RuntimeError(
                f"Config Persistence Failure: Could not write updated configuration to {path}. {e}"
            )

    def _load_toml_config(self, path: str) -> dict:
        """Loads TOML config with error story."""
        if not os.path.exists(path):
            return {}
        try:
            with open(path) as f:
                return toml.load(f)
        except Exception as e:
            raise ValueError(
                f"Config Corruption: Failed to parse TOML configuration at {path}. {e}"
            )

    def _save_toml_config(self, path: str, config: dict):
        """Saves TOML config with error story."""
        try:
            with open(path, "w") as f:
                toml.dump(config, f)
        except Exception as e:
            raise RuntimeError(
                f"Config Persistence Failure: Could not write updated TOML configuration to {path}. {e}"
            )

    @property
    def skill_dir_path(self) -> str:
        # spec.mcp.AgentSkillDriftDetection
        if self.agent_id == "antigravity":
            return os.path.join(
                self.project_root, ".gemini", "antigravity", "skills", "libspec"
            )
        elif self.agent_id == "gemini":
            return os.path.join(self.project_root, ".gemini", "skills", "libspec")
        elif self.agent_id == "claude":
            return os.path.join(self.project_root, ".claude", "skills", "libspec")
        elif self.agent_id == "opencode":
            return os.path.join(self.project_root, ".opencode", "skills", "libspec")
        elif self.agent_id == "copilot":
            return os.path.join(self.project_root, ".github", "skills", "libspec")
        elif self.agent_id == "codex":
            return os.path.join(self.project_root, ".codex", "skills", "libspec")
        raise ValueError(f"Unknown agent ID: {self.agent_id}")

    @property
    def is_active(self) -> bool:
        # spec.mcp.AgentSkillDriftDetection
        if self.agent_id == "antigravity":
            return os.path.exists(
                os.path.join(
                    self.project_root, ".gemini", "antigravity", "mcp_config.json"
                )
            )
        elif self.agent_id == "gemini":
            return os.path.exists(
                os.path.join(self.project_root, ".gemini", "settings.json")
            )
        elif self.agent_id == "claude":
            return os.path.exists(os.path.join(self.project_root, ".claude"))
        elif self.agent_id == "opencode":
            return os.path.exists(
                os.path.join(self.project_root, ".opencode", "opencode.json")
            )
        elif self.agent_id == "copilot":
            return os.path.exists(
                os.path.join(self.project_root, ".github", "mcp.json")
            )
        elif self.agent_id == "codex":
            return os.path.exists(
                os.path.join(self.project_root, ".codex", "config.toml")
            )
        return False

    def is_skill_up_to_date(self) -> bool:
        # spec.mcp.SkillVersionValidation
        skill_path = os.path.join(self.skill_dir_path, "SKILL.md")
        if not os.path.exists(skill_path):
            return False
        try:
            current_content = self._render_skill()
            with open(skill_path, encoding="utf-8") as f:
                installed_content = f.read()
            return current_content == installed_content
        except Exception:
            return False


class AntigravityConfig(AgentConfig):
    """
    Handles configuration for the Antigravity IDE agent.
    """

    def configure(self) -> str:
        # spec.mcp.AntigravityConfig
        config_dir = os.path.join(self.project_root, ".gemini", "antigravity")
        os.makedirs(config_dir, exist_ok=True)

        # Write local file & backup for backward compatibility & tests
        config_path = os.path.join(config_dir, "mcp_config.json")
        self._backup_if_exists(config_path)
        config = self._load_json_config(config_path)
        config["mcpServers"] = config.get("mcpServers", {})
        config["mcpServers"]["libspec"] = self.mcp_command
        self._save_json_config(config_path, config)

        # CLI command execution
        mcp_def = {
            "name": "libspec",
            "command": self.uv_path,
            "args": self.mcp_command_args,
        }
        cmd = ["antigravity", "--add-mcp", json.dumps(mcp_def)]

        configured_via_cli = False
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                configured_via_cli = True
        except FileNotFoundError:
            pass

        self._install_skill(
            os.path.join(config_dir, "skills", "libspec"), self._render_skill()
        )
        if configured_via_cli:
            return "Successfully configured Antigravity MCP server via CLI."
        return f"Successfully configured Antigravity in {config_path}."

    agent_id = "antigravity"
    agent_display_name = "Antigravity"
    agent_description = "Navigation and specification tools for the Antigravity IDE"


class GeminiConfig(AgentConfig):
    """
    Handles configuration for the Gemini CLI agent.
    """

    def configure(self) -> str:
        # spec.mcp.GeminiConfig
        config_dir = os.path.join(self.project_root, ".gemini")
        os.makedirs(config_dir, exist_ok=True)

        # Write local file & backup
        config_path = os.path.join(config_dir, "settings.json")
        self._backup_if_exists(config_path)
        config = self._load_json_config(config_path)
        config["mcpServers"] = config.get("mcpServers", {})
        config["mcpServers"]["libspec"] = self.mcp_command
        self._save_json_config(config_path, config)

        # CLI command execution
        cmd = ["gemini", "mcp", "add", "libspec", self.uv_path] + self.mcp_command_args

        configured_via_cli = False
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                configured_via_cli = True
        except FileNotFoundError:
            pass

        self._install_skill(
            os.path.join(config_dir, "skills", "libspec"), self._render_skill()
        )
        if configured_via_cli:
            return "Successfully configured Gemini CLI MCP server via CLI."
        return f"Successfully configured Gemini CLI in {config_path}."

    agent_id = "gemini"
    agent_display_name = "Gemini CLI"
    agent_description = "Navigation and specification tools for the Gemini CLI agent"


class ClaudeConfig(AgentConfig):
    """
    Handles configuration for Claude Desktop.
    """

    def configure(self) -> str:
        cmd = [
            "claude",
            "mcp",
            "add",
            "libspec",
            "--",
            self.uv_path,
        ] + self.mcp_command_args

        configured_via_cli = False
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                configured_via_cli = True
        except FileNotFoundError:
            pass

        self._install_skill(
            os.path.join(self.project_root, ".claude", "skills", "libspec"),
            self._render_skill(),
        )

        if configured_via_cli:
            return "Successfully configured Claude Code MCP server via CLI."

        claude_config = {"libspec": self.mcp_command}
        return (
            "To configure Claude Desktop, add this to your claude_desktop_config.json:\n\n"
            + json.dumps(claude_config, indent=2)
            + "\n\nA project-local skill has been installed in .claude/skills/libspec/SKILL.md"
        )

    agent_id = "claude"
    agent_display_name = "Claude"
    agent_description = "Navigation and specification tools for Claude Desktop"


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
            "enabled": True,
        }

        self._save_json_config(config_path, config)
        self._install_skill(
            os.path.join(config_dir, "skills", "libspec"), self._render_skill()
        )
        return f"Successfully configured OpenCode in {config_path}."

    agent_id = "opencode"
    agent_display_name = "OpenCode"
    agent_description = "Navigation and specification tools for the OpenCode agent"


class CopilotConfig(AgentConfig):
    """
    Handles configuration for GitHub Copilot.
    """

    def configure(self) -> str:
        # spec.mcp.CopilotConfig
        config_dir = os.path.join(self.project_root, ".github")
        os.makedirs(config_dir, exist_ok=True)

        # Write local file & backup
        config_path = os.path.join(config_dir, "mcp.json")
        self._backup_if_exists(config_path)
        config = self._load_json_config(config_path)
        config["mcpServers"] = config.get("mcpServers", {})
        config["mcpServers"]["libspec"] = self.mcp_command
        self._save_json_config(config_path, config)

        # CLI command execution
        cmd = ["copilot", "mcp", "add", "libspec", self.uv_path] + self.mcp_command_args

        configured_via_cli = False
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                configured_via_cli = True
        except FileNotFoundError:
            pass

        self._install_skill(
            os.path.join(config_dir, "skills", "libspec"), self._render_skill()
        )
        if configured_via_cli:
            return "Successfully configured Copilot MCP server via CLI."
        return f"Successfully configured Copilot in {config_path}."

    agent_id = "copilot"
    agent_display_name = "GitHub Copilot"
    agent_description = "Navigation and specification tools for GitHub Copilot"


class CodexConfig(AgentConfig):
    """
    Handles configuration for Codex.
    """

    def configure(self) -> str:
        # spec.mcp.CodexConfig
        config_dir = os.path.join(self.project_root, ".codex")
        os.makedirs(config_dir, exist_ok=True)

        # Write local file & backup
        config_path = os.path.join(config_dir, "config.toml")
        self._backup_if_exists(config_path)
        config = self._load_toml_config(config_path)
        config["mcp_servers"] = config.get("mcp_servers", {})
        config["mcp_servers"]["libspec"] = self.mcp_command
        self._save_toml_config(config_path, config)

        # CLI command execution
        cmd = [
            "codex",
            "mcp",
            "add",
            "libspec",
            "--",
            self.uv_path,
        ] + self.mcp_command_args

        configured_via_cli = False
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                configured_via_cli = True
        except FileNotFoundError:
            pass

        self._install_skill(
            os.path.join(config_dir, "skills", "libspec"), self._render_skill()
        )
        if configured_via_cli:
            return "Successfully configured Codex MCP server via CLI."
        return f"Successfully configured Codex in {config_path}."

    agent_id = "codex"
    agent_display_name = "Codex"
    agent_description = "Navigation and specification tools for Codex"


def list_supported_agents() -> str:
    """
    Returns a formatted list of all supported agent names.
    spec.mcp.McpAgentList
    """
    agents = sorted(AgentConfig._registry.keys())
    return "Supported agents for auto-configuration:\n" + "\n".join(
        f"  - {a}" for a in agents
    )


def get_agent_config(agent_name: str, project_root: str) -> AgentConfig:
    """Factory to get the appropriate AgentConfig subclass."""
    cls = AgentConfig._registry.get(agent_name.lower())
    if not cls:
        raise ValueError(
            f"Agent '{agent_name}' is not supported for auto-configuration."
        )
    return cls(project_root)


def check_and_heal_skills(project_root: str, auto_heal: bool = True) -> list[str]:
    """
    Scans the workspace for active agent configurations, checking for skill version alignment.
    spec.mcp.AgentSkillDriftDetection
    spec.mcp.SkillVersionValidation
    """
    messages = []
    for agent_id, cls in AgentConfig._registry.items():
        try:
            config = cls(project_root)
            if config.is_active:
                if not config.is_skill_up_to_date():
                    if auto_heal:
                        try:
                            config.configure()
                            messages.append(
                                f"Auto-healed outdated/missing skill for agent '{agent_id}'."
                            )
                        except Exception as e:
                            messages.append(
                                f"Warning: Skill for agent '{agent_id}' is outdated/missing and auto-heal failed: {e}"
                            )
                    else:
                        messages.append(
                            f"Warning: Skill for agent '{agent_id}' is outdated or missing. Run 'uv run libspec mcp_agent {agent_id}' to update."
                        )
        except Exception as e:
            messages.append(f"Debug: Error checking skill for agent '{agent_id}': {e}")
    return messages
