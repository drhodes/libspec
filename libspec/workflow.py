import os


def resolve_prefix(agent: str = None, prefix: str = None, project_root: str = ".") -> str:
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
    return f"""## Dev Workflow
1. **Edit Spec**: Edit/define the requirements/features in the specification files. **Always decompose broad requirements into granular, single-responsibility requirement classes (e.g. `HelpCommandReq`, `SnapshotsCommandReq`) rather than using monolithic requirement blocks to ensure first-class specification footprinting.**
2. **Diff Spec (MANDATORY BEFORE CODING)**: You **must absolutely** run a spec diff using either the `{pfx}diff` MCP tool or the `uv run libspec diff` command to identify specification drift and review mutations/dependencies before coding begins.
3. **Analyze and Declare Dependencies (Agent-Only)**: Immediately after reviewing the spec diff, you (the coding agent) must analyze the new/modified specification components to determine if any logical dependencies exist between them. If dependencies are identified, you must record them using the `{pfx}declare_dependency` MCP tool (e.g., `{pfx}declare_dependency(ref="spec.cli.LinkCommandOnlyOnChangesReq", depends_on="spec.cli.LinkCommand")`) before starting implementation. Do not add dependency boilerplate to the source code; rely entirely on this transactional ledger registration.
4. **Test Driven Development**: Follow best practices in test driven development to write tests for the components.
5. **Implement**: Implement the components to ensure the tests pass.
6. **Commit Spec Database**: Make sure to commit the `.libspec/libspec.jsonl` database log file to Git alongside your code changes. This is extremely important to ensure specification history is synchronized.
7. **Automated VCS Linking (Do NOT manually link)**: Git commit hooks automatically manage VCS linking (`libspec link` / `{pfx}link_snapshot`) under the hood during the commit process. Because these hooks handle linking automatically, you (the coding agent) **must NOT manually call `libspec link` or invoke the `{pfx}link_snapshot` tool**. Running the `libspec link` command manually is not usually done; rather, it should be avoided unless there are extenuating repairs needed, because executing it manually breaks the libspec developer workflow (e.g., by bypassing git-hook boundaries and leaving the workspace in a dirty state).
8. **Author a git message and present to user**"""
