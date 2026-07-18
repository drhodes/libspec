import os


def resolve_prefix(
    agent: str = None, prefix: str = None, project_root: str = "."
) -> str:
    """
    Resolves the MCP tool prefix based on agent, prefix, or project root auto-detection.
    """
    if prefix is not None:
        return prefix

    if agent:
        agent_lower = agent.lower()
        if agent_lower in ("antigravity", "gemini"):
            return "mcp_libspec_"
        if agent_lower == "claude":
            return ""
        return "libspec_"

    # Auto-detect active agent in project root
    try:
        from libspec.agent_config import AgentConfig

        for agent_id, cls in AgentConfig._registry.items():
            try:
                config = cls(project_root)
                if config.is_active:
                    if agent_id in ("antigravity", "gemini"):
                        return "mcp_libspec_"
                    if agent_id == "claude":
                        return ""
            except Exception:
                pass
    except Exception:
        pass

    return "libspec_"


def get_agent_workflow(pfx: str = "libspec_") -> str:
    """
    Returns the standardized developer agent workflow formatted as markdown
    with the specified tool prefix.
    """
    hooks = {}
    yaml_path = os.path.join(".libspec", "workflow.yaml")
    if os.path.exists(yaml_path):
        import yaml

        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "hooks" in data:
                    hooks = data["hooks"] or {}
        except Exception:
            pass

    def get_hook_lines(name: str) -> str:
        lines = hooks.get(name, [])
        if not lines:
            return ""
        if isinstance(lines, str):
            lines = [lines]
        return "\n" + "\n".join(f"   * {line}" for line in lines)

    return f"""## Dev Workflow
1. **Edit Spec**: Edit/define the requirements/features in the specification files. **Always decompose broad requirements into granular, single-responsibility requirement classes (e.g. `HelpCommandReq`, `SnapshotsCommandReq`) rather than using monolithic requirement blocks to ensure first-class specification footprinting.**{get_hook_lines("post-edit")}
2. **Diff Spec (MANDATORY BEFORE CODING)**: You **must absolutely** run a spec diff using either the `{pfx}diff` MCP tool or the `uv run libspec diff` command to identify specification drift and review mutations/dependencies before coding begins.{get_hook_lines("pre-diff")}{get_hook_lines("post-diff")}
3. **Test Driven Development**: Follow best practices in test driven development to write tests for the components.
4. **Implement**: Implement the components to ensure the tests pass.{get_hook_lines("post-implement")}
5. **Code Quality & Verification**: Run static analysis, linting, formatting, and dead code checks according to the project's guidelines.{get_hook_lines("pre-commit")}
6. **Author a git message and present to user**"""
