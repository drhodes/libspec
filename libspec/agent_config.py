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

        from libspec.workflow import get_agent_workflow, resolve_prefix

        pfx = resolve_prefix(agent=self.agent_id, project_root=self.project_root)
        workflow_text = get_agent_workflow(pfx, project_root=self.project_root)

        return template.render(
            agent_id=self.agent_id,
            agent_display_name=self.agent_display_name,
            agent_description=self.agent_description,
            workflow=workflow_text,
        )

    def _install_skill(self, dir_path: str, content: str):
        """
        Installs a skill in the specified directory after validation.
        spec.mcp.AgentSkillInstallation
        """
        filename = "SKILL.md"
        temp_file = os.path.join(dir_path, f"TEMP_{os.getpid()}_{filename}")
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
                f"Config Persistence Failure: Could not write updated JSON configuration to {path}. {e}"
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
        # spec.agents.AgentsDirectoryLayoutReq
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
        elif self.agent_id == "agents":
            primary = os.path.join(self.project_root, ".agents", "skills", "libspec")
            legacy = os.path.join(
                self.project_root, ".agents", "skills", "libspec-agent-workflow"
            )
            if not os.path.exists(primary) and os.path.exists(legacy):
                return legacy
            return primary
        raise ValueError(f"Unknown agent ID: {self.agent_id}")

    @property
    def cli_binary_name(self) -> str | None:
        """
        The CLI binary name `shutil.which(...)` resolves to detect this
        agent's presence on the host, or None if this agent has no native
        CLI (e.g. the generic `agents` configurator).
        spec.cli.AgentCliPresenceSignalReq
        """
        return {
            "antigravity": "antigravity",
            "gemini": "gemini",
            "claude": "claude",
            "opencode": "opencode",
            "copilot": "copilot",
            "codex": "codex",
        }.get(self.agent_id)

    @property
    def is_active(self) -> bool:
        # spec.mcp.AgentSkillDriftDetection
        # spec.agents.AgentsDirectoryLayoutReq
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
        elif self.agent_id == "agents":
            agents_path = os.path.join(self.project_root, ".agents")
            return os.path.exists(agents_path) and os.path.isdir(agents_path)
        return False

    def is_skill_up_to_date(self) -> bool:
        # spec.mcp.SkillVersionValidation
        # spec.agents.AgentsSkillDriftDetectionReq
        skill_path = os.path.join(self.skill_dir_path, "SKILL.md")
        if not os.path.exists(skill_path) or not os.path.isfile(skill_path):
            return False
        try:
            with open(skill_path, encoding="utf-8") as f:
                installed_content = f.read()

            if "libspec: disable-auto-heal" in installed_content:
                return True

            current_content = self._render_skill()
            return current_content.strip() == installed_content.strip()
        except Exception:
            return False


class AntigravityConfig(AgentConfig):
    """
    Handles configuration for the Antigravity IDE agent.
    """

    def configure(self) -> str:
        # spec.mcp.AntigravityConfig
        # spec.mcp.AgentConfigDelegatesToHarnessReq
        config_dir = os.path.join(self.project_root, ".gemini", "antigravity")

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

        # spec.mcp.AgentConfigCliAbsentFallbackReq: report instructions,
        # never hand-author Antigravity's own mcp_config.json.
        config_path = os.path.join(config_dir, "mcp_config.json")
        antigravity_config = {"mcpServers": {"libspec": self.mcp_command}}
        return (
            "To configure Antigravity, add this to your mcp_config.json "
            f"({config_path}):\n\n"
            + json.dumps(antigravity_config, indent=2)
            + "\n\nA project-local skill has been installed in "
            f"{config_dir}/skills/libspec/SKILL.md"
        )

    agent_id = "antigravity"
    agent_display_name = "Antigravity"
    agent_description = "Navigation and specification tools for the Antigravity IDE"


class GeminiConfig(AgentConfig):
    """
    Handles configuration for the Gemini CLI agent.
    """

    def configure(self) -> str:
        # spec.mcp.GeminiConfig
        # spec.mcp.AgentConfigDelegatesToHarnessReq
        config_dir = os.path.join(self.project_root, ".gemini")

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

        # spec.mcp.AgentConfigCliAbsentFallbackReq: report instructions,
        # never hand-author Gemini's own settings.json.
        config_path = os.path.join(config_dir, "settings.json")
        gemini_config = {"mcpServers": {"libspec": self.mcp_command}}
        return (
            f"To configure the Gemini CLI, add this to your settings.json "
            f"({config_path}):\n\n"
            + json.dumps(gemini_config, indent=2)
            + "\n\nA project-local skill has been installed in "
            f"{config_dir}/skills/libspec/SKILL.md"
        )

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
        # spec.mcp.AgentConfigDelegatesToHarnessReq
        config_dir = os.path.join(self.project_root, ".github")

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

        # spec.mcp.AgentConfigCliAbsentFallbackReq: report instructions,
        # never hand-author Copilot's own mcp.json.
        config_path = os.path.join(config_dir, "mcp.json")
        copilot_config = {"mcpServers": {"libspec": self.mcp_command}}
        return (
            f"To configure Copilot, add this to your mcp.json ({config_path}):\n\n"
            + json.dumps(copilot_config, indent=2)
            + "\n\nA project-local skill has been installed in "
            f"{config_dir}/skills/libspec/SKILL.md"
        )

    agent_id = "copilot"
    agent_display_name = "GitHub Copilot"
    agent_description = "Navigation and specification tools for GitHub Copilot"


class CodexConfig(AgentConfig):
    """
    Handles configuration for Codex.
    """

    def configure(self) -> str:
        # spec.mcp.CodexConfig
        # spec.mcp.AgentConfigDelegatesToHarnessReq
        config_dir = os.path.join(self.project_root, ".codex")

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

        # spec.mcp.AgentConfigCliAbsentFallbackReq: report instructions,
        # never hand-author Codex's own config.toml.
        config_path = os.path.join(config_dir, "config.toml")
        return (
            f"To configure Codex, add this to your config.toml ({config_path}):\n\n"
            f'[mcp_servers.libspec]\ncommand = "{self.uv_path}"\n'
            f"args = {self.mcp_command_args}\n"
            "\nA project-local skill has been installed in "
            f"{config_dir}/skills/libspec/SKILL.md"
        )

    agent_id = "codex"
    agent_display_name = "Codex"
    agent_description = "Navigation and specification tools for Codex"


AGENTS_MD_POINTER_MARKER = "<!-- libspec:agents-md-pointer -->"

AGENTS_MD_POINTER_SECTION = f"""{AGENTS_MD_POINTER_MARKER}
## libspec

This project uses [libspec](https://github.com/drhodes/libspec) for
specification-driven development. Canonical, vendor-neutral agent
instructions live in `.agents/skills/libspec/SKILL.md` — read it for the
available libspec MCP tools and workflow commands.
{AGENTS_MD_POINTER_MARKER}
"""


def ensure_agents_md_pointer(project_root: str) -> str:
    """
    Ensures the project root AGENTS.md contains a pointer to
    .agents/skills/libspec/SKILL.md, creating AGENTS.md if absent and
    appending idempotently (without touching existing content) otherwise.
    spec.agents.AgentsMdPointerReq
    spec.agents.AgentsMdCreateOrAppendReq
    """
    path = os.path.join(project_root, "AGENTS.md")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(AGENTS_MD_POINTER_SECTION)
        return f"Created {path} with a pointer to .agents/skills/libspec/SKILL.md."

    with open(path, encoding="utf-8") as f:
        content = f.read()

    if AGENTS_MD_POINTER_MARKER in content:
        return "AGENTS.md already contains the libspec pointer."

    with open(path, "a", encoding="utf-8") as f:
        f.write(
            ("" if content.endswith("\n") else "\n") + "\n" + AGENTS_MD_POINTER_SECTION
        )
    return f"Appended libspec pointer section to {path}."


class AgentsConfig(AgentConfig):
    """
    Handles configuration for workspace .agents skills and setup.
    # spec.agents.AgentsDirectoryLayoutReq
    # spec.agents.AgentsSkillValidationReq
    # spec.agents.AgentsSkillHealingFeat
    # spec.agents.AgentsMdPointerReq
    # spec.agents.AgentsMdCreateOrAppendReq
    """

    def configure(self) -> str:
        config_dir = os.path.join(self.project_root, ".agents")
        if os.path.exists(config_dir) and not os.path.isdir(config_dir):
            raise ValueError(
                f"Path Conflict: {config_dir} exists as a file instead of a directory."
            )
        os.makedirs(config_dir, exist_ok=True)
        skill_dir = self.skill_dir_path
        self._install_skill(skill_dir, self._render_skill())
        pointer_msg = ensure_agents_md_pointer(self.project_root)
        return f"Successfully configured .agents skill in {skill_dir}. {pointer_msg}"

    agent_id = "agents"
    agent_display_name = "Agents"
    agent_description = "Navigation and specification tools for workspace .agents"


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
